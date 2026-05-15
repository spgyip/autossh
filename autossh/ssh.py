import os
import sys
import pexpect
import yaml
from . import config
from . import lookup
from . import master as _master
from . import winsize

def new(destination):
    s = SSH(destination)
    return s

class SSH:
    def __init__(self, destination):
        self.__destination = destination
        self.__child = None
        self.__wd = None
        self.__c = config.load()
        self.__timeout = self.__c.timeout
        self.__lu = lookup.load(os.path.expanduser(self.__c.host_file))

    def _resolve_password(self, password):
        """Decrypt password using master key."""
        try:
            key = _master.derive_file_key(_master.load_master_key(cfg=self.__c))
            return True, _master.decrypt(key, password)
        except Exception:
            return False, "Wrong master password. Run 'amaster' to set a new one."

    def close(self):
        if self.__child is None:
            return 

        if self.__wd is not None:
            self.__wd.close()
            self.__wd = None

        self.__child.close()
        self.__child = None

    def settimeout(self, s):
        self.__timeout = s

    ## Set auto window size
    def autowinsize(self):
        if self.__wd is None:
            self.__wd = winsize.WatchDog(self.__child)

    ## Input
    ##  - expects array[string], user expects for extention
    ##  - reacts array[string], reacts for user expects
    ## Return
    ##  - result bool
    ##  - errmsg string
    def login(self, expects=None, reacts=None):
        ok = True
        errmsg = ""

        ok, info = self.__lu.get(self.__destination)
        if not ok:
            return False, "Host not found '%s'."%(self.__destination)
        host = info[0]
        port = info[1]
        user = info[2]
        ok, password = self._resolve_password(info[3])
        if not ok:
            return False, password

        # args
        args = []
        if user=="None":
            args = ["%s"%(host)]
        else:
            args = ["%s@%s"%(user, host)]
        if port!=0:
            args += ["-p", port]

        default_expects = ["yes/no", "assword:", "[#\$]", pexpect.TIMEOUT, pexpect.EOF]
        if expects is None:
            expects = default_expects
        else:
            expects = default_expects + expects

        self.__child = pexpect.spawn("ssh", args)
        self.__child.logfile_read = sys.stdout.buffer
        while True:
            n = self.__child.expect(expects, timeout=self.__timeout)
            if n==0:   # yes/no
                self.__child.sendline("yes")
            elif n==1: # assword:
                self.__child.sendline(password)
            elif n==2: # [#\$]
                break
            elif n==3: # TIMEOUT
                ok = False
                errmsg = "TIMEOUT"
                break;
            elif n==4: # EOF
                ok = False
                errmsg = "EOF"
                break;
            else:      # user-defined expects
                re = reacts[n-len(default_expects)]
                val = re 
                if callable(re):
                    val = re()
                self.__child.sendline(val)
        return ok, errmsg
    
    ## Return
    ##  - result bool
    ##  - errmsg string
    def jump(self, destination, expects=None, reacts=None):
        ok = True
        errmsg = ""

        ok, info = self.__lu.get(destination)
        if not ok:
            return False, "Host not found '%s'."%(destination)
        host = info[0]
        port = info[1]
        user = info[2]
        ok, password = self._resolve_password(info[3])
        if not ok:
            return False, password

        # cmdline
        cmdline = ""
        if user=="None":
            cmdline = "ssh %s"%(host)
        else:
            cmdline = "ssh %s@%s"%(user, host)
        if port!=0:
            cmdline += " -p %s"%(port)

        default_expects = ["yes/no", "assword:", "[#\$]", pexpect.TIMEOUT, pexpect.EOF]
        if expects is None:
            expects = default_expects
        else:
            expects = default_expects + expects

        self.__child.sendline(cmdline)
        while True:
            n = self.__child.expect(expects, timeout=self.__timeout)
            if n==0:   # yes/no
                self.__child.sendline("yes")
            elif n==1: # assword:
                self.__child.sendline(password)
            elif n==2: # [#\$]
                break
            elif n==3: # TIMEOUT
                ok = False
                errmsg = "TIMEOUT"
                break;
            elif n==4: # EOF
                ok = False
                errmsg = "EOF"
                break;
            else:      # user-defined expects
                re = reacts[n-len(default_expects)]
                val = re 
                if callable(re):
                    val = re()
                self.__child.sendline(val)

        return ok, errmsg

    ## Function
    ##    Send local file to remote.
    ## Input
    ##  - src string, Local source file
    ##  - dst string, Remote destination
    ## Return
    ##  - result bool
    ##  - errmsg string
    def send_file(self, src, dst):
        ok = True
        errmsg = ""

        ok, info = self.__lu.get(self.__destination)
        if not ok:
            return False, "Host not found '%s'."%(self.__destination)

        host = info[0]
        port = info[1]
        user = info[2]
        ok, password = self._resolve_password(info[3])
        if not ok:
            return False, password

        if port==0:
            self.__child = pexpect.spawn("scp", [src, "%s@%s:%s"%(user, host, dst)])
        else:
            self.__child = pexpect.spawn("scp", ["-P", port, src, "%s@%s:%s"%(user, host, dst)])

        self.__child.logfile_read = sys.stdout.buffer
        while True:
            n = self.__child.expect(["yes/no", "assword:", pexpect.TIMEOUT, pexpect.EOF], timeout=self.__timeout)
            if n==0:   # yes/no
                self.__child.sendline("yes")
            elif n==1: # assword:
                self.__child.sendline(password)
            elif n==2: # TIMEOUT
                ok = False
                errmsg = "TIMEOUT"
            else:      # EOF
                ## TODO:
                ## Can not distinguish error or success with EOF
                ## For example, if scp error causing by network or invalid password,
                ## the child will print error message and EOF.
                break
        return ok, errmsg

    ## Function
    ##    Pull remote file to local.
    ## Input
    ##  - src string, Remote source file
    ##  - dst string, Local destination
    ## Return
    ##  - result bool
    ##  - errmsg string
    def pull_file(self, src, dst):
        ok = True
        errmsg = ""

        ok, info = self.__lu.get(self.__destination)
        if not ok:
            return False, "Host not found '%s'."%(self.__destination)

        host = info[0]
        port = info[1]
        user = info[2]
        ok, password = self._resolve_password(info[3])
        if not ok:
            return False, password

        if port==0:
            self.__child = pexpect.spawn("scp", ["%s@%s:%s"%(user, host, src), dst])
        else:
            self.__child = pexpect.spawn("scp", ["-P", port, "%s@%s:%s"%(user, host, src), dst])
        self.__child.logfile_read = sys.stdout.buffer
        while True:
            n = self.__child.expect(["yes/no", "assword:", pexpect.TIMEOUT, pexpect.EOF], timeout=self.__timeout)
            if n==0:   # yes/no
                self.__child.sendline("yes")
            elif n==1: # assword:
                self.__child.sendline(password)
            elif n==2: # TIMEOUT
                ok = False
                errmsg = "TIMEOUT"
            else:      # EOF
                ## TODO:
                ## Can not distinguish error or success with EOF
                ## For example, if scp error causing by network or invalid password,
                ## the child will print error message and EOF.
                break
        return ok, errmsg

    def exit(self):
        self.__child.sendline("exit")

    def interact(self):
        ## Close logfile_read before interact.
        self.__child.logfile_read = None

        ## The default escape character is `\x1d`(Ctrl+]),
        ## which conflicts with vim.
        ## Set to None to disable escaping from child.
        self.__child.interact(escape_character=None)

