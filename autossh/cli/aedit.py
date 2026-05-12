import os
import os.path
import sys
import autossh.config


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "-h":
        print("")
        print("Usage:")
        print("  aedit [-h]")
        print("")
        print("")
        sys.exit(0)

    c = autossh.config.load()
    dirs = os.path.dirname(c.host_file)
    if os.access(dirs, os.F_OK) is False:
        os.makedirs(dirs)
    os.execvp("vim", ["vim", c.host_file])
