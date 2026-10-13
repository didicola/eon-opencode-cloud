#!/usr/bin/env python3
"""BBH v2 CLOUD runner — identical frozen template/scorer as local v2full.py.
Lane: ghost_ask via eon-mcp HTTP JSON-RPC (auth from env EON_ADM).
Resume: union of bbh-v2/runs/*.jsonl (task,idx). Capacity fallback -> backoff,
never recorded as answer. Batch cap per invocation. Writes records + SUMMARY.json.
"""
import json, re, os, sys, glob, time, threading, datetime, urllib.request
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
RUNS = f"{HERE}/runs"
os.makedirs(RUNS, exist_ok=True)
MCP = "https://eon-mcp.eon-sovereign.workers.dev/mcp"
AUTH = os.environ.get("EON_ADM", "")
BATCH = int(sys.argv[sys.argv.index("--batch") + 1]) if "--batch" in sys.argv else 400

TEMPLATE_ID = "bbh-v1-frozen-20261011"
PROMPT_TMPL = "Q: {q}\nGive ONLY the final answer, no explanation.\nA:"
LANE = "ghost_ask"
WORKERS = 3
CAPACITY_MARKS = ("daily capacity", "queued your question", "local brain will answer")

def ghost_ask(prompt, timeout=150):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                       "params": {"name": LANE, "arguments": {"auth": AUTH, "message": prompt}}}).encode()
    req = urllib.request.Request(MCP, data=body, method="POST", headers={
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "User-Agent": "bbh-v2-cloud/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read().decode("utf-8", "replace")
    m = re.search(r"\{.*\}", raw, re.S)
    if not m:
        return raw[:300], False
    j = json.loads(m.group(0))
    res = j.get("result", {})
    text = ""
    if "content" in res:
        text = "\n".join(c.get("text", "") for c in res.get("content", []))
    elif "error" in j:
        return "RPC-ERROR:" + json.dumps(j["error"])[:200], False
    else:
        text = raw[:400]
    inner = text
    im = re.search(r"\{.*\}", text, re.S)
    if im:
        try:
            ij = json.loads(im.group(0))
            inner = ij.get("answer") or ij.get("response") or text
        except Exception:
            pass
    cap = any(c in inner.lower() for c in CAPACITY_MARKS)
    return inner, cap

def extract_ok(resp, want):
    lines = [l.strip() for l in resp.splitlines() if l.strip()]
    tail = lines[-1] if lines else resp
    w = want.strip().lower()
    cands = {tail.lower(), tail.lower().rstrip(".!")}
    m = re.findall(r"(true|false|\(?[a-e]\)?|\byes\b|\bno\b|\d+)", tail, re.I)
    cands |= {x.lower().strip("().") for x in m}
    return w.strip("().") in {c.strip("().") for c in cands}

work = []
per_task_total = {}
for f in sorted(glob.glob(f"{HERE}/data/*.json")):
    task = os.path.basename(f)
    d = json.load(open(f))
    per_task_total[task] = len(d["examples"])
    for i, ex in enumerate(d["examples"]):
        work.append((task, i, ex["input"].strip(), ex["target"].strip()))

done = set()
for old in sorted(glob.glob(f"{RUNS}/*.jsonl")):
    for line in open(old):
        try:
            r = json.loads(line)
            done.add((r["task"], r["idx"]))
        except Exception:
            pass
todo = [w for w in work if (w[0], w[1]) not in done]
print(f"total={len(work)} done={len(done)} todo={len(todo)} batch_cap={BATCH}", flush=True)
if not todo:
    print("NOTHING TODO", flush=True)
    sys.exit(0)

run_id = f"cloud-{datetime.datetime.now(datetime.UTC):%Y%m%dT%H%M%SZ}"
logp = f"{RUNS}/{run_id}.jsonl"
lock = threading.Lock()
n_written = 0
hits = errs = 0
task_hits = {}; task_n = {}
stop = threading.Event()

def one(item):
    global n_written, hits, errs
    if stop.is_set():
        return
    task, idx, qtext, want = item
    prompt = PROMPT_TMPL.format(q=qtext)
    resp = ""; ok = False; err = None
    for attempt in range(3):
        try:
            resp, cap = ghost_ask(prompt)
            if cap:
                print(f"CAPACITY stall ({task}#{idx}) — backing off 300s", flush=True)
                time.sleep(300)
                continue
            ok = extract_ok(resp, want); err = None
            if resp.startswith("RPC-ERROR"):
                err = resp[:100]
        except Exception as e:
            resp, ok, err = "", False, str(e)[:80]
        if err is None:
            break
        time.sleep(3 + attempt * 4)
    if err and "RPC-ERROR" in (err or ""):
        # hard RPC failure: record as error (same as local v1 rule: err = MISS)
        pass
    rec = {"task": task, "idx": idx, "want": want, "got": (resp or err or "")[:200],
           "ok": bool(ok), "err": err, "ms": 0, "runner": "cloud"}
    with lock:
        if stop.is_set():
            return
        if err: errs += 1
        hits += ok
        n_written += 1
        task_hits[task] = task_hits.get(task, 0) + (1 if ok else 0)
        task_n[task] = task_n.get(task, 0) + 1
        with open(logp, "a") as lg:
            lg.write(json.dumps(rec) + "\n")
        if n_written % 25 == 0:
            print(f"[{n_written}/{BATCH}] hits={hits} errs={errs}", flush=True)
        if n_written >= BATCH:
            stop.set()

with ThreadPoolExecutor(max_workers=WORKERS) as ex:
    list(ex.map(one, todo[:BATCH + 10]))

# ---- SUMMARY (all records across ALL runs) ----
allr = []
for old in sorted(glob.glob(f"{RUNS}/*.jsonl")):
    for line in open(old):
        try:
            allr.append(json.loads(line))
        except Exception:
            pass
th = {}; tn = {}
for r in allr:
    tn[r["task"]] = tn.get(r["task"], 0) + 1
    th[r["task"]] = th.get(r["task"], 0) + (1 if r.get("ok") else 0)
total_ok = sum(th.values()); total_n = len(allr)
summary = {"updated": datetime.datetime.now(datetime.UTC).isoformat(),
           "template_id": TEMPLATE_ID, "lane": LANE,
           "n": total_n, "hits": total_ok,
           "score_pct": round(100 * total_ok / max(total_n, 1), 2),
           "per_task": {t: {"n": tn.get(t, 0), "hits": th.get(t, 0),
                            "pct": round(100 * th.get(t, 0) / max(tn.get(t, 0), 1), 1)}
                        for t in sorted(per_task_total)}}
json.dump(summary, open(f"{RUNS}/SUMMARY.json", "w"), indent=1)
print(f"BATCH DONE wrote={n_written} hits={hits} errs={errs} overall={summary['score_pct']}% n={total_n}/{len(work)}", flush=True)
