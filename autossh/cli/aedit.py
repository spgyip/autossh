import os
import os.path
import sys
import autossh.config


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
        print("")
        sys.exit(0)

    c = autossh.config.load()
    dirs = os.path.dirname(c.host_file)
    if os.access(dirs, os.F_OK) is False:
        os.makedirs(dirs)
    if not os.path.exists(c.host_file):
        with open(c.host_file, "w") as f:
            f.write(HOSTS_TEMPLATE)
    os.execvp("vim", ["vim", c.host_file])

