# infra/

Infrastructure-as-code and edge configs for `Image-Toolkit`.

| Directory | Scope | Purpose |
| --- | --- | --- |
| [`global/`](global/) | External / public-facing | Deploy & host tooling (docker, k8s, helm, terraform, ansible) |
| [`private/`](private/) | Internal / developer-only | Local developer tooling |
| [`cloud/`](cloud/) | Managed cloud hosts | AWS / Azure / Cloudflare / Firebase / Google Cloud / Oracle / Serverless configs |
| [`server/`](server/) | Edge / reverse-proxy | Standalone nginx and Envoy configs |

## global/ (external)

| Directory | What it does |
| --- | --- |
| `global/docker/` | Build + run via Docker Compose / Dockerfiles |
| `global/k8s/` | Kubernetes manifests (base + overlays) |
| `global/helm/` | Helm charts |
| `global/terraform/` | Cloud provisioning |
| `global/ansible/` | Host configuration playbooks |

## cloud/

Managed cloud deploy configs (when present):

| Directory | Config | Target |
| --- | --- | --- |
| `aws/` | `cfn-template.yaml` | CloudFormation / SAM serverless stack |
| `azure-pipelines/` | `azure-pipelines.yml` | Azure DevOps CI/CD |
| `cloudflare/` | `wrangler.toml` | Workers + Queues + R2 + D1 heavy-request worker |
| `firebase/` | `firebase_config.js` | Firebase modular SDK init |
| `gcd/` | `cloud-run-service.yaml` | Google Cloud Run (Knative) heavy-request worker — **cloud-offload PoC target** |
| `oracle/` | `oci-container-instance.tf` | OCI Container Instance (Terraform), GPU shapes for generation |
| `serverless/` | `serverless.yml` | Serverless Framework |

The `cloudflare/` / `gcd/` / `oracle/` workers back the Cloud Compute Offload
feature (roadmap `new_features.md` §4.21) — the desktop app enqueues a heavy
request (extraction, DL generation) and the selected provider's worker runs it.

## private/ (internal)

Developer-only experiments (when present).

## server/

| Directory | What it does |
| --- | --- |
| `server/nginx/` | Standalone nginx reverse-proxy / static site configs |
| `server/proxy/` | Envoy proxy configs |
