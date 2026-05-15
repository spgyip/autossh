import os
import sys
import autossh
import autossh.config
import autossh.lookup
from autossh.master import (
    decrypt, derive_file_key, get_salt, load_master_key,
    has_password_fields, transform_hosts,
)
from cryptography.exceptions import InvalidTag


def _get_file_key(cfg, content):
    master = load_master_key(cfg=cfg)
    return derive_file_key(master, get_salt(content))


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--version":
        autossh.print_version_and_exit("acat")
    if len(sys.argv) > 1 and sys.argv[1] == "-h":
        print("")
        print("Usage:")
        print("  acat [-h] [destination]")
        print("")
        print("acat              #Cat all")
        print("acat destination  #Cat destionation")
        print("")
        sys.exit(0)

    destination = ""
    if len(sys.argv) >= 2:
        destination = sys.argv[1]

    c = autossh.config.load()
    host_file = os.path.expanduser(c.host_file)
    try:
        with open(host_file) as f:
            content = f.read()
    except IOError:
        print("None")
        return
    lu = autossh.lookup.load(host_file)

    if len(destination) > 0:
        ok, info = lu.get(destination)
        if not ok:
            print("Host not found '%s'." % (destination))
            return
        host, port, user, password = info
        try:
            password = decrypt(_get_file_key(c, content), password)
        except InvalidTag:
            print("Error: wrong master password.")
            sys.exit(1)
        print((host, port, user, password))
    else:
        if has_password_fields(content):
            try:
                file_key = _get_file_key(c, content)
                content = transform_hosts(
                    content,
                    lambda pw: decrypt(file_key, pw),
                )
            except InvalidTag:
                print("Error: wrong master password.")
                sys.exit(1)
        print(content)
