"""Publishes approved posts through the Instagram API (official, free). Instagram has no 'schedule' field for API posts,
so this runs every few minutes from GitHub Actions and posts whatever is approved and due."""
import os, time, json, datetime as dt, logging
import requests
from . import queue as Q
from .config import now as now_fn, tz, media_base

log = logging.getLogger("instagram")

class IGError(Exception):
    pass

class IG:
    def __init__(self, cfg, session=None):
        c = cfg["instagram"]
        self.base = f"{c['api_host']}/{c['api_version']}"
        self.user = os.environ.get(c["user_id_env"], "")
        self.token = os.environ.get(c["token_env"], "")
        self.s = session or requests.Session()
    def _call(self, method, path, **params):
        params["access_token"] = self.token
        r = self.s.request(method, f"{self.base}/{path}", data=params if method == "POST" else None,
                           params=params if method == "GET" else None, timeout=60)
        try:
            j = r.json()
        except Exception:
            raise IGError(f"{r.status_code} {r.text[:200]}")
        if r.status_code >= 400 or "error" in j:
            raise IGError(json.dumps(j.get("error", j))[:300])
        return j
    def container(self, image_url, caption=None, alt=None, carousel_item=False):
        p = {"image_url": image_url}
        if carousel_item:
            p["is_carousel_item"] = "true"
        else:
            p["caption"] = caption
        if alt:
            p["alt_text"] = alt[:1000]
        return self._call("POST", f"{self.user}/media", **p)["id"]
    def post_reel(self, video_url, caption, meta=None):
        cid = self._call("POST", f"{self.user}/media", media_type="REELS", video_url=video_url, caption=caption, share_to_feed="true")["id"]
        self.wait(cid, tries=60, pause=5)
        mid = self.publish(cid)
        return mid, self.permalink(mid)
    def carousel(self, children, caption):
        return self._call("POST", f"{self.user}/media", media_type="CAROUSEL", children=",".join(children), caption=caption)["id"]
    def wait(self, cid, tries=30, pause=4):
        for _ in range(tries):
            st = self._call("GET", cid, fields="status_code").get("status_code")
            if st == "FINISHED":
                return
            if st in ("ERROR", "EXPIRED"):
                raise IGError("container " + st)
            time.sleep(pause)
        raise IGError("container not ready in time")
    def publish(self, cid):
        return self._call("POST", f"{self.user}/media_publish", creation_id=cid)["id"]
    def permalink(self, mid):
        try:
            return self._call("GET", mid, fields="permalink").get("permalink", "")
        except IGError:
            return ""
    def post(self, urls, caption, alt=None, meta=None):
        if getattr(self, "check_live", True):
            wait_live(urls)
        if len(urls) == 1:
            cid = self.container(urls[0], caption, alt)
        else:
            kids = []
            for u in urls:
                k = self.container(u, carousel_item=True); self.wait(k); kids.append(k)
            cid = self.carousel(kids, caption)
        self.wait(cid)
        mid = self.publish(cid)
        return mid, self.permalink(mid)

def wait_live(urls, session=None, tries=24, pause=10):
    """Instagram fetches each picture from its web address. Right after a post is approved the site (GitHub Pages) can still be
    publishing the pictures, and Instagram then says 'Only photo or video can be accepted as media type'. So check every picture
    is really there (HTTP 200 and an image) before handing the post over; if not yet, wait, and in the end let the post retry later."""
    s = session or requests.Session()
    for u in urls:
        for n in range(tries):
            try:
                r = s.get(u, timeout=20, stream=True)
                ok = r.status_code == 200 and r.headers.get("content-type", "").lower().startswith("image/")
                r.close()
            except requests.RequestException:
                ok = False
            if ok:
                break
            if n == tries - 1:
                raise IGError("picture not online yet, will retry: " + u)
            time.sleep(pause)

class WebhookPoster:
    """No Meta developer account needed: hands each due post to a no-code tool (Make.com, n8n, Zapier...) that already
    holds an approved Instagram connection. Set the secret POST_WEBHOOK_URL to switch this on."""
    def __init__(self, cfg, session=None):
        self.url = os.environ.get("POST_WEBHOOK_URL", ""); self.s = session or requests.Session()
    def post(self, urls, caption, alt=None, meta=None):
        if getattr(self, "check_live", True):
            wait_live(urls, self.s)
        body = {"id": (meta or {}).get("id", ""), "slot": (meta or {}).get("slot", ""), "caption": caption, "alt": alt or "",
                "image_count": len(urls), "image_urls": urls,
                "location_name": (meta or {}).get("location", {}).get("name", ""), "location_id": (meta or {}).get("location", {}).get("id", "")}
        for i, u in enumerate(urls, 1):
            body[f"image_url_{i}"] = u
        r = self.s.post(self.url, json=body, timeout=60)
        if r.status_code >= 300:
            raise IGError(f"webhook {r.status_code} {r.text[:150]}")
        return "webhook", ""
    def post_reel(self, video_url, caption, meta=None):
        """Same webhook, with media_type REELS and a video_url. The Make scenario needs a Router: media_type = REELS goes to 'Create a Reel'."""
        if getattr(self, "check_live", True):
            wait_live([video_url], self.s)
        body = {"id": (meta or {}).get("id", ""), "slot": (meta or {}).get("slot", ""), "caption": caption, "media_type": "REELS", "video_url": video_url, "image_count": 0,
                "location_name": (meta or {}).get("location", {}).get("name", ""), "location_id": (meta or {}).get("location", {}).get("id", "")}
        r = self.s.post(self.url, json=body, timeout=60)
        if r.status_code >= 300:
            raise IGError(f"webhook {r.status_code} {r.text[:150]}")
        return "webhook", ""

