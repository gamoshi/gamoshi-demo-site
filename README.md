# Demo Pages

Customer-facing demo pages served from:
`https://resources.gamx.io/demo-pages/customers/{customer_id}/{file}`

**S3 bucket:** `gamoshi-static-resources`  
**CDN distribution:** `E3UM5KAY62BKZF` (resources.gamoshi.io / resources.gamx.io / resources.gambid.io)  
**Default TTL:** 5 minutes — after any deploy, CDN auto-refreshes within 5 min without manual invalidation.

---

## Creating a new customer demo page

Generates a standard Prebid/RTB demo page and optionally uploads it to S3.

```bash
# Generate, review, then decide to upload
./generate_demo.sh -n "Acme Corp" -i 999 -s 12345

# Generate and go straight to upload
./generate_demo.sh -n "Acme Corp" -i 999 -s 12345 --upload

# Upload an already-generated file
./generate_demo.sh --upload-only demos/acme-corp-demo-999.html -i 999

# With explicit TTL and CloudFront invalidation
./generate_demo.sh -n "Acme Corp" -i 999 -s 12345 --upload -t 5m -d E3UM5KAY62BKZF
```

Key options: `-n` customer name · `-i` customer ID · `-s` supply partner ID · `-e` RTB endpoint · `-t` TTL · `-d` CloudFront dist ID

---

## Redeploying an existing asset to one or more customers

Use `redeploy-asset.sh` when you want to push an updated shared asset (e.g. `celtra-ad-test.html`)
to multiple customers at once. Non-interactive — no confirmation prompts.
Uploads with 5-minute TTL and issues a single batch CloudFront invalidation.

```bash
 # Redeploy celtra-ad-test.html + mraid.js stub to customers 370 and 373
./redeploy-asset.sh -f demos/celtra-ad-test.html -c 370,373
./redeploy-asset.sh -f demos/mraid.js -c 370,373

# Custom TTL (e.g. 60s for rapid iteration)
./redeploy-asset.sh -f demos/celtra-ad-test.html -c 370,373 -t 60

# Skip invalidation — rely on TTL only
./redeploy-asset.sh -f demos/celtra-ad-test.html -c 370,373 --no-invalidate

# Single customer, custom CloudFront dist
./redeploy-asset.sh -f demos/foo.html -c 999 -d EXXXXXXXXXXXXX
```

Key options: `-f` file · `-c` comma-separated customer IDs · `-t` TTL in seconds · `-d` CloudFront dist ID · `--no-invalidate`

After running, verify what's live:

```bash
aws s3api head-object \
  --bucket gamoshi-static-resources \
  --key demo-pages/customers/370/celtra-ad-test.html
```

---

## Celtra v3 tags (`celtra-ad-test.html`)

The Celtra ad test tool (`demos/celtra-ad-test.html`) supports both v3 and v4 tags.

**v3 quirks handled automatically:**
- `\[...\]` bracket escaping — customers sometimes escape macros using the Gamoshi
  do-not-replace convention (`\[MACRO\]`); the tool strips the backslashes before
  loading the tag so the JS doesn't throw a syntax error in the sandboxed iframe.
- **MRAID** — v3 tags include `<script src="mraid.js">` and require `window.mraid`
  to be present. The tool injects a MRAID 2.0 stub before the tag loads.
- **`mraid.js` 403** — when served from `resources.gamx.io`, the relative
  `<script src="mraid.js">` resolves against the page URL. A minimal empty
  `mraid.js` stub is deployed alongside the HTML to return 200 instead of 403.
  The tool's inline MRAID stub already defines `window.mraid` before this script
  loads, so the ad renders regardless.