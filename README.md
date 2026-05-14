# autossh

Alias-based SSH/SCP toolkit with encrypted password storage.

Wraps `ssh`/`scp` via `pexpect` so you can connect to any host by name without
typing passwords. All passwords are stored AES-256-GCM encrypted in a local
hosts file.

## Install

```bash
pip install autossh
```

Python 3.8+ required. Runtime dependencies: `pexpect`, `pyyaml`, `cryptography`.

## Quick start

```bash
# 1. Open the host file editor (creates the file on first run)
aedit

# 2. Add a host line, save and quit vim:
#    192.168.0.1   root   mypassword

# 3. On save, aedit prompts for a master password and encrypts all passwords.
#    The master password can be saved to ~/.config/autossh/.env for future use.

# 4. Connect
assh 192.168.0.1
```

## Commands

| Command | Description |
|---------|-------------|
| `assh <dest>`        | SSH to host |
| `apush <src> <dest>:<path>` | Push local file to remote |
| `apull <dest>:<path> <dst>` | Pull remote file to local |
| `acat [dest]`        | Print hosts file (passwords decrypted) |
| `aedit`              | Edit hosts file (passwords decrypted in editor, re-encrypted on save) |
| `amaster init`       | Encrypt a plaintext hosts file for the first time |
| `amaster`            | Rekey: re-encrypt all passwords with a new master password |

Run any command with `-h` for usage details.

## Host file format

Each non-comment line:

```
host[:port][[alias]]    user    password
```

Examples:

```
192.168.0.1             root    password1
192.168.0.2:36000       root    password2    ## custom port
192.168.0.3[dev3]       root    password3    ## with alias
192.168.0.4:22[dev4]    root    password4    ## port + alias
192.168.0.5             None    None         ## anonymous
```

- `host` — IP or hostname
- `port` — optional, defaults to 22
- `alias` — optional short name for `assh <alias>`
- `user` / `password` — use `None` for anonymous SSH

## Password encryption

Passwords are encrypted with AES-256-GCM using a master password you choose.
The master password is derived into a file key via scrypt and stored in
`~/.config/autossh/.env` (chmod 0600) so you only type it once per machine.

`aedit` decrypts passwords in memory (temp file in `/dev/shm`) so the editor
always shows plaintext; the hosts file on disk always stores ciphertext.

## Configuration

Optional config at `~/.config/autossh/config.yaml`:

```yaml
timeout: 30       # pexpect timeout in seconds (default: 30)
host_file: ~/.config/autossh/hosts   # override host file path
```
