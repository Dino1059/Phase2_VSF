# d086 deploy recipe (do not touch t086)

**SHA to deploy:** `3a83bc1` on `v5-integration`  
**Dest:** `/opt/datatrust-os-dev` · compose project `datatrust-dev` · ports **3001/8001**  
**Preserve:** `.env`, `docker-compose.override.yml`, `data_new/db/`, `.cf-tunnel-token`  
**Never:** `docker compose` without `-p datatrust-dev`, `docker system prune -a`, wrangler, t086 `/opt/datatrust-os`

## Host facts (2026-08-27)

| | StartedAt | Image |
|---|---|---|
| t086 backend | `2026-08-25T08:32:58Z` | datatrust-os-backend |
| t086 frontend | `2026-08-25T08:36:50Z` | datatrust-os-frontend |
| t086 cloudflared | `2026-08-16T16:30:41Z` | must stay |
| d086 backend | `2026-08-21T11:18:23Z` | **stale** 2.36G (`COPY data_new`) |
| d086 frontend | `2026-08-21T18:16:49Z` | stale |
| dest SHA file | `731c55c` (rsync landed; rebuild failed on disk) |
| disk | 80G loop, **1.4G free**, build cache 5.1G |

## Safe path (no backend image rebuild)

1. `git archive` only `src frontend landing_data eval/rca_benchmark schemas scripts` + Dockerfiles into dest. **Exclude** `data_new/db`, `.env`, override.
2. Patch **server-only** override bind-mounts (keep 8001/3001 + `cloudflared` profile `do-not-start`):

```yaml
services:
  backend:
    ports: !override
      - "8001:8000"
    volumes:
      - ./fixtures:/app/fixtures:ro
      - ./src:/app/src
      - ./landing_data:/app/landing_data:ro
      - ./eval:/app/eval:ro
      - ./schemas:/app/schemas:ro
      - ./scripts:/app/scripts:ro
  frontend:
    ports: !override
      - "3001:80"
  cloudflared:
    profiles:
      - do-not-start
```

3. `docker compose -p datatrust-dev up -d --no-build --no-deps backend`
4. If backend crash-loops on DuckDB WAL replay (`WriteAheadLogReplayer`): **stop `datatrust-dev-backend-1` only**, `rm` **`data_new/db/vingroup_pilot.db.wal` only** (never the `.db`), then step 3 again. Native abort skips the Python WAL handler.
5. Frontend: prefer `docker cp` of prebuilt `frontend/dist` into `datatrust-dev-frontend-1` if disk is tight (do not pull `node:20-slim`). Else `docker compose -p datatrust-dev build frontend && up -d --no-deps frontend`.
6. Confirm t086 StartedAt **unchanged**.
7. If frontend build dies on disk: `docker builder prune -f` (not `-a`, not `system prune`).

2026-08-27: dest SHA `3a83bc1`. API 502 was WAL crash-loop; recovered via step 4. Frontend last-modified 26 Aug 22:24 GMT (`7070309` stamp). t086 frozen.
