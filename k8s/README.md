# AutoScore on Kubernetes

One Deployment (the combined `ghcr.io/jkove94/autoscore` image), a PVC for job
storage, a Service, and an optional Ingress. Everything lands in the `autoscore`
namespace.

## Deploy

```bash
kubectl apply -k k8s/
kubectl -n autoscore rollout status deploy/autoscore
```

or `./run k8s` (apply + wait) / `./run k8s-down` (delete).

## Reach it

**Zero-config — port-forward:**

```bash
kubectl -n autoscore port-forward svc/autoscore 8000:8000
# open http://localhost:8000
```

**Ingress** (needs an ingress controller): edit `ingress.yaml` — set a real
`host` and your `ingressClassName` — then add the host to `/etc/hosts` pointing
at the ingress IP, or use real DNS. The proxy timeouts are already raised to
900s because `separate` / `analyze` / `omr` are long synchronous calls.

## Tuning

| What | Where |
|---|---|
| Image tag (pin instead of `:latest`) | `kustomization.yaml` → `images[].newTag` |
| Env (`STEM_FALLBACK`, `TORCH_DEVICE`, upload limit, YouTube …) | `configmap.yaml` |
| Storage size / class | `pvc.yaml` |
| CPU / memory | `deployment.yaml` → `resources` |

## Notes / limitations

- **Single replica.** Job files live on an RWO volume and separation/analysis run
  synchronously in the request. Scaling out needs an RWX volume (or object
  storage) **and** a job queue first — not wired up.
- **No CoreML / MPS** in-cluster (Linux). The librosa fallback works; for stem
  separation build the image with `--build-arg WITH_DEMUCS=1`, push it, and point
  `kustomization.yaml` at your tag (bump memory to ~4–6Gi).
- **Private image?** If you make the package private (or use another registry),
  create a pull secret and add `imagePullSecrets` to `deployment.yaml`:
  ```bash
  kubectl -n autoscore create secret docker-registry ghcr \
    --docker-server=ghcr.io --docker-username=<user> --docker-password=<token>
  ```
- **Storage class:** assumes a default StorageClass. Set `storageClassName` in
  `pvc.yaml` if your cluster has none.
