# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

`autossh` is a Python 3 toolkit that wraps `ssh`/`scp` via `pexpect` to provide password-less, alias-based access to hosts listed in a flat host file. It installs a set of CLI commands (`assh`, `apush`, `apull`, `acat`, `aedit`) that share the same `autossh` Python package for host lookup and pexpect-driven session control.

Python 2 is not supported.

## Common Commands

```bash
# Install / uninstall (installs scripts to ~/bin/)
sudo sh install
sudo sh uninstall

# Run the lookup module's built-in self-test
python3 -m autossh.lookup

# Run a CLI tool directly from the repo without installing
PYTHONPATH=. python3 bin/assh <destination>
```

There is no separate lint/test runner — `autossh/lookup.py` has an `if __name__ == "__main__"` block that serves as the only test, exercising host/alias/port parsing against an inline sample.

Runtime dependencies (declared in `setup.py`): `pexpect`, `pyyaml`, `cryptography`.

## Architecture

The CLI commands are defined as `console_scripts` entry points in `setup.py`, pointing at `autossh.cli.<cmd>:main`. The files under `bin/` are thin shims (`from autossh.cli.<cmd> import main; main()`) kept only for repo-local dev (`PYTHONPATH=. python3 bin/<cmd>`); when installed via pip they are replaced by setuptools-generated wrappers with the correct interpreter shebang.

All SSH/SCP behavior lives in the `autossh` package.

- **`autossh/ssh.py` — `SSH` class**: the core. `login()` spawns `ssh`, `jump()` issues an `ssh` command inside an already-logged-in session (intended for bastion-hopping), and `send_file()`/`pull_file()` spawn `scp`. All four methods drive a `pexpect.expect()` loop against the same default pattern list: `["yes/no", "assword:", "[#\$]", TIMEOUT, EOF]`. `login()`/`jump()` accept `expects`/`reacts` extension arrays — extra patterns are appended after the defaults, and the matching `reacts` entry (a string or a zero-arg callable) is `sendline`'d when matched. Custom auth flows (e.g. a 2FA token prompt on a bastion) can be layered on top via this extension mechanism without editing `ssh.py` — historically a `qssh` command lived here doing exactly that, but it was removed for being too site-specific.
- **`autossh/lookup.py` — `Lookup`**: parses the host file. Each non-comment line is `host[:port][[alias]]  user  password`. Two dicts are maintained (`__m0` keyed by host, `__m1` keyed by alias); `get()` checks host first, then alias. `port` is the string `0` when unset — callers in `ssh.py` test `port != 0` to decide whether to add `-p` / `-P`.
- **`autossh/master.py`**: password encryption layer. Uses AES-256-GCM (`cryptography`) and scrypt KDF. `derive_file_key(master, salt)` derives the 32-byte AES key; callers obtain `salt` via `get_salt(content)` which prefers the `## SALT: <hex>` header embedded at the top of the hosts file (portable, follows the file), falls back to the legacy `~/.config/autossh/.salt` file, and finally generates a new random salt. `inject_salt(content, salt)` writes the SALT header on encryption so the hosts file is self-contained. Encrypted passwords are raw base64 ciphertext (no prefix). `transform_hosts(content, fn)` applies `fn(password)` to every valid host line while preserving comments and layout. `has_password_fields(content)` returns True when the hosts file has any 3-field non-comment lines (used for lazy master key loading).
- **`autossh/config.py`**: loads `~/.config/autossh/config.yaml` (currently only `timeout`); defaults are returned silently on any error.
- **`autossh/winsize.py` — `WatchDog`**: SIGWINCH-based terminal resize forwarding to the pexpect child. Enabled via `SSH.autowinsize()`; every interactive CLI calls this before `interact()`.

### Adding a new command

1. Create `autossh/cli/<name>.py` with a `def main():` (mirror `autossh/cli/assh.py`: parse args, `autossh.ssh.new(dest)`, `login()`, `autowinsize()`, `interact()` or a file transfer).
2. Add `"<name> = autossh.cli.<name>:main"` to the `console_scripts` list in `setup.py`.
3. Add a 3-line shim at `bin/<name>` (`#!/usr/bin/env python3` + `from autossh.cli.<name> import main` + `main()`) so the repo-local dev workflow keeps working.
4. Add the script name to the `rm -fv` line in `uninstall` so uninstall stays in sync.

### Host file & config locations

- Host file: `~/.config/autossh/hosts` (override via `config.yaml` → `host_file`). Sample at `config/autossh/hosts`. If absent, `aedit` seeds a commented template on first run. The password column always stores AES-256-GCM ciphertext (raw base64, no prefix). On first use (any command that needs the master key), the user is prompted for a master password and chooses where it is stored: 1Password (via `op` CLI), local `.env` file, or no-save (prompt every time). The choice is persisted in `config.yaml` as `master_key_provider`. Use `amaster` to rekey with a new master password (and optionally switch provider).
- autossh config: `~/.config/autossh/config.yaml` (keys: `timeout`, `master_key_provider`, `op_secret_ref`, `op_vault`).
- Master key storage: depends on `master_key_provider` — `dotenv` → `~/.config/autossh/.env` (key `ASSH_MASTER_KEY`; chmod 0600); `op` → 1Password item referenced by `op_secret_ref`; `prompt` → not stored. Salt is embedded in the hosts file as a `## SALT: <hex>` header (16 bytes random, auto-injected on first encryption); legacy `~/.config/autossh/.salt` file is read as fallback for files predating this header.

User `None` and password `None` (literal strings) mean anonymous — `ssh.py` branches on `user == "None"` to drop the `user@` prefix.

## Versioning

Bumping the release means editing `version=` in `setup.py` and committing with the message `Upgrade version` — that is the established convention in the commit history.
