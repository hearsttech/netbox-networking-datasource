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

        # Fetch lookups at runtime so failures report cleanly instead of
        # breaking script import.
        role = DeviceRole.objects.get(name="Switch")
        device_type = DeviceType.objects.get(model="Generic Cisco")
        tag_onboard = Tag.objects.get(name="Onboarding")
        tag_omit = Tag.objects.get(name="Scan Omit")

        address_cidr = f"{data['ip_address']}/{data['prefix_len']}"

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

        # Create the management SVI interface
        interface = Interface(
            name="Vlan1",
            device=device,
            type="virtual",
        )
        interface.full_clean()
        interface.save()

        # Create and assign the IP address
        address = IPAddress(
            address=address_cidr,
            tenant=site.tenant,
            assigned_object=interface,
        )
        address.full_clean()
        address.save()

        device.primary_ip4 = address
        device.tags.add(tag_onboard, tag_omit)
        device.save()

        self.log_success(
            f"Onboarded {device} with IP {address.address} "
            f"(tags: {tag_onboard.name}, {tag_omit.name})."
        )
