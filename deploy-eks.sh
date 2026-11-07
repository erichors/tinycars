#!/usr/bin/env bash
# Build and deploy TinyCars to an existing EKS cluster with Bedrock access.
# Collector modes: dynatrace (default), bindplane, or generic otel.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AWS_REGION="${AWS_REGION:-us-east-1}"
CLUSTER="${CLUSTER:-dynatrace-easytrade}"
NAMESPACE="${NAMESPACE:-tinycars}"
AWS_PROFILE="${AWS_PROFILE:-default}"
TAG="${TAG:-eks-$(date -u +%Y%m%d%H%M%S)}"
PLATFORM="${PLATFORM:-linux/amd64}"
NODE_ARCH="${PLATFORM##*/}"
COLLECTOR_MODE="${COLLECTOR_MODE:-dynatrace}"
if [[ -z "${BUILDX_BUILDER:-}" ]]; then
  BUILDX_BUILDER="tinycars-eks-${NODE_ARCH}"
  MANAGE_BUILDER=true
else
  MANAGE_BUILDER=false
fi
DYNAKUBE="${DYNAKUBE:-eks-bottlerocket-k8s-2025-10-27}"
ADMIN_TOKEN="${ADMIN_TOKEN:-$(openssl rand -hex 18)}"
POLICY_NAME="${POLICY_NAME:-TinyCarsBedrockInvoke}"
ROLE_NAME="${ROLE_NAME:-tinycars-catalog-bedrock}"

export AWS_PROFILE AWS_REGION

cleanup_builder() {
  if [[ "$MANAGE_BUILDER" == true ]]; then
    docker buildx rm "$BUILDX_BUILDER" >/dev/null 2>&1 || true
  fi
}
trap cleanup_builder EXIT

for command_name in aws docker kubectl helm openssl; do
  command -v "$command_name" >/dev/null || {
    echo "Missing required command: $command_name" >&2
    exit 1
  }
done

ACCOUNT="$(aws sts get-caller-identity --query Account --output text)"
REGISTRY="${ACCOUNT}.dkr.ecr.${AWS_REGION}.amazonaws.com/"
POLICY_ARN="arn:aws:iam::${ACCOUNT}:policy/${POLICY_NAME}"
ROLE_ARN="arn:aws:iam::${ACCOUNT}:role/${ROLE_NAME}"

echo ">> Selecting EKS cluster ${CLUSTER}"
aws eks update-kubeconfig --name "$CLUSTER" --region "$AWS_REGION" >/dev/null

case "$COLLECTOR_MODE" in
  dynatrace)
    OTLP_ENDPOINT="${OTLP_ENDPOINT:-http://telemetry-ingest.dynatrace.svc.cluster.local:4318}"
    INSTRUMENTATION_CREATE=false
    INSTRUMENTATION_ENABLED=false
    ;;
  bindplane|otel)
    if [[ -z "${OTLP_ENDPOINT:-}" ]]; then
      echo "OTLP_ENDPOINT is required when COLLECTOR_MODE=${COLLECTOR_MODE}." >&2
      echo "Example: OTLP_ENDPOINT=http://collector.namespace.svc.cluster.local:4318" >&2
      exit 1
    fi
    if ! kubectl get crd instrumentations.opentelemetry.io >/dev/null 2>&1; then
      echo "The OpenTelemetry Operator is required for ${COLLECTOR_MODE} mode." >&2
      echo "Install it first; see docs/collectors.md." >&2
      exit 1
    fi
    INSTRUMENTATION_CREATE=true
    INSTRUMENTATION_ENABLED=true
    ;;
  *)
    echo "COLLECTOR_MODE must be dynatrace, bindplane, or otel (got: ${COLLECTOR_MODE})." >&2
    exit 1
    ;;
esac

