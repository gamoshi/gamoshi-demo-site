#!/usr/bin/env python3
"""
Generate a Gamoshi demo HTML page for a customer and optionally upload it to S3.

Usage:
    python generate_demo.py \
        --customer-name "eMarketMed" \
        --customer-id 377 \
        --supply-partner-id 28023 \
        [--rtb-endpoint "https://377.bidder.gamx.io"] \
        [--width 300] \
        [--height 250] \
        [--ttl 3600]          # seconds, or shorthand: 1h / 1d / 7d
        [--upload] \
        [--cf-distribution-id EXXXXXXXXXXXXX]
"""

import argparse
import os
import re
import sys


# ---------------------------------------------------------------------------
# HTML template
# ---------------------------------------------------------------------------

HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{customer_name} Demo Page</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 0; padding: 0; background: #f9f9f9; }}
    header {{ background: #222; color: #fff; padding: 1rem; text-align: center; }}
    main {{ max-width: 900px; margin: 2rem auto; background: #fff; padding: 2rem; border-radius: 8px; box-shadow: 0 2px 8px #0001; }}
    .ad-slot {{ width: {width}px; height: {height}px; background: #eee; border: 2px dashed #bbb; display: flex; align-items: center; justify-content: center; margin: 2rem auto; font-size: 1.2rem; color: #888; }}
    .content {{ margin-bottom: 2rem; }}
    .info {{ background: #f0f8ff; padding: 1rem; border-radius: 4px; margin: 1rem 0; }}
    pre {{ background: #f5f5f5; padding: 1rem; border-radius: 4px; overflow-x: auto; }}
  </style>
</head>
<body>
  <header>
    <h1>{customer_name} Demo Page</h1>
    <p>Demonstrates Prebid.js with Gamoshi RTB endpoint.</p>
  </header>
  <main>
    <section class="content">
      <h2>Sample Ad Placement</h2>
      <p>This is a demonstration of a {width}x{height} ad slot using Prebid.js with the {customer_name} configuration.</p>
      <div class="info">
        <strong>Endpoint:</strong> {rtb_endpoint}<br>
        <strong>Banner Size:</strong> {width}x{height}
      </div>
    </section>

    <div class="ad-slot" id="sgamoshi-ad-slot">
      Ad Slot {width}x{height}
    </div>

    <hr>
    <h2>Live Configuration:</h2>
    <h3>Prebid AdUnits:</h3>
    <pre id="prebidConfigOutput"></pre>
    <hr>

    <!-- Prebid.js integration -->
    <script src="https://cdn.jsdelivr.net/npm/prebid.js@10.8.0/dist/not-for-prod/prebid.min.js"></script>

    <script type="application/javascript">
      var pbjs = pbjs || {{}};
      pbjs.que = pbjs.que || [];

      function getUrlParameter(name) {{
        name = name.replace(/[\\[\\]]/, function(c) {{ return '\\\\' + c; }});
        var regex = new RegExp('[\\\\?&]' + name + '=([^&#]*)');
        var results = regex.exec(location.search);
        return results === null ? '' : decodeURIComponent(results[1].replace(/\\+/g, ' '));
      }}

      var supplyPartnerId = getUrlParameter('supply_partner_id') || '{supply_partner_id}';
      var adWidth  = parseInt(getUrlParameter('adw'))  || {width};
      var adHeight = parseInt(getUrlParameter('adh'))  || {height};

      var adSlotDiv = document.getElementById('sgamoshi-ad-slot');
      if (adSlotDiv) {{
        adSlotDiv.textContent = 'Ad Slot ' + adWidth + 'x' + adHeight;
        adSlotDiv.style.width  = adWidth  + 'px';
        adSlotDiv.style.height = adHeight + 'px';
      }}

      var adUnits = [{{
        code: 'sgamoshi-ad-slot',
        mediaTypes: {{
          banner: {{
            sizes: [[adWidth, adHeight]]
          }}
        }},
        bids: [{{
          bidder: 'gamoshi',
          params: {{
            supplyPartnerId: supplyPartnerId,
            rtbEndpoint: '{rtb_endpoint}',
            placementId: 'sgamoshi-ad-slot'
          }}
        }}]
      }}];

      pbjs.que.push(function() {{
        pbjs.addAdUnits(adUnits);
        pbjs.requestBids({{
          bidsBackHandler: function() {{
            var bids = pbjs.getHighestCpmBids('sgamoshi-ad-slot');
            if (bids && bids.length > 0) {{
              console.log('Bid received:', bids[0]);
              var adSlot = document.getElementById('sgamoshi-ad-slot');
              var iframe = document.createElement('iframe');
              iframe.width = adWidth;
              iframe.height = adHeight;
              iframe.frameBorder = 0;
              iframe.scrolling = 'no';
              adSlot.innerHTML = '';
              adSlot.appendChild(iframe);
              var iframeDoc = iframe.contentWindow.document;
              pbjs.renderAd(iframeDoc, bids[0].adId);
            }} else {{
              console.log('No bids returned');
              document.getElementById('sgamoshi-ad-slot').innerHTML =
                '<div style="color: #999; padding: 2rem;">No ad returned</div>';
            }}
          }}
        }});

        document.getElementById('prebidConfigOutput').textContent =
          JSON.stringify(adUnits, null, 2);
      }});
    </script>
  </main>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def slugify(name: str) -> str:
    """Convert a customer name to a filename-safe slug."""
    return name.lower().replace(" ", "-").replace("_", "-")


def build_rtb_endpoint(customer_id: str) -> str:
    return f"https://{customer_id}.bidder.gamx.io"


def generate_html(customer_name, customer_id, rtb_endpoint, width, height, supply_partner_id):
    return HTML_TEMPLATE.format(
        customer_name=customer_name,
        customer_id=customer_id,
        rtb_endpoint=rtb_endpoint,
        width=width,
        height=height,
        supply_partner_id=supply_partner_id,
    )


def parse_ttl(value: str) -> int:
    """Accept seconds (int) or human shorthand: 30s, 10m, 2h, 7d."""
    value = value.strip()
    match = re.fullmatch(r"(\d+)\s*([smhd]?)", value, re.IGNORECASE)
    if not match:
        raise argparse.ArgumentTypeError(
            f"Invalid TTL '{value}'. Use seconds (e.g. 3600) or shorthand: 30s, 10m, 2h, 7d"
        )
    amount, unit = int(match.group(1)), match.group(2).lower()
    multipliers = {"": 1, "s": 1, "m": 60, "h": 3600, "d": 86400}
    return amount * multipliers[unit]


def fmt_ttl(seconds: int) -> str:
    """Human-readable representation of a TTL in seconds."""
    if seconds == 0:
        return "0s (no-cache)"
    for unit, div in (("d", 86400), ("h", 3600), ("m", 60)):
        if seconds % div == 0:
            return f"{seconds // div}{unit} ({seconds}s)"
    return f"{seconds}s"


def write_local(output_path: str, content: str):
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as fh:
        fh.write(content)
    print(f"[OK] File written: {output_path}")


def invalidate_cloudfront(cf_client, distribution_id: str, s3_key: str):
    """Create a CloudFront invalidation for the uploaded path."""
    import time
    cf_path = f"/{s3_key}"
    resp = cf_client.create_invalidation(
        DistributionId=distribution_id,
        InvalidationBatch={
            "Paths": {"Quantity": 1, "Items": [cf_path]},
            "CallerReference": str(int(time.time())),
        },
    )
    inv_id = resp["Invalidation"]["Id"]
    status  = resp["Invalidation"]["Status"]
    print(f"[OK] CloudFront invalidation created: {inv_id} (status: {status})")
    print(f"     Path: {cf_path}")


def upload_to_s3(local_path: str, customer_id: str, ttl: int, cf_distribution_id: str | None):
    """Upload the file to S3 after explicit user confirmation."""
    bucket = "gamoshi-static-resources"
    s3_key = f"demo-pages/customers/{customer_id}/{os.path.basename(local_path)}"
    s3_uri = f"s3://{bucket}/{s3_key}"

    cache_control = f"max-age={ttl}" if ttl > 0 else "no-cache, no-store, must-revalidate"

    print()
    print("=" * 60)
    print("S3 UPLOAD CONFIRMATION")
    print("=" * 60)
    print(f"  Local file    : {local_path}")
    print(f"  Destination   : {s3_uri}")
    print(f"  Cache-Control : {cache_control}  [{fmt_ttl(ttl)}]")
    if cf_distribution_id:
        print(f"  CF invalidate : {cf_distribution_id}  (/{s3_key})")
    print("=" * 60)
    answer = input("Upload this file to S3? [y/N] ").strip().lower()

    if answer not in ("y", "yes"):
        print("[SKIPPED] Upload cancelled.")
        return

    try:
        import boto3
        s3 = boto3.client("s3")
        s3.upload_file(
            local_path,
            bucket,
            s3_key,
            ExtraArgs={
                "ContentType": "text/html",
                "CacheControl": cache_control,
            },
        )
        print(f"[OK] Uploaded to {s3_uri}")

        if cf_distribution_id:
            cf = boto3.client("cloudfront")
            invalidate_cloudfront(cf, cf_distribution_id, s3_key)

    except ImportError:
        print("[ERROR] boto3 is not installed. Run: pip install boto3")
        sys.exit(1)
    except Exception as exc:
        print(f"[ERROR] {exc}")
        sys.exit(1)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate a Gamoshi customer demo HTML page.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--customer-name",    default=None,   help="Customer display name (e.g. 'eMarketMed')")
    parser.add_argument("--customer-id",      required=True,  help="Customer ID (e.g. '377') — always required")
    parser.add_argument("--supply-partner-id",default=None,   help="Supply partner ID used in Prebid params")
    parser.add_argument("--rtb-endpoint",     default=None,
                        help="RTB endpoint URL. Defaults to https://{customer_id}.bidder.gamx.io")
    parser.add_argument("--width",            type=int, default=300, help="Ad slot width in pixels")
    parser.add_argument("--height",           type=int, default=250, help="Ad slot height in pixels")
    parser.add_argument("--ttl",              type=parse_ttl, default="5m",
                        metavar="TTL",
                        help="CDN/browser cache TTL. Seconds or shorthand: 30s, 5m, 2h, 7d (default: 5m)")
    parser.add_argument("--output-dir",       default="demos",
                        help="Local directory to write the HTML file into")
    parser.add_argument("--upload",           action="store_true",
                        help="After generating, prompt to upload to S3")
    parser.add_argument("--upload-only",      default=None, metavar="FILE",
                        help="Skip generation — upload an existing local file to S3")
    parser.add_argument("--cf-distribution-id", default=None, metavar="DIST_ID",
                        help="CloudFront distribution ID — creates an invalidation after upload")
    return parser.parse_args()


def main():
    args = parse_args()

    # ------------------------------------------------------------------
    # Mode A: upload-only — skip generation entirely
    # ------------------------------------------------------------------
    if args.upload_only:
        local_path = args.upload_only
        if not os.path.isfile(local_path):
            print(f"[ERROR] File not found: {local_path}")
            sys.exit(1)
        if not args.customer_id:
            print("[ERROR] --customer-id is required with --upload-only")
            sys.exit(1)
        print(f"[upload-only] {local_path}")
        print(f"  TTL        : {fmt_ttl(args.ttl)}")
        upload_to_s3(local_path, args.customer_id, args.ttl, args.cf_distribution_id)
        return

    # ------------------------------------------------------------------
    # Mode B: generate (and optionally upload)
    # ------------------------------------------------------------------
    missing = [f for f, v in [("--customer-name", args.customer_name),
                               ("--supply-partner-id", args.supply_partner_id)] if not v]
    if missing:
        print(f"[ERROR] Missing required argument(s) for generation: {', '.join(missing)}")
        sys.exit(1)

    rtb_endpoint = args.rtb_endpoint or build_rtb_endpoint(args.customer_id)

    html = generate_html(
        customer_name=args.customer_name,
        customer_id=args.customer_id,
        rtb_endpoint=rtb_endpoint,
        width=args.width,
        height=args.height,
        supply_partner_id=args.supply_partner_id,
    )

    filename = f"{slugify(args.customer_name)}-demo-{args.customer_id}.html"
    output_path = os.path.join(args.output_dir, filename)

    write_local(output_path, html)

    print(f"  Customer   : {args.customer_name}")
    print(f"  Customer ID: {args.customer_id}")
    print(f"  RTB        : {rtb_endpoint}")
    print(f"  Size       : {args.width}x{args.height}")
    print(f"  Partner ID : {args.supply_partner_id}")
    print(f"  TTL        : {fmt_ttl(args.ttl)}")

    if args.upload:
        # --upload flag: go straight to upload prompt
        upload_to_s3(output_path, args.customer_id, args.ttl, args.cf_distribution_id)
    else:
        # No --upload flag: ask interactively so inspect→upload works in one run
        print()
        answer = input("Upload to S3 now? [y/N] ").strip().lower()
        if answer in ("y", "yes"):
            upload_to_s3(output_path, args.customer_id, args.ttl, args.cf_distribution_id)
        else:
            print(f"[SKIPPED] To upload later:  ./generate_demo.sh --upload-only {output_path} -i {args.customer_id}")


if __name__ == "__main__":
    main()