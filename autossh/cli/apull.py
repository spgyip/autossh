import sys
import autossh
import autossh.ssh


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--version":
        autossh.print_version_and_exit("apull")
    if len(sys.argv) < 4 or (len(sys.argv) > 1 and sys.argv[1] == "-h"):
        print("")
        print("Usage:")
        print("  apull [-h] destination src dst")
        print("")
        sys.exit(0)

    destination = sys.argv[1]
    src = sys.argv[2]
    dst = sys.argv[3]

    s = autossh.ssh.new(destination)
    ok, err = s.pull_file(src, dst)
    if not ok:
        print(err)
        sys.exit(1)
    s.close()
