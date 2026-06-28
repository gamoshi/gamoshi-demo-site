#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# redeploy-asset.sh — Upload a demo asset to one or more customer paths in S3
#                     and issue a single batch CloudFront invalidation.
#
# Default TTL is 5 minutes so future deploys are picked up by the CDN
# automatically — no manual invalidation needed.
#
# Usage:
#   ./redeploy-asset.sh -f demos/celtra-ad-test.html -c 370,373
#   ./redeploy-asset.sh -f demos/celtra-ad-test.html -c 370,373 -t 300 -d E3UM5KAY62BKZF
#   ./redeploy-asset.sh -f demos/foo.html -c 370 --no-invalidate
# ---------------------------------------------------------------------------
set -euo pipefail

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
BUCKET="gamoshi-static-resources"
CF_DIST_ID="E3UM5KAY62BKZF"   # resources.gamoshi.io / resources.gamx.io / resources.gambid.io
TTL=300                         # 5 minutes
FILE=""
CUSTOMERS=()
NO_INVALIDATE=false
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MRAID_STUB="${SCRIPT_DIR}/demos/mraid.js"

# ---------------------------------------------------------------------------
# Usage
# ---------------------------------------------------------------------------
usage() {
  cat <<EOF
Usage: $(basename "$0") [OPTIONS]

Required:
  -f, --file       FILE              Path to the local asset file to deploy
  -c, --customers  ID[,ID,...]       Comma-separated customer IDs (e.g. 370,373)

Optional:
  -t, --ttl        SECONDS           Cache-Control max-age in seconds (default: 300 = 5 min)
  -d, --cf-dist-id DISTRIBUTION_ID  CloudFront distribution ID (default: E3UM5KAY62BKZF)
      --no-invalidate                Skip CloudFront invalidation (rely on TTL only)
      --no-mraid                     Skip auto-deploying mraid.js alongside HTML files
  -h, --help                         Show this help and exit

Examples:
  $(basename "$0") -f demos/celtra-ad-test.html -c 370,373
  $(basename "$0") -f demos/celtra-ad-test.html -c 370,373 -t 60
  $(basename "$0") -f demos/celtra-ad-test.html -c 370 --no-invalidate
EOF
}

# ---------------------------------------------------------------------------
# Parse arguments
# ---------------------------------------------------------------------------
while [[ $# -gt 0 ]]; do
  case "$1" in
    -f|--file)          FILE="$2";                                   shift 2 ;;
    -c|--customers)     IFS=',' read -ra CUSTOMERS <<< "$2";         shift 2 ;;
    -t|--ttl)           TTL="$2";                                    shift 2 ;;
    -d|--cf-dist-id)    CF_DIST_ID="$2";                             shift 2 ;;
    --no-invalidate)    NO_INVALIDATE=true;                          shift   ;;
    --no-mraid)         MRAID_STUB="";                               shift   ;;
    -h|--help)          usage; exit 0 ;;
    *) echo "[ERROR] Unknown option: $1" >&2; usage; exit 1 ;;
  esac
done

# ---------------------------------------------------------------------------
# Validate
# ---------------------------------------------------------------------------
ERRORS=()
[[ -z "$FILE"               ]] && ERRORS+=("--file is required")
[[ ${#CUSTOMERS[@]} -eq 0   ]] && ERRORS+=("--customers is required")
[[ -n "$FILE" && ! -f "$FILE" ]] && ERRORS+=("file not found: $FILE")

if [[ ${#ERRORS[@]} -gt 0 ]]; then
  for e in "${ERRORS[@]}"; do echo "[ERROR] $e" >&2; done
  echo "" >&2
  usage
  exit 1
fi

# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------
FILENAME=$(basename "$FILE")
CACHE_CONTROL="max-age=${TTL}"
INVALIDATION_PATHS=()

echo ""
echo "============================================================"
echo "  redeploy-asset"
echo "============================================================"
echo "  Asset     : $FILENAME"
echo "  Customers : ${CUSTOMERS[*]}"
echo "  Bucket    : $BUCKET"
echo "  TTL       : ${TTL}s  (Cache-Control: ${CACHE_CONTROL})"
echo "  Invalidate: $([[ "$NO_INVALIDATE" == true ]] && echo "no (rely on TTL)" || echo "yes — ${CF_DIST_ID}")"
echo "============================================================"
echo ""

IS_HTML=false
[[ "$FILENAME" == *.html ]] && IS_HTML=true

for CID in "${CUSTOMERS[@]}"; do
  CID="${CID// /}"   # strip any accidental spaces
  S3_KEY="demo-pages/customers/${CID}/${FILENAME}"

  echo "[→] s3://${BUCKET}/${S3_KEY}"
  aws s3 cp "$FILE" "s3://${BUCKET}/${S3_KEY}" \
    --content-type "text/html" \
    --cache-control "$CACHE_CONTROL"
  echo "[✓] customer ${CID} uploaded"
  INVALIDATION_PATHS+=("/${S3_KEY}")

  # Auto-deploy mraid.js alongside every HTML file so MRAID v3 tags work
  if [[ "$IS_HTML" == true && -n "$MRAID_STUB" && -f "$MRAID_STUB" ]]; then
    MRAID_KEY="demo-pages/customers/${CID}/mraid.js"
    aws s3 cp "$MRAID_STUB" "s3://${BUCKET}/${MRAID_KEY}" \
      --content-type "application/javascript" \
      --cache-control "$CACHE_CONTROL"
    echo "[✓] customer ${CID} mraid.js"
    INVALIDATION_PATHS+=("/${MRAID_KEY}")
  fi
done

# ---------------------------------------------------------------------------
# CloudFront invalidation (single batch for all paths)
# ---------------------------------------------------------------------------
if [[ "$NO_INVALIDATE" == false ]]; then
  echo ""
  echo "[→] Creating CloudFront invalidation (${CF_DIST_ID})..."

  QUANTITY=${#INVALIDATION_PATHS[@]}
  # build JSON array: ["/path/a", "/path/b"]
  ITEMS_JSON=$(printf '"%s",' "${INVALIDATION_PATHS[@]}")
  ITEMS_JSON="[${ITEMS_JSON%,}]"

  INVALIDATION_ID=$(aws cloudfront create-invalidation \
    --distribution-id "$CF_DIST_ID" \
    --invalidation-batch \
      "{\"Paths\":{\"Quantity\":${QUANTITY},\"Items\":${ITEMS_JSON}},\"CallerReference\":\"redeploy-$(date +%s)\"}" \
    --query 'Invalidation.Id' \
    --output text)

  echo "[✓] Invalidation created: ${INVALIDATION_ID}"
  echo "    (propagates in ~30–60s; TTL=${TTL}s keeps future deploys automatic)"
fi

echo ""
echo "============================================================"
echo "  Done."
echo "  URLs updated:"
for CID in "${CUSTOMERS[@]}"; do
  CID="${CID// /}"
  echo "    https://resources.gamx.io/demo-pages/customers/${CID}/${FILENAME}"
done
echo "============================================================"