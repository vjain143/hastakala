from __future__ import annotations
from typing import Dict, Optional
from .models import AccessControlRules
from .parser import match_identity
import re

PRIVS = ["SELECT","INSERT","DELETE","UPDATE","OWNERSHIP","GRANT_SELECT","CREATE_VIEW"]

def _match(pat: str, value: str) -> bool:
    try:
        return re.fullmatch(pat, value) is not None
    except re.error:
        return pat == value

def eval_catalog(rules: AccessControlRules, user: str, groups: list[str], roles: list[str], catalog: str) -> Dict:
    for rule in rules.catalogs:
        if not match_identity(rule, user, groups, roles): 
            continue
        if _match(rule.catalog, catalog):
            allow = rule.allow
            return {
                "matched_rule": rule,
                "allow": allow,
                "allowed_privileges": (PRIVS if allow=="all" else (["SELECT","CREATE_VIEW"] if allow=="read-only" else []))
            }
    return {"matched_rule": None, "allow": "none", "allowed_privileges": []}

def eval_schema(rules: AccessControlRules, user: str, groups: list[str], roles: list[str], catalog: str, schema: str) -> Dict:
    for rule in rules.schemas:
        if not match_identity(rule, user, groups, roles):
            continue
        if _match(rule.catalog, catalog) and _match(rule.schema, schema):
            return {"matched_rule": rule, "owner": rule.owner}
    return {"matched_rule": None, "owner": False}

def eval_table(rules: AccessControlRules, user: str, groups: list[str], roles: list[str], catalog: str, schema: str, table: str) -> Dict:
    for rule in rules.tables:
        if not match_identity(rule, user, groups, roles):
            continue
        if _match(rule.catalog, catalog) and _match(rule.schema, schema) and _match(rule.table, table):
            allowed = [p for p in rule.privileges if p in PRIVS]
            return {"matched_rule": rule, "privileges": allowed}
    return {"matched_rule": None, "privileges": []}

def effective_access(rules: AccessControlRules, user: str, groups: list[str], roles: list[str],
                     catalog: str, schema: Optional[str]=None, table: Optional[str]=None) -> Dict:
    result = {}
    cat = eval_catalog(rules, user, groups, roles, catalog)
    result["catalog"] = cat
    if schema:
        sch = eval_schema(rules, user, groups, roles, catalog, schema)
        result["schema"] = sch
    if schema and table:
        tbl = eval_table(rules, user, groups, roles, catalog, schema, table)
        result["table"] = tbl
    result["visible"] = (cat["allow"] != "none")
    return result
