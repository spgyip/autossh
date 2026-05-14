import getpass
import os
import sys

import autossh.config
from autossh.master import (
    ENV_KEY, DOTENV_FILE,
    decrypt, encrypt,
    derive_file_key, load_dotenv, save_to_dotenv,
    has_password_fields, transform_hosts,
)
from cryptography.exceptions import InvalidTag


def _prompt_new_master():
    while True:
        new_master = getpass.getpass("New master password: ")
        confirm = getpass.getpass("Confirm new master password: ")
        if new_master == confirm:
            return new_master
        print("Passwords do not match, try again.")


def _offer_dotenv_update(new_master):
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


def _load_host_file(host_file):
    try:
        with open(host_file) as f:
            return f.read()
    except IOError:
        print(f"Host file not found: {host_file}")
        print("Run `aedit` to create one.")
        sys.exit(1)


def _write_host_file(host_file, content):
    fd = os.open(host_file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(content)


def _offer_dotenv_save(master):
    """Always offer to save master key to .env."""
    try:
        ans = input("Save master key to ~/.config/autossh/.env? [Y/n] ").strip().lower()
    except EOFError:
        ans = "y"
    if ans != "n":
        save_to_dotenv(master)
        print("~/.config/autossh/.env updated.")


def cmd_init(host_file):
    """Treat all passwords as plaintext and encrypt with a new master key."""
    content = _load_host_file(host_file)

    if not has_password_fields(content):
        print("No password fields found in hosts file.")
        sys.exit(0)

    new_master = _prompt_new_master()
    new_key = derive_file_key(new_master)

    new_content = transform_hosts(content, lambda pw: encrypt(new_key, pw))
    _write_host_file(host_file, new_content)
    print("Hosts file encrypted.")

    _offer_dotenv_save(new_master)


def cmd_rekey(host_file):
    """Verify current master, then re-encrypt all passwords with a new master key."""
    content = _load_host_file(host_file)

    if not has_password_fields(content):
        print("No password fields found. Use 'amaster init' to encrypt a plaintext hosts file.")
        sys.exit(0)

    cur_master = getpass.getpass("Current master password: ")
    cur_key = derive_file_key(cur_master)

    # Verify by attempting to decrypt all fields
    try:
        transform_hosts(content, lambda pw: decrypt(cur_key, pw))
    except InvalidTag:
        print("Error: wrong current master password.")
        sys.exit(1)

    new_master = _prompt_new_master()
    new_key = derive_file_key(new_master)

    new_content = transform_hosts(
        content,
        lambda pw: encrypt(new_key, decrypt(cur_key, pw)),
    )
    _write_host_file(host_file, new_content)
    print("Master password updated.")

    _offer_dotenv_update(new_master)


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "-h":
        print("")
        print("Usage:")
        print("  amaster [-h] [init]")
        print("")
        print("  amaster        Rekey: re-encrypt all passwords with a new master key")
        print("  amaster init   Init: encrypt a plaintext hosts file for the first time")
        print("")
        sys.exit(0)

    c = autossh.config.load()
    host_file = c.host_file

    if len(sys.argv) > 1 and sys.argv[1] == "init":
        cmd_init(host_file)
    else:
        cmd_rekey(host_file)
