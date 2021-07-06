from os import path
import os, time
from typing import List, Tuple
import broadlink
import base64
import json
from broadlink.device import device
from simple_term_menu import TerminalMenu

DEFAULTS = {
    'name': '',
    'min_temp': 22,
    'max_temp': 27,
    'precision': 1,
    'modes': ["heat", "cool", "heat_cool", "dry", "fan_only"],
    'fan': ["quiet", "low", "med", "high", "turbo", "auto"],
    'swing': ["stop", "swing"]
}

def input_wrap(msg, default=None):
    value = input(msg)
    if value == '' and default is not None:
        return DEFAULTS[default]
    else:
        return value

def menu_wrap(options: List[str], title='') -> int:
    index = TerminalMenu(options, title=title).show()
    return index

def multi_menu_wrap(options: List[str], title='') -> Tuple:
    menu = TerminalMenu(options, title=title, multi_select=True)
    menu.show()
    return menu.chosen_menu_entries

class AC_Config:
    def __init__(self, name=DEFAULTS['name'], min_temp=DEFAULTS['min_temp'], max_temp=DEFAULTS['max_temp'], precision=DEFAULTS['precision'], modes=DEFAULTS['modes'], fan=DEFAULTS['fan'], swing=DEFAULTS['swing']) -> None:
        self.name = name
        self.minTemperature = min_temp
        self.maxTemperature = max_temp
        self.precision = precision
        self.operationModes = modes
        self.fanModes = fan
        self.swingModes = swing
        self.commands = {}
    
    def learn_command(self, device, operation_mode, fan_mode, swing_mode, temp):
        print('Temperature:', temp, '| code: ', end='', flush=True)
        ir_code = self.get_code(device)
        print(ir_code)
        if operation_mode not in self.commands:
            self.commands[operation_mode] = {}
        if fan_mode not in self.commands[operation_mode]:
            self.commands[operation_mode][fan_mode] = {}
        if swing_mode not in self.commands[operation_mode][fan_mode]:
            self.commands[operation_mode][fan_mode][swing_mode] = {}
        self.commands[operation_mode][fan_mode][swing_mode][temp] = ir_code

    def get_temp_range_list(self):
        temp_range_list = list(range(
            self.minTemperature, self.maxTemperature+self.precision, self.precision))
        return list(map(lambda x:str(x), temp_range_list))

    def learn_temperature(self, device:device, operation_mode: str, fan_mode:str, swing_mode:str):
        temp_range_list = self.get_temp_range_list()
        menu_options = ['Learn all temperatures'] + temp_range_list + ['Back']
        option_index = -1
        while option_index != len(menu_options) - 1:
            option_index = menu_wrap(menu_options)
            if option_index == 0:
                for temp in temp_range_list:
                    self.learn_command(device, operation_mode, fan_mode, swing_mode, temp)
            elif option_index != len(menu_options)-1:
                self.learn_command(device, operation_mode, fan_mode, swing_mode, menu_options[option_index])
        

    def learn_swing_modes(self, device:device, operation_mode: str, fan_mode:str):
        swing_mode_options = self.swingModes+['Back']
        swing_index = -1
        while swing_index != len(swing_mode_options)-1:
            swing_index = menu_wrap(swing_mode_options, 'Swing mode to learn')
            if swing_index != len(swing_mode_options)-1:
                self.learn_temperature(device, operation_mode, fan_mode, self.swingModes[swing_index])

    def learn_fans(self, device:device, operation_mode: str):
        fan_mode_options = self.fanModes+['Back']
        fan_index = -1
        while fan_index != len(fan_mode_options)-1:
            fan_index = menu_wrap(fan_mode_options, 'Fan mode to learn')
            if fan_index != len(fan_mode_options)-1:
                self.learn_swing_modes(device, operation_mode, self.fanModes[fan_index])

    def learn_operations(self, device: device):
        operation_mode_options = self.operationModes+['Back']
        operation_index = -1
        while operation_index != len(operation_mode_options)-1:
            operation_index = menu_wrap(operation_mode_options, 'Operation mode to learn')
            if operation_index != len(operation_mode_options)-1:
                self.learn_fans(device, self.operationModes[operation_index])
        
    def clone_fan_mode(self, source_operation_mode, source_fan_mode, dest_operation_mode, dest_fan_mode):
        if dest_operation_mode not in self.commands:
            self.commands[dest_operation_mode] = {}
        self.commands[dest_operation_mode][dest_fan_mode] = (self.commands[source_operation_mode][source_fan_mode]).copy()
    
    def fill_fan_modes(self):
        source_operation_mode = self.operationModes[menu_wrap(self.operationModes, 'Source operation mode')]
        source_fan_mode = self.fanModes[menu_wrap(self.fanModes, 'Source fan mode')]
        dest_operation_modes = multi_menu_wrap(self.operationModes, 'Destination operation mode')
        dest_fan_modes = multi_menu_wrap(self.fanModes, 'Destination fan mode')
        for operation in dest_operation_modes:
            for fan in dest_fan_modes:
                self.clone_fan_mode(source_operation_mode, source_fan_mode, operation, fan)
    
    def fill_temperatures(self):
        temp_range_list = self.get_temp_range_list()
        source_operation_mode = self.operationModes[menu_wrap(self.operationModes, 'Source operation mode')]
        source_fan_mode = self.fanModes[menu_wrap(self.fanModes, 'Source fan mode')]
        source_swing_mode = self.swingModes[menu_wrap(self.swingModes, 'Source swing mode')]
        source_temp = temp_range_list[menu_wrap(temp_range_list, 'Source temperature')]
        command_dict = self.commands[source_operation_mode][source_fan_mode][source_swing_mode]
        source_temp_value = command_dict[source_temp]
        for i in temp_range_list:
            if i not in command_dict:
                command_dict[i] = source_temp_value
        

    def get_code(self, device: device):
        device.enter_learning()
        while True:
            try:
                ir_code = device.check_data()
                return base64.b64encode(ir_code).decode('ascii') 
            except Exception:
                time.sleep(0.2)
    
    def load(self, config: dict) -> None:
        self.name = config['name']
        self.minTemperature = config['minTemperature']
        self.maxTemperature = config['maxTemperature']
        self.precision = config['precision']
        self.operationModes = config['operationModes']
        self.fanModes = config['fanModes']
        self.swingModes = config['swingModes']
        self.commands = config['commands']

