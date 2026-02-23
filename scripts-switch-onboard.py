from extras.scripts import Script, ObjectVar, StringVar, ChoiceVar
from dcim.models import Device, Site, Interface
from ipam.models import IPAddress
from extras.models import CustomFieldChoiceSet


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
        description="Enter the IP address of the switch (e.g., 192.168.1.1).",
        required=True,
    )
    var = ChoiceVar(
        choices=(("#ff0000", "Red"), ("#00ff00", "Green"), ("#0000ff", "Blue")),
        label="Color",
        description="Select a color for the switch.",
        required=False,
    )
