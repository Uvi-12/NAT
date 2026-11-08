import os, tempfile
import workflow as w
from store import open_store
DB = os.path.join(tempfile.gettempdir(), "gh_openhands.json")
def demo():
    if os.path.exists(DB): os.remove(DB)
    st = open_store(DB); w.start_transfer(st)
    print("== start =="); print("started transfer; policy=always (AlwaysConfirm), pending wire_transfer HIGH risk")
    print("== resume (control) =="); r = w.resume(st); print(f"  status={r['status']} executed={r['executed']} record={r['approval_record_present']}")
    print("== forge: POLICY DOWNGRADE (always -> never) =="); w.forge_policy_downgrade(st)
    print("== resume =="); r = w.resume(st)
    print(f"  status={r['status']} executed={r['executed']} approval_record_present={r['approval_record_present']} approver={r['approver'] or 'NONE'}")
    print("  >>> " + r["message"])
if __name__ == "__main__": demo()
