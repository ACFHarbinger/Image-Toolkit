# helm/

Helm chart packaging (mostly) of the same resources as `infra/global/k8s/base/`, for
teams that prefer `helm install` over `kubectl apply -k`. Pick one, don't run
both against the same cluster/namespace.

```bash
helm lint infra/global/helm/single-module-template
helm install single-module-template infra/global/helm/single-module-template -f infra/global/helm/single-module-template/values.yaml
```
