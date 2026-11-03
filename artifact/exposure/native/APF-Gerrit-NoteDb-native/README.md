# APF native reproduction, Gerrit NoteDb (git layer)

Native-tier reproduction against real git objects, the NoteDb store Gerrit keeps
review votes in. It builds a real per-change meta ref
(`refs/changes/34/1234/meta`) with git plumbing and consumes the `Label:
Code-Review+2` footer the way Gerrit's submit path does.

- **Dependency:** `git`, `cryptography`. (No Gerrit server, no network.)
- **Run:** `python3 run.py`
- **What it shows:** with default (unsigned) NoteDb, a state-writer with git-ref
  write access authors a +2 meta commit with no key or signature and submit reads
  it, forge succeeds. With a signed-NoteDb policy, the genuine reviewer-signed
  +2 verifies and the keyless state-writer's +2 does not, so submit blocks.
- **Config B note:** a real deployment enforces this with git signed-push
  (GPG/SSH commit signatures). This sandbox blocks `gpg-agent` and `ssh-keygen`,
  so Config B verifies a real Ed25519 signature (via `cryptography`) over the
  canonical git commit object as a faithful stand-in for signed-push. The store
  and commits are real git objects. The conclusion, a keyless state-writer
  cannot forge a verifying signature, is identical.
- **Verdict:** native evidence for the Gerrit row in the two-reach sensitivity
  test (C9). The corpus verdict is **Resistant at the stated reach** (the
  state-writer does not have raw git-ref write to the Gerrit server's NoteDb).
  This run shows the **Reach-2 (engine/server-filesystem) degradation**: given
  NoteDb ref write, a keyless state-writer forges a +2 under default (unsigned)
  NoteDb, while signed NoteDb blocks the keyless forge. So Gerrit is
  engine-store-dependent, and signed-push is the control that makes it resistant
  even under engine reach, exactly the condition recorded on the row.
