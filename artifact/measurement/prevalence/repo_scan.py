#!/usr/bin/env python3
"""Repository-level public-code measurement (read-only; nothing from a clone is executed).

For each exposed framework: collect keyword-search results restricted to code, drop
forks, vendored paths, framework copies and first-party organizations, keep one file
per repository, shuffle with a fixed seed, and for up to SAMPLE repositories confirm the
API is really called, then shallow-clone and scan the whole repository for
  durable  - a persistence mechanism on which the framework resumes
  anywhere - any provenance-verification token anywhere in the repository's code
  near     - such a token in a file that also concerns approval or resume

Named working data stay in PRIVATE (argv[1]); the release file holds only a hash.
"""
import csv, hashlib, json, os, random, re, shutil, subprocess, sys, tempfile, time, urllib.request
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from classify import VERIFY
HOST = "git" + "hub.com"
PRIVATE = sys.argv[1]; SAMPLE = int(sys.argv[2]) if len(sys.argv) > 2 else 50; PAGES = 5; SEED = 20261102
RELEASE = os.path.join(HERE, "data", "repo_scan.csv")
VENDORED = re.compile(r"(^|/)(site-packages|\.?venv[^/]*|env|node_modules|vendor|third_party|external[^/]*|references?|dist|build|__pycache__)(/|$)", re.I)
F = {  # query, proof of real use, durable resume mechanism, framework-copy paths, first-party owners
 "LangGraph": ("Command resume interrupt langgraph language:python", r"Command\(\s*resume\s*=", r"(Sqlite|Postgres|Redis|Mongo\w*|DynamoDB\w*|Cosmos\w*|Couchbase\w*)Saver|langgraph[-_]checkpoint[-_](sqlite|postgres|redis|mongodb)", r"langgraph/(types|pregel|graph)", {"langchain-ai"}),
 "OpenAI Agents SDK": ("needs_approval agents language:python", r"needs_approval\s*=", r"RunState|\.to_state\(|SQLiteSession|SQLAlchemySession|RedisSession", r"src/agents/|/agents/(run|tool)\.py", {"openai"}),
 "CrewAI": ("crewai persist approved language:python", r"from crewai", r"@persist\b|FlowPersistence", r"crewai/flow|src/crewai/", {"crewaiinc"}),
 "Haystack": ("AgentSnapshot haystack language:python", r"from haystack|import haystack", r"AgentSnapshot|load_pipeline_snapshot|snapshot_file_path", r"haystack(_experimental)?/(dataclasses|components|core)", {"deepset-ai"}),
 "AutoGen": ("autogen_agentchat UserProxyAgent save_state language:python", r"autogen_agentchat", r"\.save_state\(|\.load_state\(", r"autogen[-_]agentchat/|autogen_agentchat/", {"microsoft"}),
 "LlamaIndex Workflows": ("InputRequiredEvent HumanResponseEvent language:python", r"HumanResponseEvent|InputRequiredEvent", r"\.to_dict\(|Context\.from_dict|JsonSerializer|WorkflowCheckpointer", r"llama_index/core/workflow|workflows/(events|workflow)\.py|site-packages", {"run-llama"}),
 "Semantic Kernel": ("semantic_kernel KernelProcessStep approved language:python", r"semantic_kernel", r"KernelProcessStepState|save_state|to_process_state_metadata|DaprKernelProcess", r"semantic_kernel/processes", {"microsoft"}),
 "n8n": ('"n8n-nodes-base.wait" language:JSON', r"n8n-nodes-base\.wait", r"n8n-nodes-base\.wait", r"packages/nodes-base", {"n8n-io"}),
}
CODE = {".py",".ts",".tsx",".js",".jsx",".mjs",".go",".rs",".java",".kt",".rb",".cs",".json",".yaml",".yml",".toml"}
TOK = [re.compile(p, re.I) for p in VERIFY]; APP = re.compile(r"approv|interrupt|resume|human_input|human_in_the_loop|hitl|confirm", re.I)
sh = lambda *a, **k: subprocess.run(a, capture_output=True, text=True, **k)

def search(q):
    out = []
    for page in range(1, PAGES+1):
        for attempt in range(6):
            p = sh("gh","api","-X","GET","search/code","-f",f"q={q}","-f","per_page=100","-f",f"page={page}")
            time.sleep(7)
            if p.returncode == 0: break
            time.sleep(25*(attempt+1))
        else: break
        d = json.loads(p.stdout); items = d.get("items", [])
        if page == 1: total = d.get("total_count", 0)
        out += [(i["repository"]["full_name"], i["path"], i["repository"]["fork"], i["repository"].get("default_branch")) for i in items]
        if len(items) < 100: break
    return total, out

