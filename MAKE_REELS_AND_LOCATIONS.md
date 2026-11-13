# Make.com: Reels and location tags

The bot sends every post to your Make webhook. Fields: `caption`, `alt`, `id`, `image_count`, `image_url_1`..`image_url_6`, `location_name`, `location_id`.
Reels add: `media_type` = `REELS` and `video_url` (and `image_count` = 0).

## 1. Location tags (carousel and photo routes)
1. Open the scenario, click the Instagram **Create a Carousel Post** module (do the same for the single-photo module).
2. Find the field **Location ID** (under "Show advanced settings" if hidden).
3. Click the field and map `location_id` from the webhook (the purple/orange chip). Leave it empty if you want no tag: posts with no place send an empty `location_id` and Make skips the tag.
4. The IDs are in `config.yaml` under `locations:` (for example Negril 110074689016001). To add a place, paste its Instagram location ID there and add words in `match:`.
5. Run once with an approved post that names a place and check the tag shows on the Instagram post.

## 2. Reel route
1. Right-click the webhook module > the router you already have > **Add another route**.
2. Click the line (filter) on the new route: Label `Reel`, condition `media_type` **Equal to** `REELS`.
3. Click the **+** on the new route > Instagram for Business > **Create a Reel** (shown as "Create a Post" with Media type Reel on older versions).
4. Connection: the same @arahrides connection.
5. Fill in: **Video URL** = `video_url`, **Caption** = `caption`, **Share to feed** = yes, **Location ID** = `location_id` (as in step 1).
6. Reorder: put the Reel route first (drag it to the top) so Make checks it before the carousel routes.
7. On each existing route, add the condition `image_count` **Greater than** `0` so a reel can never fall into a photo route.
8. Reels take longer to process on Instagram. In the Reel module, if available, leave the default wait, and set the scenario timeout to 5 minutes (Scenario settings).
9. Save and turn the scenario on.

## 3. Turn reels on
1. Upload the reels folder from a PC (the two animated ads go in `content/reels`). If you skip this, daily slideshow reels still work; only the animated ad is missing.
2. In `config.yaml` set `reels: publish_as_reel: true` (leave `per_day: 4`).
3. Test: approve one reel post, run **Post approved**, and check Make shows the Reel route running.
Until step 3, nothing changes: posts keep going out as carousels.
