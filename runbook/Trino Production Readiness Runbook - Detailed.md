# Trino Production Readiness Runbook Detailed ✅

This runbook is a **detailed checklist** to ensure a production Trino cluster is reliable, secure, and maintainable.  
Each item includes configuration examples, commands, and verification steps.

---

## 1. Reliability & Stability

- [ ] **Coordinator isolation**  
  Config: `node-scheduler.include-coordinator=false`  
  Why: Keeps coordinator lightweight.  
  Check: `SELECT * FROM system.runtime.nodes;` → coordinator has no splits.

- [ ] **Enable spill**  
  Config:  
  ```ini
  spill-enabled=true
  spiller-spill-path=/nvme/trino-spill
  max-spill-per-node=200GB
  ```  
  Why: Queries larger than memory succeed.  
  Verify: `jmx:trino.execution:name=TaskExecutor.spilledDataSize` > 0 when spilling.

- [ ] **Memory guardrails**  
  Config:  
  ```ini
  query.max-memory-per-node=8GB
  query.max-total-memory-per-node=12GB
  memory.heap-headroom-per-node=4GB
  ```  
  Verify: `system.runtime.queries` → `memory_reservation` < limits.

- [ ] **Resource groups**  
  Config: `etc/resource-groups.json`  
  Example: ETL 40%, BI 20%, Ad-hoc 10%.  
  Verify: `system.runtime.queries` → correct `resource_group_id`.

---

## 2. Performance & Capacity

- [ ] **File formats**  
  Use Iceberg + Parquet + ZSTD.  
  Compact small files daily:  
  ```sql
  CALL system.rewrite_table('iceberg.prod.large_table', 'REWRITE_DATA');
  ```

- [ ] **S3/HDFS connections**  
  Config:  
  ```ini
  hive.s3.max-connections=500
  hive.s3.connect-timeout=2s
  hive.s3.socket-timeout=2m
  ```  
  Verify: `jmx:hive:name=HiveS3FileSystem.numConnections` < max.

- [ ] **Concurrency limits**  
  Hard limit via resource groups.  
  Rule of thumb: 5–10 queries per worker.

- [ ] **Benchmarking**  
  Run TPC-DS scale 100 in staging after upgrades.  
  Compare p95 latency vs baseline.

---

## 3. Security & Governance

- [ ] **TLS**  
  Config:  
  ```ini
  http-server.https.enabled=true
  http-server.https.port=8443
  http-server.https.keystore.path=/etc/trino/keystore.jks
  ```  
  Verify: `curl -vk https://worker:8443/v1/info` works.

- [ ] **Authentication**  
  LDAP config:  
  ```ini
  password-authenticator.name=ldap
  ldap.url=ldaps://ldap.example.com:636
  ldap.user-bind-pattern=uid=${USER},ou=people,dc=example,dc=com
  ```  
  Verify: `system.runtime.queries` → `principal` populated.

- [ ] **Authorization**  
  Start: file-based rules.  
  Enterprise: Ranger/OPA.  
  Verify: unauthorized user gets `Access Denied`.

- [ ] **Audit**  
  Event listener → DB.  
  Verify: `trino_queries` table updates per query.

---

## 4. Observability & Monitoring

- [ ] **Prometheus + Grafana**  
  Metrics to track:  
  - QPS (`trino_execution_query_started_total`)  
  - Running vs queued (`trino_execution_query_queued_total`)  
  - Spill bytes (`trino_execution_spilled_bytes_total`)  
  - Exchange bytes (`trino_execution_exchange_bytes_total`)  

- [ ] **Centralized logs**  
  Config: `log.format=json`  
  Ship to ELK/CloudWatch.  

- [ ] **Alerts**  
  - Coordinator heap > 85%  
  - Spill disk > 80%  
  - Query fail % > 5% in 10 min  
  - Worker count mismatch

---

## 5. Operations & Change Management

- [ ] **Upgrade playbook**  
  1. Upgrade coordinator first.  
  2. Roll workers one by one.  
  3. Monitor regressions.  
  Rollback: keep previous tarball.

- [ ] **Worker node loss**  
  Replace in autoscaler.  
  Reattach/mount spill disk.  
  Verify via `system.runtime.nodes`.

- [ ] **Backups**  
  - Hive Metastore DB daily snapshot  
  - Ranger/OPA configs weekly export  
  - Monthly restore test in staging

---

## 6. SQL & Workload Hygiene

- [ ] **Ban SELECT ***  
  Enforce via views or query rewrite hooks.

- [ ] **Joins**  
  - Broadcast: small dim + big fact  
  - Partitioned: big vs big with spill

- [ ] **Runaway query kill**  
  Script to kill >1h or >100GB queries:  
  ```sql
  CALL system.runtime.kill_query('<query_id>', 'reason');
  ```

---

## 7. Version & Dependency Management

- [ ] **Stay close to upstream**  
  Upgrade every ~3 months. Don’t lag >6 months.

- [ ] **Test connectors**  
  Run schema + read/write in staging.

- [ ] **JVM**  
  Java 21 (LTS). Align across nodes.

---

## 8. Day-2 Operations

### Weekly Health Check
- [ ] Top failed queries:  
  ```sql
  SELECT error_type, error_code, COUNT(*)
  FROM trino_queries
  WHERE query_state='FAILED'
  GROUP BY 1,2
  ORDER BY 3 DESC;
  ```
- [ ] Top memory-heavy queries:  
  ```sql
  SELECT query_id, user, peak_memory_bytes
  FROM trino_queries
  ORDER BY peak_memory_bytes DESC
  LIMIT 10;
  ```
- [ ] Peak concurrency trend: monitor Prometheus `trino_execution_query_count`.

### Monthly Review
- [ ] Iceberg file size distribution: run `SHOW STATS` and check small file counts.  
- [ ] Spill disk usage: check worker filesystem usage, ensure <70%.  
- [ ] Resource group fairness: compare `completed_queries` counts per group.

### Quarterly Drills
- [ ] Upgrade + rollback test in staging.  
- [ ] DR restore test: restore Hive Metastore DB from backup into staging.  
- [ ] Secret & TLS cert rotation.

---