def get_poster(cfg):
    if os.environ.get("POST_WEBHOOK_URL"):
        return WebhookPoster(cfg)
    ig = IG(cfg)
    return ig if (ig.user and ig.token) else None

def refresh_token(cfg):
    c = cfg["instagram"]
    r = requests.get(f"{c['api_host']}/refresh_access_token", params={"grant_type": "ig_refresh_token", "access_token": os.environ[c["token_env"]]}, timeout=30)
    j = r.json()
    if r.status_code >= 400 or "access_token" not in j:
        raise IGError(json.dumps(j)[:300])
    return j["access_token"], j.get("expires_in")

def due_posts(cfg, now, posts, decisions, pub):
    """Yield (post, caption) for approved, due, unpublished posts inside the grace window, oldest first. Also reports what was skipped."""
    grace = dt.timedelta(hours=cfg["publish_grace_hours"]); out = []; skipped = []
    for p in sorted(posts, key=lambda x: x["slot"]):
        if p["id"] in pub and pub[p["id"]]["status"] in ("published", "skipped", "rejected"):
            continue
        slot = dt.datetime.fromisoformat(p["slot"])
        if slot > now:
            continue
        d = decisions.get(p["id"])
        if now - slot > grace:
            skipped.append((p["id"], "rejected" if d and d["decision"] == "reject" else "skipped", "not approved in time" if not (d and d["decision"] == "approve") else "missed its window"))
            continue
        if not d or d["decision"] != "approve":
            continue
        out.append((p, d.get("caption") or p["caption"]))
    return out, skipped

def publish_due(cfg, ig=None, dry_run=False, max_posts=None, spacing=True):
    now = now_fn(cfg); posts = Q.all_posts(); dec = Q.decisions(); pub = Q.published()
    if not spacing and not dry_run:        # catch-up: posts that failed while Make was down get a fresh start
        for pid in [k for k, v in pub.items() if v.get("status") in ("failed", "retrying")]:
            pub.pop(pid)
    due, skipped = due_posts(cfg, now, posts, dec, pub)
    log_ = []
    for pid, st, why in skipped:
        pub[pid] = {"status": st, "at": now.isoformat(), "note": why}; log_.append(f"{st}: {pid} ({why})")
    cap = min(cfg["posts_per_day"], cfg["max_posts_per_day_hard_cap"])
    today = str(now.date())
    count = sum(1 for v in pub.values() if v["status"] == "published" and v.get("at", "")[:10] == today)
    pubs = [dt.datetime.fromisoformat(v['at']) for v in pub.values() if v['status'] == 'published']
    last = max(pubs) if pubs else None
    gap = dt.timedelta(minutes=cfg.get("min_gap_minutes", 20))
    max_posts = max_posts if max_posts is not None else cfg.get("max_posts_per_run", 1)
    base = media_base(cfg); n = 0
    for p, cap_txt in due:
        if n >= max_posts:
            break
        if count >= cap:
            log_.append(f"daily cap {cap} reached, holding {p['id']}"); break
        if spacing and last and now - last < gap and not dry_run:
            log_.append(f"spacing posts out, holding {p['id']}"); break
        tries = pub.get(p["id"], {}).get("tries", 0)
        if tries >= 3:
            pub[p["id"]] = {"status": "failed", "at": now.isoformat(), "note": pub[p["id"]].get("note", ""), "tries": tries}; continue
        urls = [base + i for i in p["images"]]
        try:
            if dry_run:
                log_.append(f"DRY RUN would post {p['id']} ({len(urls)} image(s))"); n += 1; continue
            if p.get("reel") and cfg.get("reels", {}).get("publish_as_reel", False) and hasattr(ig, "post_reel"):
                mid, link = ig.post_reel(base + p["reel"], cap_txt, meta=p)
            else:
                mid, link = ig.post(urls, cap_txt, p.get("alt"), meta=p)
            pub[p["id"]] = {"status": "published", "at": now.isoformat(), "media_id": mid, "permalink": link}
            log_.append(f"published {p['id']} {link}"); count += 1; n += 1; last = now
        except IGError as e:
            pub[p["id"]] = {"status": "retrying", "at": now.isoformat(), "note": str(e)[:300], "tries": tries + 1}
            log_.append(f"ERROR {p['id']}: {e}")
            break
    if not dry_run:
        Q.save_published(pub)
    return log_
