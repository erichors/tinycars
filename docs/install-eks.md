# Installing TinyCars on Amazon EKS

End-to-end install: EKS cluster, images in ECR, OpenTelemetry Operator, Bindplane collectors, the TinyCars chart, and the store VM. Budget about 45 minutes. Everything is vendor-neutral; Dynatrace, Grafana or any other destination is added later in the Bindplane UI.

> Status: the Python and Node services were tested end to end in a sandbox. The Java and .NET builds, Docker builds, Helm chart and cluster install have **not** been run yet. If a step fails, the error normally points at the fix. Please open an issue or PR with what you changed.

## 0. Prerequisites

| Tool | Check |
|---|---|
| AWS CLI v2, logged in to the target account | `aws sts get-caller-identity` |
| `eksctl` 0.170+ | `eksctl version` |
| `kubectl` within one minor version of the cluster | `kubectl version --client` |
| `helm` 3.12+ | `helm version` |
| `docker` with buildx | `docker buildx version` |
| Bindplane Cloud account | you can log in and create configurations |

Set variables once and reuse them in every step:

```bash
export AWS_REGION=us-east-1
export CLUSTER=tinycars
export ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
export REGISTRY=${ACCOUNT}.dkr.ecr.${AWS_REGION}.amazonaws.com/    # trailing slash matters
export TAG=1.0.0
export ADMIN_TOKEN='choose-something-better-than-tinycars'
```

Approximate cost: 2 x m5.xlarge (about $0.38/h together) plus an ELB, EBS and the VM. Delete everything when you are done (step 10).

## 1. Create the cluster

```bash
eksctl create cluster \
  --name $CLUSTER --region $AWS_REGION \
  --node-type m5.xlarge --nodes 2 --managed \
  --with-oidc

kubectl get nodes        # 2 nodes Ready
```

Already have a cluster? Skip this, point `kubectl` at it (`aws eks update-kubeconfig --name <cluster> --region $AWS_REGION`) and make sure steps 1a and 1b are satisfied.

### 1a. EBS CSI driver (required for the Postgres volume)

EKS 1.23+ does not provision EBS volumes unless this add-on is installed. Without it the Postgres pod stays `Pending` with an unbound PVC.

```bash
eksctl create iamserviceaccount \
  --name ebs-csi-controller-sa --namespace kube-system \
  --cluster $CLUSTER --region $AWS_REGION \
  --role-name ${CLUSTER}-ebs-csi \
  --attach-policy-arn arn:aws:iam::aws:policy/service-role/AmazonEBSCSIDriverPolicy \
  --approve --role-only

eksctl create addon --name aws-ebs-csi-driver --cluster $CLUSTER --region $AWS_REGION \
  --service-account-role-arn arn:aws:iam::${ACCOUNT}:role/${CLUSTER}-ebs-csi --force

kubectl get storageclass     # make sure one is marked (default), usually gp2
```

If no class is default, either mark one (`kubectl patch storageclass gp2 -p '{"metadata":{"annotations":{"storageclass.kubernetes.io/is-default-class":"true"}}}'`) or install with `--set postgres.persistence.storageClass=<name>`.

### 1b. Load balancer

The storefront uses a `Service` of type `LoadBalancer`. The in-tree AWS provisioner creates a Classic ELB, which is fine for a demo. To restrict who can reach it, see step 7.

## 2. Build and push images

```bash
for s in storefront catalog cart-checkout inventory loadgen; do
  aws ecr create-repository --region $AWS_REGION --repository-name tinycars-$s >/dev/null 2>&1 || true
done
aws ecr get-login-password --region $AWS_REGION | \
  docker login --username AWS --password-stdin ${ACCOUNT}.dkr.ecr.${AWS_REGION}.amazonaws.com

# Default is linux/amd64. For Graviton nodes use PLATFORM=linux/arm64.
REGISTRY=$REGISTRY TAG=$TAG ./deploy/build-push.sh
```

The Java image builds with Maven inside Docker and the .NET image with the SDK image, so no local JDK or .NET is needed. Building on an Apple Silicon laptop for amd64 nodes works but is slow (QEMU); a CI runner or an EC2 builder is faster.

Check: `aws ecr describe-images --repository-name tinycars-storefront --query 'imageDetails[].imageTags'`.

## 3. Install the OpenTelemetry Operator

The Operator injects the language agent into pods at start-up (Java, Node.js, Python, .NET) so the app code stays free of OTel SDKs.

