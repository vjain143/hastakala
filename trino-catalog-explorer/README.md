# Trino Catalog Explorer

**Trino Catalog Explorer** is a Streamlit + FastAPI app that connects to **multiple Trino clusters**, fetches **catalog and schema metadata**, and presents it as:

- An **interactive Streamlit UI** (sortable/searchable table, CSV export)
- A **REST JSON API** (for automation and integration)

Schemas are omitted for **database-type catalogs** (e.g., Hive, Iceberg, MySQL, Postgres, Oracle, Snowflake, etc.), so you get a clean and relevant metadata view.

---

## Features

- 🔌 Connect to **multiple Trino clusters** at once  
- 📑 Fetch **catalogs** and **schemas** per cluster  
- 🧹 Auto-detect **database-type catalogs** and omit schemas  
- 📊 Streamlit UI with **downloadable CSV**  
- 🌐 JSON API with `/api/health`, `/api/last`, and `/api/build`  
- ⚡ Stateless API mode (send cluster config in POST request)  
- 🔒 Basic authentication support for clusters  
- 🛠️ Easy to extend with more auth/session options  

---

## Quickstart

### 1. Clone & setup
```bash
git clone https://github.com/your-org/trino-catalog-explorer.git
cd trino-catalog-explorer

python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

# Run
```bash
streamlit run app.py
```

This starts:
	•	Streamlit UI at: http://localhost:8501
	•	JSON API at: http://localhost:8787

# Usage

UI
	1.	Open the sidebar
	2.	Paste in your cluster configuration JSON (example below)
	3.	Click Build table

```bash
[
  {
    "name": "trino-dev",
    "host": "localhost",
    "port": 8080,
    "user": "streamlit",
    "http_scheme": "http",
    "auth_type": "none"
  },
  {
    "name": "trino-prod",
    "host": "prod-trino.example.com",
    "port": 8443,
    "user": "catalog-viewer",
    "http_scheme": "https",
    "auth_type": "basic",
    "username": "viewer",
    "password": "REPLACE_ME"
  }
]
```

API Endpoints
	Health 
        curl http://localhost:8787/api/health
    Get last built table (from UI run)
        curl http://localhost:8787/api/last
    Build directly via API
        curl -X POST http://localhost:8787/api/build \
         -H "Content-Type: application/json" \
        -d '[{"name":"trino-dev","host":"localhost","port":8080,"auth_type":"none"}]'
    Response example:
        {
        "status": "ok",
        "rows": 12,
        "data": [
            {"sr/no": 1, "trino cluster name": "trino-dev", "catalog name": "hive", "schema name": ""},
            {"sr/no": 2, "trino cluster name": "trino-dev", "catalog name": "tpch", "schema name": "sf1"}
        ]
        }

# Requirements
	•	Python 3.9+
	•	Trino Python client
	•	Streamlit, FastAPI, Uvicorn, Pandas

See requirements.txt for full list.

Code Overview
	•	ClusterConfig: cluster connection model
	•	get_conn(): opens Trino DBAPI connection
	•	fetch_catalogs_and_connectors(): gets catalogs and connector types
	•	fetch_schemas_for_catalog(): lists schemas unless database-type
	•	build_dataframe(): builds consolidated Pandas DataFrame
	•	Streamlit UI: handles JSON config input, table rendering, CSV export
	•	FastAPI: exposes /api/health, /api/last, /api/build

Adding New Features
	•	Auth: Extend get_conn() with Kerberos, JWT, or OAuth via trino.auth
	•	Output formats: Add /api/excel or /api/html endpoints
	•	UI: Add filters (per-cluster, per-catalog) using Streamlit widgets

⸻

Roadmap
	•	Support Kerberos / OAuth2 auth
	•	Add search & filter controls in UI
	•	Add Excel/Parquet download option
	•	Containerize with Docker for deployment

⸻

License

MIT License – free to use, modify, and share.

Credits

Developed by 🚀 Vivek Jain
Inspired by need to explore Trino catalogs & schemas across clusters with a simple UI + API.
