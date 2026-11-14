import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import joblib

from backend.app.core.config import settings

STATUSES = ("candidate", "staging", "production", "archived")
TRANSITIONS = {
    "candidate": {"staging", "archived"},
    "staging": {"production", "candidate", "archived"},
    "production": {"archived"},
    "archived": set(),
}
NAME_PATTERN = re.compile(r"^[A-Za-z0-9_.-]{1,80}$")


class RegistryError(Exception):
    pass


class ModelRegistry:
    def __init__(self, root: str | Path | None = None) -> None:
        base = Path(root) if root else Path(settings.DATA_LAKE_PATH) / "artifacts" / "models"
        self.root = base
        self.root.mkdir(parents=True, exist_ok=True)

    def _model_dir(self, name: str) -> Path:
        if not NAME_PATTERN.match(name):
            raise RegistryError(f"Недопустимое имя модели: {name}")
        return self.root / name

    @staticmethod
    def _write_json(path: Path, payload: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        handle, temp = tempfile.mkstemp(dir=path.parent, prefix=".tmp-")
        with os.fdopen(handle, "w", encoding="utf-8") as file:
            json.dump(payload, file, ensure_ascii=False, indent=2, default=str)
        os.replace(temp, path)

    def _versions(self, name: str) -> list[int]:
        directory = self._model_dir(name)
        if not directory.is_dir():
            return []
        return sorted(
            int(item.name[1:])
            for item in directory.iterdir()
            if item.is_dir() and re.fullmatch(r"v\d+", item.name)
        )

    def register(self, name: str, model, metadata: dict) -> dict:
        versions = self._versions(name)
        number = (versions[-1] + 1) if versions else 1
        version = f"v{number}"
        target = self._model_dir(name) / version
        target.mkdir(parents=True, exist_ok=False)
        joblib.dump(model, target / "model.joblib")
        record = {
            **metadata,
            "model_name": name,
            "model_version": version,
            "status": "candidate",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "approved_by": None,
            "comments": [],
        }
        self._write_json(target / "metadata.json", record)
        return record

    def get_metadata(self, name: str, version: str) -> dict:
        path = self._model_dir(name) / version / "metadata.json"
        if not path.is_file():
            raise RegistryError(f"Модель {name}:{version} не найдена")
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)

    def list_versions(self, name: str) -> list[dict]:
        return [self.get_metadata(name, f"v{number}") for number in self._versions(name)]

    def list_models(self) -> list[dict]:
        models = []
        for directory in sorted(self.root.iterdir()):
            if not directory.is_dir() or not NAME_PATTERN.match(directory.name):
                continue
            versions = self.list_versions(directory.name)
            if not versions:
                continue
            production = [item for item in versions if item["status"] == "production"]
            models.append(
                {
                    "model_name": directory.name,
                    "latest_version": versions[-1]["model_version"],
                    "production_version": production[-1]["model_version"] if production else None,
                    "versions": versions,
                }
            )
        return models

    def set_status(
        self,
        name: str,
        version: str,
        status: str,
        approved_by: str | None = None,
        comment: str | None = None,
    ) -> dict:
        if status not in STATUSES:
            raise RegistryError(f"Неизвестный статус: {status}")
        metadata = self.get_metadata(name, version)
        current = metadata["status"]
        if status not in TRANSITIONS[current]:
            raise RegistryError(f"Переход {current} → {status} запрещён")
        if status == "production":
            if not approved_by or not approved_by.strip():
                raise RegistryError("Для production требуется approved_by")
            for other in self.list_versions(name):
                if other["status"] == "production":
                    other["status"] = "archived"
                    self._write_json(self._model_dir(name) / other["model_version"] / "metadata.json", other)
            metadata["approved_by"] = approved_by
        metadata["status"] = status
        if comment:
            metadata["comments"].append(
                {"at": datetime.now(timezone.utc).isoformat(), "text": comment}
            )
        self._write_json(self._model_dir(name) / version / "metadata.json", metadata)
        return metadata

    def resolve(self, name: str, version: str | None = None, allow_candidate: bool = False) -> dict:
        if version:
            return self.get_metadata(name, version)
        versions = self.list_versions(name)
        production = [item for item in versions if item["status"] == "production"]
        if production:
            return production[-1]
        if allow_candidate and versions:
            return versions[-1]
        raise RegistryError(f"Для модели {name} нет production-версии")

    def load(self, name: str, version: str | None = None, allow_candidate: bool = False):
        metadata = self.resolve(name, version, allow_candidate)
        path = self._model_dir(name) / metadata["model_version"] / "model.joblib"
        return joblib.load(path), metadata
