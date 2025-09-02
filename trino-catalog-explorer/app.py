import json
import threading
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Tuple, Iterable

import streamlit as st
import pandas as pd

# pip install trino
from trino.dbapi import connect
from trino.auth import BasicAuthentication

# --- FastAPI bits ---
from fastapi import FastAPI, Body
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

st.set_page_config(page_title="Multi-Trino Catalog & Schema Explorer (+ JSON API)", layout="wide")
st.title("Multi-Trino Catalog & Schema Explorer")
st.caption("Builds a consolidated table across clusters. Schema column is blank for database-type catalogs. Also serves a JSON API on a separate port.")

# ---- Shared *in-memory* result store for the API ----
_LAST_DF: Optional[pd.DataFrame] = None
_LOCK = threading.Lock()

# --- Treat these connectors as "database" types (omit schema listing) ---
DATABASE_CONNECTORS = {
    # Relational
    "mysql", "mariadb", "postgresql", "sqlserver", "oracle", "db2", "clickhouse",
    # Lake/warehouse
    "hive", "iceberg", "delta_lake", "bigquery", "redshift", "snowflake", "vertica",
    # NoSQL / others
    "mongodb", "cassandra", "elasticsearch"
}

@dataclass
class ClusterConfig:
    name: str
    host: str
    port: int = 8080
    user: str = "streamlit"
    http_scheme: str = "http"  # "http" or "https"
    auth_type: str = "none"    # "none" or "basic"
    username: Optional[str] = None
    password: Optional[str] = None
    session_props: Optional[Dict[str, str]] = None
    catalog_filter: Optional[str] = None  # optional substring filter for catalogs

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "ClusterConfig":
        return ClusterConfig(
            name=d["name"],
            host=d["host"],
            port=int(d.get("port", 8080)),
            user=d.get("user", "streamlit"),
            http_scheme=d.get("http_scheme", "http"),
            auth_type=d.get("auth_type", "none"),
            username=d.get("username"),
            password=d.get("password"),
            session_props=d.get("session_props"),
            catalog_filter=d.get("catalog_filter")
        )

def get_conn(cfg: ClusterConfig):
    kwargs = dict(
        host=cfg.host,
        port=cfg.port,
        user=cfg.user,
        http_scheme=cfg.http_scheme,
        source="streamlit-app",
        session_properties=cfg.session_props or {}
    )
    if cfg.auth_type == "basic":
        if not (cfg.username and cfg.password):
            raise ValueError(f"[{cfg.name}] Basic auth requires username and password.")
        kwargs["auth"] = BasicAuthentication(cfg.username, cfg.password)
    return connect(**kwargs)

def fetch_catalogs_and_connectors(conn) -> List[Tuple[str, str]]:
    sql = "SELECT catalog_name, connector_name FROM system.metadata.catalogs ORDER BY catalog_name"
    cur = conn.cursor()
    cur.execute(sql)
    rows = cur.fetchall()
    cur.close()
    return [(r[0], r[1]) for r in rows]

def fetch_schemas_for_catalog(conn, catalog: str) -> List[str]:
    cur = conn.cursor()
    sql = f'SELECT schema_name FROM "{catalog}".information_schema.schemata ORDER BY schema_name'
    cur.execute(sql)
    rows = [r[0] for r in cur.fetchall()]
    cur.close()
    return rows

def iter_rows_for_cluster(cfg: ClusterConfig, sr_start: int = 1) -> Iterable[Tuple[int, str, str, Optional[str]]]:
    try:
        conn = get_conn(cfg)
    except Exception as e:
        yield sr_start, f"{cfg.name} (connection error)", f"{type(e).__name__}", None
        return

    try:
        cat_conn_pairs = fetch_catalogs_and_connectors(conn)
    except Exception as e:
        yield sr_start, f"{cfg.name} (catalogs error)", f"{type(e).__name__}", None
        return

    sr = sr_start
    for catalog_name, connector_name in cat_conn_pairs:
        if cfg.catalog_filter and cfg.catalog_filter.lower() not in catalog_name.lower():
            continue

        if (connector_name or "").lower() in DATABASE_CONNECTORS:
            yield sr, cfg.name, catalog_name, None
            sr += 1
            continue

        try:
            schemas = fetch_schemas_for_catalog(conn, catalog_name)
            if not schemas:
                yield sr, cfg.name, catalog_name, None
                sr += 1
            else:
                for schema in schemas:
                    yield sr, cfg.name, catalog_name, schema
                    sr += 1
        except Exception:
            yield sr, cfg.name, catalog_name, None
            sr += 1

