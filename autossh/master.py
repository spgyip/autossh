import base64
import getpass
import os
import shutil
import subprocess

from cryptography.exceptions import InvalidTag  # re-exported for callers
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

ENV_KEY = "ASSH_MASTER_KEY"
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
    """Return base64(nonce+ct+tag) — no prefix."""
    nonce = os.urandom(12)
    ct = AESGCM(file_key).encrypt(nonce, plaintext.encode(), None)
    return base64.b64encode(nonce + ct).decode()


def decrypt(file_key, ciphertext_b64):
    """Decrypt base64-encoded ciphertext. Raises InvalidTag on wrong key."""
    blob = base64.b64decode(ciphertext_b64)
    nonce, ct = blob[:12], blob[12:]
    return AESGCM(file_key).decrypt(nonce, ct, None).decode()


# ── Hosts file helpers ────────────────────────────────────────────────────────

def has_password_fields(content):
    """Return True if the hosts file has any non-comment 3-field lines."""
    for line in content.splitlines():
        cp = line.find("#")
        data = line[:cp] if cp >= 0 else line
        if len(data.split()) == 3:
            return True
    return False


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


# ── 1Password helpers ────────────────────────────────────────────────────────

def _op_available():
    return shutil.which("op") is not None


def op_read(secret_ref):
    """Run `op read <ref>`, return master key string or None on failure."""
    try:
        r = subprocess.run(
            ["op", "read", secret_ref],
            capture_output=True, text=True, timeout=10,
        )
        return r.stdout.strip() if r.returncode == 0 else None
    except Exception:
        return None


def op_save(master, vault, title="autossh", field="master_key"):
    """Create or update a 1Password item. Returns op:// reference or None."""
    try:
        check = subprocess.run(
            ["op", "item", "get", title, "--vault", vault, "--fields", field],
            capture_output=True, text=True, timeout=10,
        )
        if check.returncode == 0:
            cmd = ["op", "item", "edit", title, "--vault", vault, f"{field}={master}"]
        else:
            cmd = ["op", "item", "create", "--category=password",
                   f"--title={title}", f"--vault={vault}", f"{field}={master}"]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        return f"op://{vault}/{title}/{field}" if r.returncode == 0 else None
    except Exception:
        return None


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


# ── Provider selection helpers ──────────────────────────────────────────────

def prompt_provider():
    """Interactive menu: returns 'op' | 'dotenv' | 'prompt'."""
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


def save_master_for_provider(master, provider, cfg):
    """Persist master key according to the chosen provider."""
    if provider == "op":
        if not _op_available():
            print("Warning: op CLI not installed, saving to .env instead.")
            save_to_dotenv(master)
            print("Saved to ~/.config/autossh/.env")
            return
        ref = op_save(master, cfg.op_vault)
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


# ── Master key loading ────────────────────────────────────────────────────────

def load_master_key(offer_save=True, cfg=None):
    """Load master key using the configured provider.

    When cfg.master_key_provider is None and offer_save is True, prompts the
    user once and then shows the provider-selection menu to persist the choice.
    """
    provider = getattr(cfg, "master_key_provider", None)

    if provider is None:
        load_dotenv()
        master = os.environ.get(ENV_KEY)
        if master:
            return master
        if offer_save and cfg is not None:
            new_provider = prompt_provider()
            master = getpass.getpass("Master password: ")
            cfg.master_key_provider = new_provider
            cfg.op_secret_ref = f"op://{cfg.op_vault}/autossh/master_key"
            try:
                import autossh.config as _config
                _config.save(cfg)
            except Exception as e:
                print(f"Warning: could not persist provider choice to config.yaml: {e}")
            save_master_for_provider(master, new_provider, cfg)
            return master
        return getpass.getpass("Master password: ")

    if provider == "op":
        if not _op_available():
            print("Warning: op CLI not found, falling back to prompt.")
            return getpass.getpass("Master password: ")
        master = op_read(cfg.op_secret_ref)
        if master:
            return master
        print(f"Warning: could not read from 1Password ({cfg.op_secret_ref}), falling back to prompt.")
        return getpass.getpass("Master password: ")

    if provider == "dotenv":
        load_dotenv()
        master = os.environ.get(ENV_KEY)
        if master:
            return master
        print("Warning: ASSH_MASTER_KEY not in .env, falling back to prompt.")
        return getpass.getpass("Master password: ")

    # provider == "prompt" or unknown
    return getpass.getpass("Master password: ")
