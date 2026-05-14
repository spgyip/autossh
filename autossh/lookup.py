
def load(fpath):
    lu = Lookup()
    ok, _ = lu.loadFromFile(fpath)
    if not ok:
        print("WARNING: host file \"%s\" not found. Run `aedit` to create one." % (fpath))
    return lu

class Lookup:
    def __init__(self):
        self.__m0 = {} ## host->tupple(host, port, user, password)
        self.__m1 = {} ## alias->tupple(host, port, user, password)
    
    ## Input
    ##  - path: File path
    ##
    ## Return
    ##  - ok bool: if success
    ##  - n   int: Number of hosts loaded
    def loadFromFile(self, path):
        try:
            f = open(path)
        except IOError as e:
            return False, 0
        n = self.load(f)
        f.close()
        return True, n

    ## Input
    ##  - r: File object
    ##
    ## Return
    ##  - n: Number of hosts loaded
    def load(self, r):
        while True:
            line = r.readline()

            ## EOF
            if line=="":
                break;

            ## Strip commets
            pos = line.find("#")
            if pos>=0:
                line = line[0:pos]

            ## Error line
            sp = line.split()
            if len(sp)!=3:
                continue
            
            ## [0] host
            ## [1] user
            ## [2] password
            host = sp[0]
            port = 0
            user = sp[1]
            password = sp[2]
            alias = None

            ## Parse alias
            ##   Example: www.example.com[example]
            ##            `host` = www.example.com
            ##            `alias` = example
            pos1 = host.find("[")
            pos2 = host.find("]")
            if pos1>=0 and pos2>=0 and pos2>pos1:
                alias = host[pos1+1:pos2]
                host = host[0:pos1]
            
            ## Parse port
            ##   Example: www.example.com:36000
            ##            `host` = www.example.com
            ##            `port` = 36000
            pos = host.find(":")
            if pos>0:
                port = host[pos+1:]
                host = host[0:pos]

            self.__m0[host] = (host, port, user, password)
            if alias is not None:
                self.__m1[alias] = (host, port, user, password)

        return len(self.__m0)

    ## Input
    ##  - destination: Host name or alias name
    ##
    ## Return
    ##  - result bool
    ##  - info tupple (host, port, user, password)
    def get(self, destination):
        if destination in self.__m0:
            return True, self.__m0[destination]

        if destination in self.__m1:
            return True, self.__m1[destination]

        return False, None

## Testing
TESTSAMPLE = \
'''
## Commet
192.168.0.1  root    password1
192.168.0.2  root    password2          ## Commet
192.168.0.3[dev3]  root    password3    ## Commet
192.168.0.4[dev4]  root    password4
192.168.0.5:36000  root    password4
192.168.0.6:9918[dev6]  root    password4
'''

if __name__=="__main__":
    import sys
    from io import StringIO

    lu = Lookup()
    n = lu.load(StringIO(TESTSAMPLE))
    print(n, "hosts loaded success ...")
    print("Get by host =>", lu.get("192.168.0.1"))
    print("Get by host =>", lu.get("192.168.0.2"))
    print("Get by host =>", lu.get("192.168.0.3"))
    print("Get by host =>", lu.get("192.168.0.4"))
    print("Get by host =>", lu.get("192.168.0.5"))
    print("Get by host =>", lu.get("192.168.0.6"))
    print("Get by alias =>", lu.get("dev3"))
    print("Get by alias =>", lu.get("dev4"))
    print("Get by alias =>", lu.get("dev6"))
    print("Get notfound =>", lu.get("notfound"))
