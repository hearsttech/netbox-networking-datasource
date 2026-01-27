from extras.scripts import Script
from datetime import date
from dcim.models import Device


class eolUpdate(Script):
    class Meta:
        name = "EOL Date Update"
        description = "Checks if if devices have passed their End of Life (EOL) date. If so, updates their status to 'EOL'."
    def run(self, data, commit):
        now = date.today()
        data_obj = data
        # Confirms that Objects Created by Event are Present
        if not data_obj or not isinstance(data_obj, dict):
            self.log_failure("No valid object found in event data.")
            return
        device_id = data_obj.get("id")
        if not device_id:
            self.log_failure("No device ID found in event data.")
            return
        try:
            device = Device.objects.get(id=device_id)
        except Device.DoesNotExist:
            self.log_failure(f"Device with ID {device_id} does not exist.")
            return
        device_type = device.device_type
        if not device_type:
            self.log_failure(f"Device ID {device_id} has no associated Device Type.")
            return
        eol_date = device_type.custom_fields.get("eol")
        if not eol_date:
            self.log_info(f"Device Type '{device_type}' has no EOL date set.")
            return
        if not isinstance(eol_date, date):
            self.log_failure(f"EOL date for Device Type '{device_type}' is not a valid date.")
            return
        if now > eol_date:
            if commit:
                device.custom_fields['eol'] = 'EOL'
                device.save()
                self.log_info(f"Device ID {device_id} status updated to 'EOL'.")
            else:
                device.custom_fields['eol'] = device_type.custom_fields.get('eol')
        