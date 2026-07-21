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

    def _dissolve_virtual_chassis(self, vc, commit):
        """Break up a Virtual Chassis so its members can be cleaned as standalone
        devices.

        A device that is moved into inventory must not stay a stack member: the
        stack's primary IP lives on the master device only, and NetBox refuses to
        detach a device that is still designated as its VC master
        (Device.clean() -> vc_master_for guard). We therefore:

          1. Clear the VC's ``master`` pointer so no member is protected as master.
          2. Null ``virtual_chassis`` / ``vc_position`` / ``vc_priority`` on every
             member.
          3. Delete the now-empty VirtualChassis.

        Manual dissolution (rather than ``vc.delete()``) is deliberate: the built-in
        delete raises ProtectedError when members share a cross-chassis LAG, which
        is common on real switch stacks and would abort the whole cleanup.

        Returns the list of member device ids that were part of the stack.
        """
        member_ids = list(vc.members.values_list("id", flat=True))

        if not commit:
            self.log_info(
                f"Dry run - would dissolve virtual chassis '{vc.name}' "
                f"({len(member_ids)} member(s)) before inventory cleanup."
            )
            return member_ids

        try:
            # Clear the master pointer first; otherwise detaching the master member
            # trips the "device is currently designated as its master" guard.
            if vc.master_id is not None:
                vc.master = None
                vc.save()

            for member in vc.members.all():
                member.virtual_chassis = None
                member.vc_position = None
                member.vc_priority = None
                member.save()

            vc.delete()
            self.log_success(
                f"Dissolved virtual chassis '{vc.name}': "
                f"{len(member_ids)} member(s) detached."
            )
        except Exception as exc:
            # Surface the failure instead of letting it die quietly in the
            # background job result.
            self.log_failure(
                f"Failed to dissolve virtual chassis '{vc.name}': {exc}"
            )

        return member_ids

    def _clean_device_for_inventory(self, device, inventory_tenant, commit):
        """Compute and apply the full set of changes required to bring a single
        (standalone) device into a clean 'inventory' state.

        Applies everything with a SINGLE save(). Each save() emits another
        "Object Updated" event that re-evaluates this rule, so minimizing saves
        (and making the end state not match the rule) prevents the script from
        re-triggering itself into a race of overlapping background jobs.

        Returns True if a change was applied (or would be, in a dry run).
        """
        site_name = device.site.name if device.site else "unknown"

        # Capture current values for logging / journaling before we mutate.
        previous_status = device.status
        previous_name = device.name or None
        previous_ip = device.primary_ip4 or None
        previous_tenant = device.tenant.name if device.tenant else None

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
            return False

        if not commit:
            self.log_info(
                f"Dry run (commit disabled) - would apply to "
                f"'{previous_name or 'unnamed'}': " + "; ".join(changes)
            )
            return True

        # Single save for the device, then delete the now-orphaned primary IP.
        # Wrapped so a save failure is reported rather than silently lost in the
        # background job result.
        try:
            device.save()

            if ip_to_delete is not None:
                try:
                    IPAddress.objects.filter(id=ip_to_delete.id).delete()
                except IPAddress.DoesNotExist:
                    pass
        except Exception as exc:
            self.log_failure(
                f"Failed to clean device "
                f"'{previous_name or device.id}' for inventory: {exc}"
            )
            return False

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

        return True

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

        # Resolve target tenant once, up front, so we fail clearly if it is gone.
        try:
            inventory_tenant = Tenant.objects.get(id=INVENTORY_TENANT_ID)
        except Tenant.DoesNotExist:
            self.log_failure(
                f"Inventory tenant (id={INVENTORY_TENANT_ID}) not found; aborting."
            )
            return

        # If the device belongs to a Virtual Chassis, the whole stack is being
        # retired to inventory. Break the stack up first, then clean every former
        # member as a standalone device. This is what previously failed silently:
        # the stack's primary IP lives only on the master, so a member-triggered
        # event would skip IP cleanup, and detaching the master would raise inside
        # the background job with no user-visible error.
        if device.virtual_chassis_id:
            vc = device.virtual_chassis
            self.log_info(
                f"Device '{device.name or device_id}' is a member of virtual "
                f"chassis '{vc.name}'; dissolving stack before inventory cleanup."
            )
            device_ids = self._dissolve_virtual_chassis(vc, commit)
            # Ensure the triggering device is cleaned even if the member lookup
            # missed it for any reason.
            if device_id not in device_ids:
                device_ids.append(device_id)
        else:
            device_ids = [device_id]

        # Re-read each device fresh (dissolution and self-triggered events may have
        # mutated state) and bring it to a clean inventory state.
        for dev_id in device_ids:
            try:
                dev = Device.objects.get(id=dev_id)
            except Device.DoesNotExist:
                continue
            self._clean_device_for_inventory(dev, inventory_tenant, commit)
