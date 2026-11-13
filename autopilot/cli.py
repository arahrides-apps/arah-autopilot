import argparse, logging, os, sys, random, datetime as dt, shutil, json
from . import config, queue as Q

def main(argv=None):
    ap = argparse.ArgumentParser(prog="autopilot")
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("generate"); g.add_argument("--days", type=int); g.add_argument("--no-render", action="store_true")
    r = sub.add_parser("regenerate"); r.add_argument("--from", dest="start"); r.add_argument("--no-render", action="store_true"); r.add_argument("--wipe", action="store_true", help="throw away every post not yet published, approved ones too, and start fresh")
    p = sub.add_parser("publish"); p.add_argument("--dry-run", action="store_true"); p.add_argument("--catch-up", action="store_true", help="post every approved due post now, ignoring the 20-minute spacing")
    sub.add_parser("recaption"); rs = sub.add_parser("resend"); rs.add_argument("--since", required=True, help="e.g. 2026-11-01T08:00 (Jamaica time)"); sub.add_parser("refresh-token"); sub.add_parser("prune"); sub.add_parser("index-photos"); sub.add_parser("status"); sub.add_parser("test-webhook")
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    cfg = config.load()
    if a.cmd == "generate":
        from .generate import run
        made, notes = run(cfg, render=not a.no_render, days=a.days)
        print("generated:", made or "nothing new"); [print("note:", n) for n in notes]
    elif a.cmd == "regenerate":
        from .regen import run as regen
        made, kept, dropped, notes = regen(cfg, a.start, render=not a.no_render, wipe=a.wipe)
        print(f"kept {kept} approved/published posts, redid {dropped}, new drafts:", made or "none"); [print("note:", n) for n in notes]
    elif a.cmd == "publish":
        from .instagram import get_poster, publish_due
        ig = None if a.dry_run else get_poster(cfg)
        if not a.dry_run and ig is None:
            print("Manual mode: no posting connection set (IG_USER_ID + IG_ACCESS_TOKEN, or POST_WEBHOOK_URL). Nothing posted."); return 0
        out = publish_due(cfg, ig, a.dry_run, max_posts=5 if a.catch_up else None, spacing=not a.catch_up); print("\n".join(out) or "nothing due")
    elif a.cmd == "resend":
        since = dt.datetime.fromisoformat(a.since).replace(tzinfo=config.now(cfg).tzinfo)
        pub = Q.published(); posts = {p["id"]: p for p in Q.all_posts()}; n = 0
        for pid, v in list(pub.items()):
            if v.get("status") == "published" and v.get("media_id") == "webhook" and pid in posts and dt.datetime.fromisoformat(posts[pid]["slot"]) >= since:
                pub.pop(pid); n += 1
        Q.save_published(pub); print(f"{n} post(s) marked as not sent, ready to be sent again")
    elif a.cmd == "index-photos":
        from .indexer import run as idx
        n, done = idx(cfg)
        import collections
        c = collections.Counter(m.get("place") or m.get("kind", "?") for m in done.values())
        print("indexed %d new photo(s). By place:" % n, dict(c.most_common(25)))
    elif a.cmd == "recaption":
        from .recaption import run as recap
        n = recap(cfg); print(f"rewrote the caption of {n} post(s): new hashtags, search line and location")
    elif a.cmd == "test-webhook":
        import os as _os
        from .instagram import WebhookPoster
        from .config import media_base
        if not _os.environ.get("POST_WEBHOOK_URL"):
            print("POST_WEBHOOK_URL secret is not set."); return 1
        posts = Q.all_posts()
        if not posts:
            print("No drafts yet. Run Draft new posts first."); return 1
        p = max(posts, key=lambda x: len(x["images"])); base = media_base(cfg)   # a carousel, so Make learns image_url_1 to image_url_6
        urls = [base + i for i in p["images"][:6]]
        while len(urls) < 6:               # pad to 6 so Make learns every carousel field (test message only)
            urls.append(urls[len(urls) % len(p["images"])])
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
