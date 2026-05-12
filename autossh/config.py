import os
import yaml

config_file = os.path.expanduser("~/.config/autossh/config.yaml")

class config:
    def __init__(self):
        self.host_file = os.path.expanduser("~/.config/autossh/hosts") # Default
        self.timeout = 20

def load():
    c = config()
    try:
        f = open(config_file)
        o = yaml.safe_load(f)
        f.close()
    except Exception as e:
        # Load from config file error, return default config().
        return c
     
    try:
        c.timeout = int(o["timeout"])
    except Exception as e:
        None

    return c


