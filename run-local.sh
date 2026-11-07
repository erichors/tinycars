#!/usr/bin/env bash
# Start the complete TinyCars stack locally, optionally backed by Amazon Bedrock.
# Uses the caller's AWS CLI profile to obtain temporary credentials; no AWS keys
# are written to disk or copied into the repository.
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_FILE="$ROOT_DIR/deploy/docker-compose.yml"
AWS_PROFILE_NAME="${AWS_PROFILE:-default}"
AWS_REGION_NAME="${AWS_REGION:-us-east-1}"
AI_MODEL="${AI_MODEL_ID:-us.anthropic.claude-haiku-5-5}"
AI_PROVIDER="bedrock"
ACTION="up"
INSTALL_DEPS=false
CHECK_BEDROCK=true
SESSION_SECONDS="${AWS_SESSION_SECONDS:-28800}"

usage() {
  cat <<'EOF'
Usage: ./run-local.sh [options]

Starts TinyCars at http://localhost:8080 using Amazon Bedrock for Find my car.

Options:
  --profile NAME          AWS CLI profile (default: $AWS_PROFILE or default)
  --region REGION        AWS/Bedrock region (default: us-east-1)
  --model-id ID          Bedrock model or inference profile ID
  --keyword              Use the local keyword matcher instead of Bedrock
  --skip-bedrock-check   Do not make the small preflight Bedrock request
  --install-deps         On macOS, install Colima and Docker Compose with Homebrew
  --down                 Stop and remove the local stack
  --logs                 Follow logs from the running stack
  -h, --help             Show this help

Examples:
  ./run-local.sh
  ./run-local.sh --profile sandbox --region us-east-1
  ./run-local.sh --install-deps
  ./run-local.sh --down
EOF
}

die() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --profile) [[ $# -ge 2 ]] || die "--profile requires a value"; AWS_PROFILE_NAME="$2"; shift 2 ;;
    --region) [[ $# -ge 2 ]] || die "--region requires a value"; AWS_REGION_NAME="$2"; shift 2 ;;
    --model-id) [[ $# -ge 2 ]] || die "--model-id requires a value"; AI_MODEL="$2"; shift 2 ;;
    --keyword) AI_PROVIDER="keyword"; CHECK_BEDROCK=false; shift ;;
    --skip-bedrock-check) CHECK_BEDROCK=false; shift ;;
    --install-deps) INSTALL_DEPS=true; shift ;;
    --down) ACTION="down"; shift ;;
    --logs) ACTION="logs"; shift ;;
    -h|--help) usage; exit 0 ;;
    *) die "unknown option: $1" ;;
  esac
done

if ! command -v docker >/dev/null 2>&1; then
  die "Docker CLI is required. On macOS, install it with: brew install docker"
fi

if ! docker compose version >/dev/null 2>&1 && ! command -v docker-compose >/dev/null 2>&1; then
  if [[ "$INSTALL_DEPS" == true ]] && [[ "$(uname -s)" == "Darwin" ]] && command -v brew >/dev/null 2>&1; then
    printf 'Installing Colima and Docker Compose with Homebrew...\n'
    brew install colima docker-compose
  else
    die "Docker Compose is missing. Re-run with --install-deps, or install Docker Compose."
  fi
fi

if docker compose version >/dev/null 2>&1; then
  COMPOSE=(docker compose)
else
  COMPOSE=(docker-compose)
fi

ensure_docker_daemon() {
  if docker info >/dev/null 2>&1; then
    return
  fi

  if command -v colima >/dev/null 2>&1; then
    printf 'Starting Colima...\n'
    colima start --cpu 4 --memory 6
  elif [[ "$(uname -s)" == "Darwin" ]] && [[ -d /Applications/Docker.app ]]; then
    printf 'Starting Docker Desktop...\n'
    open -a Docker
  else
    die "Docker daemon is not running. Start Docker Desktop, or re-run with --install-deps."
  fi

  printf 'Waiting for Docker'
  for _ in $(seq 1 90); do
    if docker info >/dev/null 2>&1; then
      printf ' ready.\n'
      return
    fi
    printf '.'
    sleep 2
  done
  printf '\n'
  die "Docker did not become ready within 3 minutes"
}

ensure_docker_daemon

if [[ "$ACTION" == "down" ]]; then
  "${COMPOSE[@]}" -f "$COMPOSE_FILE" down --remove-orphans
  exit 0
fi

if [[ "$ACTION" == "logs" ]]; then
  "${COMPOSE[@]}" -f "$COMPOSE_FILE" logs -f
  exit 0
