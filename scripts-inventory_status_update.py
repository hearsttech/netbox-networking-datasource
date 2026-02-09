from extras.scripts import Script
from dcim.models import Device
from ipam.models import IPAddress
from extras.models import JournalEntry
from django.contrib.contenttypes.models import ContentType


class DeviceToInventorySiteUpdater(Script):
    class Meta:
        name = "Device to Inventory Site Updater"
        description = (
            "Updates the status of the device to inventory based on the site name."
        )

    def run(self, data, commit):
        data_obj = data
        # Confirms that Objects Created by Event are Present
        if not data_obj or not isinstance(data_obj, dict):
            self.log_failure("No valid object found in event data.")
            return
        # Extracts Site Name from Event Data
        device = Device.objects.get(name=data_obj.get("name"))
        address = IPAddress.objects.get(address=data_obj.get("primary_ip4"))
        previous_status = device.status
        if device.status == "inventory":
            self.log_info(
                f"Device '{device.name}' is already in 'inventory' status for site '{device.site.name}'. No update needed."
            )

        elif device.status != "inventory" and commit:
            device.status = "inventory"
            device.name = None
            device.primary_ip4 = None
            IPAddress.objects.filter(id=address.id).delete()
            device.save()
            self.log_info(
                f"Device '{device.name}' status updated from '{previous_status}' to 'inventory' for site '{device.site.name}'."
            )
            JournalEntry.objects.create(
                assigned_object_type=ContentType.objects.get_for_model(device),
                assigned_object_id=device.id,
                kind="info",
                comments=f"""
                Device moved to 'Inventory' status for {device.name}. 
                Previous Hostname: {device.name}. 
                Previous status: {previous_status}. 
                Previous IP: {address.address}. 
""",
            )