def build_dataframe(clusters: List[ClusterConfig]) -> pd.DataFrame:
    all_rows: List[Tuple[int, str, str, Optional[str]]] = []
    sr_no = 1
    for cfg in clusters:
        for row in iter_rows_for_cluster(cfg, sr_start=sr_no):
            all_rows.append(row)
            sr_no = row[0] + 1
    df = pd.DataFrame(all_rows, columns=["sr/no", "trino cluster name", "catalog name", "schema name"])
    df["schema name"] = df["schema name"].fillna("")
    return df

# ----------------- FastAPI server (runs once) -----------------
API_PORT = 8787
def start_api_once():
    if "api_started" in st.session_state and st.session_state.api_started:
        return

    app = FastAPI(title="Multi-Trino JSON API", version="1.0.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"]
    )

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    @app.get("/api/last")
    def get_last():
        with _LOCK:
            if _LAST_DF is None:
                return {"status": "empty", "rows": 0, "data": []}
            data = _LAST_DF.to_dict(orient="records")
        return {"status": "ok", "rows": len(data), "data": data}

    @app.post("/api/build")
    def build(clusters: List[Dict[str, Any]] = Body(..., description="List of cluster config objects")):
        cfgs = [ClusterConfig.from_dict(item) for item in clusters]
        df = build_dataframe(cfgs)
        return {"status": "ok", "rows": len(df), "data": df.to_dict(orient="records")}

    def _run():
        uvicorn.run(app, host="0.0.0.0", port=API_PORT, log_level="info")

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    st.session_state.api_started = True

start_api_once()

# ----------------- Streamlit UI -----------------
st.sidebar.header("Cluster configuration")

default_clusters_json = """
[
  {
    "name": "trino-dev",
    "host": "localhost",
    "port": 8080,
    "user": "streamlit",
    "http_scheme": "http",
    "auth_type": "none",
    "catalog_filter": null
  },
  {
    "name": "trino-prod",
    "host": "prod-trino.example.com",
    "port": 8443,
    "user": "catalog-viewer",
    "http_scheme": "https",
    "auth_type": "basic",
    "username": "viewer",
    "password": "REPLACE_ME",
    "catalog_filter": null
  }
]
""".strip()

clusters_json = st.sidebar.text_area(
    "Paste clusters JSON (array). Each item needs: name, host. Optional: port, user, http_scheme, auth_type, username, password, session_props, catalog_filter.",
    value=default_clusters_json,
    height=260
)

st.sidebar.markdown("**Database-type connectors (schemas omitted):**")
st.sidebar.code(", ".join(sorted(DATABASE_CONNECTORS)), language="text")

st.sidebar.info(
    f"JSON API runs on port {API_PORT}. Endpoints: /api/health, /api/last (GET), /api/build (POST)."
)

run_btn = st.sidebar.button("Build table")

if run_btn:
    try:
        raw = json.loads(clusters_json)
        clusters = [ClusterConfig.from_dict(item) for item in raw]
    except Exception as e:
        st.error(f"Invalid JSON: {e}")
        st.stop()

    with st.spinner("Connecting to clusters and fetching catalogs/schemas..."):
        df = build_dataframe(clusters)

    if df.empty:
        st.warning("No data found. Check your connections or filters.")
    else:
        with _LOCK:
            _LAST_DF = df

        st.success("Done!")
        st.dataframe(df, use_container_width=True)

        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button("Download CSV", data=csv, file_name="trino_catalogs_and_schemas.csv", mime="text/csv")

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Rows", len(df))
        with col2:
            st.metric("Distinct clusters", df["trino cluster name"].nunique())
        with col3:
            st.metric("Distinct catalogs", df["catalog name"].nunique())
else:
    st.info("Configure your clusters in the sidebar, then click **Build table**.")