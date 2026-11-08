

## LAUNDER expected verdicts (fixes baked in)

- RESISTANT: Temporal, Restate, AWS Step Functions, Inngest, Gitea, Atlantis
- EXPOSED: Kestra, Flowable, Conductor, Dapr, n8n, BeeAI

IMPORTANT for LAUNDER: Gitea and Atlantis are expected RESISTANT here (a review is bound to its
pull request. A foreign PR cannot merge/apply under another PR's approval). So a merge REFUSAL
(the gitea 405) or an apply that does not fire actually SUPPORTS the RESISTANT verdict - the foreign
PR should fail to merge/apply. Kestra may still be flaky (flow occasionally fails before PAUSED). 
that is non-thesis-critical. Restate uses python3 -m hypercorn (validated). Watch for
"restate service UP :9080".
