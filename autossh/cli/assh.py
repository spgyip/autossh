import sys
import autossh
import autossh.ssh


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--version":
        autossh.print_version_and_exit("assh")
    if len(sys.argv) == 1 or (len(sys.argv) > 1 and sys.argv[1] == "-h"):
        print("")
        print("Usage:")
        print("  assh [-h] destination")
        print("")
        sys.exit(1)

    s = autossh.ssh.new(sys.argv[1])
    ok, err = s.login()
    if not ok:
        print(err)
        sys.exit(1)
    s.autowinsize()
    s.interact()
