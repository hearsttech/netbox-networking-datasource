from extras.scripts import Script
from dcim.models import Device, Site


class DeviceToInvetorySiteUpdater(Script):
    class Meta:
        name = "Device to Inventory Site Updater"
        description = (
            "Updates the status of the device to inventory based on the site name."
        )

    def run(self, data, commit):
        for device in Device.objects.all():
            data_obj = data
        # Confirms that Objects Created by Event are Present
        if not data_obj or not isinstance(data_obj, dict):
            self.log_failure("No valid object found in event data.")
            return
        # Extracts Site Name from Event Data
        site_name = data_obj.get("site")
        if not site_name:
            self.log_failure("Site name not found in event data.")
            return
        # Retrieves Site Object Based on Site Name
        try:
            site = Site.objects.get(name=site_name)
        except Site.DoesNotExist:
            self.log_failure(f"Site with name '{site_name}' does not exist.")
            return
        # Updates Device Status to 'inventory' if Site Matches
        if device.site == site:
            previous_status = device.status
            device.status = "inventory"
            if commit:
                device.save()
            self.log_info(
                f"Device '{device.name}' status updated from '{previous_status}' to 'inventory' for site '{site_name}'."
            )
