import os
import yaml

config_file = os.path.expanduser("~/.config/autossh/config.yaml")

class config:
    def __init__(self):
        self.host_file = os.path.expanduser("~/.config/autossh/hosts")
        self.timeout = 20
        self.master_key_provider = None   # None = backward-compat fallback
        self.op_secret_ref = "op://Personal/autossh/master_key"
        self.op_vault = "Personal"

def load():
    c = config()
    try:
        f = open(config_file)
        o = yaml.safe_load(f)
        f.close()
    except Exception:
        return c

    try:
        c.timeout = int(o["timeout"])
    except Exception:
        pass

    for attr, key in [("master_key_provider", "master_key_provider"),
                      ("op_secret_ref", "op_secret_ref"),
                      ("op_vault", "op_vault")]:
        try:
            setattr(c, attr, str(o[key]))
        except Exception:
            pass

    return c


def save(c):
    """Persist config fields to CONFIG_FILE, preserving unknown fields."""
    data = {}
    try:
        with open(config_file) as f:
            data = yaml.safe_load(f) or {}
    except Exception:
        pass
    data["timeout"] = c.timeout
    if c.master_key_provider is not None:
        data["master_key_provider"] = c.master_key_provider
        data["op_secret_ref"] = c.op_secret_ref
        data["op_vault"] = c.op_vault
    os.makedirs(os.path.dirname(config_file), exist_ok=True)
    fd = os.open(config_file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        yaml.dump(data, f, default_flow_style=False)
