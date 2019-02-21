class HostLookup:
    def __init__(self):
        self.__m0 = {} ## host->tupple(host, user, password)
        self.__m1 = {} ## alias->tupple(host, user, password)
    
    ## Input
    ##  - path: File path
    ##
    ## Return
    ##  - n: Number of hosts loaded
    def loadFromFile(self, path):
        f = open(path)
        n = self.load(f)
        f.close()
        return n

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
            user = sp[1]
            password = sp[2]
            alias = None

            ## Alias
            ##   Example: www.example.com[example]
            ##            `host` = www.example.com
            ##            `alias` = example
            pos1 = host.find("[")
            pos2 = host.find("]")
            if pos1>=0 and pos2>=0 and pos2>pos1:
                alias = host[pos1+1:pos2]
                host = host[0:pos1]
            
            self.__m0[host] = (host, user, password)
            if alias is not None:
                self.__m1[alias] = (host, user, password)

        return len(self.__m0)

    ## Input
    ##  - target: Host name or alias name
    ##
    ## Return
    ##  - result bool
    ##  - info tupple (host, user, password)
    def get(self, target):
        if self.__m0.has_key(target):
            return True, self.__m0[target]

        if self.__m1.has_key(target):
            return True, self.__m1[target]

        return False, None

## Testing
TESTSAMPLE = \
'''
## Commet
192.168.0.1  root    password1
192.168.0.2  root    password2          ## Commet
192.168.0.3[dev3]  root    password3    ## Commet
192.168.0.4[dev4]  root    password4
'''

if __name__=="__main__":
    import sys
    import StringIO

    hl = HostLookup()
    n = hl.load(StringIO.StringIO(TESTSAMPLE))
    print n, "hosts loaded success ..."
    print "Get by host =>", hl.get("192.168.0.1")
    print "Get by host =>", hl.get("192.168.0.2")
    print "Get by host =>", hl.get("192.168.0.3")
    print "Get by host =>", hl.get("192.168.0.4")
    print "Get by alias =>", hl.get("dev3")
    print "Get by alias =>", hl.get("dev4")
    print "Get notfound =>", hl.get("notfound")