ac_configs: List[AC_Config] = []

def get_device() -> device:
    devices = broadlink.discover(timeout=5)
    if len(devices) > 0:
        menu_options = list(map(lambda x:x.host[0], devices))
        device_index = menu_wrap(menu_options)
        return devices[device_index]
    else:
        menu_wrap(["No devices found"])
        return None

def create_ac_config():
    global ac_configs
    name = input_wrap('Config name: ', default='name')
    min_temp = input_wrap("Minimum temperature: ", default='min_temp')
    max_temp = input_wrap("Maximum temperature: ", default='max_temp')
    precision = input_wrap("Temperature precision: ", default='precision')
    modes = input_wrap("AC modes: ", default='modes')
    fan = input_wrap("Fan modes: ", default='fan')
    swing = input_wrap("Swing modes: ", default='swing')
    new_config = AC_Config(name=name, min_temp=min_temp, max_temp=max_temp, precision=precision, modes=modes, fan=fan, swing=swing)
    #json.loads(modes)
    #json.loads(fan)
    #json.loads(swing)
    ac_configs.append(new_config)


MAIN_MENU_TITLE_TEMPLATE = "Main - {}"
MAIN_MENU_TITLE = MAIN_MENU_TITLE_TEMPLATE.format('None')
MAIN_MENU_OPTIONS = ["Select device", "Create AC Config", "Learn Commands", "List configs", "Clone Fan Mode", "Fill temperatures", "Exit"]

dir_path = os.path.dirname(os.path.realpath(__file__))
CONFIG_FILE = os.path.join(dir_path, 'ac_configs.json')

def update_main_title(device: device):
    global MAIN_MENU_TITLE
    MAIN_MENU_TITLE = MAIN_MENU_TITLE_TEMPLATE.format(device.host[0])

def ac_config_dumper(config: AC_Config) -> dict:
    return config.__dict__

def load_configs(config_file):
    global ac_configs
    configs = json.load(config_file)
    for config in configs:
        new_ac_config = AC_Config()
        new_ac_config.load(config)
        ac_configs.append(new_ac_config)

def main() -> None:
    global MAIN_MENU_TITLE, MAIN_MENU_OPTIONS, ac_configs
    current_device = None
    menu_index = -1
    if path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as ac_config_file:
            load_configs(ac_config_file)
    while menu_index != len(MAIN_MENU_OPTIONS)-1:
        menu_index = menu_wrap(MAIN_MENU_OPTIONS, title=MAIN_MENU_TITLE)
        if menu_index == 0:
            current_device = get_device()
            current_device.auth()
            update_main_title(current_device)
        elif menu_index == 1:
            create_ac_config()
        elif menu_index == 2:
            config_index = menu_wrap(list(map(lambda x:x.name, ac_configs)), title='Choose the AC config')
            ac_configs[config_index].learn_operations(current_device)
        elif menu_index == 3:
            print(ac_configs)
        elif menu_index == 4:
            config_index = menu_wrap(list(map(lambda x:x.name, ac_configs)), title='Choose the AC config')
            ac_configs[config_index].fill_fan_modes()
        elif menu_index == 5:
            config_index = menu_wrap(list(map(lambda x:x.name, ac_configs)), title='Choose the AC config')
            ac_configs[config_index].fill_temperatures()
    if input_wrap("Save configs? ").lower() in ['y', 'yes']:
        with open(CONFIG_FILE, 'w') as ac_config_file:
            json.dump(ac_configs, ac_config_file, default=ac_config_dumper, indent=2)



if __name__ == '__main__':
    main()
