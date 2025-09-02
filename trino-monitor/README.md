# Trino Monitor Streamlit

One-page Streamlit app to visualize key Trino query metrics from the **event listener DB** (`trino_queries`).  
Supports **multiple clusters**, **on-demand refresh**, and **60-minute caching** to avoid DB load.

## Features
- Multi-cluster configs (YAML/JSON) under `clusters/`
- Manual **Load / Refresh** button (no auto queries)
- `st.cache_data(ttl=3600)` — cached per cluster
- Optional time charts (require `create_time`)
- Works with **MySQL** or **Postgres**

## Quickstart (Local)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# edit clusters/*.yaml|json with your credentials
streamlit run app.py
```

## Docker
```bash
docker build -t trino-monitor-streamlit .
docker run --rm -p 8501:8501 \
  -v $(pwd)/clusters:/app/clusters \
  trino-monitor-streamlit
```

## Helpful indexes (adjust to your usage)
CREATE INDEX IF NOT EXISTS idx_state      ON trino_queries (query_state);
CREATE INDEX IF NOT EXISTS idx_user       ON trino_queries (user);
CREATE INDEX IF NOT EXISTS idx_catalog    ON trino_queries (catalog);
CREATE INDEX IF NOT EXISTS idx_qtype      ON trino_queries (query_type);
CREATE INDEX IF NOT EXISTS idx_create_time ON trino_queries (create_time);