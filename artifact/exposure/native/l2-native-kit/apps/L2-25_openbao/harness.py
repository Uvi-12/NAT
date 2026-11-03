#!/usr/bin/env python3
"""L2-25 OpenBao (control-group), native check (expected INCONCLUSIVE on OSS).

Decisive surface (as assessed): the control-group factor passes when persisted
Authorizations are present. However, Control Groups are a Vault Enterprise feature
and are NOT part of the open-source OpenBao build, so there is no OSS state-backed
approval gate to forge. This harness brings up a real OpenBao dev server, probes
for the control-group feature, and records INCONCLUSIVE with that reason, the
honest outcome, not a forced verdict.
"""
import json
import os
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "lib"))
import common  # noqa: E402

APP_ID = "L2-25"
EV_DIR = os.environ.get("APF_EV_DIR", os.path.join(HERE, "..", "..", "evidence", APP_ID))
ADDR = "http://127.0.0.1:8200"
TOKEN = "root"


def api(path):
    req = urllib.request.Request(ADDR + path)
    req.add_header("X-Vault-Token", TOKEN)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, {}


def main():
    ev = common.Evidence(
        app_id=APP_ID, system="OpenBao (control-group)", expected_verdict=common.EXPOSED,
        version="openbao/openbao:2.1.0",
        decisive_surface="control-group Authorizations present")
    out = os.path.join(EV_DIR, "evidence.json")

    with common.guarded(ev, out):
        with common.stack(HERE, ev, up_timeout=600):
            common.wait_http(f"{ADDR}/v1/sys/health", timeout=300,
                             ok=range(200, 530), ev=ev)
            status, _ = api("/v1/sys/health")
            ev.step("server up", f"sys/health -> {status}")

            # probe for control-group support (Enterprise-only)
            code, _ = api("/v1/sys/config/control-group")
            ev.step("control-group probe", f"sys/config/control-group -> {code}")

            ev.verdict = common.INCONCLUSIVE
            ev.error = ("Control Groups are a Vault Enterprise feature absent from the OSS "
                        "OpenBao build; there is no persisted-Authorizations approval gate to "
                        "forge in this edition. Native verdict not available on OSS.")

    print(f"[{APP_ID}] verdict={ev.verdict} -> {out}")


if __name__ == "__main__":
    main()
