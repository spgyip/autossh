import os
import sys
import autossh.config
import autossh.lookup
from autossh.master import (
    decrypt, derive_file_key, load_master_key, has_password_fields, transform_hosts,
)
from cryptography.exceptions import InvalidTag


def _get_file_key():
    master = load_master_key(offer_save=False)
    return derive_file_key(master)


def main():
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
    lu = autossh.lookup.load(os.path.expanduser(c.host_file))

    if len(destination) > 0:
        ok, info = lu.get(destination)
        if not ok:
            print("Host not found '%s'." % (destination))
            return
        host, port, user, password = info
        try:
            password = decrypt(_get_file_key(), password)
        except InvalidTag:
            print("Error: wrong master password.")
            sys.exit(1)
        print((host, port, user, password))
    else:
        try:
            with open(os.path.expanduser(c.host_file)) as f:
                content = f.read()
        except IOError:
            print("None")
            return
        if has_password_fields(content):
            try:
                file_key = _get_file_key()
                content = transform_hosts(
                    content,
                    lambda pw: decrypt(file_key, pw),
                )
            except InvalidTag:
                print("Error: wrong master password.")
                sys.exit(1)
        print(content)
