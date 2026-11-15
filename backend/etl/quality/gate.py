PASSED = "passed"
WARNING = "warning"
FAILED = "failed"


def evaluate_gate(results: list[dict]) -> str:
    if not any(item["status"] != "skipped" for item in results):
        return WARNING  # ни одно правило не выполнено — доверять данным нельзя
    failed = [item for item in results if item["status"] == "failed"]
    if any(item["severity"] == "critical" for item in failed):
        return FAILED
    if any(item["severity"] == "warning" for item in failed):
        return WARNING
    return PASSED


def rule_coverage(results: list[dict]) -> float:
    """Доля правил, которые реально выполнены (не пропущены)."""
    if not results:
        return 0.0
    executed = sum(1 for item in results if item["status"] != "skipped")
    return round(executed / len(results), 4)


def critical_failures(results: list[dict]) -> int:
    return sum(
        1 for item in results if item["status"] == "failed" and item["severity"] == "critical"
    )


def quality_score(results: list[dict]) -> float:
    """Доля пройденных правил от всех настроенных.

    Пропущенные правила считаются не пройденными, поэтому при пустом наборе
    или нулевом покрытии оценка равна 0, а не 100%. Любой critical-провал
    обнуляет оценку.
    """
    if not results or critical_failures(results):
        return 0.0
    passed = sum(1 for item in results if item["status"] == "passed")
    return round(passed / len(results), 4)


def allows_downstream(status: str, allow_warning: bool = True) -> bool:
    if status == PASSED:
        return True
    if status == WARNING:
        return allow_warning
    return False
