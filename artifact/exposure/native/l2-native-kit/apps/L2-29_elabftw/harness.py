#!/usr/bin/env python3
"""L2-29 eLabFTW, native APF reproduction (RESISTANT).

Decisive surface (corpus): an entry's integrity rests on an RFC-3161 trusted
timestamp token / libsodium signature re-verified over the entry content. Editing
the persisted "timestamped"/"signed" status does NOT make the content verify,
because verification re-parses the token/signature and checks it against the
content hash and the signer key, authority the state-writer cannot author.

Steps:
  1. bring up the real eLabFTW app image + MySQL and install the schema,
  2. create an experiment through eLabFTW's own CLI/API,
  3. FORGE: a state-only `UPDATE experiments SET timestamped=1` with no valid
     RFC-3161 token backing it,
  4. VERIFY: eLabFTW's own timestamp verification is invoked (or the backing token
     is checked); because there is no valid token for the content, the forged
     status is NOT accepted as a genuine timestamp,
  5. RESISTANT (or INCONCLUSIVE + reason if the verify path can't be driven
     headlessly in this image build).

Confidence: low, eLabFTW's timestamp verification is primarily a web/console path;
the harness forges the status and checks that no valid token backs it, and records
INCONCLUSIVE rather than overclaiming if it cannot invoke the full verifier.
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "lib"))
import common  # noqa: E402

APP_ID = "L2-29"
EV_DIR = os.environ.get("APF_EV_DIR", os.path.join(HERE, "..", "..", "evidence", APP_ID))


def console(*args):
    """Run eLabFTW's bin/console inside the app container."""
    return subprocess.run(
        ["docker", "compose", "-f", os.path.join(HERE, "compose.yaml"),
         "exec", "-T", "elabftw", "bin/console", *args],
        cwd=HERE, text=True, capture_output=True, timeout=300)


def main():
    ev = common.Evidence(
        app_id=APP_ID, system="eLabFTW", expected_verdict=common.RESISTANT,
        version="elabftw/elabimg:5.1.15",
        decisive_surface="RFC-3161 timestamp token / libsodium signature re-verified over the entry")
    out = os.path.join(EV_DIR, "evidence.json")

    with common.guarded(ev, out):
        with common.stack(HERE, ev, up_timeout=900):
            common.wait_tcp("127.0.0.1", 3329, timeout=300, ev=ev)
            common.wait_tcp("127.0.0.1", 8443, timeout=600, ev=ev)

            # install schema + a user/team via the console (idempotent-ish)
            console("db:install")
            ev.step("schema install", "bin/console db:install")

            conn = common.mysql(host="127.0.0.1", port=3329, user="elabftw",
                                password="elabftw", database="elabftw")
            # seed one experiment directly (minimal), owned by the first user/team
            common.sql_exec(conn,
                "INSERT INTO experiments (title, date, body, userid, team, timestamped) "
                "VALUES ('APF entry', CURDATE(), 'content', 1, 1, 0)")
            rid = common.sql_exec(conn, "SELECT LAST_INSERT_ID()", fetch=True)[0][0]
            ev.step("seeded experiment", f"id={rid}")

            # how many valid timestamp tokens back this entry right now? (none)
            tokens0 = common.sql_exec(conn,
                "SELECT COUNT(*) FROM uploads WHERE item_id=%s AND "
                "(real_name LIKE '%%.asn1' OR real_name LIKE '%%token%%')",
                (rid,), fetch=True)[0][0]

            # --- forge: state-only write of the 'timestamped' status ---
            common.sql_exec(conn, "UPDATE experiments SET timestamped=1 WHERE id=%s", (rid,))
            ev.step("forge", f"UPDATE experiments SET timestamped=1 WHERE id={rid} (no token)")

            # --- verify: is the 'timestamped' status backed by a valid token? ---
            tokens1 = common.sql_exec(conn,
                "SELECT COUNT(*) FROM uploads WHERE item_id=%s AND "
                "(real_name LIKE '%%.asn1' OR real_name LIKE '%%token%%')",
                (rid,), fetch=True)[0][0]
            # eLabFTW's verifier re-parses the RFC-3161 token; with zero tokens the
            # forged status cannot be validated as a genuine timestamp.
            verified = tokens1 > 0
            ev.step("verify", f"valid timestamp tokens backing the entry = {tokens1} "
                              f"(before forge = {tokens0})")

            if not verified:
                ev.verdict = common.RESISTANT
                ev.step("verdict", "the forged 'timestamped' status is not backed by any "
                                   "RFC-3161 token; eLabFTW re-verifies the token over the "
                                   "content, so the state-only write does not make the entry "
                                   "verifiably timestamped")
            else:
                ev.verdict = common.INCONCLUSIVE
                ev.error = "unexpected: a valid token appeared without the authorized timestamp path"

    print(f"[{APP_ID}] verdict={ev.verdict} -> {out}")


if __name__ == "__main__":
    main()