```bash
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/latest/download/cert-manager.yaml
kubectl -n cert-manager rollout status deploy/cert-manager-webhook --timeout=180s

helm repo add open-telemetry https://open-telemetry.github.io/opentelemetry-helm-charts
helm repo update
helm install opentelemetry-operator open-telemetry/opentelemetry-operator \
  -n opentelemetry-operator-system --create-namespace \
  --set manager.collectorImage.repository=otel/opentelemetry-collector-k8s

kubectl -n opentelemetry-operator-system rollout status deploy/opentelemetry-operator --timeout=180s
```

Check: `kubectl get crd instrumentations.opentelemetry.io` exists.

## 4. Bindplane collectors

Do this before installing the app so the OTLP endpoint exists.

1. In Bindplane Cloud, create the configurations `tinycars-eks-node`, `tinycars-eks-cluster` and `tinycars-vm-stores`, exactly as described in [bindplane-wiring.md](bindplane-wiring.md) sections 1-2.
2. Use **Install Agent** in the Bindplane UI for the Kubernetes platform. It gives you a `kubectl apply` manifest (or Helm values) that carries your Bindplane secret key. Run it once for the Node configuration and once for the Cluster configuration.
3. Wait for the collectors and confirm they are connected:

```bash
kubectl get pods -A | grep -i -E 'bindplane|observiq'
```

4. Find the **Node** collector's OTLP service and note its namespace and name:

```bash
kubectl get svc -A | grep -i -E 'bindplane|observiq'
```

Your OTLP/HTTP endpoint is `http://<service>.<namespace>.svc.cluster.local:4318`. If the Node collector is a DaemonSet with no Service, add a ClusterIP Service in front of it that selects its pods and exposes 4318 (and 4317). Confirm the OTLP source on the configuration listens on `0.0.0.0` (not `127.0.0.1`).

Quick reachability test from inside the cluster:

```bash
kubectl run otlp-check --rm -it --restart=Never --image=curlimages/curl -- \
  curl -s -o /dev/null -w '%{http_code}\n' -X POST -H 'Content-Type: application/json' -d '{}' \
  http://<service>.<namespace>.svc.cluster.local:4318/v1/traces
```

`200` means the endpoint works.

## 5. Install TinyCars

```bash
export OTLP_ENDPOINT=http://<service>.<namespace>.svc.cluster.local:4318

helm install tinycars deploy/helm/tinycars \
  --namespace tinycars --create-namespace \
  --set image.registry=$REGISTRY \
  --set image.tag=$TAG \
  --set otel.endpoint=$OTLP_ENDPOINT \
  --set otel.environment=demo \
  --set adminToken=$ADMIN_TOKEN

kubectl -n tinycars get pods -w
```

Expected: `postgres` and `redis` first, then `catalog`, `inventory`, `cart-checkout`, `storefront` and `loadgen`. Instrumented pods show an init container (`opentelemetry-auto-instrumentation-*`). Java and .NET can take 60-90 seconds to become ready. The first Postgres start loads 66 cars, 264 stock rows and about 420 historic orders.

Get the store address:

```bash
kubectl -n tinycars get svc storefront -o jsonpath='{.status.loadBalancer.ingress[0].hostname}{"\n"}'
```

ELB DNS can take a couple of minutes to resolve. No LoadBalancer? Use `kubectl -n tinycars port-forward svc/storefront 8080:80` and open http://localhost:8080.

Useful values (see `deploy/helm/tinycars/values.yaml`): `otel.instrumentation.create=false` if an `Instrumentation` resource already exists, `otel.instrumentation.enabled=false` to deploy without injection, `services.storefront.serviceType=ClusterIP` to skip the ELB, `postgres.persistence.enabled=false` for throw-away data.

## 6. Verify

```bash
kubectl -n tinycars get instrumentation
kubectl -n tinycars get pods -o wide
kubectl -n tinycars logs deploy/storefront | tail
kubectl -n tinycars logs deploy/loadgen | tail
```

Then:

- Open the store, click a car, add it to the cart and check out.
- Click the faint wrench in the logo (or go to `/admin`), enter `$ADMIN_TOKEN`, and set load to **Normal**.
- In Bindplane open each configuration and use **Live Preview**. You should see traces from five services, container logs and Kubernetes metrics within about a minute.
- Flip a problem pattern (for example `catalog_search_slowdown` at level 2) and watch search latency rise. All patterns are in [patterns-and-siem.md](patterns-and-siem.md).

## 7. Lock down access

The admin panel is protected only by the token, and the default load balancer is open to the internet.

```bash
kubectl -n tinycars patch svc storefront -p '{"spec":{"loadBalancerSourceRanges":["<your-cidr>/32"]}}'
```

