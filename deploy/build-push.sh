#!/usr/bin/env bash
# Build and push the five TinyCars images.
# Usage: REGISTRY=123456789012.dkr.ecr.us-east-1.amazonaws.com/ TAG=1.0.0 ./deploy/build-push.sh
# (REGISTRY must end with "/"; leave it empty to build locally only, e.g. for kind: kind load docker-image ...)
# For ECR, create the repos first:
#   for s in storefront catalog cart-checkout inventory loadgen; do aws ecr create-repository --repository-name tinycars-$s; done
#   aws ecr get-login-password | docker login --username AWS --password-stdin <account>.dkr.ecr.<region>.amazonaws.com
set -euo pipefail
cd "$(dirname "$0")/.."
REGISTRY="${REGISTRY:-}"
TAG="${TAG:-1.0.0}"
PLATFORM="${PLATFORM:-linux/amd64}"   # match your node architecture (use linux/arm64 for Graviton)

for svc in storefront catalog cart-checkout inventory loadgen; do
  img="${REGISTRY}tinycars-${svc}:${TAG}"
  echo ">> building $img"
  docker build --platform "$PLATFORM" -t "$img" "services/$svc"
  if [ -n "$REGISTRY" ]; then docker push "$img"; fi
done
echo "done. helm install tinycars deploy/helm/tinycars --set image.registry=${REGISTRY} --set image.tag=${TAG} ..."
