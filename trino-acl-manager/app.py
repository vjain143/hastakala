import streamlit as st
import json
from typing import List
from acl.models import AccessControlRules, CatalogAccessControlRule, CatalogSchemaAccessControlRule, TableAccessControlRule, Privilege
from acl.parser import load_rules, dump_rules
from acl.evaluator import effective_access

st.set_page_config(page_title="Trino ACL Manager", layout="wide")
st.title("🔐 Trino ACL Manager (File-based)")

with st.sidebar:
    st.header("Rules JSON")
    uploaded = st.file_uploader("Load ACL JSON", type=["json"])
    if "rules" not in st.session_state:
        st.session_state.rules = AccessControlRules.empty()
    if uploaded:
        try:
            obj = json.load(uploaded)
            st.session_state.rules = load_rules(obj)
            st.success("Loaded rules")
        except Exception as e:
            st.error(f"Failed to load: {e}")

    data = dump_rules(st.session_state.rules)
    st.download_button("Save rules.json", json.dumps(data, indent=2), file_name="rules.json", mime="application/json")

tabs = st.tabs(["Edit Rules", "Evaluate Access", "Preview JSON"])

with tabs[0]:
    st.subheader("Catalog Rules")
    for i, rule in enumerate(list(st.session_state.rules.catalogs)):
        cols = st.columns(5)
        rule.catalog = cols[0].text_input(f"catalog pattern {i}", value=rule.catalog, key=f"cat_{i}_catalog")
        rule.allow = cols[1].selectbox(f"allow {i}", options=["all","read-only","none"], index=["all","read-only","none"].index(rule.allow), key=f"cat_{i}_allow")
        rule.user = cols[2].text_input(f"user regex {i}", value=rule.user or "", key=f"cat_{i}_user") or None
        rule.group = cols[3].text_input(f"group regex {i}", value=rule.group or "", key=f"cat_{i}_group") or None
        rule.role = cols[4].text_input(f"role regex {i}", value=rule.role or "", key=f"cat_{i}_role") or None
    if st.button("➕ Add catalog rule"):
        st.session_state.rules.catalogs.append(CatalogAccessControlRule(catalog=".*", allow="read-only"))

    st.markdown("---")
    st.subheader("Schema Rules (ownership)")
    for i, rule in enumerate(list(st.session_state.rules.schemas)):
        cols = st.columns(6)
        rule.catalog = cols[0].text_input(f"catalog {i}", value=rule.catalog, key=f"sch_{i}_catalog")
        rule.schema = cols[1].text_input(f"schema {i}", value=rule.schema, key=f"sch_{i}_schema")
        rule.owner = cols[2].checkbox(f"owner {i}", value=rule.owner, key=f"sch_{i}_owner")
        rule.user = cols[3].text_input(f"user {i}", value=rule.user or "", key=f"sch_{i}_user") or None
        rule.group = cols[4].text_input(f"group {i}", value=rule.group or "", key=f"sch_{i}_group") or None
        rule.role = cols[5].text_input(f"role {i}", value=rule.role or "", key=f"sch_{i}_role") or None
    if st.button("➕ Add schema rule"):
        st.session_state.rules.schemas.append(CatalogSchemaAccessControlRule(catalog="hive", schema="default", owner=True))

    st.markdown("---")
    st.subheader("Table Rules (privileges)")
    for i, rule in enumerate(list(st.session_state.rules.tables)):
        cols = st.columns(7)
        rule.catalog = cols[0].text_input(f"catalog {i}", value=rule.catalog, key=f"tbl_{i}_catalog")
        rule.schema  = cols[1].text_input(f"schema {i}",  value=rule.schema,  key=f"tbl_{i}_schema")
        rule.table   = cols[2].text_input(f"table {i}",   value=rule.table,   key=f"tbl_{i}_table")
        current = set(rule.privileges)
        choices: List[Privilege] = ["SELECT","INSERT","DELETE","UPDATE","OWNERSHIP","GRANT_SELECT","CREATE_VIEW"]
        selected = []
        # spread checkboxes across remaining columns
        for j, p in enumerate(choices):
            if cols[3 + (j % 4)].checkbox(f"{p} {i}", value=(p in current), key=f"tbl_{i}_{p}"):
                selected.append(p)
        rule.privileges = selected
    if st.button("➕ Add table rule"):
        st.session_state.rules.tables.append(TableAccessControlRule(catalog="hive", schema="default", table=".*", privileges=["SELECT"]))

    st.info("Order matters (first match wins). Add rules in desired order.")

with tabs[1]:
    st.subheader("Evaluate Effective Access")
    user = st.text_input("User", value="alice")
    groups = st.text_input("Groups (comma separated)", value="analyst,finance")
    roles = st.text_input("Roles (comma separated)", value="")
    catalog = st.text_input("Catalog", value="hive")
    schema = st.text_input("Schema (optional)", value="default")
    table = st.text_input("Table (optional)", value="orders")

    if st.button("Evaluate"):
        res = effective_access(st.session_state.rules, user, [g.strip() for g in groups.split(",") if g.strip()],
                               [r.strip() for r in roles.split(",") if r.strip()],
                               catalog, schema or None, table or None)
        # jsonify pydantic objects
        def ser(o):
            if hasattr(o, "model_dump"): return o.model_dump()
            if hasattr(o, "__dict__"): return o.__dict__
            return str(o)
        st.json(json.loads(json.dumps(res, default=ser)))

with tabs[2]:
    st.subheader("Current JSON")
    st.code(json.dumps(dump_rules(st.session_state.rules), indent=2), language="json")
