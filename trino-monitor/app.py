import os
import glob
import json
import time
import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Optional YAML support
try:
    import yaml  # PyYAML
    HAS_YAML = True
except Exception:
    HAS_YAML = False

load_dotenv()

st.set_page_config(page_title="Trino Monitoring Dashboard", page_icon="🧭", layout="wide")
st.title("🧭 Trino Monitoring Dashboard")
st.caption("Multi-cluster, cached metrics from the Trino event-listener table `trino_queries`.")

# -----------------------
# Config discovery
# -----------------------
CONFIG_DIR = os.getenv("CONFIG_DIR", "clusters")

def load_cluster_files(config_dir: str):
    paths = []
    paths.extend(glob.glob(os.path.join(config_dir, "*.yaml")))
    paths.extend(glob.glob(os.path.join(config_dir, "*.yml")))
    paths.extend(glob.glob(os.path.join(config_dir, "*.json")))
    return sorted(paths)

def load_cluster_config(path: str):
    """Load one config file and return a list of cluster dicts.

    Supports:
    - YAML single-doc (dict) or list
    - YAML multi-doc (--- separated)
    - JSON dict or list
    """
    clusters_in_file = []

    if path.endswith((".yaml", ".yml")):
        if not HAS_YAML:
            raise RuntimeError(
                "PyYAML is not installed but a YAML file was provided. Install 'PyYAML'."
            )
        with open(path, "r", encoding="utf-8") as f:
            # Load all YAML documents; each doc can be a dict or a list of dicts
            docs = list(yaml.safe_load_all(f))
        for doc in docs:
            if not doc:
                continue
            if isinstance(doc, list):
                for item in doc:
                    if isinstance(item, dict):
                        clusters_in_file.append(item)
            elif isinstance(doc, dict):
                clusters_in_file.append(doc)
    else:
        with open(path, "r", encoding="utf-8") as f:
            doc = json.load(f)
        if isinstance(doc, list):
            for item in doc:
                if isinstance(item, dict):
                    clusters_in_file.append(item)
        elif isinstance(doc, dict):
            clusters_in_file.append(doc)

    return clusters_in_file

cluster_files = load_cluster_files(CONFIG_DIR)
if not cluster_files:
    st.warning(
        f"No cluster config files found in `{CONFIG_DIR}`. "
        "Add YAML/JSON files (see examples) and reload."
    )
    st.stop()

clusters = []
for p in cluster_files:
    try:
        clusters.extend(load_cluster_config(p))
    except Exception as e:
        st.error(f"Failed to load config '{p}': {e}")

if not clusters:
    st.warning(
        f"No cluster entries found in `{CONFIG_DIR}` config files. "
        "Add YAML/JSON cluster definitions and reload."
    )
    st.stop()

# Normalize & validate
for c in clusters:
    c.setdefault("name", f"{c.get('host')} ({c.get('dialect')})")
    c.setdefault("schema", "trino_events")
    c.setdefault("table", "trino_queries")

cluster_names = [c["name"] for c in clusters]

# -----------------------
# Sidebar: cluster pick + controls
# -----------------------
with st.sidebar:
    st.header("Cluster & Controls")
    selected_name = st.selectbox("Select cluster", cluster_names, index=0)
    st.caption("The selected cluster determines DB connection + table source.")

    hours_recent = st.slider("Recent Hours (for time charts)", 1, 72, 24)
    top_n = st.slider("Top N (tables)", 5, 50, 10)

    refresh_btn = st.button("Load / Refresh", type="primary", use_container_width=True)
    st.caption("Click to query. Results are cached for 60 minutes per cluster.")

# Keep a tiny counter in session to force re-key cache on manual refresh
if "refresh_nonce" not in st.session_state:
    st.session_state.refresh_nonce = 0
if refresh_btn:
    st.session_state.refresh_nonce += 1

# Resolve chosen cluster config
cfg = clusters[cluster_names.index(selected_name)]
DIALECT = cfg["dialect"].lower()
HOST = cfg["host"]
PORT = int(cfg.get("port", 3306 if DIALECT == "mysql" else 5432))
USER = cfg["user"]
PASS = cfg["password"]
DBNAME = cfg["database"]
SCHEMA = cfg.get("schema", "trino_events")
TABLE = cfg.get("table", "trino_queries")

