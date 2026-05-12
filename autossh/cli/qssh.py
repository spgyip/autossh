import os
import sys
import time
import getpass
import yaml
import autossh.ssh

config_file = os.path.expanduser("~/.config/qssh/config.yaml")


class Config:
    def __init__(self):
        self.cache_file = os.path.expanduser("~/.qssh.token")
        self.cache_ttl = 60


def load_config():
    c = Config()
    try:
        f = open(config_file)
        o = yaml.safe_load(f)
        f.close()
    except Exception:
        return c

    try:
        c.cache_file = os.path.expanduser(o["cache"]["file"])
    except Exception:
        None

    try:
        c.cache_ttl = int(o["cache"]["ttl"])
    except Exception:
        None

    return c


class Token:
    def __init__(self, config):
        self.__cache_file = config.cache_file
        self.__cache_ttl = config.cache_ttl

    def __call__(self):
        ok, token = self.__try_cache()
        if ok is False:
            token = getpass.getpass("")
            token = token.strip()
            self.__refresh_cache(token)
        return token

    def __try_cache(self):
        try:
            st = os.lstat(self.__cache_file)
            if time.time() - st.st_mtime > self.__cache_ttl:
                return False, ""

            f = open(self.__cache_file)
            token = f.readline()
            f.close()
            return True, token.strip()
        except Exception:
            return False, ""

    def __refresh_cache(self, token):
        f = open(self.__cache_file, "w")
        f.write(token)
        f.close()


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "-h":
        print("")
        print("Usage:")
        print("  qssh [-h] [destination]")
        print("")
        print("qssh             #ssh to 'mnet'")
        print("qssh destination #ssh to 'destination' from 'mnet'")
        print("")
        sys.exit(1)

    c = load_config()
    tk = Token(c)
    s = autossh.ssh.new("mnet")
    ok, err = s.login(["Token: "], [tk])
    if not ok:
        print(err)
        sys.exit(1)
    if len(sys.argv) > 1:
        ok, err = s.jump(sys.argv[1])
        if not ok:
            print(err)
            sys.exit(1)
    s.autowinsize()
    s.interact()
