import hashlib
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path

from backend.app.core.config import settings
from backend.etl.common.versions import resolve_published, version_path

LAYERS = ("bronze", "silver", "quarantine", "gold")


@dataclass(frozen=True)
class RunContext:
    dataset_id: str
    version_id: str
    batch_id: str
    job_id: str
    source_uri: str | None = None
    schema_version: str = "1.0"
    data_root: str = field(default_factory=lambda: settings.DATA_LAKE_PATH)
    attempt_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    orchestrator_run_id: str | None = None
    config_checksum: str | None = None
    code_version: str | None = None

    @property
    def run_key(self) -> str:
        raw = f"{self.dataset_id}:{self.version_id}:{self.batch_id}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]

    def layer_dir(self, layer: str) -> Path:
        if layer not in LAYERS:
            raise ValueError(f"Неизвестный слой: {layer}")
        return (
            Path(self.data_root)
            / layer
            / f"dataset_id={self.dataset_id}"
            / f"batch_id={self.batch_id}"
        )

    def staging_dir(self, layer: str) -> Path:
        return self.layer_dir(layer) / "_attempts" / self.attempt_id

    def version_dir(self, layer: str) -> Path:
        return version_path(self.layer_dir(layer), self.attempt_id)

    def published_dir(self, layer: str) -> Path:
        return resolve_published(self.layer_dir(layer))

    def manifest_path(self, layer: str) -> Path:
        return self.layer_dir(layer) / "manifest.json"

    def log_fields(self) -> dict:
        return {
            "dataset_id": self.dataset_id,
            "batch_id": self.batch_id,
            "run_id": self.run_key,
            "job_id": self.job_id,
        }

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict) -> "RunContext":
        known = {item for item in cls.__dataclass_fields__}
        return cls(**{key: value for key, value in payload.items() if key in known})

    @classmethod
    def from_ids(
        cls,
        dataset_id: str,
        version_id: str,
        job_id: str,
        batch_id: str,
        **extra,
    ) -> "RunContext":
        for name, value in (
            ("dataset_id", dataset_id),
            ("version_id", version_id),
            ("job_id", job_id),
            ("batch_id", batch_id),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"Пустое значение: {name}")
        return cls(
            dataset_id=dataset_id,
            version_id=version_id,
            batch_id=batch_id,
            job_id=job_id,
            **extra,
        )
