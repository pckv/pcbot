import json
from os.path import exists
from os import mkdir


class Config:
    config_path = "config/"

    def __init__(self, filename: str, data=None, load: bool=True):
        """ Setup the config file if it does not exist.

        :param filename: usually a string representing the module name.
        :param data: default data setup, usually an empty/defaulted dictionary or list.
        :param load: should the config file load when initialized? Only loads when a config already exists. """
        self.filepath = "{}{}.json".format(self.config_path, filename)

        if not exists(self.config_path):
            mkdir(self.config_path)

        loaded_data = None

        if load:
            loaded_data = self.load()

        if data is not None and not loaded_data:
            self.data = data
        elif loaded_data:
            self.data = loaded_data
        else:
            self.data = None

        if not self.data == loaded_data:
            self.save()

    def save(self):
        """ Write the current config to file. """
        with open(self.filepath, "w") as f:
            json.dump(self.data, f)

    def load(self):
        """ Load the config from file if it exists.

        :return: config parsed from json or None"""
        if exists(self.filepath):
            with open(self.filepath, "r") as f:
                return json.load(f)

        return None
