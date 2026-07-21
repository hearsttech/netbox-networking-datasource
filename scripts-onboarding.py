from django.core.exceptions import ObjectDoesNotExist

from extras.scripts import Script, ObjectVar, StringVar, ChoiceVar, IntegerVar
from dcim.models import Device, Site, Interface, DeviceType, DeviceRole
from ipam.models import IPAddress
from extras.models import CustomFieldChoiceSet, Tag


def _var_choices():
    """Resolve VAR choices at class-definition time, tolerating a missing set."""
    try:
        choice_set = CustomFieldChoiceSet.objects.get(name="VAR Choices")
        return [(c[0], c[1]) for c in choice_set.extra_choices]
    except CustomFieldChoiceSet.DoesNotExist:
        return []


class Onboarding(Script):
    class Meta:
        name = "Switch Onboarding"
        description = "Onboards a switch to Netbox with the specified IP address, Location and Var."

    site = ObjectVar(
        model=Site,
        label="Location Code",
        description="Select the site where the switch is located.",
        required=True,
    )
    ip_address = StringVar(
        label="IP Address",
        description="Enter the IP address of the switch (e.g., 192.168.1.1)",
        required=True,
    )
    prefix_len = IntegerVar(
        label="Prefix Length",
        description="CIDR prefix length for the management IP.",
        required=True,
        default=24,
        min_value=1,
        max_value=32,
    )
    var = ChoiceVar(
        choices=_var_choices(),
        label="VAR",
        description="Select the VAR associated with the switch.",
        required=True,
        default="Curvature",
    )

    def run(self, data, commit):
        site = data["site"]
        var = data["var"]
        address_cidr = f"{data['ip_address']}/{data['prefix_len']}"

        self.log_info(
            f"Starting onboarding — site: **{site}** (tenant: "
            f"{site.tenant or 'none'}), IP: `{address_cidr}`, VAR: {var}, "
            f"commit={commit}."
        )
        if not commit:
            self.log_warning(
                "Running in **dry-run** mode — changes will be validated and "
                "then rolled back. Enable commit to persist."
            )

        # Fetch lookups at runtime so failures report cleanly instead of
        # breaking script import.
        self.log_debug("Resolving device role, device type, and tags.")
        try:
            role = DeviceRole.objects.get(name="Switch")
            device_type = DeviceType.objects.get(model="Generic Cisco")
            tag_onboard = Tag.objects.get(name="Onboarding")
            tag_omit = Tag.objects.get(name="Scan Omit")
        except ObjectDoesNotExist as exc:
            self.log_failure(
                f"Required NetBox object is missing: {exc}. Aborting onboarding."
            )
            return
        self.log_info(
            f"Resolved lookups — role: {role}, device type: {device_type}, "
            f"tags: {tag_onboard.name}, {tag_omit.name}."
        )

        # Create the device. NetBox wraps run() in a transaction and rolls it
        # back automatically when commit=False, so full_clean() still validates
        # on a dry run.
        device = Device(
            site=site,
            device_type=device_type,
            tenant=site.tenant,
            role=role,
            status="active",
            custom_field_data={"var": var},
        )
        device.full_clean()
        device.save()
        self.log_success(f"Created device **{device}** (id={device.pk}).")

        # Create the management SVI interface
        interface = Interface(
            name="Vlan1",
            device=device,
            type="virtual",
        )
        interface.full_clean()
        interface.save()
        self.log_success(
            f"Created interface **{interface.name}** ({interface.type}) on {device}."
        )

        # Create and assign the IP address
        address = IPAddress(
            address=address_cidr,
            tenant=site.tenant,
            assigned_object=interface,
        )
        address.full_clean()
        address.save()
        self.log_success(
            f"Created IP address `{address.address}` and assigned it to "
            f"{interface.name}."
        )

        # Assign the address as the device's primary IPv4 and persist it. Run
        # full_clean() here (not just at creation time) so NetBox validates that
        # the IP is IPv4 and is actually assigned to an interface on this device.
        device.primary_ip4 = address  # type: ignore[assignment]
        device.full_clean()
        device.save()
        self.log_success(f"Set `{address.address}` as the primary IPv4 for {device}.")

        device.tags.add(tag_onboard, tag_omit)
        self.log_info(f"Applied tags: {tag_onboard.name}, {tag_omit.name}.")

        self.log_success(
            f"Onboarding complete for **{device}** with IP {address.address} "
            f"(tags: {tag_onboard.name}, {tag_omit.name})."
        )

        # Returned text is rendered as the script's output summary in the UI.
        return (
            f"Onboarded {device} at {site}\n"
            f"- Device ID: {device.pk}\n"
            f"- Role: {role}\n"
            f"- Device type: {device_type}\n"
            f"- Management interface: {interface.name} ({interface.type})\n"
            f"- Primary IPv4: {address.address}\n"
            f"- Tenant: {site.tenant or 'none'}\n"
            f"- VAR: {var}\n"
            f"- Tags: {tag_onboard.name}, {tag_omit.name}"
        )
