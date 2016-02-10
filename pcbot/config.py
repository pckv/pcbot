import json
from os.path import exists
from os import mkdir


class Config:
    config_path = "config/"

    def __init__(self, filename, data=None, load=True):
        self.filepath = "{}{}.json".format(self.config_path, filename)

        if not exists(self.config_path):
            mkdir(self.config_path)

        loaded_data = None

        if load:
            loaded_data = self.load()

        if data and not loaded_data:
            self.data = data
        elif loaded_data:
            self.data = loaded_data
        else:
            self.data = None

        if not self.data == loaded_data:
            self.save()

    def save(self):
        with open(self.filepath, "w") as f:
            json.dump(self.data, f)

    def load(self):
        if exists(self.filepath):
            with open(self.filepath, "r") as f:
                return json.load(f)

        return None
