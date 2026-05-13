import os
import os.path
import subprocess
import sys
import tempfile

import autossh.config
from autossh.master import (
    decrypt, encrypt,
    derive_file_key, load_master_key, has_password_fields, transform_hosts,
)
from cryptography.exceptions import InvalidTag


HOSTS_TEMPLATE = """\
## autossh host file.
## Each non-comment line:
##   host[:port][[alias]]    user    password
##
## Use 'None' for user/password to ssh anonymously.
## Lines starting with '#' are comments.

## Examples — uncomment and edit, or add your own:
#
# 192.168.0.1            root    password1
# 192.168.0.2            root    password2          ## inline comment
# 192.168.0.3[dev3]      root    password3          ## with alias
# 192.168.0.4:36000      root    password4          ## with custom port
# 192.168.0.5:22[dev5]   root    password5          ## port + alias
# 192.168.0.6            None    None               ## anonymous
"""


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "-h":
        print("")
        print("Usage:")
        print("  aedit [-h]")
        print("")
        sys.exit(0)

    c = autossh.config.load()
    host_file = c.host_file
    dirs = os.path.dirname(host_file)
    if not os.access(dirs, os.F_OK):
        os.makedirs(dirs)

    # Seed template on first run
    if not os.path.exists(host_file):
        fd = os.open(host_file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(HOSTS_TEMPLATE)
    else:
        os.chmod(host_file, 0o600)

    with open(host_file) as f:
        original_content = f.read()

    # No password fields — open directly in vim (nothing to encrypt/decrypt)
    if not has_password_fields(original_content):
        os.execvp("vim", ["vim", host_file])
        return  # unreachable

    # Load master key and verify it decrypts correctly
    master = load_master_key(offer_save=True)
    file_key = derive_file_key(master)

    # Decrypt all password fields for editing
    try:
        decrypted_content = transform_hosts(
            original_content,
            lambda pw: decrypt(file_key, pw),
        )
    except InvalidTag:
        print("Error: wrong master password.")
        print("Run 'amaster init' to re-encrypt your hosts file.")
        sys.exit(1)

    # Write plaintext to temp file (in-memory fs when available)
    shm = "/dev/shm" if os.path.isdir("/dev/shm") else tempfile.gettempdir()
    fd, tmp_path = tempfile.mkstemp(dir=shm, suffix=".hosts")
    os.chmod(tmp_path, 0o600)

    saved_ok = False
    try:
        with os.fdopen(fd, "w") as f:
            f.write(decrypted_content)

        subprocess.call(["vim", "-n", tmp_path])

        with open(tmp_path) as f:
            edited_content = f.read()

        # Encrypt all password fields and write back
        encrypted_content = transform_hosts(
            edited_content,
            lambda pw: encrypt(file_key, pw),
        )
        wfd = os.open(host_file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(wfd, "w") as f:
            f.write(encrypted_content)
        saved_ok = True

    finally:
        if saved_ok:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
        else:
            print(f"Error: hosts file not saved. Plaintext edits preserved at: {tmp_path}")
