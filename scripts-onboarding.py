from extras.scripts import Script, ObjectVar, StringVar, ChoiceVar
from dcim.models import Device, Site, Interface, DeviceType, DeviceRole
from ipam.models import IPAddress
from extras.models import CustomFieldChoiceSet, Tag


choice_set = ()
choices = CustomFieldChoiceSet.objects.get(name="VAR Choices")
for choice in choices.extra_choices:
    choice_set += ((choice[0], choice[1]),)
role = DeviceRole.objects.get(name="Switch")
tag_onboard = Tag.objects.get(name="Onboarding")
tag_omit = Tag.objects.get(name="Scan Omit")
model = DeviceType.objects.get(model="Generic Cisco")


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
    var = ChoiceVar(
        choices=(choice_set),
        label="VAR",
        description="Select the VAR associated with the switch.",
        required=True,
        default="Curvature",
    )

    def run(self, data, commit):

        site = data["site"]
        ip_address = data["ip_address"] + "/24"  # Assuming a default subnet mask of /24
        var = data["var"]
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
            new_device.tags.add(tag_onboard)
            new_device.tags.add(tag_omit)
            self.log_success(f"Tag '{tag_onboard.name}' added to device .")
            self.log_success(f"Tag '{tag_omit.name}' added to device .")
            new_device.save()
