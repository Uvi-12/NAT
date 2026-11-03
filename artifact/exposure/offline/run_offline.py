#!/usr/bin/env python3
"""Run every offline (contract-level, N2) exposure harness and check the
observable behaviour: with no approval the gate blocks; after a state-only forge
of the persisted approval the gated action executes. These harnesses reconstruct
the documented resume/consume path of each framework against a local store; they
use only the Python standard library (no framework install, no network).
"""
import glob
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    clis = sorted(glob.glob(os.path.join(HERE, "*", "cli.py")))
    if not clis:
        print("no offline harnesses found"); sys.exit(1)
    ok = True
    for cli in clis:
        name = os.path.basename(os.path.dirname(cli))
        p = subprocess.run([sys.executable, "cli.py", "demo"], cwd=os.path.dirname(cli),
                           text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        out = p.stdout
        blocked = ("REJECTED" in out) or ("BLOCKED" in out)
        executed = "EXECUTED" in out
        good = (p.returncode == 0 and blocked and executed)
        ok &= good
        print(f"  {name:34} control={'blocked' if blocked else '??':8} "
              f"forge={'executed' if executed else '??':9} {'OK' if good else 'FAIL'}")
    print(f"\n{len(clis)} harnesses")
    print("RESULT:", "PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
