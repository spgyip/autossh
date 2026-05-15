
__all__ = ["ssh", "config", "lookup"]

__version__ = "1.5.0"


def _git_info():
    """Return (commit, branch, dirty) from the source repo, or (None, None, False)."""
    import os
    import subprocess
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if not os.path.isdir(os.path.join(repo_root, ".git")):
        return None, None, False
    try:
        commit = subprocess.run(
            ["git", "-C", repo_root, "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=2,
        )
        if commit.returncode != 0:
            return None, None, False
        branch = subprocess.run(
            ["git", "-C", repo_root, "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, timeout=2,
        )
        status = subprocess.run(
            ["git", "-C", repo_root, "status", "--porcelain"],
            capture_output=True, text=True, timeout=2,
        )
        return (commit.stdout.strip(),
                branch.stdout.strip() if branch.returncode == 0 else None,
                bool(status.stdout.strip()))
    except Exception:
        return None, None, False


def print_version_and_exit(prog):
    """Print '<prog> <version> [(<commit>[-dirty] on <branch>)]' and exit."""
    import sys
    commit, branch, dirty = _git_info()
    suffix = ""
    if commit:
        rev = f"{commit}-dirty" if dirty else commit
        if branch and branch != "HEAD":
            suffix = f" ({rev} on {branch})"
        else:
            suffix = f" ({rev})"
    print(f"{prog} {__version__}{suffix}")
    sys.exit(0)
