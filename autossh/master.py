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


# ── Salt management ──────────────────────────────────────────────────────────

SALT_HEADER = "## SALT:"


def extract_salt(content):
    """Return salt bytes from a '## SALT: <hex>' line in content, else None."""
    for line in content.splitlines():
        s = line.strip()
        if s.startswith(SALT_HEADER):
            try:
                return bytes.fromhex(s[len(SALT_HEADER):].strip())
            except ValueError:
                return None
    return None


SALT_WARNING_LINES = (
    "## DO NOT EDIT OR REMOVE the SALT line below.",
    "## It is required to decrypt the passwords in this file.",
)


def inject_salt(content, salt):
    """Return content with the SALT header (plus warning) at top.

    Replaces any existing SALT header and previously-written warning lines
    so the file stays clean across rewrites.
    """
    drop_prefixes = SALT_WARNING_LINES + (SALT_HEADER,)
    out = [l for l in content.splitlines(keepends=True)
           if not any(l.strip().startswith(p) for p in drop_prefixes)]
    header = "\n".join(SALT_WARNING_LINES) + f"\n{SALT_HEADER} {salt.hex()}\n"
    return header + "".join(out)


def get_salt(content):
    """Resolve salt for the given hosts content.

    Priority: embedded SALT header > legacy .salt file > new random salt.
    Does not write to disk; the caller persists via inject_salt() on write.
    """
    salt = extract_salt(content)
    if salt is not None:
        return salt
    if os.path.exists(SALT_FILE):
        with open(SALT_FILE, "rb") as f:
            return f.read()
    return os.urandom(16)


# ── Key derivation ────────────────────────────────────────────────────────────

def derive_file_key(master, salt):
    """Derive 32-byte AES key from master password via scrypt."""
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


def first_ciphertext(content):
    """Return the first encrypted password field from hosts content, or None."""
    for line in content.splitlines():
        cp = line.find("#")
        data = line[:cp] if cp >= 0 else line
        fields = data.split()
        if len(fields) == 3:
            return fields[2]
    return None


def make_verifier_for(salt, ciphertext_b64):
    """Build verify(master)->bool that tests decryption of one ciphertext."""
    def verify(master):
        try:
            decrypt(derive_file_key(master, salt), ciphertext_b64)
            return True
        except Exception:
            return False
    return verify


def make_verifier(content):
    """Build verify(master)->bool from hosts content, or None when there is
    no encrypted entry to test against (e.g. fresh file)."""
    pw = first_ciphertext(content)
    if pw is None:
        return None
    return make_verifier_for(get_salt(content), pw)


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
    """Run `op read <ref>`. Returns (master, error).

    - (value, None) on success
    - (None, None) when item is absent (legitimate first-time setup)
    - (None, message) when the CLI call itself failed (not signed in, network,
      vault permissions, etc.) — callers should surface `message` to the user
      instead of silently falling back to a master-password prompt.
    """
    try:
        r = subprocess.run(
            ["op", "read", secret_ref],
            capture_output=True, text=True, timeout=10,
        )
    except Exception as e:
        return None, str(e)
    if r.returncode == 0:
        return r.stdout.strip(), None
    stderr = (r.stderr or "").strip()
    if "isn't an item" in stderr or "no item found" in stderr.lower():
        return None, None
    return None, stderr or f"op read exited with status {r.returncode}"


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
    """Interactive menu: returns 'dotenv' | 'op' | 'prompt'. Default is 'dotenv'."""
    print("\nChoose the master key provider:")
    print("  1. Local .env file (default)")
    print("  2. 1Password (op CLI)")
    print("  3. Don't save (ask every time)")
    while True:
        try:
            ans = input("> ").strip()
        except EOFError:
            return "dotenv"
        if ans == "":
            return "dotenv"
        if ans in ("1", "2", "3"):
            return {"1": "dotenv", "2": "op", "3": "prompt"}[ans]
        print("Please enter 1, 2, or 3.")


def save_master_for_provider(master, provider, cfg):
    """Persist master key according to the chosen provider. Returns True on success."""
    if provider == "op":
        if not _op_available():
            print("Error: op CLI not found. Install 1Password CLI (`op`) and retry.")
            return False
        ref = op_save(master, cfg.op_vault)
        if not ref:
            print("Error: 1Password save failed. Check `op signin` and vault access.")
            return False
        print(f"Saved to 1Password ({ref})")
        return True
    if provider == "dotenv":
        save_to_dotenv(master)
        print("Saved to ~/.config/autossh/.env")
        return True
    # provider == "prompt": nothing to save
    return True


# ── Master key loading ────────────────────────────────────────────────────────

