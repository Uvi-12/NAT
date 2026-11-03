#!/usr/bin/env python3
"""APF native reproduction against real git NoteDb objects (Gerrit's approval
store), git layer, no Gerrit server required.

Gerrit stores review votes in NoteDb: a per-change meta ref
(refs/changes/NN/NNNN/meta) whose commit footers carry labels like
`Label: Code-Review+2`, attributed to a reviewer identity. Gerrit's submit path
reads the current label values from that ref. We build the ref as REAL git
objects with git plumbing and consume it the way submit does.

Threat model: the state-writer can write the git ref store but holds no key and
cannot produce a signature.

Two configurations:
  A. default NoteDb (unsigned commits).  The state-writer authors a meta commit
     carrying Code-Review+2 with an arbitrary author line and no signature, and
     points the meta ref at it. Submit reads +2.  -> FORGE SUCCEEDS (Conditional)
  B. signed-NoteDb policy. Submit additionally requires a valid signature over
     the meta commit from an authorized reviewer key. The genuine +2 is signed
     by the reviewer's private key and verifies; the state-writer, lacking that
     key, cannot produce a signature that verifies against the authorized public
     key.  -> BLOCKED (Resistant)

Note on Config B: a real deployment enforces this with git signed-push (GPG/SSH
commit signatures). This sandbox blocks gpg-agent and ssh-keygen, so we verify a
real Ed25519 signature (via `cryptography`) computed over the canonical git
commit object instead. The store and commits are real git objects; the signature
mechanism stands in for signed-push, and the conclusion -- a keyless state-writer
cannot forge a verifying signature -- is identical.

Honest verdict: native evidence for the C9 two-reach sensitivity test. The corpus
verdict is Resistant at the stated reach (the state-writer has no raw NoteDb-ref
write). Under engine/server-filesystem reach (Reach 2), a git-ref writer forges a
+2 under default unsigned NoteDb, and only commit signing blocks it -- exactly the
deployment condition recorded on the row.

Requires: git, cryptography.    Run: python3 run.py
"""
import os, re, shutil, subprocess, sys, tempfile
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey, Ed25519PublicKey)
from cryptography.exceptions import InvalidSignature

META_REF = "refs/changes/34/1234/meta"

def sh(args, cwd, env, inp=None, check=True):
    p = subprocess.run(args, cwd=cwd, env=env, text=True, input=inp,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if check and p.returncode != 0:
        raise RuntimeError(f"{' '.join(args)}\n{p.stdout}")
    return p.stdout.strip()

def mk_meta_commit(repo, env, author):
    """Author a real NoteDb-style meta commit as git objects; return its sha."""
    tree = sh(["git", "hash-object", "-t", "tree", "-w", "--stdin"], repo, env, inp="")
    msg = (f"Update patch set 1\n\nPatch-set: 1\nReviewer: {author}\n"
           f"Label: Code-Review+2\n")
    return sh(["git", "commit-tree", tree, "-m", msg], repo, env)

def raw_commit(repo, env, sha):
    return sh(["git", "cat-file", "commit", sha], repo, env)

def submit_reads_label(repo, env):
    body = raw_commit(repo, env, META_REF)
    m = re.search(r"^Label:\s*Code-Review([+-]\d)", body, re.M)
    return int(m.group(1)) if m else 0

def main():
    work = tempfile.mkdtemp(prefix="apf_gerrit_")
    repo = os.path.join(work, "repo"); os.makedirs(repo)
    env = dict(os.environ, GIT_AUTHOR_NAME="x", GIT_AUTHOR_EMAIL="x@example.com",
               GIT_COMMITTER_NAME="x", GIT_COMMITTER_EMAIL="x@example.com",
               GIT_CONFIG_GLOBAL="/dev/null", GIT_CONFIG_SYSTEM="/dev/null")
    sh(["git", "init", "-q"], repo, env)

    # authorized reviewer key pair; private half exists only server-side
    reviewer_sk = Ed25519PrivateKey.generate()
    reviewer_pk = reviewer_sk.public_key()

    ok = True
    print("Gerrit NoteDb native reproduction (real git objects)\n")

    # ---- Config A: default NoteDb, unsigned. State-writer forges +2. ----
    sha = mk_meta_commit(repo, env, "attacker <x@example.com>")
    sh(["git", "update-ref", META_REF, sha], repo, env)
    vote = submit_reads_label(repo, env)
    a_forged = (vote == 2)
    print(f"  A default (unsigned NoteDb): submit reads Code-Review{vote:+d} from a"
          f" state-written meta commit\n"
          f"      -> {'FORGE SUCCEEDS (Conditional)' if a_forged else 'blocked'}")
    ok &= a_forged

    # ---- Config B: signed-NoteDb policy. ----
    def signed_submit_ok(sha, sig):
        """Policy: read the label only if a signature over the commit object
        verifies against the authorized reviewer public key."""
        body = raw_commit(repo, env, sha).encode()
        try:
            reviewer_pk.verify(sig, body)
        except InvalidSignature:
            return False
        return bool(re.search(rb"^Label:\s*Code-Review\+2", body, re.M))

    # genuine: reviewer signs their own +2 meta commit
    gsha = mk_meta_commit(repo, env, "reviewer <reviewer@example.com>")
    sh(["git", "update-ref", META_REF, gsha], repo, env)
    gsig = reviewer_sk.sign(raw_commit(repo, env, gsha).encode())
    genuine_ok = signed_submit_ok(gsha, gsig)

    # state-writer (no key) re-forges an unsigned +2 and tries a self-made sig
    fsha = mk_meta_commit(repo, env, "attacker <x@example.com>")
    sh(["git", "update-ref", META_REF, fsha], repo, env)
    attacker_sk = Ed25519PrivateKey.generate()          # attacker's own key
    attacker_sig = attacker_sk.sign(raw_commit(repo, env, fsha).encode())
    forged_ok = signed_submit_ok(fsha, attacker_sig)    # must fail: wrong key

    b_blocked = genuine_ok and not forged_ok
    print(f"  B signed-NoteDb policy:      genuine signed +2 verifies={genuine_ok};"
          f" attacker's self-signed +2 verifies={forged_ok}\n"
          f"      -> {'BLOCKED (Resistant under signing)' if b_blocked else 'NOT ENFORCED'}")
    ok &= b_blocked

    shutil.rmtree(work, ignore_errors=True)
    print("\nFinding: a git-ref writer forges a Code-Review+2 meta commit with no")
    print("key or signature (A); enforcing a reviewer-key signature blocks it (B),")
    print("because the state-writer cannot sign as the authorized reviewer.")
    print("Native evidence for C9: corpus verdict is Resistant at the stated reach")
    print("(no raw NoteDb-ref write); under engine/server reach it is forgeable by")
    print("default (unsigned) and resistant only where commit signing is enforced.")
    print("\nRESULT:", "PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)

if __name__ == "__main__":
    main()
