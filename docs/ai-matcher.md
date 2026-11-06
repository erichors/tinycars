# "Find my car": the AI matcher

Shoppers click **Find my car** in the header, describe themselves in a sentence ("outdoorsy, a bit loud, loves the 70s"), and a model picks one TinyCar for them with a one-line reason. The result pops up with the car, its price, and Add to cart / View details.

## How it works

```
browser ──POST /api/catalog/match──▶ storefront ──▶ catalog (Python) ──Converse──▶ Amazon Bedrock (Claude Haiku)
                                                         │
                                                         └── keyword matcher (fallback / default, no cloud)
```

- `services/catalog/matcher.py` sends the shopper's text (capped at 300 characters) plus the 72-car catalog as a compact list, and asks for JSON `{"sku", "reason"}`.
- The answer is only accepted if the SKU exists in the catalog. Anything else (bad JSON, an invented SKU, "ignore your instructions" text, throttling, timeouts, missing permissions) falls back to the local keyword matcher. The shopper always gets a car.
- The shopper's text is never logged; the `ai match` log line records provider, model, latency, token counts, fallback reason and the chosen SKU.

| Setting (Helm) | Default | Meaning |
|---|---|---|
| `ai.matcher.provider` | `keyword` | `keyword` runs anywhere with no cloud; `bedrock` calls the model |
| `ai.matcher.modelId` | `us.anthropic.claude-haiku-5-5` | Bedrock model or inference-profile ID |
| `ai.matcher.region` | `us-east-1` | Bedrock region |
| `ai.serviceAccount.name` | `tinycars-catalog` | Service account the catalog pod runs as |
| `ai.serviceAccount.annotations` | `{}` | Only for IRSA: `eks.amazonaws.com/role-arn: ...` |

The `us.` inference profile keeps requests in US regions. `global.anthropic.claude-haiku-5-5` also exists if you prefer extra capacity over data residency.

## Turn on Bedrock (EKS)

Uses the variables from [install-eks.md](install-eks.md) (`AWS_REGION`, `CLUSTER`, `ACCOUNT`).

**1. Check model access** (from your laptop):

```bash
aws bedrock-runtime converse --region us-east-1 --model-id us.anthropic.claude-haiku-5-5 \
  --messages '[{"role":"user","content":[{"text":"Reply with one word: ready"}]}]' \
  --query "output.message.content[0].text" --output text
```

**2. Create an IAM policy** that allows only this model. Cross-region inference profiles need permission on the profile and on the underlying model in every region the profile can route to, hence the `*` region on the foundation-model ARN.

```bash
cat > /tmp/tinycars-bedrock.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Action": ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"],
    "Resource": [
      "arn:aws:bedrock:*:${ACCOUNT}:inference-profile/us.anthropic.claude-haiku-5-5",
      "arn:aws:bedrock:*::foundation-model/anthropic.claude-haiku-5-5"
    ]
  }]
}
EOF
aws iam create-policy --policy-name TinyCarsBedrockInvoke --policy-document file:///tmp/tinycars-bedrock.json
```

**3. Give the catalog pod that role with EKS Pod Identity** (no keys in the cluster, no annotation needed):

```bash
eksctl create addon --cluster $CLUSTER --region $AWS_REGION --name eks-pod-identity-agent
eksctl create podidentityassociation --cluster $CLUSTER --region $AWS_REGION \
  --namespace tinycars --service-account-name tinycars-catalog \
  --role-name tinycars-catalog-bedrock \
  --permission-policy-arns arn:aws:iam::${ACCOUNT}:policy/TinyCarsBedrockInvoke
```

Prefer IRSA? Create the role with `eksctl create iamserviceaccount ... --role-only` and set `--set-string ai.serviceAccount.annotations."eks\.amazonaws\.com/role-arn"=arn:aws:iam::${ACCOUNT}:role/<role>`.

**4. Switch the provider on:**

```bash
helm upgrade tinycars deploy/helm/tinycars -n tinycars --reuse-values --set ai.matcher.provider=bedrock
kubectl -n tinycars rollout restart deploy/catalog
```

**5. Verify.** Use Find my car in the store; the result says "Matched by Claude on Amazon Bedrock". In the logs:

```bash
kubectl -n tinycars logs deploy/catalog | grep '"ai match"' | tail -n 3
```

You want `"provider": "bedrock"`, `"fallback": false` and token counts. `"fallback": true` with an `error` such as `AccessDeniedException` means step 2 or 3 is not in effect yet (restart the pod after creating the association).

Switching back is `--set ai.matcher.provider=keyword`.

## What it adds to observability

- **Traces:** the OTel Operator's Python agent instruments botocore, so the Bedrock call appears as a client span inside the `/match` request (browser click → storefront → catalog → Bedrock). Newer instrumentation versions add GenAI attributes (`gen_ai.*`, model and token usage); check which ones arrive in your backend.
- **Logs:** one `event_type=ai.match` line per request with `provider`, `model`, `fallback`, `error`, `latency_ms`, `input_tokens`, `output_tokens`, `sku`. Fallbacks are logged at WARNING.
- **Problem pattern `ai_matcher_slowdown`** (admin panel, group "AI"): adds 0.8 s × level of model latency; from level 3 calls are throttled and the keyword fallback answers. Good for showing a dependency slowdown and graceful degradation side by side.

## Cost

One match is roughly 1,000 input tokens (the catalog list) and about 40 output tokens. On Haiku that is a fraction of a cent per match; the loadgen does not call the matcher, so cost only comes from people using the button.
