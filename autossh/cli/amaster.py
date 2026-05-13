import getpass
import os
import sys

import autossh.config
from autossh.master import (
    ENV_KEY, DOTENV_FILE,
    decrypt, encrypt, is_encrypted,
    derive_file_key, load_dotenv, save_to_dotenv, transform_hosts,
)
from cryptography.exceptions import InvalidTag


def _first_encrypted_pw(content):
    for line in content.splitlines():
        cp = line.find("#")
        data = line[:cp] if cp >= 0 else line
        fields = data.split()
        if len(fields) == 3 and is_encrypted(fields[2]):
            return fields[2]
    return None


def _prompt_new_master():
    while True:
        new_master = getpass.getpass("New master password: ")
        confirm = getpass.getpass("Confirm new master password: ")
        if new_master == confirm:
            return new_master
        print("Passwords do not match, try again.")


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "-h":
        print("")
        print("Usage:")
        print("  amaster [-h]")
        print("")
        print("Set or change the master password used to encrypt the hosts file.")
        print("")
        sys.exit(0)

    c = autossh.config.load()
    host_file = c.host_file

    try:
        with open(host_file) as f:
            content = f.read()
    except IOError:
        print(f"Host file not found: {host_file}")
        print("Run `aedit` to create one.")
        sys.exit(1)

    first_enc = _first_encrypted_pw(content)

    if first_enc is None:
        # First-time encryption: no current master to verify
        try:
            ans = input("No encrypted passwords found. Encrypt all with a new master key? [y/N] ").strip().lower()
        except EOFError:
            ans = ""
        if ans != "y":
            print("Aborted.")
            sys.exit(0)
        new_master = _prompt_new_master()
        new_key = derive_file_key(new_master)
        new_content = transform_hosts(
            content,
            lambda pw: pw if is_encrypted(pw) else encrypt(new_key, pw),
        )
    else:
        # Re-keying: verify current master first
        cur_master = getpass.getpass("Current master password: ")
        cur_key = derive_file_key(cur_master)
        try:
            decrypt(cur_key, first_enc)
        except InvalidTag:
            print("Error: wrong current master password.")
            sys.exit(1)

        new_master = _prompt_new_master()
        new_key = derive_file_key(new_master)

        new_content = transform_hosts(
            content,
            lambda pw: encrypt(new_key, decrypt(cur_key, pw)) if is_encrypted(pw) else pw,
        )

    # Write back
    fd = os.open(host_file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(new_content)
    print("Master password updated.")

    # Offer to update .env if it's in use
    load_dotenv()
    dotenv_has_key = False
    if os.path.exists(DOTENV_FILE):
        with open(DOTENV_FILE) as f:
            dotenv_has_key = any(l.startswith(ENV_KEY + "=") for l in f)

    if dotenv_has_key or os.environ.get(ENV_KEY):
        try:
            ans = input("Update ASSH_MASTER_KEY in ~/.config/autossh/.env? [Y/n] ").strip().lower()
        except EOFError:
            ans = "y"
        if ans != "n":
            save_to_dotenv(new_master)
            print("~/.config/autossh/.env updated.")
