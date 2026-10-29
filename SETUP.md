# Setup guide (about 45 minutes, once)

You need four things: a GitHub account, a Google Drive folder (you have it), an Instagram professional account, and a Meta developer app. Meta changes its screens now and then; if a button has moved, search for the name in quotes.

## 1. Instagram account type
Instagram app > Settings > Account type and tools > **Switch to professional account** (Business or Creator). @arahrides probably already is.

## 2. Choose how posts reach Instagram
You do **not** need a Facebook developer account. Pick one path.

| Path | Needs developer account? | Fully automatic? | Cost |
|---|---|---|---|
| **A. Make.com** (recommended for you) | No | Yes | Free plan (see limits below) |
| B. Meta developer app | Yes | Yes | Free |
| C. Manual mode | No | No (you schedule in the Instagram app) | Free |

### Path A: Make.com (no developer account)
Make.com is a free no-code tool that already has an approved Instagram connection. The bot decides what is approved and due, then sends each post to Make, and Make publishes it to @arahrides. You only log in to Facebook the normal way, as you do for Business Suite.

**Before you start:** @arahrides must be a Business or Creator account **linked to a Facebook Page** (Instagram app > Settings > Account type and tools, then Settings > Accounts Center, or Page settings > Linked accounts). If the normal Facebook login also stalls on the text-message code, use the authenticator-app fix in Path B, step 2A.1, which fixes it for every Meta login.

1. Create a free account at **make.com**.
2. Click **Create a new scenario**. Click the big **+** and choose **Webhooks > Custom webhook**. Click **Add**, name it `arah-post`, Save. **Copy the webhook URL.**
3. In your GitHub repo add a secret named `POST_WEBHOOK_URL` and paste that URL (step 3 below shows where). Do not add the `IG_` secrets.
4. Back in Make, click **Run once** (the webhook now waits for data). In GitHub approve one post on the review page, then go to Actions > **Post approved** > Run workflow. (A post only goes out once its time slot has arrived, so pick one whose time is within the last few hours.) Make shows "Successfully determined" and now knows the fields: `caption`, `image_url_1` to `image_url_6`, `image_count`, `alt`, `id`.
5. Add a second module: **Instagram for Business > Create a Photo Post**. Click **Add** to connect, log in with Facebook, and tick your Page and @arahrides when asked. Set **Photo URL** = `image_url_1` and **Caption** = `caption`.
6. For carousels, right-click the webhook module and **Add a router**. Make the first route the photo post with the filter `image_count` equal to `1`. Add more routes with **Instagram for Business > Create a Carousel Post**, one each for `image_count` equal to `4`, `5` and `6`. In each, add that many photo URLs (`image_url_1`, `image_url_2`, and so on) and set the caption to `caption`.
7. Turn **Scheduling** on (the switch at the bottom left) so the scenario is live, and save. The webhook runs instantly whenever the bot sends a post.

**Limits to check:** Make's free plan allows about 1,000 operations a month, and each post uses about 2. At 15 posts a day you would use about 900, which is close to the limit. If Make says you are running out, lower `posts_per_day` and trim `slots` in `config.yaml` (for example 10 a day), or move to a paid Make plan. Check Make's current plan limits when you sign up, since they change.

Anyone using n8n, Zapier or Pipedream can use the same webhook URL; the data fields are the same.

### Path B: Meta developer app (official, direct)

### 2A. If Meta will not send your verification code (fix this first)
Try these in order. Stop as soon as one works.
1. **Switch off text messages altogether.** On facebook.com go to Settings & privacy > Settings > Accounts Center > Password and security > Two-factor authentication. Pick your Facebook profile and choose **Authentication app** (Google Authenticator, Microsoft Authenticator or Authy, all free). Scan the QR code, enter the 6-digit code, and save the **recovery codes** it shows. From then on, Meta asks for the app code, not a text. Then go back to developers.facebook.com.
2. **On the verification screen, click "Try another way"** (or "Didn't get a code?"). Choose email, authenticator app, a recovery code, or a phone call if offered.
3. **Check the phone number.** In Accounts Center > Personal details > Contact info, confirm the number is correct and verified. Use a real mobile number, not a Google Voice or other internet number. Add a second number if you have one.
4. **Remove blockers.** Turn off any VPN, use a private/incognito window or another browser, and use the same device you normally log into Facebook with. If you have requested codes many times, wait 24 hours, because Meta pauses codes after repeated tries.
5. **Ask your phone carrier** to allow short-code text messages and confirm the number is not blocking "service" texts.
6. **Meta's own help**: facebook.com/help, search "I can't log in because I don't get the security code", and follow the "Get help" option.

