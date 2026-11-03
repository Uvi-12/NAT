#!/usr/bin/env python3
"""Resumable orchestrator for the Layer-2 native-promotion kit.

Discovers every app under apps/<id>_<slug>/, runs each app's harness.py in turn,
captures its evidence under evidence/<id>/, and records per-app status in
progress.json so a re-run resumes where it left off.

Usage (normally via run.sh, which sets up the venv first):
    python orchestrate.py                 # run all pending/failed apps
    python orchestrate.py --only L2-15    # run just one app (repeatable)
    python orchestrate.py --resume        # default: skip apps already DONE
    python orchestrate.py --force         # re-run everything, ignore progress
    python orchestrate.py --list          # list discovered apps and status

An app is DONE when its harness wrote an evidence record with a real verdict
(EXPOSED/RESISTANT). INCONCLUSIVE is retried on the next run (it usually means a
container didn't come up); a genuine verdict is never recomputed unless --force.
"""
import argparse
import glob
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
APPS = os.path.join(HERE, "apps")
EV = os.path.join(HERE, "evidence")
PROG = os.path.join(HERE, "progress.json")
sys.path.insert(0, os.path.join(HERE, "lib"))
import common  # noqa: E402


def discover():
    out = []
    for d in sorted(glob.glob(os.path.join(APPS, "L2-*"))):
        if os.path.isfile(os.path.join(d, "harness.py")):
            out.append(d)
    return out


def load_prog():
    if os.path.isfile(PROG):
        with open(PROG) as fh:
            return json.load(fh)
    return {}


def save_prog(p):
    tmp = PROG + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(p, fh, indent=2)
    os.replace(tmp, PROG)


def verdict_of(app_id):
    path = os.path.join(EV, app_id, "evidence.json")
    if os.path.isfile(path):
        with open(path) as fh:
            return json.load(fh).get("verdict", "")
    return ""


def run_one(app_dir, log_dir):
    """Run an app's harness as a subprocess; capture its log. The harness is
    responsible for writing evidence/<id>/evidence.json (via common.guarded)."""
    app_id = os.path.basename(app_dir).split("_")[0]
    os.makedirs(log_dir, exist_ok=True)
    log = os.path.join(log_dir, "run.log")
    env = dict(os.environ, APF_EV_DIR=os.path.join(EV, app_id))
    with open(log, "w") as fh:
        p = subprocess.run([sys.executable, "harness.py"], cwd=app_dir, env=env,
                           stdout=fh, stderr=subprocess.STDOUT, text=True)
    return p.returncode, verdict_of(app_id)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", action="append", default=[], help="run only this app id (repeatable)")
    ap.add_argument("--force", action="store_true", help="re-run even completed apps")
    ap.add_argument("--resume", action="store_true", help="skip apps with a real verdict (default)")
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()

    apps = discover()
    prog = load_prog()

    if args.list:
        for d in apps:
            aid = os.path.basename(d).split("_")[0]
            print(f"  {aid:7} {os.path.basename(d):28} status={prog.get(aid,{}).get('status','pending')} verdict={verdict_of(aid) or '-'}")
        return

    if not common.have_docker():
        print("PREFLIGHT FAIL: Docker (with compose v2) is required and was not found.")
        print("Install Docker Desktop / Engine + the compose plugin, then re-run ./run.sh")
        sys.exit(2)

    todo = []
    for d in apps:
        aid = os.path.basename(d).split("_")[0]
        if args.only and aid not in args.only:
            continue
        v = verdict_of(aid)
        done = v in (common.EXPOSED, common.RESISTANT)
        if done and not args.force:
            print(f"[skip] {aid} already {v}")
            continue
        todo.append(d)

    print(f"[plan] {len(todo)} app(s) to run: {[os.path.basename(d).split('_')[0] for d in todo]}")
    results = {}
    for d in todo:
        aid = os.path.basename(d).split("_")[0]
        print(f"\n==================== {aid}  {os.path.basename(d)} ====================")
        prog[aid] = {"status": "running", "t": time.strftime("%Y-%m-%dT%H:%M:%SZ")}
        save_prog(prog)
        t0 = time.time()
        try:
            rc, v = run_one(d, os.path.join(EV, aid))
        except Exception as e:  # noqa: BLE001
            rc, v = 1, ""
            print(f"  orchestrator error: {e}")
        dt = int(time.time() - t0)
        status = "done" if v in (common.EXPOSED, common.RESISTANT) else "inconclusive"
        prog[aid] = {"status": status, "verdict": v, "seconds": dt,
                     "t": time.strftime("%Y-%m-%dT%H:%M:%SZ")}
        save_prog(prog)
        results[aid] = (status, v, dt)
        print(f"  -> {status} verdict={v or '-'} ({dt}s). evidence/{aid}/evidence.json")

    print("\n==================== SUMMARY ====================")
    done = sum(1 for s, _, _ in results.values() if s == "done")
    print(f"ran {len(results)}  done {done}  inconclusive {len(results)-done}")
    for aid, (s, v, dt) in sorted(results.items()):
        print(f"  {aid:7} {s:12} {v or '-':11} {dt}s")
    print("\nCollect results with:  zip -r l2_native_evidence.zip evidence progress.json")


if __name__ == "__main__":
    main()
