import getpass
import sys

import autossh.config
from autossh.master import (
    decrypt, encrypt,
    derive_file_key, load_master_key,
    has_password_fields, transform_hosts,
    prompt_provider, save_master_for_provider,
)
from cryptography.exceptions import InvalidTag

import os


def _prompt_new_master():
    while True:
        new_master = getpass.getpass("New master password: ")
        confirm = getpass.getpass("Confirm new master password: ")
        if new_master == confirm:
            return new_master
        print("Passwords do not match, try again.")


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


def cmd_rekey(host_file):
    """Verify current master, then re-encrypt all passwords with a new master key."""
    content = _load_host_file(host_file)

    if not has_password_fields(content):
        print("No password fields found. Run `aedit` to add hosts first.")
        sys.exit(0)

    cfg = autossh.config.load()
    cur_master = load_master_key(offer_save=False, cfg=cfg)
    cur_key = derive_file_key(cur_master)

    try:
        transform_hosts(content, lambda pw: decrypt(cur_key, pw))
    except InvalidTag:
        print("Error: wrong current master password.")
        sys.exit(1)

    provider = prompt_provider()
    new_master = _prompt_new_master()
    new_key = derive_file_key(new_master)

    new_content = transform_hosts(
        content,
        lambda pw: encrypt(new_key, decrypt(cur_key, pw)),
    )
    _write_host_file(host_file, new_content)
    print("Master password updated.")

    cfg.master_key_provider = provider
    cfg.op_secret_ref = f"op://{cfg.op_vault}/autossh/master_key"
    autossh.config.save(cfg)
    save_master_for_provider(new_master, provider, cfg)


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "-h":
        print("")
        print("Usage:")
        print("  amaster [-h]")
        print("")
        print("  Re-encrypt all passwords with a new master key.")
        print("")
        sys.exit(0)

    c = autossh.config.load()
    cmd_rekey(c.host_file)