### 2B. Let someone else create the app
Meta only needs one working Facebook account to create the app, and that person does not have to be you. Ask a teammate whose Facebook account works to do steps 1 to 7 below. During step 3 they will log into the @arahrides Instagram account inside the Meta dashboard (you give them the Instagram login for those few minutes, then change the password or log them out). They send you the **access token** and the **Instagram user ID** through a private channel.

### Steps once you can log in to developers.facebook.com
1. Go to **developers.facebook.com**, log in and accept the developer terms.
2. Click **My Apps > Create App**. Choose **Business** (or "Other", then Business). Name it "Arah Autopilot".
3. On the app dashboard find **Add product > Instagram** and open **API setup with Instagram login**.
4. Under "Generate access tokens" click **Add account** and log in as @arahrides. If it asks you to be an **Instagram Tester**, add the account under App roles, then accept the invite in the Instagram app (Settings > Website permissions > Tester invites).
5. Make sure the permissions **instagram_business_basic** and **instagram_business_content_publish** are ticked.
6. Click **Generate token** next to @arahrides. Copy the **access token** and the **Instagram user ID** into a private note.
7. Leave the app in Development mode. That is allowed for your own account and needs no Meta review.

### Path C: manual mode (works today)
If neither Make nor the Meta app works yet, skip the posting secrets in step 3. Everything else still works: the bot drafts 15 posts a day and you review them on the same page. Each card has **Copy caption** and **Download image** buttons. Then schedule them in the Instagram app (create a post, then Advanced settings or **Schedule**) or in Meta Business Suite. It takes a few minutes a day instead of nothing. When the Meta app works later, add the two Instagram secrets and the bot starts posting by itself with no other change.

## 3. GitHub
1. Create a GitHub account if needed, then **New repository**: name `arah-autopilot`, **Public**.
2. Upload everything from the zip (drag the folder's contents into the repo page, or use `git push`). Make sure the `.github` folder uploaded.
3. **Settings > Pages**: Source = *Deploy from a branch*, Branch = `main`, folder = `/docs`. Your review page will be at `https://YOURNAME.github.io/arah-autopilot/`.
4. **Settings > Actions > General > Workflow permissions**: *Read and write permissions*. Save.
5. **Settings > Secrets and variables > Actions > New repository secret**. Add:
   | Name | Value |
   |---|---|
   | `POST_WEBHOOK_URL` | Path A only: the Make webhook URL |
   | `IG_USER_ID` | Path B only: the Instagram user ID |
   | `IG_ACCESS_TOKEN` | Path B only: the token |
   | `GDRIVE_SA_JSON` | the whole contents of the Google key file (step 4) |
   | `PEXELS_API_KEY` | free key from pexels.com/api (optional but recommended) |
   | `GH_ADMIN_TOKEN` | Path B only: a token that can update secrets (step 5) |

## 4. Google Drive access (so the bot can read your photos)
1. console.cloud.google.com > create a project > **APIs & Services > Enable APIs** > enable **Google Drive API**.
2. **IAM & Admin > Service accounts > Create**. Open it > **Keys > Add key > JSON**. A file downloads: paste its full text into the `GDRIVE_SA_JSON` secret.
3. Copy the service account's email (looks like `name@project.iam.gserviceaccount.com`). In Drive, right-click the **Arah Rides Content** folder > Share > add that email as **Viewer**.

## 5. Two GitHub tokens
GitHub > your profile > Settings > Developer settings > **Fine-grained tokens > Generate new token**.
- **Token A (for the review page)**: only this repository, permission **Contents: Read and write**. You paste it into the review page once.
- **Token B (`GH_ADMIN_TOKEN`)**: only this repository, permissions **Secrets: Read and write** (add Contents: Read). It lets the Monday job store the renewed Instagram token.

## 6. First run
1. **Actions** tab > *Draft new posts* > **Run workflow**. After a few minutes you should see new files under `docs/queue`.
2. Open the review page on your phone, tap **Settings**, enter `YOURNAME/arah-autopilot` and Token A. Add it to your home screen.
3. Approve a few posts. In **Actions** > *Post approved* > **Run workflow** with *Dry run* ticked to see what it would post, then untick it for the real thing. After that it runs by itself every 10 minutes.

## Troubleshooting
- Review page empty: the draft job has not run yet, or Pages is still building (first build takes a few minutes).
- "GitHub says no": re-create Token A with Contents read/write on this repo.
- Posts stay approved but do not publish: open Actions > Post approved > latest run. Common causes: expired or wrong token, or user ID mismatch. The failing reason is also shown on the card.
- Instagram error mentioning the image URL: the repo is not public, or the draft was not pushed yet.
