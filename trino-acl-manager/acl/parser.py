from __future__ import annotations
import json, re
from typing import Dict, Any
from .models import AccessControlRules

def load_rules(obj: Dict[str, Any]) -> AccessControlRules:
    data = obj.get("data", obj)
    return AccessControlRules(**data)

def dump_rules(rules: AccessControlRules, wrap: bool=False) -> Dict[str, Any]:
    data = json.loads(rules.model_dump_json(exclude_none=True))
    return {"data": data} if wrap else data

def match_identity(rule, user: str, groups: list[str], roles: list[str]) -> bool:
    def m(pat: str, value: str) -> bool:
        try:
            return re.fullmatch(pat, value) is not None
        except re.error:
            return pat == value
    ok = False
    if getattr(rule, "user", None):
        ok = ok or m(rule.user, user)
    if getattr(rule, "group", None):
        ok = ok or any(m(rule.group, g) for g in groups)
    if getattr(rule, "role", None):
        ok = ok or any(m(rule.role, r) for r in roles)
    if getattr(rule, "user", None) is None and getattr(rule, "group", None) is None and getattr(rule, "role", None) is None:
        ok = True
    return ok
