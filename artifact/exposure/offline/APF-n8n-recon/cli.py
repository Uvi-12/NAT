import os, sys, tempfile
import runtime
from store import open_store
DB = os.path.join(tempfile.gettempdir(), "gh_%s.json" % os.path.basename(os.getcwd()))
APPROVER = "Rahul S. (Senior Compliance Officer) [14:32:01]"
def demo():
    if os.path.exists(DB): os.remove(DB)
    st = open_store(DB)
    print("== start =="); runtime.start_transfer(st)
    print("started transfer amount=$100,000.00 (awaiting approval)")
    print("== resume (control) =="); r = runtime.resume(st)
    print(f"resumed status={r['status']} approved={r['approved']} executed={r['executed']}"); print("  " + r["message"])
    print("== forge =="); runtime.inject_approval(st, APPROVER)
    print(f"forged persisted approval approver={APPROVER!r}")
    print("== resume =="); r = runtime.resume(st)
    print(f"resumed status={r['status']} approved={r['approved']} executed={r['executed']}"); print("  " + r["message"])
if __name__ == "__main__":
    demo()
