import json
from acl.models import AccessControlRules
from acl.evaluator import effective_access

def test_effective_access_select_allowed():
    rules = AccessControlRules(**{
        "catalogs":[{"catalog":"hive","allow":"read-only"}],
        "tables":[{"group":"analyst","catalog":"hive","schema":"sales","table":"orders","privileges":["SELECT","CREATE_VIEW"]}]
    })
    res = effective_access(rules, "bob", ["analyst"], [], "hive", "sales", "orders")
    assert res["catalog"]["allow"] == "read-only"
    assert "SELECT" in res["table"]["privileges"]

def test_default_deny():
    rules = AccessControlRules()
    res = effective_access(rules, "bob", [], [], "hive", "sales", "orders")
    assert res["catalog"]["allow"] == "none"
    assert res.get("table", {"privileges":[]})["privileges"] == []
