PASSED = "passed"
WARNING = "warning"
FAILED = "failed"


def evaluate_gate(results: list[dict]) -> str:
    failed = [item for item in results if item["status"] == "failed"]
    if any(item["severity"] == "critical" for item in failed):
        return FAILED
    if any(item["severity"] == "warning" for item in failed):
        return WARNING
    return PASSED


def quality_score(results: list[dict]) -> float:
    evaluated = [item for item in results if item["status"] != "skipped"]
    if not evaluated:
        return 1.0
    passed = sum(1 for item in evaluated if item["status"] == "passed")
    return round(passed / len(evaluated), 4)


def allows_downstream(status: str, allow_warning: bool = True) -> bool:
    if status == PASSED:
        return True
    if status == WARNING:
        return allow_warning
    return False
