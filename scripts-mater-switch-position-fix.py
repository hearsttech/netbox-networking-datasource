from extras.scripts import Script
from dcim.models import Device, VirtualChassis


class StackMasterPositionFix(Script):
    class Meta:
        name = "Stack Master Position Fix"
        description = "Assigns correct position to Master switch based on naming convention."
    def run(self, data, commit):
        data_obj = data
        # Confirms that Objects Created by Event are Present
        if not data_obj or not isinstance(data_obj, dict):
            self.log_failure("No valid object found in event data.")
            return
        switch_name = data_obj.get('name')
        self.log_info(f"Processing switch: {switch_name}")
        switch = Device.objects.get(name=switch_name)
        virtual_chassis_name = switch_name.rsplit("-", 1)[0] + "-Stack"
        self.log_info(f"Derived Virtual Chassis name: {virtual_chassis_name}")
        try:
            VirtualChassis.objects.get(name=virtual_chassis_name)
        except VirtualChassis.DoesNotExist:
            self.log_failure(f"Virtual Chassis {virtual_chassis_name} does not exist. No changes made.")
        else:
            if VirtualChassis.objects.get(name=virtual_chassis_name):
                virtual_chassis = VirtualChassis.objects.get(name=virtual_chassis_name)
                if switch == virtual_chassis.master:
                    switch.vc_position = switch_name.rsplit("-", 1)[1]
                    switch.save()
                    self.log_success(f"Successfully set {switch_name} position to Master {switch.vc_position} in {virtual_chassis_name}")
                else:
                    self.log_info(f"{switch_name} is not the master switch in {virtual_chassis_name}, no changes made.")