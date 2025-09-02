# Trino Production Readiness Runbook ✅

Generated: 2025-09-02 20:07:14

This runbook is a **checklist** to verify that a production Trino cluster is reliable, secure, and maintainable.  
Use it before go-live and as a recurring health audit.

---

## 1. Reliability & Stability

- [ ] Coordinator isolated (`node-scheduler.include-coordinator=false`)
- [ ] Spill enabled (`spill-enabled=true`)
- [ ] Spill path on fast disk (`spiller-spill-path=/nvme/trino-spill`)
- [ ] Max spill per node set (50–200 GB)
- [ ] Memory guardrails set:
  - [ ] `query.max-memory-per-node`
  - [ ] `query.max-total-memory-per-node`
  - [ ] `memory.heap-headroom-per-node`
- [ ] Resource groups configured (ETL / BI / Adhoc lanes)

---

## 2. Performance & Capacity

- [ ] File formats: Iceberg/Parquet + ZSTD
- [ ] Small file compaction jobs scheduled
- [ ] S3/HDFS connections tuned (`hive.s3.max-connections`)
- [ ] Concurrency limits set & monitored
- [ ] Benchmark performed after each upgrade

---

## 3. Security & Governance

- [ ] TLS enabled for all client & worker traffic
- [ ] Authentication configured (LDAP/OIDC/OAuth)
- [ ] Authorization enforced (Ranger / OPA / file rules)
- [ ] Row/column masking applied for sensitive data
- [ ] Audit logs enabled (event listener → DB → SIEM)

---

## 4. Observability & Monitoring

- [ ] Prometheus + Grafana dashboards deployed
- [ ] Key metrics:
  - [ ] Query concurrency (running/queued)
  - [ ] Spill & exchange bytes
  - [ ] Worker heap/GC/CPU
  - [ ] Catalog latency (HMS/REST)
- [ ] Logs centralized (JSON → ELK/CloudWatch/Datadog)
- [ ] Alerts defined:
  - [ ] Query fail % > threshold
  - [ ] Coordinator heap > 85%
  - [ ] Spill disk usage > 80%
  - [ ] Worker count mismatch

---

## 5. Operations & Change Management

- [ ] Rolling/blue-green upgrade playbook documented
- [ ] Runbook for worker node loss tested
- [ ] Capacity planning in place (3–6 month forecast)
- [ ] Backup & DR:
  - [ ] Hive Metastore / Iceberg REST DB
  - [ ] Ranger/OPA configs
  - [ ] Metrics DB
- [ ] DR restore drill performed in last 3 months

---

## 6. SQL & Workload Hygiene

- [ ] SELECT * discouraged / blocked on large tables
- [ ] Broadcast vs. partitioned joins guidance shared
- [ ] Runaway query kill automation in place
- [ ] BI dashboards optimized with extracts/prepared queries

---

## 7. Version & Dependency Management

- [ ] Cluster within 3–6 months of latest Trino release
- [ ] Connector upgrades tested in staging
- [ ] JVM pinned to supported LTS (Java 21+)
- [ ] OS/security patches applied regularly

---

## 8. Day-2 Operations

- Weekly health check:
  - [ ] Failed queries by error code
  - [ ] Top memory-heavy queries
  - [ ] Peak concurrency trend
  - [ ] Catalog latency
- Monthly review:
  - [ ] Iceberg file size distribution & compaction
  - [ ] Spill disk usage
  - [ ] Resource group fairness
- Quarterly drills:
  - [ ] Upgrade & rollback test
  - [ ] DR restore test
  - [ ] Secret/key rotation

---