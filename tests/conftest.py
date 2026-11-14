import hashlib
import os
import sys
import tempfile
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

_TMP_ROOT = Path(tempfile.mkdtemp(prefix="ekover-tests-"))
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP_ROOT / 'test.db'}"
os.environ["DATA_LAKE_PATH"] = str(_TMP_ROOT / "lake")
os.environ.setdefault("SPARK_SHUFFLE_PARTITIONS", "2")

import pytest

from backend.app.infrastructure.database import models
from backend.app.infrastructure.database.session import Base, SessionLocal, engine
from backend.etl.common.spark import get_spark


@pytest.fixture(scope="session", autouse=True)
def database():
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture(scope="session")
def spark():
    session = get_spark("ekover-tests")
    yield session
    session.stop()


@pytest.fixture(scope="session")
def register_csv():
    def factory(content: str | bytes, filename: str = "data.csv", encoding: str = "utf-8") -> dict:
        dataset_id, version_id, job_id, batch_id = (str(uuid.uuid4()) for _ in range(4))
        raw_dir = Path(os.environ["DATA_LAKE_PATH"]) / "raw" / dataset_id
        raw_dir.mkdir(parents=True, exist_ok=True)
        path = raw_dir / f"{version_id}_{filename}"
        payload = content if isinstance(content, bytes) else content.encode(encoding)
        path.write_bytes(payload)

        db = SessionLocal()
        try:
            db.add(models.Dataset(id=dataset_id, name=Path(filename).stem, status="uploaded"))
            db.add(
                models.DatasetVersion(
                    id=version_id,
                    dataset_id=dataset_id,
                    source_uri=str(path),
                    file_format="csv",
                    checksum=hashlib.sha256(payload).hexdigest(),
                )
            )
            db.add(models.ETLJob(id=job_id, dataset_version_id=version_id, batch_id=batch_id, status="queued"))
            db.commit()
        finally:
            db.close()

        return {
            "dataset_id": dataset_id,
            "version_id": version_id,
            "job_id": job_id,
            "batch_id": batch_id,
            "path": path,
        }

    return factory
