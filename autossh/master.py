import base64
import getpass
import os

from cryptography.exceptions import InvalidTag  # re-exported for callers
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

ENV_KEY = "ASSH_MASTER_KEY"
ENC_PREFIX = "enc:v1:"
SALT_FILE = os.path.expanduser("~/.config/autossh/.salt")
DOTENV_FILE = os.path.expanduser("~/.config/autossh/.env")


# ── Key derivation ────────────────────────────────────────────────────────────

def _load_or_create_salt():
    if os.path.exists(SALT_FILE):
        with open(SALT_FILE, "rb") as f:
            return f.read()
    salt = os.urandom(16)
    os.makedirs(os.path.dirname(SALT_FILE), exist_ok=True)
    fd = os.open(SALT_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(salt)
    return salt


def derive_file_key(master):
    """Derive 32-byte AES key from master password via scrypt (run once per session)."""
    salt = _load_or_create_salt()
    return Scrypt(salt=salt, length=32, n=2**14, r=8, p=1).derive(master.encode())


# ── Encrypt / decrypt ─────────────────────────────────────────────────────────

def encrypt(file_key, plaintext):
    """Return enc:v1:<base64(nonce+ct+tag)>."""
    nonce = os.urandom(12)
    ct = AESGCM(file_key).encrypt(nonce, plaintext.encode(), None)
    return ENC_PREFIX + base64.b64encode(nonce + ct).decode()


def decrypt(file_key, enc_str):
    """Decrypt enc:v1:… string. Raises InvalidTag on wrong key."""
    blob = base64.b64decode(enc_str[len(ENC_PREFIX):])
    nonce, ct = blob[:12], blob[12:]
    return AESGCM(file_key).decrypt(nonce, ct, None).decode()


def is_encrypted(s):
    return s.startswith(ENC_PREFIX)


# ── Hosts file transformation ─────────────────────────────────────────────────

def transform_hosts(content, transform_fn):
    """Apply transform_fn(password) to every valid host-line password field."""
    return "".join(_transform_line(line, transform_fn)
                   for line in content.splitlines(keepends=True))


def _transform_line(line, transform_fn):
    stripped = line.rstrip("\r\n")
    ending = line[len(stripped):]

    comment_pos = stripped.find("#")
    if comment_pos >= 0:
        comment = stripped[comment_pos:]
        data = stripped[:comment_pos]
    else:
        comment = ""
        data = stripped

    fields = data.split()
    if len(fields) != 3:
        return line

    new_pw = transform_fn(fields[2])
    if new_pw == fields[2]:
        return line

    leading = data[: len(data) - len(data.lstrip())]
    core = f"{leading}{fields[0]}   {fields[1]}   {new_pw}"
    if comment:
        core += "   " + comment
    return core + ending


# ── .env helpers ─────────────────────────────────────────────────────────────

def load_dotenv():
    """Load DOTENV_FILE into os.environ (setdefault — does not overwrite)."""
    if not os.path.exists(DOTENV_FILE):
        return
    with open(DOTENV_FILE) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def save_to_dotenv(master):
    """Write/update ASSH_MASTER_KEY in DOTENV_FILE (chmod 0600)."""
    lines = []
    found = False
    if os.path.exists(DOTENV_FILE):
        with open(DOTENV_FILE) as f:
            for line in f:
                if line.startswith(ENV_KEY + "="):
                    lines.append(f"{ENV_KEY}={master}\n")
                    found = True
                else:
                    lines.append(line)
    if not found:
        lines.append(f"{ENV_KEY}={master}\n")
    os.makedirs(os.path.dirname(DOTENV_FILE), exist_ok=True)
    fd = os.open(DOTENV_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.writelines(lines)


# ── Master key loading ────────────────────────────────────────────────────────

def load_master_key(offer_save=True):
    """Load master: DOTENV_FILE → env var → interactive prompt."""
    load_dotenv()
    master = os.environ.get(ENV_KEY)
    if master:
        return master
    master = getpass.getpass("Master password: ")
    if offer_save:
        try:
            ans = input("Save to ~/.config/autossh/.env? [y/N] ").strip().lower()
        except EOFError:
            ans = ""
        if ans == "y":
            save_to_dotenv(master)
    return master