if [[ "$OTLP_ENDPOINT" != http://* && "$OTLP_ENDPOINT" != https://* ]]; then
  echo "OTLP_ENDPOINT must be an http:// or https:// endpoint." >&2
  exit 1
fi

echo ">> Preparing native ${NODE_ARCH} builder in EKS"
if ! docker buildx inspect "$BUILDX_BUILDER" >/dev/null 2>&1; then
  docker buildx create --name "$BUILDX_BUILDER" --driver kubernetes \
    --platform "$PLATFORM" --driver-opt namespace=kube-system \
    --driver-opt "nodeselector=kubernetes.io/arch=${NODE_ARCH}" >/dev/null
fi
docker buildx inspect "$BUILDX_BUILDER" --bootstrap >/dev/null

echo ">> Creating ECR repositories when missing"
for service_name in storefront catalog cart-checkout inventory loadgen; do
  aws ecr describe-repositories --repository-names "tinycars-${service_name}" >/dev/null 2>&1 || \
    aws ecr create-repository --repository-name "tinycars-${service_name}" >/dev/null
done
aws ecr get-login-password | docker login --username AWS --password-stdin "${REGISTRY%/}"

echo ">> Building and pushing TinyCars ${TAG} (${PLATFORM})"
REGISTRY="$REGISTRY" TAG="$TAG" PLATFORM="$PLATFORM" BUILDX_BUILDER="$BUILDX_BUILDER" \
  "$ROOT_DIR/deploy/build-push.sh"
cleanup_builder
MANAGE_BUILDER=false

echo ">> Configuring least-privilege Bedrock access"
POLICY_DOCUMENT="$(printf '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Action":["bedrock:InvokeModel","bedrock:InvokeModelWithResponseStream"],"Resource":["arn:aws:bedrock:*:%s:inference-profile/us.anthropic.claude-haiku-5-5","arn:aws:bedrock:*::foundation-model/anthropic.claude-haiku-5-5"]}]}' "$ACCOUNT")"
if ! aws iam get-policy --policy-arn "$POLICY_ARN" >/dev/null 2>&1; then
  aws iam create-policy --policy-name "$POLICY_NAME" --policy-document "$POLICY_DOCUMENT" >/dev/null
fi

TRUST_DOCUMENT='{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"pods.eks.amazonaws.com"},"Action":["sts:AssumeRole","sts:TagSession"]}]}'
if ! aws iam get-role --role-name "$ROLE_NAME" >/dev/null 2>&1; then
  aws iam create-role --role-name "$ROLE_NAME" --assume-role-policy-document "$TRUST_DOCUMENT" >/dev/null
fi
aws iam attach-role-policy --role-name "$ROLE_NAME" --policy-arn "$POLICY_ARN"

if ! aws eks describe-addon --cluster-name "$CLUSTER" --addon-name eks-pod-identity-agent >/dev/null 2>&1; then
  aws eks create-addon --cluster-name "$CLUSTER" --addon-name eks-pod-identity-agent >/dev/null
fi
aws eks wait addon-active --cluster-name "$CLUSTER" --addon-name eks-pod-identity-agent

ASSOCIATION_ID="$(aws eks list-pod-identity-associations --cluster-name "$CLUSTER" \
  --query "associations[?namespace=='${NAMESPACE}' && serviceAccount=='tinycars-catalog'].associationId | [0]" \
  --output text)"
if [[ -z "$ASSOCIATION_ID" || "$ASSOCIATION_ID" == "None" ]]; then
  aws eks create-pod-identity-association --cluster-name "$CLUSTER" \
    --namespace "$NAMESPACE" --service-account tinycars-catalog --role-arn "$ROLE_ARN" >/dev/null
fi

echo ">> Preparing namespace for ${COLLECTOR_MODE} collector mode"
kubectl create namespace "$NAMESPACE" --dry-run=client -o yaml | kubectl apply -f - >/dev/null
if [[ "$COLLECTOR_MODE" == dynatrace ]]; then
  kubectl label namespace "$NAMESPACE" \
    "dynakube.internal.dynatrace.com/instance=${DYNAKUBE}" --overwrite >/dev/null
else
  # Avoid injecting both OneAgent and OpenTelemetry language agents.
  kubectl label namespace "$NAMESPACE" \
    dynakube.internal.dynatrace.com/instance- >/dev/null 2>&1 || true
fi

echo ">> Installing TinyCars"
helm upgrade --install tinycars "$ROOT_DIR/deploy/helm/tinycars" \
  --namespace "$NAMESPACE" \
  --set-string "image.registry=${REGISTRY}" \
  --set-string "image.tag=${TAG}" \
  --set-string "nodeSelector.kubernetes\\.io/arch=${NODE_ARCH}" \
  --set-string "collector.type=${COLLECTOR_MODE}" \
  --set-string "otel.endpoint=${OTLP_ENDPOINT}" \
  --set "otel.instrumentation.create=${INSTRUMENTATION_CREATE}" \
  --set "otel.instrumentation.enabled=${INSTRUMENTATION_ENABLED}" \
  --set ai.matcher.provider=bedrock \
  --set postgres.persistence.enabled=false \
  --set services.storefront.serviceType=ClusterIP \
  --set-string "adminToken=${ADMIN_TOKEN}" \
  --wait --timeout 10m

echo
echo "TinyCars is ready in EKS."
echo "Collector mode: ${COLLECTOR_MODE} (${OTLP_ENDPOINT})"
echo "Admin token: ${ADMIN_TOKEN}"
echo "Run: kubectl -n ${NAMESPACE} port-forward svc/storefront 8080:80"
echo "Open: http://localhost:8080 (wrench opens /admin)"