# Build engine URL
if DIALECT == "mysql":
    url = f"mysql+pymysql://{USER}:{PASS}@{HOST}:{PORT}/{DBNAME}"
elif DIALECT == "postgres":
    url = f"postgresql+psycopg2://{USER}:{PASS}@{HOST}:{PORT}/{DBNAME}"
else:
    st.error("Unsupported dialect in cluster config (use 'mysql' or 'postgres').")
    st.stop()

engine = create_engine(url, pool_pre_ping=True)
FULL_TABLE = f"{SCHEMA}.{TABLE}" if DIALECT == "postgres" else TABLE

# -----------------------
# SQL helpers (dialect-aware)
# -----------------------
def T(expr_mysql, expr_pg):
    return expr_mysql if DIALECT == "mysql" else expr_pg

def sql_qps_hour(full_table):
    return text(T(
        f"""
        SELECT DATE_FORMAT(create_time, '%%Y-%%m-%%d %%H:00:00') AS hour,
               COUNT(*) AS query_count
        FROM {full_table}
        WHERE create_time >= NOW() - INTERVAL :hours HOUR
        GROUP BY hour
        ORDER BY hour;
        """,
        f"""
        SELECT date_trunc('hour', create_time) AS hour,
               COUNT(*) AS query_count
        FROM {full_table}
        WHERE create_time >= NOW() - (:hours || ' hours')::interval
        GROUP BY 1
        ORDER BY 1;
        """
    ))

def sql_concurrency(full_table):
    return text(T(
        f"""
        SELECT MAX(running_queries) AS max_concurrency
        FROM (
          SELECT COUNT(*) AS running_queries,
                 DATE_FORMAT(create_time, '%%Y-%%m-%%d %%H:%%i:00') AS ts
          FROM {full_table}
          WHERE create_time >= NOW() - INTERVAL :hours HOUR
            AND query_state = 'RUNNING'
          GROUP BY ts
        ) t;
        """,
        f"""
        SELECT MAX(running_queries) AS max_concurrency
        FROM (
          SELECT COUNT(*) AS running_queries,
                 date_trunc('minute', create_time) AS ts
          FROM {full_table}
          WHERE create_time >= NOW() - (:hours || ' hours')::interval
            AND query_state = 'RUNNING'
          GROUP BY ts
        ) t;
        """
    ))

sql_success = lambda ft: text(f"SELECT query_state, COUNT(*) AS count FROM {ft} GROUP BY query_state;")

def sql_top_users(ft):
    if DIALECT == "mysql":
        return text(f"""
            SELECT `user` AS user, COUNT(*) AS query_count
            FROM {ft}
            GROUP BY `user`
            ORDER BY query_count DESC
            LIMIT :limit;
        """)
    return text(f"""
        SELECT "user" AS user, COUNT(*) AS query_count
        FROM {ft}
        GROUP BY "user"
        ORDER BY query_count DESC
        LIMIT :limit;
    """)

sql_longest_wall = lambda ft: text(f"""
    SELECT query_id, {"`user`" if DIALECT == "mysql" else '"user"'} AS user,
           LEFT(query, 400) AS query,
           wall_time_millis
    FROM {ft}
    ORDER BY wall_time_millis DESC
    LIMIT :limit;
""")

sql_errors = lambda ft: text(f"""
    SELECT COALESCE(error_type,'UNKNOWN') AS error_type,
           COALESCE(error_code,'UNKNOWN') AS error_code,
           COUNT(*) AS failures
    FROM {ft}
    WHERE query_state = 'FAILED'
    GROUP BY error_type, error_code
    ORDER BY failures DESC
    LIMIT :limit;
""")