def _try_load_from_provider(provider, cfg):
    """Try to fetch an existing master key from the given provider.

    Returns (master, error). master=None with error=None means "not stored yet"
    (legitimate first-run); error!=None means the provider call failed and the
    caller should surface the message rather than silently re-prompting.
    """
    if provider == "dotenv":
        load_dotenv()
        return os.environ.get(ENV_KEY), None
    if provider == "op":
        if not _op_available():
            return None, "op CLI not found"
        return op_read(cfg.op_secret_ref)
    return None, None  # "prompt": never has a stored key


def _prompt_master_with_verify(verify_fn):
    """Prompt for the master password, looping until verify_fn passes.

    Returns the master string once verified. If verify_fn is None (e.g. fresh
    file with no encrypted entries to test against), returns the first input.
    """
    while True:
        master = getpass.getpass("Master password: ")
        if verify_fn is None or verify_fn(master):
            return master
        print("Error: master password does not decrypt existing entries. Try again.")


def load_master_key(offer_save=True, cfg=None, verify_fn=None):
    """Load master key using the configured provider.

    When cfg.master_key_provider is None and offer_save is True, prompts the
    user to pick a provider; first attempts to load an existing key from that
    provider (multi-machine sync case), and only prompts for the master if
    nothing is stored there yet.
    """
    provider = getattr(cfg, "master_key_provider", None)

    if provider is None:
        load_dotenv()
        master = os.environ.get(ENV_KEY)
        if master:
            return master
        if offer_save and cfg is not None:
            print("No master key provider configured yet — setting one up now.")
            while True:
                new_provider = prompt_provider()
                if new_provider == "op" and not _op_available():
                    print("Error: op CLI not found. Install 1Password CLI (`op`) and retry.")
                    print()
                    continue
                existing, load_err = _try_load_from_provider(new_provider, cfg)
                if existing is not None:
                    master = existing
                    if new_provider == "op":
                        print(f"Loaded from 1Password ({cfg.op_secret_ref})")
                    elif new_provider == "dotenv":
                        print("Loaded from ~/.config/autossh/.env")
                    break
                if load_err is not None:
                    print(f"Error: failed to read from {new_provider}: {load_err}")
                    print("Pick a different provider, or fix the issue and retry.")
                    print()
                    continue
                if new_provider == "op":
                    print(f"No master key item found in 1Password at {cfg.op_secret_ref}.")
                    print("Enter your master key — it will be saved to 1Password for future use.")
                elif new_provider == "dotenv":
                    print(f"ASSH_MASTER_KEY is not set in {DOTENV_FILE}.")
                    print("Enter your master key — it will be saved to the .env file for future use.")
                master = _prompt_master_with_verify(verify_fn)
                if save_master_for_provider(master, new_provider, cfg):
                    break
                print()
            cfg.master_key_provider = new_provider
            cfg.op_secret_ref = f"op://{cfg.op_vault}/autossh/master_key"
            try:
                import autossh.config as _config
                _config.save(cfg)
            except Exception as e:
                print(f"Warning: could not persist provider choice to config.yaml: {e}")
            return master
        return getpass.getpass("Master password: ")

    if provider == "op":
        if not _op_available():
            print("Error: op CLI not found, but master_key_provider=op is configured.")
            print("Install 1Password CLI (`op`), or run `amaster` to switch providers.")
            import sys
            sys.exit(1)
        master, err = op_read(cfg.op_secret_ref)
        if master:
            return master
        if err is not None:
            print(f"Error: failed to read master key from 1Password ({cfg.op_secret_ref}).")
            print(f"  {err}")
            print("Run `op signin` to authenticate, or `amaster` to switch providers.")
            import sys
            sys.exit(1)
        print(f"No master key item found in 1Password at {cfg.op_secret_ref}.")
        print("If this is your first time using autossh on this machine, enter your")
        print("master key — it will be saved to 1Password for future use.")
        print("If you don't remember it, press Ctrl-C and run `amaster` to reset.")
        master = _prompt_master_with_verify(verify_fn)
        ref = op_save(master, cfg.op_vault)
        if ref:
            print(f"Saved to 1Password ({ref})")
        else:
            print("Warning: 1Password save failed; key will be re-prompted next time.")
        return master

    if provider == "dotenv":
        load_dotenv()
        master = os.environ.get(ENV_KEY)
        if master:
            return master
        print(f"ASSH_MASTER_KEY is not set in {DOTENV_FILE}.")
        print("If this is your first time using autossh on this machine, enter your")
        print("master key — it will be saved to the .env file for future use.")
        print("If you don't remember it, press Ctrl-C and run `amaster` to reset.")
        master = _prompt_master_with_verify(verify_fn)
        save_to_dotenv(master)
        print(f"Saved to {DOTENV_FILE}")
        return master

    # provider == "prompt" or unknown
    return _prompt_master_with_verify(verify_fn)
