from extras.scripts import Script
from dcim.models import Device, VirtualChassis


class StackCleanUp(Script):
    class Meta:
        name = "Add stack members to appropriate Virtual Chassis"
        description = "Cleans up stacks when ingested by diode"
    def run(self, data, commit):
        data_obj = data
        # Confirms that Objects Created by Event are Present
        if not data_obj or not isinstance(data_obj, dict):
            self.log_failure("No valid object found in event data.")
            return
        switch_name = data_obj.get('name')

        switch = Device.objects.get(name=switch_name)
        virtual_chassis_name = switch_name.rsplit("-", 1)[0] + "-Stack"
        if switch.vc_position:
            self.log_info(f"Switch is apart of {virtual_chassis_name} adding to Virtual Chassis Object ")
            switch.virtual_chassis = VirtualChassis.objects.get(name=virtual_chassis_name).id
            switch.save()
