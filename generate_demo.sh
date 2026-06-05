#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# generate_demo.sh — Gamoshi customer demo page generator
# Wraps generate_demo.py with argument parsing and usage help.
# ---------------------------------------------------------------------------
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="${PYTHON:-python3}"

# ---------------------------------------------------------------------------
# Usage
# ---------------------------------------------------------------------------
usage() {
  cat <<EOF
Usage: $(basename "$0") [OPTIONS]

Modes:
  (default)                       Generate the demo file, then ask "Upload now?"
  --upload                        Generate and go straight to the upload prompt
  -U, --upload-only FILE          Skip generation — upload an existing file to S3

Required (generation):
  -n, --customer-name NAME        Customer display name  (e.g. "eMarketMed")
  -i, --customer-id   ID          Customer / bidder ID   (e.g. 377)
  -s, --supply-partner-id ID      Supply partner ID used in Prebid params

Required (upload-only):
  -i, --customer-id   ID          Determines the S3 destination path

Optional:
  -e, --rtb-endpoint  URL         RTB endpoint (default: https://{id}.bidder.gamx.io)
  -W, --width         PX          Ad slot width  in pixels (default: 300)
  -H, --height        PX          Ad slot height in pixels (default: 250)
  -t, --ttl           TTL         Cache TTL: seconds or shorthand 30s/5m/2h/7d (default: 5m)
  -o, --output-dir    DIR         Local output directory (default: demos)
  -d, --cf-dist-id    DIST_ID     CloudFront distribution ID — invalidates path after upload
  -h, --help                      Show this help and exit

Examples:
  # Generate, inspect interactively, then decide to upload
  $(basename "$0") -n "Acme Corp" -i 999 -s 12345

  # Generate and skip straight to upload prompt
  $(basename "$0") -n "Acme Corp" -i 999 -s 12345 --upload

  # Upload an already-generated file (no regeneration)
  $(basename "$0") --upload-only demos/acme-corp-demo-999.html -i 999

  # Upload-only with custom TTL and CloudFront invalidation
  $(basename "$0") -U demos/acme-corp-demo-999.html -i 999 -t 1h -d EXXXXXXXXXXXXX
EOF
}

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
CUSTOMER_NAME=""
CUSTOMER_ID=""
SUPPLY_PARTNER_ID=""
RTB_ENDPOINT=""
WIDTH=300
HEIGHT=250
TTL="5m"
OUTPUT_DIR="demos"
UPLOAD=false
UPLOAD_ONLY=""
CF_DIST_ID=""

# ---------------------------------------------------------------------------
# Parse arguments
# ---------------------------------------------------------------------------
while [[ $# -gt 0 ]]; do
  case "$1" in
    -n|--customer-name)     CUSTOMER_NAME="$2";     shift 2 ;;
    -i|--customer-id)       CUSTOMER_ID="$2";       shift 2 ;;
    -s|--supply-partner-id) SUPPLY_PARTNER_ID="$2"; shift 2 ;;
    -e|--rtb-endpoint)      RTB_ENDPOINT="$2";      shift 2 ;;
    -W|--width)             WIDTH="$2";             shift 2 ;;
    -H|--height)            HEIGHT="$2";            shift 2 ;;
    -t|--ttl)               TTL="$2";               shift 2 ;;
    -o|--output-dir)        OUTPUT_DIR="$2";        shift 2 ;;
    -u|--upload)            UPLOAD=true;            shift   ;;
    -U|--upload-only)       UPLOAD_ONLY="$2";       shift 2 ;;
    -d|--cf-dist-id)        CF_DIST_ID="$2";        shift 2 ;;
    -h|--help)              usage; exit 0 ;;
    *) echo "[ERROR] Unknown option: $1" >&2; usage; exit 1 ;;
  esac
done

# ---------------------------------------------------------------------------
# Validate required args
# ---------------------------------------------------------------------------
if [[ -n "$UPLOAD_ONLY" ]]; then
  # upload-only mode: only customer-id is required
  if [[ -z "$CUSTOMER_ID" ]]; then
    echo "[ERROR] --customer-id is required with --upload-only" >&2
    exit 1
  fi
else
  # generation mode: all three required
  MISSING=()
  [[ -z "$CUSTOMER_NAME"     ]] && MISSING+=("--customer-name")
  [[ -z "$CUSTOMER_ID"       ]] && MISSING+=("--customer-id")
  [[ -z "$SUPPLY_PARTNER_ID" ]] && MISSING+=("--supply-partner-id")

  if [[ ${#MISSING[@]} -gt 0 ]]; then
    echo "[ERROR] Missing required argument(s): ${MISSING[*]}" >&2
    echo ""
    usage
    exit 1
  fi
fi

# ---------------------------------------------------------------------------
# Build python command
# ---------------------------------------------------------------------------
CMD=(
  "$PYTHON" "$SCRIPT_DIR/generate_demo.py"
  --customer-id "$CUSTOMER_ID"
  --ttl         "$TTL"
)

if [[ -n "$UPLOAD_ONLY" ]]; then
  CMD+=(--upload-only "$UPLOAD_ONLY")
else
  CMD+=(
    --customer-name     "$CUSTOMER_NAME"
    --supply-partner-id "$SUPPLY_PARTNER_ID"
    --width             "$WIDTH"
    --height            "$HEIGHT"
    --output-dir        "$OUTPUT_DIR"
  )
  [[ -n "$RTB_ENDPOINT" ]] && CMD+=(--rtb-endpoint "$RTB_ENDPOINT")
  [[ "$UPLOAD" == true  ]] && CMD+=(--upload)
fi

[[ -n "$CF_DIST_ID" ]] && CMD+=(--cf-distribution-id "$CF_DIST_ID")

# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------
exec "${CMD[@]}"
