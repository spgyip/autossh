import os
import sys
import autossh.config
import autossh.lookup


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "-h":
        print("")
        print("Usage:")
        print("  acat [-h] [destination]")
        print("")
        print("acat              #Cat all")
        print("acat destination  #Cat destionation")
        print("")
        sys.exit(0)

    destination = ""
    if len(sys.argv) >= 2:
        destination = sys.argv[1]

    c = autossh.config.load()
    lu = autossh.lookup.load(os.path.expanduser(c.host_file))

    if len(destination) > 0:
        ok, info = lu.get(destination)
        if not ok:
            print("Host not found '%s'." % (destination))
        else:
            print(info)
    else:
        content = ""
        try:
            f = open(os.path.expanduser(c.host_file))
            content = f.read()
            f.close()
        except IOError:
            content = "None"
        print(content)