def sql_peak_mem(ft):
    if DIALECT == "mysql":
        return text(f"""
            SELECT query_id, `user` AS user,
                   ROUND(peak_memory_bytes / 1024 / 1024) AS peak_memory_mb
            FROM {ft}
            ORDER BY peak_memory_mb DESC
            LIMIT :limit;
        """)
    return text(f"""
        SELECT query_id, "user" AS user,
               ROUND(peak_memory_bytes / 1024.0 / 1024.0) AS peak_memory_mb
        FROM {ft}
        ORDER BY peak_memory_mb DESC
        LIMIT :limit;
    """)

sql_catalog_usage = lambda ft: text(f"""
    SELECT COALESCE(catalog,'(none)') AS catalog, COUNT(*) AS query_count
    FROM {ft}
    GROUP BY catalog
    ORDER BY query_count DESC;
""")

sql_query_type = lambda ft: text(f"""
    SELECT COALESCE(query_type,'(none)') AS query_type, COUNT(*) AS query_count
    FROM {ft}
    GROUP BY query_type
    ORDER BY query_count DESC;
""")

sql_source_usage = lambda ft: text(f"""
    SELECT COALESCE(source,'(none)') AS source, COUNT(*) AS query_count
    FROM {ft}
    GROUP BY source
    ORDER BY query_count DESC
    LIMIT :limit;
""")

sql_expensive_cpu = lambda ft: text(f"""
    SELECT query_id, {"`user`" if DIALECT == "mysql" else '"user"'} AS user,
           cpu_time_millis, wall_time_millis,
           peak_memory_bytes, total_rows, total_bytes,
           LEFT(query, 400) AS query
    FROM {ft}
    ORDER BY cpu_time_millis DESC
    LIMIT :limit;
""")

# -----------------------
# Low-level helpers
# -----------------------
def list_columns(engine, dbname, schema, table):
    if DIALECT == "mysql":
        sql = text("""
            SELECT COLUMN_NAME
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = :db AND TABLE_NAME = :tbl
        """)
        with engine.connect() as c:
            df = pd.read_sql(sql, c, params={"db": dbname, "tbl": table})
    else:
        sql = text("""
            SELECT column_name AS COLUMN_NAME
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE table_schema = :schema AND table_name = :tbl
        """)
        with engine.connect() as c:
            df = pd.read_sql(sql, c, params={"schema": schema, "tbl": table})
    return set(df["COLUMN_NAME"].str.lower().tolist())

def run_df(engine, sql_text, **binds):
    with engine.connect() as conn:
        return pd.read_sql(sql=sql_text, con=conn, params=binds)

# -----------------------
# Cached fetch (60 min)
# -----------------------
@st.cache_data(ttl=3600, show_spinner=False)
def fetch_all_metrics(cluster_key: str, hours_recent: int, top_n: int):
    """Run all queries for a cluster. Cached by cluster_key + inputs."""
    eng = engine  # already built for current cluster
    cols = list_columns(eng, DBNAME, SCHEMA, TABLE)
    has_create = "create_time" in cols

    bundle = {"has_create": has_create, "generated_at": int(time.time())}

    # Time-based (optional)
    if has_create:
        qps = run_df(eng, sql_qps_hour(FULL_TABLE), hours=hours_recent)
        conc = run_df(eng, sql_concurrency(FULL_TABLE), hours=hours_recent)
        bundle["qps"] = qps
        bundle["concurrency"] = conc

    # Always-available sections (match your schema)
    bundle["state"]   = run_df(eng, sql_success(FULL_TABLE))
    bundle["qtype"]   = run_df(eng, sql_query_type(FULL_TABLE))
    bundle["users"]   = run_df(eng, sql_top_users(FULL_TABLE), limit=top_n)
    bundle["source"]  = run_df(eng, sql_source_usage(FULL_TABLE), limit=top_n)
    bundle["longest"] = run_df(eng, sql_longest_wall(FULL_TABLE), limit=top_n)
    bundle["errors"]  = run_df(eng, sql_errors(FULL_TABLE), limit=top_n)
    bundle["mem"]     = run_df(eng, sql_peak_mem(FULL_TABLE), limit=top_n)
    bundle["catalog"] = run_df(eng, sql_catalog_usage(FULL_TABLE))
    bundle["expensive"] = run_df(eng, sql_expensive_cpu(FULL_TABLE), limit=top_n)
    return bundle

