from extras.scripts import Script
from dcim.models import Device, VirtualChassis, Interface


class StackMemberEventRule(Script):
    class Meta:
        name = "Stack Event Rule to add stack members to appropriate Virtual Chassis"
        description = "Cleans up stacks when ingested by diode"
    def run(self, data, commit):
        data_obj = data
        # Confirms that Objects Created by Event are Present
        if not data_obj or not isinstance(data_obj, dict):
            self.log_failure("No valid object found in event data.")
            return
        '''
        Check if the switch has a vc_position and is not already part of a virtual chassis,
        then add it to the appropriate Virtual Chassis and then update interfaces with apporpriate vc_position 
        '''
        switch_name = data_obj.get('name')
        switch = Device.objects.get(name=switch_name)
        virtual_chassis_name = switch_name.rsplit("-", 1)[0] + "-Stack"
        if switch.vc_position and switch.virtual_chassis is None:
                switch = Device.objects.get(name=switch_name)
                self.log_info(f"{switch_name} is apart of {virtual_chassis_name} adding to Virtual Chassis Object ")
                virtual_chassis = VirtualChassis.objects.get(name=virtual_chassis_name)
                switch.virtual_chassis = VirtualChassis.objects.get(id=virtual_chassis.id)
                switch.save()
                self.log_success(f"Successfully added {switch_name} to {virtual_chassis_name}")
        for interface in Interface.objects.filter(device=switch.id):
                name = interface.name.replace("t1/", f"t{switch.vc_position}/")
                interface.name = name
                interface.save()

        