fi

export AI_MATCHER_PROVIDER="$AI_PROVIDER"
export AI_MODEL_ID="$AI_MODEL"
export AWS_REGION="$AWS_REGION_NAME"
export AWS_DEFAULT_REGION="$AWS_REGION_NAME"

cleanup_credentials() {
  unset AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN AWS_CREDENTIAL_EXPIRATION
}
trap cleanup_credentials EXIT

if [[ "$AI_PROVIDER" == "bedrock" ]]; then
  command -v aws >/dev/null 2>&1 || die "AWS CLI v2 is required for Bedrock mode"

  if ! IDENTITY_JSON="$(aws sts get-caller-identity --profile "$AWS_PROFILE_NAME" --output json 2>/dev/null)"; then
    printf 'AWS session is not valid; attempting AWS SSO login for profile %s...\n' "$AWS_PROFILE_NAME"
    aws sso login --profile "$AWS_PROFILE_NAME"
    IDENTITY_JSON="$(aws sts get-caller-identity --profile "$AWS_PROFILE_NAME" --output json)"
  fi

  IDENTITY_ARN="$(aws sts get-caller-identity --profile "$AWS_PROFILE_NAME" --query Arn --output text)"
  ACCOUNT_ID="$(aws sts get-caller-identity --profile "$AWS_PROFILE_NAME" --query Account --output text)"
  printf 'AWS identity: %s (account %s)\n' "$IDENTITY_ARN" "$ACCOUNT_ID"

  # For a long-lived IAM user profile, exchange the keys for an eight-hour STS
  # session before exposing credentials to the local catalog container. SSO and
  # assumed-role profiles already return temporary credentials.
  if [[ "$IDENTITY_ARN" == arn:aws:iam::*:user/* ]]; then
    read -r AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN <<EOF
$(aws sts get-session-token --profile "$AWS_PROFILE_NAME" --duration-seconds "$SESSION_SECONDS" \
  --query 'Credentials.[AccessKeyId,SecretAccessKey,SessionToken]' --output text)
EOF
    export AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN
  else
    while IFS='=' read -r key value; do
      case "$key" in
        AWS_ACCESS_KEY_ID|AWS_SECRET_ACCESS_KEY|AWS_SESSION_TOKEN|AWS_CREDENTIAL_EXPIRATION)
          export "$key=$value"
          ;;
      esac
    done < <(aws configure export-credentials --profile "$AWS_PROFILE_NAME" --format env-no-export)
  fi

  [[ -n "${AWS_ACCESS_KEY_ID:-}" && -n "${AWS_SECRET_ACCESS_KEY:-}" ]] || die "AWS credentials could not be exported"

  if [[ "$CHECK_BEDROCK" == true ]]; then
    printf 'Checking Bedrock access to %s...\n' "$AI_MODEL"
    BEDROCK_REPLY="$(aws bedrock-runtime converse --region "$AWS_REGION_NAME" --model-id "$AI_MODEL" \
      --messages '[{"role":"user","content":[{"text":"Reply with one word: ready"}]}]' \
      --query 'output.message.content[0].text' --output text)"
    printf 'Bedrock replied: %s\n' "$BEDROCK_REPLY"
  fi
fi

if command -v lsof >/dev/null 2>&1 \
  && lsof -nP -iTCP:8080 -sTCP:LISTEN >/dev/null 2>&1 \
  && [[ -z "$("${COMPOSE[@]}" -f "$COMPOSE_FILE" ps -q storefront 2>/dev/null)" ]]; then
  die "port 8080 is already in use"
fi

printf 'Building and starting TinyCars (%s matcher)...\n' "$AI_PROVIDER"
"${COMPOSE[@]}" -f "$COMPOSE_FILE" up --build -d

printf 'Waiting for the storefront'
for _ in $(seq 1 90); do
  if curl -fsS http://localhost:8080/ >/dev/null 2>&1 \
    && curl -fsS http://localhost:8080/api/catalog/categories >/dev/null 2>&1; then
    printf ' ready.\n\n'
    printf 'TinyCars: http://localhost:8080\n'
    printf 'Admin:    http://localhost:8080/admin  (token: tinycars)\n'
    printf 'Logs:     ./run-local.sh --logs\n'
    printf 'Stop:     ./run-local.sh --down\n'
    exit 0
  fi
  printf '.'
  sleep 2
done

printf '\nTinyCars did not become ready. Recent logs:\n' >&2
"${COMPOSE[@]}" -f "$COMPOSE_FILE" logs --tail=100 >&2
exit 1