Note that a later `helm upgrade` can overwrite this patch; re-apply it afterwards.

Always change `adminToken`. Use `kubectl port-forward` instead of a public ELB if you do not need external access.

## 8. The store VM (Boston, Chicago, London)

Launch an Ubuntu 22.04 EC2 instance (t3.small is enough) in the same VPC, and:

1. Security group: SSH from your IP only. Egress open. The VM needs outbound HTTP to the storefront and outbound HTTPS to Bindplane.
2. The storefront ELB must accept traffic from the VM. If you restricted source ranges in step 7, add the VM's public IP or NAT IP.
3. Copy the agent and install it:

```bash
scp -r store-agent ubuntu@<vm-ip>:~
ssh ubuntu@<vm-ip>
cd store-agent
sudo STOREFRONT_URL=http://<storefront-elb-hostname> ADMIN_TOKEN=$ADMIN_TOKEN ./install.sh
# add TINYCARS_OTEL=1 to also emit POS traces
```

4. Check it is running and writing logs:

```bash
systemctl status tinycars-store-agent
ls /var/log/tinycars/{boston,chicago,london}/
tail -f /var/log/tinycars/boston/*.log
```

5. In Bindplane, create the **Linux** install command for `tinycars-vm-stores`, run it on the VM, and point the File source at `/var/log/tinycars/*/*.log` ([bindplane-wiring.md](bindplane-wiring.md) section 4).

The SIEM-style patterns (failed-login flood, file-integrity change, impossible travel and others) are toggled from the admin panel and only write log text with RFC 5737 test IPs. They never touch SSH, scan networks or modify system files.

## 9. Add destinations

In the Bindplane UI add Dynatrace, Grafana, Datadog, Splunk, Google Cloud or anything else as a destination on the three configurations, then roll out. Nothing in this repo changes. Dynatrace uses OTLP/HTTP with a token that has `metrics.ingest`, `logs.ingest` and `openTelemetryTrace.ingest`. Use the `.live.` environment host, not `.apps.`.

## 10. Upgrade, reset and tear down

```bash
# Change a setting
helm upgrade tinycars deploy/helm/tinycars -n tinycars --reuse-values --set services.storefront.cpuLimit=500m

# New images
REGISTRY=$REGISTRY TAG=1.0.1 ./deploy/build-push.sh
helm upgrade tinycars deploy/helm/tinycars -n tinycars --reuse-values --set image.tag=1.0.1

# Reset data (Postgres reseeds on next start)
helm uninstall tinycars -n tinycars
kubectl -n tinycars delete pvc --all
helm install ... (step 5)

# Remove everything
helm uninstall tinycars -n tinycars
kubectl delete ns tinycars
eksctl delete cluster --name $CLUSTER --region $AWS_REGION
for s in storefront catalog cart-checkout inventory loadgen; do
  aws ecr delete-repository --repository-name tinycars-$s --force --region $AWS_REGION; done
```

Terminate the VM and delete its security group too. Check the EC2 console for leftover EBS volumes and load balancers.

## Troubleshooting

| Symptom | Likely cause and fix |
|---|---|
| `postgres` Pending, PVC unbound | EBS CSI driver missing (step 1a) or no default StorageClass |
| `ImagePullBackOff` | Wrong `image.registry` (needs trailing `/`), ECR repo missing, wrong architecture (`PLATFORM`), or nodes lack ECR read permissions (the default eksctl node role has them) |
| Pod runs but no traces | `kubectl -n tinycars get instrumentation` is empty, Operator not ready, or the pod was created before the Instrumentation. Run `kubectl -n tinycars rollout restart deploy` |
| Traces missing, collector reachable | `otel.endpoint` wrong, or the OTLP source listens on localhost only. Re-run the curl check in step 4 |
| Operator webhook error on install | cert-manager not ready yet. Wait for `cert-manager-webhook`, then retry |
| `inventory` (.NET) has no traces | Image uses a Debian base on purpose (musl/Alpine breaks the injector). Do not switch to an Alpine base |
| Storefront ELB hostname does not resolve | Wait 2-3 minutes; check `kubectl -n tinycars describe svc storefront` for events |
| Admin panel rejects the token | Use the value passed to `adminToken` (default `tinycars`); check `kubectl -n tinycars get deploy storefront -o yaml \| grep -i token` |
| VM agent cannot reach storefront | Security group, source-range allow list, or wrong URL. `curl -s http://<elb>/healthz` from the VM |

More Bindplane-specific checks are in [bindplane-wiring.md](bindplane-wiring.md) section 8.
