import json
import os
import pathlib


class StubEw:
    def __init__(self):
        self.potato = "123"

    def write_event(self, event):
        print(event)

class StubDefinition:
    def __init__(self):
        helper = StubHelper()
        self.parameters = helper.config_dict


class StubHelper:
    def __init__(self):
        current = os.path.dirname(os.path.realpath(__file__))
        parent = pathlib.Path(current).parent.absolute()
        test_config_path = pathlib.Path(parent) / 'test_config.json'
        f = open(test_config_path)
        self.config_dict = json.load(f)

    def get_arg(self, key):
        return self.config_dict[key]

    def get_proxy(self):
        return self.config_dict.get("proxy_settings")

    def save_check_point(self, key, value):
        self.config_dict['checkpoints'][key] = value
        with open('..\\test_config.json', 'w') as f:
            json.dump(self.config_dict, f)

    def get_check_point(self, key):
        return self.config_dict['checkpoints'].get(key)

    def get_input_type(self):
        return 'hsm_stub'

    def get_output_index(self):
        return 'hsm_stub'

    def get_sourcetype(self):
        return 'hsm_stub'

    def new_event(self, source, index, sourcetype, data):
        return data

    def log(self, msg):
        print(msg)

    def log_debug(self, msg):
        print(msg)

    def log_info(self, msg):
        print(msg)

    def log_warning(self, msg):
        print(msg)

    def log_error(self, msg):
        print(msg)

    def log_critical(self, msg):
        print(msg)
