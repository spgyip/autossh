
__all__ = ["ssh", "config", "lookup"]

__version__ = "1.5.0"


def print_version_and_exit(prog):
    """Print '<prog> <version>' and exit. Helper for CLI --version handlers."""
    import sys
    print(f"{prog} {__version__}")
    sys.exit(0)