# Compose a stable cache key + the session nonce so clicking refresh re-queries
cluster_key = f"{selected_name}|{DIALECT}|{HOST}|{PORT}|{DBNAME}|{SCHEMA}|{TABLE}|nonce={st.session_state.refresh_nonce}"

# -----------------------
# Only query when button clicked
# -----------------------
if not refresh_btn and st.session_state.refresh_nonce == 0:
    st.info("Select a cluster, adjust controls, then click **Load / Refresh** to pull metrics (cached 60 min).")
    st.stop()

with st.spinner(f"Loading metrics from {selected_name}..."):
    data = fetch_all_metrics(cluster_key, hours_recent, top_n)

# -----------------------
# Render
# -----------------------
last_updated = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(data["generated_at"]))
st.success(f"Showing cached results for **{selected_name}** • Last updated: {last_updated} • Cache TTL: 60 min")

# Time-based (if create_time column exists)
if data["has_create"]:
    c1, c2 = st.columns((2,1), vertical_alignment="top")
    with c1:
        st.subheader("📈 Query Volume per Hour")
        df_qps = data["qps"].copy()
        if not df_qps.empty:
            df_qps["hour"] = pd.to_datetime(df_qps["hour"])
            st.line_chart(df_qps.set_index("hour")["query_count"])
        else:
            st.info("No rows for the selected window.")
    with c2:
        st.subheader("👥 Peak Concurrency (RUNNING)")
        df_conc = data["concurrency"]
        max_conc = int(df_conc["max_concurrency"].iloc[0]) if not df_conc.empty and df_conc["max_concurrency"].iloc[0] is not None else 0
        st.metric("Max Concurrency", f"{max_conc}", help="Max concurrent RUNNING queries in the selected window")
    st.divider()
else:
    st.info("Time-based charts hidden (no `create_time` column in this table).")

# Row 1
c3, c4 = st.columns(2)
with c3:
    st.subheader("✅ Distribution by Query State")
    st.bar_chart(data["state"].set_index("query_state")["count"] if not data["state"].empty else data["state"])
    st.dataframe(data["state"], use_container_width=True)
with c4:
    st.subheader("🔎 Distribution by Query Type")
    st.bar_chart(data["qtype"].set_index("query_type")["query_count"] if not data["qtype"].empty else data["qtype"])
    st.dataframe(data["qtype"], use_container_width=True)

st.divider()

# Row 2
c5, c6 = st.columns(2)
with c5:
    st.subheader("🏅 Top Users by Query Count")
    st.bar_chart(data["users"].set_index("user")["query_count"] if not data["users"].empty else data["users"])
    st.dataframe(data["users"], use_container_width=True)
with c6:
    st.subheader("🧰 Source / Client Usage")
    st.bar_chart(data["source"].set_index("source")["query_count"] if not data["source"].empty else data["source"])
    st.dataframe(data["source"], use_container_width=True)

st.divider()

# Row 3
c7, c8 = st.columns(2)
with c7:
    st.subheader("⏳ Longest Wall Time (ms)")
    st.dataframe(data["longest"], use_container_width=True)
with c8:
    st.subheader("🚫 Top Failures (Type / Code)")
    if not data["errors"].empty:
        st.bar_chart(data["errors"].set_index("error_code")["failures"])
    st.dataframe(data["errors"], use_container_width=True)

st.divider()

# Row 4
c9, c10 = st.columns(2)
with c9:
    st.subheader("💥 Peak Memory per Query (MB)")
    if not data["mem"].empty:
        st.bar_chart(data["mem"].set_index("query_id")["peak_memory_mb"])
    st.dataframe(data["mem"], use_container_width=True)
with c10:
    st.subheader("🗂️ Catalog Usage")
    if not data["catalog"].empty:
        st.bar_chart(data["catalog"].set_index("catalog")["query_count"])
    st.dataframe(data["catalog"], use_container_width=True)

st.divider()

# Row 5
st.subheader("💸 Most Expensive Queries by CPU Time (ms)")
st.dataframe(data["expensive"], use_container_width=True)