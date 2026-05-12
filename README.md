Toolkits for convenient SSH.
=====================================

## Notice

Python2 is not supported.

## Install & Uninstall

```
sudo sh install
sudo sh uninstall
```

## Configuration

### Config

All configurations have default values, you don't have to create config file. Or you can create one at `~/.config/<module>/config.yaml`. Refer to \$repo`/config/<module>/config.yaml` for configuration detail.

### Host file
Use `aedit` to add host. Or host file path is at `~/.config/autossh/hosts`, you can create by your own. Refer to \$repo`/config/autossh/hosts`.

Format:

```
host[:port][\[alias\]]     user    password
```

- host: Ip or hostname, required.
- port: Port, optional.
- alias: Alias name for host, optional.
- user: Login user, required. "None" for anonymous.
- password: Login password, required. "None" for anonymous.

## Toolkits

Run `-h` for help messages.

- assh : Auto-ssh.
- apush: Push local file to remote.
- apull: Pull file from remote to local.
- acat : Cat host file.
- aedit: Edit host file.

## TODO

- Fix escape character '\x1d' conflicted with `vim`.
    + DONE
- Remove `pexpect.py`.
    + DONE
- Messy window size with `vim` or `man page`.
    + DONE
- Migrage to Py3
    + Done
- Default configuration.
    + DONE
- Publish to PyPI.
- Command line arguments.
    + -t timeout
- Add tool `apush` `apull`.
    + DONE
- Install exec to specified dir, etc `/usr/local/bin/`.
    + DONE
