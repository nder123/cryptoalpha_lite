CONTRACT_RULES = [
    {
        "name": "trace_required",
        "type": "hard_deny",
        "field": "trace_id",
        "op": "is_null",
    },
    {
        "name": "deny_is_terminal",
        "type": "hard_deny",
        "field": "decision",
        "op": "equals",
        "value": "DENY",
    },
    {
        "name": "reject_is_terminal",
        "type": "hard_deny",
        "field": "decision",
        "op": "equals",
        "value": "REJECT",
    },
]
