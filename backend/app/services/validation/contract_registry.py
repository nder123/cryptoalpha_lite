# STABILITY CLASS: SEMANTIC CORE
# CHANGE RULE: breaking changes require Gate D review

from collections.abc import Mapping

from .contracts import CONTRACT_RULES


class ContractRegistry:
    """
    Single interpreter for all contract rules
    """

    def evaluate(self, decision: Mapping[str, object]) -> dict[str, object]:
        violations: list[str] = []

        for rule in CONTRACT_RULES:
            field = rule["field"]
            value = decision.get(field)

            if rule["op"] == "is_null":
                if value is None:
                    violations.append(str(rule["name"]))

            elif rule["op"] == "equals":
                if value == rule.get("value"):
                    violations.append(str(rule["name"]))

        return {
            "valid": len(violations) == 0,
            "violations": violations,
        }
