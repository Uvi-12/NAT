#!/usr/bin/env python3
"""Default-deployment reachability audit (read-only, nothing is executed).

The claim this supports is deliberately narrow. For each listed system, the
vendor's OWN default or quickstart deployment connects a principal that is NOT the
approval authority to the store that holds the decisive approval field, the exact
field the native reproduction in artifact/exposure/native/ identifies as the one the
runtime trusts. This script re-fetches each vendor default manifest and re-extracts
the shipped credential or grant that reaches that store.

Each row also records writer_scope. For the five database-backed systems the shipped
role is broad and owns every table, including the identity and secret tables, so the
principal is not narrower than the application. Argo is scoped: its update-workflows
grant reaches the resume status but not secrets or the identity store. See
METHODOLOGY.md and the paper's co-located-authority discussion.

Output: reachability.csv. No application is run.
"""
import csv
import os
import re
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "reachability.csv")

# system, decisive approval field, default-reachable non-approval writer, reach class,
# writer_scope (broad owns-all vs scoped), native backing, manifest URL, signal regex.
ROWS = [
 ("OpenEMR", "billing.authorized == 1 (releases the claim/billing path)",
  "phpMyAdmin container or any co-located client, as DB root", "R1+R2",
  "broad: DB root owns every table, including identity and secret tables",
  "config verified by collect.py, runtime trust shown natively (L2-22 EXPOSED)",
  "https://raw.githubusercontent.com/openemr/openemr/master/docker/development-easy/docker-compose.yml",
  r"MYSQL_ROOT_PASSWORD:\s*root"),
 ("ERPNext", "tabPurchase Order.docstatus == 1 (Submitted)",
  "background queue-long/queue-short workers, as DB root", "R1+R2",
  "broad: shared app DB role owns every table, including identity and secret tables",
  "config verified by collect.py, decisive field confirmed in source (L2-13 harness)",
  "https://raw.githubusercontent.com/frappe/frappe_docker/main/pwd.yml",
  r"MYSQL_ROOT_PASSWORD:\s*admin"),
 ("DocuSeal", "submitters.completed_at IS NOT NULL",
  "any co-located container, as the postgres superuser", "R1",
  "broad: postgres superuser owns every table",
  "config verified by collect.py, decisive field confirmed in source (L2-07 harness)",
  "https://raw.githubusercontent.com/docusealco/docuseal/master/docker-compose.yml",
  r"postgres:postgres@postgres"),
 ("Documenso", "Document/Envelope.status == COMPLETED",
  "any co-located holder of the single app DB role", "R2",
  "broad: single app role owns every table, including identity and secret tables",
  "config verified by collect.py, decisive field confirmed in source (L2-06 harness)",
  "https://raw.githubusercontent.com/documenso/documenso/main/docker/production/compose.yml",
  r"NEXT_PRIVATE_DATABASE_URL"),
 ("LedgerSMB", "transactions.approved == true",
  "any co-located container, as the shipped DB role", "R1",
  "broad: shipped superuser owns every table",
  "config verified by collect.py, decisive field confirmed in source (L2-14 harness)",
  "https://raw.githubusercontent.com/ledgersmb/ledgersmb-docker/master/docker-compose.yml",
  r"POSTGRES_PASSWORD:\s*abc"),
 ("Argo Workflows", "Workflow CR .status (suspend-node resume)",
  "any ServiceAccount with `update workflows` (ordinary operation grant)", "R3",
  "scoped: update-workflows grant only, secret access is in separate server and controller roles",
  "config verified by collect.py, decisive field is the suspend-node status (L2-01), state-only",
  "https://raw.githubusercontent.com/argoproj/argo-workflows/v3.5.8/manifests/quick-start-minimal.yaml",
  r"- workflows"),
]


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "apf-reachability-audit"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def main():
    results = []
    for system, field, writer, cls, writer_scope, native, url, signal in ROWS:
        try:
            text = fetch(url)
            m = re.search(signal, text)
            locator = ""
            if m:
                line_no = text[:m.start()].count("\n") + 1
                locator = f"line {line_no}: {text.splitlines()[line_no-1].strip()[:80]}"
            status = "SIGNAL_PRESENT" if m else "SIGNAL_NOT_FOUND"
        except Exception as e:                       # noqa: BLE001
            status, locator = f"FETCH_FAIL: {type(e).__name__}", ""
        results.append(dict(system=system, approval_field=field,
                            non_approval_writer=writer, reach_class=cls,
                            writer_scope=writer_scope, native_backing=native,
                            signal_status=status, default_manifest=url,
                            evidence_locator=locator))
        print(f"  {system:16} {cls:6} {status:16} {locator[:60]}", flush=True)
    with open(OUT, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(results[0].keys()))
        w.writeheader()
        w.writerows(results)
    ok = sum(r["signal_status"] == "SIGNAL_PRESENT" for r in results)
    print(f"\n{ok}/{len(results)} shipped-credential signals present in the vendor "
          f"default. writer_scope records that five own every table and Argo is scoped "
          f"-> {os.path.relpath(OUT, HERE)}")


if __name__ == "__main__":
    main()
