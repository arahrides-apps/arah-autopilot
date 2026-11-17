"""Explores the public GraphQL API (https://www.arahrides.com/api/graphql): lists what can be asked for, so prices and availability can be wired in.
Public data only: no key is sent. Run it from GitHub Actions ("Explore Arah API"), which has internet access."""
import json, logging, requests
log = logging.getLogger("arahapi")
URL = "https://www.arahrides.com/api/graphql"
INTRO = """query { __schema { queryType { name } types { kind name description fields { name description args { name type { kind name ofType { kind name ofType { kind name ofType { name } } } } } type { kind name ofType { kind name ofType { kind name ofType { name } } } } } inputFields { name type { kind name ofType { kind name ofType { name } } } } enumValues { name } } } }"""

def post(query, variables=None):
    r = requests.post(URL, json={"query": query, "variables": variables or {}}, timeout=60, headers={"content-type": "application/json", "user-agent": "arah-autopilot/1.0"})
    r.raise_for_status()
    return r.json()

def tname(t):
    if not t: return "?"
    if t.get("name"): return t["name"]
    inner = tname(t.get("ofType"))
    return "[%s]" % inner if t["kind"] == "LIST" else inner + ("!" if t["kind"] == "NON_NULL" else "")

def explore(out="data/arah_api_schema.txt"):
    d = post(INTRO)
    if d.get("errors") and not d.get("data"):
        raise RuntimeError("introspection refused: %s" % json.dumps(d["errors"])[:400])
    types = {t["name"]: t for t in d["data"]["__schema"]["types"] if not t["name"].startswith("__")}
    qn = d["data"]["__schema"]["queryType"]["name"]
    lines = ["QUERIES YOU CAN ASK (%s):" % qn]
    for f in types[qn]["fields"] or []:
        args = ", ".join("%s: %s" % (a["name"], tname(a["type"])) for a in f["args"])
        lines.append("  %s(%s) -> %s   %s" % (f["name"], args, tname(f["type"]), (f.get("description") or "")[:80]))
    lines.append("\nOBJECT TYPES (fields):")
    for n, t in sorted(types.items()):
        if t["kind"] == "OBJECT" and n != qn and t.get("fields"):
            lines.append("  %s: %s" % (n, ", ".join("%s:%s" % (f["name"], tname(f["type"])) for f in t["fields"])))
    lines.append("\nINPUT TYPES:")
    for n, t in sorted(types.items()):
        if t["kind"] == "INPUT_OBJECT":
            lines.append("  %s: %s" % (n, ", ".join("%s:%s" % (f["name"], tname(f["type"])) for f in t["inputFields"] or [])))
    from pathlib import Path
    Path(out).parent.mkdir(parents=True, exist_ok=True); Path(out).write_text("\n".join(lines))
    return "\n".join(lines)
