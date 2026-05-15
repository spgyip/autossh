import getpass
import os
import sys

import autossh.config
import autossh.master as _m
from autossh.master import (
    decrypt, encrypt,
    derive_file_key, load_master_key, save_to_dotenv,
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


def _prompt_provider():
    print("\nHow to save the master key?")
    print("  1. 1Password (op CLI)")
    print("  2. Local .env file")
    print("  3. Don't save (ask every time)")
    while True:
        try:
            ans = input("> ").strip()
        except EOFError:
            return "prompt"
        if ans in ("1", "2", "3"):
            return {"1": "op", "2": "dotenv", "3": "prompt"}[ans]
        print("Please enter 1, 2, or 3.")


def _save_master_for_provider(master, provider, cfg):
    if provider == "op":
        if not _m._op_available():
            print("Warning: op CLI not installed, saving to .env instead.")
            save_to_dotenv(master)
            print("Saved to ~/.config/autossh/.env")
            return
        ref = _m.op_save(master, cfg.op_vault)
        if ref:
            print(f"Saved to 1Password ({ref})")
        else:
            print("Warning: 1Password save failed, saving to .env instead.")
            save_to_dotenv(master)
            print("Saved to ~/.config/autossh/.env")
    elif provider == "dotenv":
        save_to_dotenv(master)
        print("Saved to ~/.config/autossh/.env")
    # provider == "prompt": nothing to save


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


def cmd_init(host_file):
    """Treat all passwords as plaintext and encrypt with a new master key."""
    content = _load_host_file(host_file)

    if not has_password_fields(content):
        print("No password fields found in hosts file.")
        sys.exit(0)

    cfg = autossh.config.load()
    provider = _prompt_provider()
    new_master = _prompt_new_master()
    new_key = derive_file_key(new_master)

    new_content = transform_hosts(content, lambda pw: encrypt(new_key, pw))
    _write_host_file(host_file, new_content)
    print("Hosts file encrypted.")

    cfg.master_key_provider = provider
    cfg.op_secret_ref = f"op://{cfg.op_vault}/autossh/master_key"
    autossh.config.save(cfg)
    _save_master_for_provider(new_master, provider, cfg)


def cmd_rekey(host_file):
    """Verify current master, then re-encrypt all passwords with a new master key."""
    content = _load_host_file(host_file)

    if not has_password_fields(content):
        print("No password fields found. Use 'amaster init' to encrypt a plaintext hosts file.")
        sys.exit(0)

    cfg = autossh.config.load()
    cur_master = load_master_key(offer_save=False, cfg=cfg)
    cur_key = derive_file_key(cur_master)

    try:
        transform_hosts(content, lambda pw: decrypt(cur_key, pw))
    except InvalidTag:
        print("Error: wrong current master password.")
        sys.exit(1)

    provider = _prompt_provider()
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
    _save_master_for_provider(new_master, provider, cfg)


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
