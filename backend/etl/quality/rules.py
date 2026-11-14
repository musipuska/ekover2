from pyspark.sql import Column, DataFrame
from pyspark.sql import functions as F

from backend.etl.common.config import RuleSpec
from backend.etl.common.exceptions import ValidationError

ROW_RULES = {
    "not_null",
    "between",
    "allowed_values",
    "regex",
    "valid_timestamp",
    "not_in_future",
}
DATASET_RULES = {
    "min_rows",
    "max_null_ratio",
    "unique",
    "required_columns",
    "row_count_change",
}
SEVERITIES = {"critical", "warning", "info"}


def _col(name: str) -> Column:
    return F.col(f"`{name}`")


def validate_specs(specs: list[RuleSpec]) -> None:
    names = set()
    for spec in specs:
        if spec.rule not in ROW_RULES | DATASET_RULES:
            raise ValidationError(f"Неизвестное правило качества: {spec.rule}")
        if spec.severity not in SEVERITIES:
            raise ValidationError(f"Неизвестная severity: {spec.severity}")
        if spec.name in names:
            raise ValidationError(f"Повторяющееся имя правила: {spec.name}")
        names.add(spec.name)


def row_failure_condition(spec: RuleSpec) -> Column:
    column = _col(spec.column)

    if spec.rule == "not_null":
        condition = column.isNull()
    elif spec.rule == "between":
        numeric = column.cast("double")
        invalid = numeric.isNull()
        if spec.min is not None:
            invalid = invalid | (numeric < F.lit(float(spec.min)))
        if spec.max is not None:
            invalid = invalid | (numeric > F.lit(float(spec.max)))
        condition = column.isNotNull() & invalid
    elif spec.rule == "allowed_values":
        allowed = [str(value) for value in (spec.values or [])]
        condition = column.isNotNull() & ~column.cast("string").isin(allowed)
    elif spec.rule == "regex":
        condition = column.isNotNull() & ~column.cast("string").rlike(spec.pattern or ".*")
    elif spec.rule == "valid_timestamp":
        condition = column.isNotNull() & F.to_timestamp(column.cast("string")).isNull()
    elif spec.rule == "not_in_future":
        condition = F.to_timestamp(column.cast("string")) > F.current_timestamp()
    else:
        raise ValidationError(f"Правило {spec.rule} не является построчным")

    return F.coalesce(condition, F.lit(False))


def _result(spec: RuleSpec, status: str, **fields) -> dict:
    return {
        "rule": spec.name,
        "rule_type": spec.rule,
        "column": spec.column,
        "severity": spec.severity,
        "status": status,
        "quarantine": spec.quarantine,
        "failed_rows": fields.get("failed_rows"),
        "observed_value": fields.get("observed_value"),
        "expected": fields.get("expected"),
        "message": fields.get("message"),
    }


def _expected_text(spec: RuleSpec) -> str | None:
    if spec.rule == "between":
        return f"[{spec.min}, {spec.max}]"
    if spec.rule == "allowed_values":
        return str(spec.values)
    if spec.rule == "regex":
        return spec.pattern
    if spec.rule in {"min_rows", "max_null_ratio", "row_count_change"}:
        return str(spec.threshold)
    if spec.rule in {"unique", "required_columns"}:
        return ",".join(spec.columns or [])
    return None


def evaluate_rules(
    df: DataFrame,
    specs: list[RuleSpec],
    previous_row_count: int | None = None,
) -> tuple[list[dict], Column | None, int]:
    validate_specs(specs)
    available = set(df.columns)
    results: dict[str, dict] = {}
    aggregations = [F.count(F.lit(1)).alias("__total__")]
    row_rules: list[RuleSpec] = []
    null_rules: list[RuleSpec] = []
    quarantine: Column | None = None

    for spec in specs:
        if spec.rule == "required_columns":
            missing = [name for name in (spec.columns or []) if name not in available]
            results[spec.name] = _result(
                spec,
                "failed" if missing else "passed",
                failed_rows=len(missing),
                expected=_expected_text(spec),
                message=f"Отсутствуют столбцы: {missing}" if missing else None,
            )
        elif spec.rule in ROW_RULES:
            if spec.column not in available:
                results[spec.name] = _result(
                    spec, "skipped", expected=_expected_text(spec),
                    message=f"Столбец {spec.column} отсутствует",
                )
                continue
            condition = row_failure_condition(spec)
            aggregations.append(
                F.sum(F.when(condition, 1).otherwise(0)).alias(f"r::{spec.name}")
            )
            row_rules.append(spec)
            if spec.quarantine:
                quarantine = condition if quarantine is None else (quarantine | condition)
        elif spec.rule == "max_null_ratio":
            if spec.column not in available:
                results[spec.name] = _result(
                    spec, "skipped", expected=_expected_text(spec),
                    message=f"Столбец {spec.column} отсутствует",
                )
                continue
            aggregations.append(
                F.sum(F.when(_col(spec.column).isNull(), 1).otherwise(0)).alias(f"n::{spec.name}")
            )
            null_rules.append(spec)

    aggregated = df.agg(*aggregations).first().asDict()
    total = int(aggregated["__total__"] or 0)

    for spec in row_rules:
        failed = int(aggregated[f"r::{spec.name}"] or 0)
        results[spec.name] = _result(
            spec,
            "failed" if failed else "passed",
            failed_rows=failed,
            observed_value=failed,
            expected=_expected_text(spec),
        )

    for spec in null_rules:
        nulls = int(aggregated[f"n::{spec.name}"] or 0)
        ratio = (nulls / total) if total else 0.0
        threshold = spec.threshold if spec.threshold is not None else 0.0
        results[spec.name] = _result(
            spec,
            "failed" if ratio > threshold else "passed",
            failed_rows=nulls,
            observed_value=round(ratio, 6),
            expected=_expected_text(spec),
        )

    for spec in specs:
        if spec.rule == "min_rows":
            threshold = int(spec.threshold if spec.threshold is not None else 1)
            results[spec.name] = _result(
                spec,
                "failed" if total < threshold else "passed",
                failed_rows=0,
                observed_value=total,
                expected=_expected_text(spec),
            )
        elif spec.rule == "unique":
            columns = [name for name in (spec.columns or []) if name in available]
            if not spec.columns or len(columns) != len(spec.columns):
                results[spec.name] = _result(
                    spec, "skipped", expected=_expected_text(spec),
                    message="Ключевые столбцы отсутствуют",
                )
                continue
            grouped = df.groupBy(*[_col(name) for name in columns]).count()
            duplicates = grouped.filter(F.col("count") > 1).agg(
                F.sum(F.col("count") - 1).alias("extra")
            ).first()["extra"]
            duplicates = int(duplicates or 0)
            results[spec.name] = _result(
                spec,
                "failed" if duplicates else "passed",
                failed_rows=duplicates,
                observed_value=duplicates,
                expected=_expected_text(spec),
            )
        elif spec.rule == "row_count_change":
            if not previous_row_count:
                results[spec.name] = _result(
                    spec, "skipped", expected=_expected_text(spec),
                    message="Нет предыдущего batch для сравнения",
                )
                continue
            change = abs(total - previous_row_count) / previous_row_count
            threshold = spec.threshold if spec.threshold is not None else 0.5
            results[spec.name] = _result(
                spec,
                "failed" if change > threshold else "passed",
                failed_rows=0,
                observed_value=round(change, 6),
                expected=_expected_text(spec),
            )

    ordered = [results[spec.name] for spec in specs if spec.name in results]
    return ordered, quarantine, total
