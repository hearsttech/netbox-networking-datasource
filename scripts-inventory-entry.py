from extras.scripts import Script, ObjectVar, ChoiceVar, StringVar
from dcim.models import Device, Site, DeviceType
from extras.models import CustomFieldChoiceSet


choice_set = ()
choices = CustomFieldChoiceSet.objects.get(name="VAR Choices")
for choice in choices.extra_choices:
    choice_set += ((choice[0], choice[1]),)


class InventoryEntry(Script):
    class Meta:
        name = "Inventory Entry"
        description = (
            "Adds a device to the inventory based on site and tenant information."
        )

    site = ObjectVar(
        model=Site,
        label="Inventory Location",
        description="Select the site where the device is located.",
        required=True,
        query_params={"tag": ["inventory"]},
    )
    var = ChoiceVar(
        choices=(choice_set),
        label="VAR",
        description="Select the VAR associated with the device.",
        required=True,
        default="HTS-Curvature",
    )
    model = ObjectVar(
        model=DeviceType,
        label="Device Model",
        description="Select the device model for the device.",
        required=True,
    )
    serial_number = StringVar(
        label="Serial Number",
        description="Enter the serial number for the device.",
        required=True,
    )

    def run(self, data, commit):

        site = data["site"]
        var = data["var"]
        model = data["model"]
        serial_number = data["serial_number"]
        tenant = Site.objects.get(name=site).tenant
        role = DeviceType.objects.get(model=model).role
        # Create the device
        new_device = Device(
            site=site,
            device_type=model,
            tenant=tenant,
            role=role,
            status="active",
            serial_number=serial_number,
            asset_tag=serial_number,
            custom_field_data={"var": var},
        )
        if commit:
            new_device.full_clean()
            new_device.save()
