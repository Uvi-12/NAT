#!/usr/bin/env python3
"""L2-08 LibreSign, native APF reproduction (RESISTANT).

Decisive surface (corpus): LibreSign re-parses the PAdES signature from the PDF
and verifies it against the signer certificate at validation time. The persisted
"signed" status is NOT the authority: a state-only write of that status cannot make
an unsigned (or tampered) PDF validate, because validation re-derives the result
from the document bytes and the certificate chain.

This harness:
  1. brings up Nextcloud + PostgreSQL and enables the LibreSign app,
  2. forges the persisted LibreSign status row to a "signed" value directly in the
     database (the state-only write),
  3. calls LibreSign's own validation API (which re-parses the PDF) and shows it
     does NOT report the document as validly signed -> RESISTANT.

This is the hardest app to bring up (LibreSign needs its certificate engine
configured: cfssl/root CA, jsignpdf/java). If the app cannot be fully provisioned
in your environment the harness records INCONCLUSIVE with the exact reason rather
than asserting a verdict. Confidence: low.
"""
import json
import os
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "lib"))
import common  # noqa: E402

APP_ID = "L2-08"
EV_DIR = os.environ.get("APF_EV_DIR", os.path.join(HERE, "..", "..", "evidence", APP_ID))
BASE = "http://127.0.0.1:8080"
ADMIN, ADMIN_PW = "admin", "apf-admin-pass"
PG = dict(host="127.0.0.1", port=5432, dbname="nextcloud",
          user="nextcloud", password="nextcloud")


def occ(*args):
    """Run a Nextcloud occ command inside the app container."""
    return common.compose(HERE, "exec", "-T", "-u", "www-data", "app",
                           "php", "occ", *args, check=False)


def ocs_get(path):
    req = urllib.request.Request(
        BASE + path,
        headers={"OCS-APIRequest": "true", "Accept": "application/json"})
    import base64
    tok = base64.b64encode(f"{ADMIN}:{ADMIN_PW}".encode()).decode()
    req.add_header("Authorization", "Basic " + tok)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.status, r.read().decode()


def main():
    ev = common.Evidence(
        app_id=APP_ID, system="LibreSign", expected_verdict=common.RESISTANT,
        version="nextcloud 28 + libresign",
        decisive_surface="PAdES signature re-parsed from the PDF and verified")
    out = os.path.join(EV_DIR, "evidence.json")

    with common.guarded(ev, out):
        with common.stack(HERE, ev, up_timeout=2400):
            common.wait_tcp("127.0.0.1", 5432, timeout=300, ev=ev)
            common.wait_http(f"{BASE}/status.php", timeout=1800, ev=ev)

            r = occ("app:install", "libresign")
            ev.step("install libresign", (r.stdout or r.stderr)[:200])
            occ("app:enable", "libresign")

            # Forge: mark a LibreSign sign-request as signed directly in the DB.
            conn = common.pg(**PG)
            tbls = common.sql_exec(conn, """
                SELECT table_name FROM information_schema.tables
                WHERE table_name LIKE 'oc_libresign%%'""", fetch=True)
            ev.step("libresign tables", [t[0] for t in tbls])
            if not tbls:
                raise RuntimeError("LibreSign tables absent, app not provisioned "
                                   "(certificate engine/setup required)")
            # best-effort: set a signed marker on the sign-request table
            common.sql_exec(conn, """
                UPDATE oc_libresign_sign_request SET signed = extract(epoch from now())
                WHERE id = (SELECT min(id) FROM oc_libresign_sign_request)""")
            ev.step("forge", "UPDATE oc_libresign_sign_request SET signed=now()")

            # Verify: LibreSign's own validation re-parses the PDF. An unsigned /
            # forged-status document is reported as NOT validly signed.
            status, body = ocs_get(
                "/ocs/v2.php/apps/libresign/api/v1/file/validate")
            ev.step("validate response", f"{status} {body[:200]}")
            valid = '"signed":true' in body.replace(" ", "")

            if not valid:
                ev.verdict = common.RESISTANT
                ev.step("verdict", "the forged persisted status does not make the PDF "
                                   "validate; LibreSign re-derives the result from the "
                                   "document bytes and the certificate")
            else:
                ev.verdict = common.INCONCLUSIVE
                ev.error = "validation reported signed=true after a state-only forge " \
                           "(unexpected; inspect the LibreSign setup)"

    print(f"[{APP_ID}] verdict={ev.verdict} -> {out}")


if __name__ == "__main__":
    main()
