import json, os
class Store:
    def __init__(self, p): self.p = p
    def save(self, s): open(self.p, "w").write(json.dumps(s))
    def load(self): return json.loads(open(self.p).read())
    def exists(self): return os.path.exists(self.p)
def open_store(p): return Store(p)
