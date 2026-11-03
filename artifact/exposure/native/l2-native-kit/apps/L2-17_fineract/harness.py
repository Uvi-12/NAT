#!/usr/bin/env python3
"""L2-17 Apache Fineract, native APF reproduction (EXPOSED).

Decisive surface: a loan's disbursement is gated by its status; money release is
permitted once the loan is APPROVED. In Fineract the persisted status lives in
`m_loan.loan_status_id` (100 = submitted & pending approval, 200 = approved). The
authorized path is the Approve command (which enforces the approve permission and
records the approving user). The APF forge is a state-only write of
`loan_status_id = 200`.

Steps: bring up Fineract + MariaDB; seed a client, a loan product, and a loan
application via the REST API, leaving it pending (CONTROL, status 100); UPDATE
m_loan.loan_status_id to 200 directly in MariaDB (FORGE); re-read the loan through
the REST API and confirm Fineract now reports it Approved (VERIFY).
"""
import json
import os
import ssl
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "lib"))
import common  # noqa: E402

APP_ID = "L2-17"
EV_DIR = os.environ.get("APF_EV_DIR", os.path.join(HERE, "..", "..", "evidence", APP_ID))
BASE = "https://127.0.0.1:8443/fineract-provider/api/v1"
TENANT = "default"
AUTH = "Basic bWlmb3M6cGFzc3dvcmQ="  # mifos:password
MYSQL = dict(host="127.0.0.1", port=3306, user="root", password="mysql")
CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE


def api(method, path, body=None):
    url = BASE + path
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", AUTH)
    req.add_header("Fineract-Platform-TenantId", TENANT)
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=40, context=CTX) as r:
        return r.status, json.loads(r.read() or b"{}")


def main():
    ev = common.Evidence(
        app_id=APP_ID, system="Apache Fineract", expected_verdict=common.EXPOSED,
        version="apache/fineract:1.9.0",
        decisive_surface="m_loan.loan_status_id == 200 (APPROVED)")
    out = os.path.join(EV_DIR, "evidence.json")

    with common.guarded(ev, out):
        with common.stack(HERE, ev, up_timeout=2400):
            common.wait_tcp("127.0.0.1", 3306, timeout=600, ev=ev)
            common.wait_http(f"{BASE}/offices?limit=1", timeout=2000,
                             ok=range(200, 500), ev=ev)

            # seed office/client/loan product/loan application
            _, client = api("POST", "/clients",
                            {"officeId": 1, "firstname": "APF", "lastname": "Client",
                             "legalFormId": 1, "active": True,
                             "activationDate": "01 January 2027", "dateFormat": "dd MMMM yyyy",
                             "locale": "en"})
            cid = client.get("clientId") or client.get("resourceId")
            _, prod = api("POST", "/loanproducts",
                          {"name": "APF Loan", "shortName": "APFL", "currencyCode": "USD",
                           "digitsAfterDecimal": 2, "principal": 1000, "numberOfRepayments": 6,
                           "repaymentEvery": 1, "repaymentFrequencyType": 2,
                           "interestRatePerPeriod": 1, "interestRateFrequencyType": 2,
                           "amortizationType": 1, "interestType": 0,
                           "interestCalculationPeriodType": 1, "transactionProcessingStrategyCode": "mifos-standard-strategy",
                           "accountingRule": 1, "locale": "en"})
            pid = prod.get("resourceId")
            if not cid or not pid:
                ev.verdict = common.INCONCLUSIVE
                ev.error = f"could not seed client/product: client={client} product={prod}"
                return
            _, loan = api("POST", "/loans",
                          {"clientId": cid, "productId": pid, "principal": 1000,
                           "loanType": "individual", "numberOfRepayments": 6,
                           "repaymentEvery": 1, "repaymentFrequencyType": 2,
                           "interestRatePerPeriod": 1, "amortizationType": 1,
                           "interestType": 0, "interestCalculationPeriodType": 1,
                           "transactionProcessingStrategyCode": "mifos-standard-strategy",
                           "expectedDisbursementDate": "02 January 2027",
                           "submittedOnDate": "01 January 2027",
                           "loanTermFrequency": 6, "loanTermFrequencyType": 2,
                           "dateFormat": "dd MMMM yyyy", "locale": "en"})
            lid = loan.get("loanId") or loan.get("resourceId")
            if not lid:
                ev.verdict = common.INCONCLUSIVE
                ev.error = f"could not seed loan: {loan}"
                return
            ev.step("seeded loan", f"loan_id={lid}")

            _, r0 = api("GET", f"/loans/{lid}")
            s0 = (r0.get("status") or {}).get("id")
            ev.step("control status", s0)
            if s0 == 200:
                raise RuntimeError("control precondition failed: loan already approved")

            conn = common.mysql(database="fineract_default", **MYSQL)
            common.sql_exec(conn, "UPDATE m_loan SET loan_status_id=200 WHERE id=%s", (lid,))
            ev.step("forge", f"UPDATE m_loan SET loan_status_id=200 WHERE id={lid}")

            _, r1 = api("GET", f"/loans/{lid}")
            s1 = (r1.get("status") or {}).get("id")
            ev.step("verify status", s1)

            if s0 != 200 and s1 == 200:
                ev.verdict = common.EXPOSED
                ev.step("verdict", "state-only loan_status_id write made Fineract report the "
                                   "loan Approved (disbursement gate open) without the Approve command")
            else:
                ev.verdict = common.INCONCLUSIVE
                ev.error = f"unexpected status control={s0} after_forge={s1}"

    print(f"[{APP_ID}] verdict={ev.verdict} -> {out}")


if __name__ == "__main__":
    main()
