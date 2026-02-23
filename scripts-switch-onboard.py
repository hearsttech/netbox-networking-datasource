from extras.scripts import Script, ObjectVar, StringVar, ChoiceVar
from dcim.models import Device, Site, Interface
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
        description="Enter the IP address of the switch (e.g., 192.168.1.1).",
        required=True,
    )
    var = ChoiceVar(
        choices=(choice_set),
        label="VAR",
        description="Select the VAR associated with the switch.",
        required=True,
        default="Curvature",
    )