def raw(repo, path):
    for b in ("HEAD",):
        try:
            with urllib.request.urlopen(f"https://raw.githubusercontent.com/{repo}/{b}/{urllib.parse.quote(path)}", timeout=20) as r: return r.read(2_000_000).decode("utf-8","replace")
        except Exception: return None

def stars(repo):
    p = sh("gh","api","-X","GET","search/repositories","-f",f"q=repo:{repo}","--jq",".items[0].stargazers_count"); time.sleep(2.2)
    return int(p.stdout) if p.stdout.strip().isdigit() else None

def scan(repo, durable_re):
    d = tempfile.mkdtemp(dir=os.environ.get("SCAN_TMP"))
    try:
        c = sh("git","-c","core.symlinks=false","-c","protocol.file.allow=never","clone","--quiet","--depth","1","--single-branch","--no-tags","--filter=blob:limit=512k","--no-recurse-submodules","https://" + HOST + f"/{repo}.git",d+"/r",timeout=150,env={**os.environ,"GIT_TERMINAL_PROMPT":"0","GIT_LFS_SKIP_SMUDGE":"1"})
        if c.returncode: return None
        dur = anyv = near = False; files = 0
        for root, ds, fs in os.walk(d+"/r"):
            ds[:] = [x for x in ds if x != ".git" and not VENDORED.search(x+"/")]
            for f in fs:
                if os.path.splitext(f)[1].lower() not in CODE or "lock" in f.lower(): continue
                fp = os.path.join(root, f)
                if os.path.islink(fp) or os.path.getsize(fp) > 512_000: continue
                try: t = open(fp, encoding="utf-8", errors="replace").read()
                except OSError: continue
                files += 1
                if not dur and durable_re.search(t): dur = True
                if any(x.search(t) for x in TOK):
                    anyv = True
                    if APP.search(t): near = True
        return dict(files=files, durable=dur, verifier_anywhere=anyv, verifier_near_approval=near)
    except subprocess.TimeoutExpired: return None
    finally: shutil.rmtree(d, ignore_errors=True)

import urllib.parse
os.makedirs(PRIVATE, exist_ok=True); done_p = os.path.join(PRIVATE,"scanned.jsonl"); done = {}
if os.path.exists(done_p):
    for l in open(done_p): r = json.loads(l); done[(r["framework"], r["repo"])] = r
frame = {}; fp_frame = os.path.join(PRIVATE,"frame.json")
if os.path.exists(fp_frame): frame = json.load(open(fp_frame))
for fw, (q, use, dur, copy, owners) in F.items():
    if fw not in frame:
        total, items = search(q)
        seen = {}; 
        for repo, path, fork, br in items:
            if fork or VENDORED.search(path) or re.search(copy, path) or repo.split("/")[0].lower() in owners: continue
            seen.setdefault(repo, path)
        frame[fw] = dict(query=q, total=total, returned=len(items), eligible=sorted(seen.items()))
        json.dump(frame, open(fp_frame,"w")); print(fw,"total",total,"returned",len(items),"eligible repos",len(seen),flush=True)
for fw, (q, use, dur, copy, owners) in F.items():
    el = list(frame[fw]["eligible"]); random.Random(SEED).shuffle(el); got = sum(1 for k in done if k[0]==fw and done[k]["status"]=="ok"); ure = re.compile(use); dre = re.compile(dur)
    for repo, path in el:
        if got >= SAMPLE: break
        if (fw, repo) in done: continue
        t = raw(repo, path); rec = dict(framework=fw, repo=repo, path=path)
        if t is None: rec["status"] = "fetch_fail"
        elif not ure.search(t): rec["status"] = "api_not_used"
        else:
            s = scan(repo, dre)
            if s is None: rec["status"] = "clone_fail"
            else: rec.update(s, status="ok", stars=stars(repo)); got += 1
        open(done_p,"a").write(json.dumps(rec)+"\n"); done[(fw,repo)] = rec
    print(fw,"scanned",got,flush=True)
with open(RELEASE,"w",newline="") as fh:
    w = csv.writer(fh); w.writerow(["repo_id","framework","status","stars_bucket","files","durable","verifier_anywhere","verifier_near_approval"])
    for r in done.values():
        st = r.get("stars"); b = "" if st is None else ("100+" if st>=100 else "10-99" if st>=10 else "0-9")
        w.writerow([hashlib.sha256(r["repo"].encode()).hexdigest()[:16], r["framework"], r["status"], b, r.get("files",""), r.get("durable",""), r.get("verifier_anywhere",""), r.get("verifier_near_approval","")])
json.dump({k:{"query":v["query"],"total":v["total"],"returned":v["returned"],"eligible":len(v["eligible"])} for k,v in frame.items()}, open(os.path.join(HERE,"data","repo_scan_frame.json"),"w"), indent=1)
print("DONE", flush=True)
