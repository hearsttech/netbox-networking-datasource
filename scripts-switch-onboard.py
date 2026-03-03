from extras.scripts import Script, ObjectVar, StringVar, ChoiceVar
from dcim.models import Device, Site, Interface, DeviceType, DeviceRole
from ipam.models import IPAddress
from extras.models import CustomFieldChoiceSet, Tag


choice_set = ()
choices = CustomFieldChoiceSet.objects.get(name="VAR Choices")
for choice in choices.extra_choices:
    choice_set += ((choice[0], choice[1]),)
role = DeviceRole.objects.get(name="Switch")
tag = Tag.objects.get(name="Onboarding")


class SwitchOnboard(Script):
    class Meta:
        name = "Switch Onboard"
        description = (
            "Onboards a switch to the inventory based on site and tenant information."
        )

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
    var = ChoiceVar(
        choices=(choice_set),
        label="VAR",
        description="Select the VAR associated with the switch.",
        required=True,
        default="Curvature",
    )
    model = ObjectVar(
        model=DeviceType,
        label="Device Model",
        description="Select the device model for the switch.",
        required=True,
        query_params={"tag": ["curvature"]},
    )

    def run(self, data, commit):
        site = data["site"]
        ip_address = data["ip_address"] + "/24"  # Assuming a default subnet mask of /24
        var = data["var"]
        model = data["model"]
        tenant = Site.objects.get(name=site).tenant
        # Create the device
        new_device = Device(
            site=site,
            device_type=model,
            tenant=tenant,
            role=role,
            status="active",
            custom_field_data={"var": var},
        )
        if commit:
            new_device.full_clean()
            new_device.save()

        # Create the interface
        interface = Interface(
            name="Vlan1",
            device=new_device,
            type="virtual",
        )
        if commit:
            interface.full_clean()
            interface.save()

        # Create the IP address
        address = IPAddress(
            address=ip_address,
            tenant=tenant,
            assigned_object=interface,
        )
        if commit:
            address.full_clean()
            address.save()
            self.log_success(
                f"Device onboarded successfully with IP {address.address}."
            )

        if commit:
            new_device.primary_ip4 = address
            new_device.save()
            self.log_success(f"Primary IP {address.address} assigned to device .")
            new_device.tags.add(tag)
            self.log_success(f"Tag '{tag.name}' added to device .")
            new_device.save()
