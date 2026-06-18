from extras.scripts import Script
from dcim.models import Device
from tenancy.models import Tenant
from ipam.models import IPAddress
from extras.models import JournalEntry
from django.contrib.contenttypes.models import ContentType

INVENTORY_TENANT_ID = 34


class DeviceToInventorySiteUpdater(Script):
    class Meta:
        name = "Device to Inventory Site Updater"
        description = (
            "Updates the status of the device to inventory based on the site name."
        )

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
            return

        # Get device from event data
        device_id = data.get("id")
        if not device_id:
            self.log_failure("Device id not found in event data.")
            return

        # NOTE: conditions matched a *snapshot* of the device taken at save time;
        # we re-read the live object here and only act on its current state.
        try:
            device = Device.objects.get(id=device_id)
        except Device.DoesNotExist:
            self.log_failure(f"Device '{device_id}' not found.")
            return

        if not device.site:
            self.log_failure(
                f"Device '{device.name or device_id}' has no site assigned."
            )
            return

        site_name = device.site.name

        # Resolve target tenant once, up front, so we fail clearly if it is gone.
        try:
            inventory_tenant = Tenant.objects.get(id=INVENTORY_TENANT_ID)
        except Tenant.DoesNotExist:
            self.log_failure(
                f"Inventory tenant (id={INVENTORY_TENANT_ID}) not found; aborting."
            )
            return

        # Capture current values for logging / journaling before we mutate.
        previous_status = device.status
        previous_name = device.name or None
        previous_ip = device.primary_ip4 or None
        previous_tenant = device.tenant.name if device.tenant else None

        # Compute the full set of changes required to reach the clean inventory
        # state, then apply them with a SINGLE save(). Each save() emits another
        # "Object Updated" event that re-evaluates this rule, so minimizing saves
        # (and making the end state not match the rule) prevents the script from
        # re-triggering itself into a race of overlapping background jobs.
        changes = []
        ip_to_delete = None

        if device.status != "inventory":
            device.status = "inventory"
            changes.append(f"Status: '{previous_status}' -> 'inventory'")

        if device.primary_ip4:
            ip_to_delete = device.primary_ip4
            device.primary_ip4 = None
            changes.append(f"Removed Primary IP: {previous_ip}")

        if device.name:
            device.name = None
            changes.append(f"Removed Hostname: {previous_name}")

        if not device.tenant or device.tenant_id != INVENTORY_TENANT_ID:
            device.tenant = inventory_tenant
            changes.append(
                f"Tenant: '{previous_tenant}' -> '{inventory_tenant.name}'"
            )

        # Already in the desired state -> true no-op. Returning without saving is
        # what lets the self-triggered event chain terminate cleanly.
        if not changes:
            self.log_success(
                f"Device '{previous_name or 'unnamed'}' already clean in "
                f"'inventory' status for site '{site_name}' - no changes needed."
            )
            return

        if not commit:
            self.log_info(
                "Dry run (commit disabled) - would apply: " + "; ".join(changes)
            )
            return

        # Single save for the device, then delete the now-orphaned primary IP.
        device.save()

        if ip_to_delete is not None:
            try:
                IPAddress.objects.filter(id=ip_to_delete.id).delete()
            except IPAddress.DoesNotExist:
                pass

        self.log_success(
            f"Device '{previous_name or 'unnamed'}' cleaned for inventory at "
            f"site '{site_name}': " + "; ".join(changes)
        )

        journal_message = "Device moved to / cleaned for 'Inventory' status  \n"
        journal_message += f"Previous Status: {previous_status}  \n"
        if previous_name:
            journal_message += f"Previous Hostname: {previous_name}  \n"
        if previous_ip:
            journal_message += f"Previous IP: {previous_ip}  \n"
        if previous_tenant:
            journal_message += f"Previous Tenant: {previous_tenant}  \n"
        self._create_journal_entry(device, journal_message)
