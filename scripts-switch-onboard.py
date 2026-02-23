from extras.scripts import Script, ObjectVar, StringVar, ChoiceVar
from dcim.models import Device, Site, Interface, DeviceType
from ipam.models import IPAddress
from extras.models import CustomFieldChoiceSet

choice_set = ()
choices = CustomFieldChoiceSet.objects.get(name="VAR Choices")
for choice in choices.extra_choices:
    choice_set += ((choice[0], choice[1]),)


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
        device = Device(
            site=site,
            device_type=model,
            tenant=tenant,
            cf={"VAR": var},
        )
        if commit:
            device.save()

        # Create the interface
        interface = Interface(
            name="Vlan1",
            device=device,
            type="virtual",
        )
        if commit:
            interface.save()

        # Create the IP address
        ip = IPAddress(
            address=ip_address,
            tenant=tenant,
            assigned_object=interface,
        )
        if commit:
            ip.save()

        device.primary_ip4 = ip
        if commit:
            device.save()
