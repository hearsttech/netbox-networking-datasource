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

    def _cleanup_device_for_inventory(self, device, log_context=""):
        """
        Remove primary IP and hostname from device for inventory status.
        Returns tuple of (name, ip, site) for logging.
        """
        name = device.name if device.name else None
        ip = device.primary_ip4 if device.primary_ip4 else None
        site = device.site.name if device.site else None

        # Delete primary IP address if it exists
        if device.primary_ip4:
            try:
                IPAddress.objects.filter(id=device.primary_ip4.id).delete()
            except IPAddress.DoesNotExist:
                pass

        # Clear device fields
        device.primary_ip4 = None
        device.name = None
        device.save()

        return name, ip, site

    def _create_journal_entry(self, device, message):
        """Create a journal entry for the device."""
        JournalEntry.objects.create(
            assigned_object_type=ContentType.objects.get_for_model(device),
            assigned_object_id=device.id,
            kind="info",
            comments=message,
        )

    def run(self, data, commit):
        # Validate input data
        if not data or not isinstance(data, dict):
            self.log_failure("No valid object found in event data.")

        # Get device from event data
        device_id = data.get("id")
        if not device_id:
            self.log_failure("Device name not found in event data.")

        try:
            device = Device.objects.get(id=device_id)
        except Device.DoesNotExist:
            self.log_failure(f"Device '{device_id}' not found.")

        site_name = device.site.name

        # Handle device already in inventory status - Cleanup existing IP and/or hostname if needed.
        if device.status == "inventory":
            self.log_success(
                f"Device '{device.name or 'unnamed'}' is already in 'inventory' status for site '{site_name}'."
            )

            # Check if cleanup is needed
            if device.primary_ip4 or device.name:
                name, ip, site = self._cleanup_device_for_inventory(device)
                self.log_success(
                    f"Cleaned up device '{name}' - removed primary IP '{ip}' for site '{site}'."
                )
            else:
                self.log_success(
                    f"Device in 'inventory' status for site '{site_name}' - no cleanup needed."
                )

        # Handle device status change to inventory and clean up IP and/or Hostname if needed - Creating Journal entry for status change and cleanup details.
        elif commit:
            previous_status = device.status
            name, ip, site = self._cleanup_device_for_inventory(device)

            device.status = "inventory"
            device.save()

            self.log_success(
                f"Device '{name}' status updated from '{previous_status}' to 'inventory' for site '{site}'."
            )
            self._create_journal_entry(
                device,
                f""""Device moved to 'Inventory' status.  
                Previous Hostname: {name}.  
                Previous Status: {previous_status}.  
                Previous IP: {ip}.  """,
            )
