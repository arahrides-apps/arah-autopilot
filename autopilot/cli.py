import argparse, logging, os, sys, random, datetime as dt, shutil, json
from . import config, queue as Q

def main(argv=None):
    ap = argparse.ArgumentParser(prog="autopilot")
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("generate"); g.add_argument("--days", type=int); g.add_argument("--no-render", action="store_true")
    p = sub.add_parser("publish"); p.add_argument("--dry-run", action="store_true")
    sub.add_parser("refresh-token"); sub.add_parser("prune"); sub.add_parser("status"); sub.add_parser("test-webhook")
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    cfg = config.load()
    if a.cmd == "generate":
        from .generate import run
        made, notes = run(cfg, render=not a.no_render, days=a.days)
        print("generated:", made or "nothing new"); [print("note:", n) for n in notes]
    elif a.cmd == "publish":
        from .instagram import get_poster, publish_due
        ig = None if a.dry_run else get_poster(cfg)
        if not a.dry_run and ig is None:
            print("Manual mode: no posting connection set (IG_USER_ID + IG_ACCESS_TOKEN, or POST_WEBHOOK_URL). Nothing posted."); return 0
        out = publish_due(cfg, ig, a.dry_run); print("\n".join(out) or "nothing due")
    elif a.cmd == "test-webhook":
        import os as _os
        from .instagram import WebhookPoster
        from .config import media_base
        if not _os.environ.get("POST_WEBHOOK_URL"):
            print("POST_WEBHOOK_URL secret is not set."); return 1
        posts = Q.all_posts()
        if not posts:
            print("No drafts yet. Run Draft new posts first."); return 1
        p = posts[0]; base = media_base(cfg)
        urls = [base + i for i in p["images"][:1]]
        WebhookPoster(cfg).post(urls, "TEST ONLY - this is a connection test from Arah Autopilot. Do not publish.", "test", meta={"id": "TEST", "slot": ""})
        print("Test sent to Make with image", urls[0])
    elif a.cmd == "refresh-token":
        from .instagram import refresh_token
        tok, exp = refresh_token(cfg)
        out = os.environ.get("GITHUB_OUTPUT")
        print("::add-mask::" + tok)
        if out:
            open(out, "a").write(f"token={tok}\n")
        print("token refreshed, expires in", exp, "seconds")
    elif a.cmd == "prune":
        now = config.now(cfg); keep = now.date() - dt.timedelta(days=14); n = 0
        for f in (Q.DOCS / "queue").glob("*.json"):
            if dt.date.fromisoformat(f.stem) < keep:
                shutil.rmtree(Q.DOCS / "media" / f.stem, ignore_errors=True); f.unlink(); n += 1
        for f in (Q.DOCS / "decisions").glob("*.json"):
            if f.stem[:10] < str(keep): f.unlink()
        Q.write_index([], now.isoformat()); print("pruned", n, "old days")
    elif a.cmd == "status":
        pub = Q.published(); posts = Q.all_posts(); dec = Q.decisions()
        for p in posts:
            print(p["slot"][:16], p["type"].ljust(9), (pub.get(p["id"], {}).get("status") or dec.get(p["id"], {}).get("decision") or "pending"))
    return 0

if __name__ == "__main__":
    sys.exit(main())
