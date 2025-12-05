## Action Board

### WS1: Data & Pipeline Hardening
- [x] Parquet + CSV/SQLite export
- [x] Inference optimization (`heapq.nsmallest`, haversine micro-opt)
- [x] Logging instead of prints; schema validation
- [ ] More edge-case tests (ties, missing zips, empty data, schema failure)

### WS2: API Layer (FastAPI)
- [x] Scaffold API with auth (bearer token), filters/pagination, stats, exports
- [ ] Add rate limiting and better auth integration (proxy-level if needed)
- [ ] Add request metrics/log redaction policy

### WS3: UI Layer (Streamlit)
- [ ] Point UI to API, cache datasets/filters, handle auth securely
- [ ] Precompute colors server-side and pass through API

### WS4: Ops/Infra
- [x] Dockerfile (api/ui/pipeline targets)
- [x] docker-compose.yml (api/ui/pipeline)
- [x] Proxy sample (Nginx)
- [ ] Harden proxy (TLS with Let’s Encrypt, stricter headers/policies)
- [ ] Add healthchecks/log rotation guidance
- [ ] Add backup script/cron guidance

### WS5: Process & Scheduling
- [ ] Add cron/systemd timer guidance for pipeline refresh
- [ ] Document SLAs (pipeline duration, API p95 latency, UI load)

### WS6: Documentation
- [ ] README/ARCHITECTURE/API/OPERATIONS/SECURITY/Sales Ops how-to stubs
