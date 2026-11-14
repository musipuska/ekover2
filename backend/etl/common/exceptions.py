class ETLError(Exception):
    code = "ETL_ERROR"
    retryable = False
    severity = "error"
    notify = False

    def __init__(self, message: str, details: dict | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "message": self.message,
            "retryable": self.retryable,
            "severity": self.severity,
            "details": self.details,
        }


class ValidationError(ETLError):
    code = "VALIDATION_ERROR"


class SchemaError(ETLError):
    code = "SCHEMA_ERROR"


class StorageError(ETLError):
    code = "STORAGE_ERROR"
    retryable = True


class TransformationError(ETLError):
    code = "TRANSFORMATION_ERROR"


class QualityGateError(ETLError):
    code = "QUALITY_GATE_FAILED"
    severity = "critical"
    notify = True


class InfrastructureError(ETLError):
    code = "INFRASTRUCTURE_ERROR"
    retryable = True
    severity = "critical"
    notify = True
