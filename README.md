# Arah Rides Instagram Autopilot

Makes regular feed posts (single images and swipe carousels), puts them in a review page, and posts the ones you approve to @arahrides at the time slot. Free: GitHub, Instagram's official API, Pexels and Openverse (free photos), Google Drive (your own photos) and open-source tools (Python, Pillow, Playwright/Chromium, OpenCV).

## What happens each day
1. **6:00 pm Jamaica time**: the bot drafts the next 3 days, 15 posts per day (6:30 am to 8:30 pm, hourly). Each post gets a fresh photo (or a typographic design), a caption and 5 hashtags at most.
2. **You open the review page** (`https://YOURNAME.github.io/REPO/`), look through the day, edit any caption, tap **Approve** (or **Approve all**, or **Reject**). That is your only job.
3. **Every 10 minutes** the publisher posts anything that is approved and due. One post per run, at least 20 minutes apart, never more than 15 a day.
4. Anything you did not approve is **never posted**. If a post is approved late, it still goes out as long as it is within 4 hours of its slot; after that it is skipped.

## The no-reuse rule for photos
`data/ledger.json` records every photo used (its Drive/Pexels id, file name and a fingerprint of the picture). A photo is blocked for 90 days, a near-identical burst shot for 30 days. It already contains every photo used in your October posts. Photos with people in them are skipped (OpenCV face check for new ones, and your catalogue notes for the Drive photos I reviewed).

## Folders
| Path | What it is |
|---|---|
| `config.yaml` | times, 15/day, hashtags, photo rules, offers (off until you fill them in) |
| `content/bank.yaml` | all wording: hero lines, place posts, Q&A, tips, lists, chats, carousels |
| `content/moments.yaml` | holidays and dated posts (Heroes Day, Christmas, Black Friday once you add an offer) |
| `content/photo_meta.yaml` | notes on the Drive photos I reviewed (car or scenery, people, quality) |
| `docs/` | the review page, queue, images and decisions (served by GitHub Pages) |
| `autopilot/` | the code |
| `.github/workflows/` | the three schedules: draft, post, renew token |
| `tests/` | offline test: `python tests/test_end_to_end.py` |

## No Meta developer account?
Use Make.com (free webhook, SETUP.md Path A): the bot sends each approved post to Make and Make publishes it. Or

Manual mode: skip the Instagram secrets. Each card on the review page has Copy caption and Download image buttons, so you can schedule in the Instagram app or Meta Business Suite yourself. See SETUP.md step 2C.

## Things to know
- **Limits**: Instagram's API cannot post reels with this setup, cannot post stories reliably, and has no "schedule" field, which is why the bot waits and posts at the slot time itself.
- **Wording runs out**: the bank has about 140 entries. When a list is being recycled, the review page shows a yellow note. Ask Claude to add more, or copy a line in `content/bank.yaml` and edit it.
- **Web photos**: Pexels and Openverse results are only as accurate as their descriptions. The bot adds a place name to a post only when the photo's own description names that place. Otherwise it uses a neutral line and flags it. Check each web photo for people, brands and that it really looks like Jamaica.
- **Your own car photos run out**: the catalogue has about 19 clean, unused car photos, so the daily car post uses them for roughly 3 weeks. After that the slot becomes a text design until you add more photos to the Drive folder. Web scenery photos are plentiful, so place posts keep going.
- **Your own new photos**: drop them in the Drive folder. The bot finds them (tagged "not looked at" on the review card so you check them). Car photos only; number plates are never blurred.
- **Offers**: nothing about the 7+ day lounge pass, Black Friday or Smile Jamaica is posted until you enable it and type the text in `config.yaml`.
- **Public repo**: GitHub Pages and Instagram image fetching need the repo to be public. Drafts are visible there until posted. Never put customer photos or private details in it.
- **Token**: the Instagram token lasts 60 days and is renewed every Monday automatically.

## Run it on your own computer
```
pip install -r requirements.txt && python -m playwright install chromium
python -m autopilot generate        # draft posts into docs/
python -m autopilot status
python -m autopilot publish --dry-run
```
