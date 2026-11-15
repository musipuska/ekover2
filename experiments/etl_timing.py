import argparse
import hashlib
import json
import os
import sys
import tempfile
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
_ROOT = Path(tempfile.mkdtemp(prefix="ekover-bench-"))
os.environ["DATA_LAKE_PATH"] = str(_ROOT / "lake")
os.environ["DATABASE_URL"] = f"sqlite:///{_ROOT / 'bench.db'}"

import numpy as np
import pandas as pd

from backend.etl.common.config import PipelineConfig, RuleSpec
from backend.etl.jobs.full_pipeline import run_pipeline


def write_csv(path, rows):
    rng = np.random.default_rng(0)
    pd.DataFrame(
        {
            "station_id": rng.integers(0, 50, rows).astype(str),
            "measured_at": pd.Timestamp("2026-01-01") + pd.to_timedelta(np.arange(rows), unit="m"),
            "ph": rng.normal(7.2, 0.2, rows),
            "temperature": rng.normal(15, 2, rows),
        }
    ).to_csv(path, index=False)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sizes", type=int, nargs="+", default=[100_000, 1_000_000])
    parser.add_argument("--out", default="experiments/results_etl_timing.json")
    args = parser.parse_args()

    root = _ROOT
    from backend.app.infrastructure.database.session import Base, engine

    Base.metadata.create_all(bind=engine)
    from backend.app.infrastructure.database.models import Dataset, DatasetVersion, ETLJob
    from backend.app.infrastructure.database.session import SessionLocal

    config = PipelineConfig(
        timestamp_columns=["measured_at"],
        rules=[RuleSpec(name="ph", rule="between", column="ph", min=0, max=14, severity="warning")],
    )
    results = []
    for rows in args.sizes:
        ids = [str(uuid.uuid4()) for _ in range(4)]
        dataset_id, version_id, job_id, batch_id = ids
        csv_path = root / f"{rows}.csv"
        write_csv(csv_path, rows)
        db = SessionLocal()
        db.add(Dataset(id=dataset_id, name="bench", status="uploaded"))
        db.add(DatasetVersion(id=version_id, dataset_id=dataset_id, source_uri=str(csv_path),
                              file_format="csv", checksum=hashlib.sha256(csv_path.read_bytes()).hexdigest(), source_filename=csv_path.name,
                              file_size_bytes=csv_path.stat().st_size, schema_version="1.0"))
        db.add(ETLJob(id=job_id, dataset_version_id=version_id, batch_id=batch_id, status="queued"))
        db.commit()
        db.close()
        start = time.perf_counter()
        run_pipeline(dataset_id, version_id, job_id, batch_id, config=config)
        total = round(time.perf_counter() - start, 2)
        db = SessionLocal()
        metrics = json.loads(db.get(ETLJob, job_id).metrics or "{}")
        db.close()
        results.append({"rows": rows, "total_seconds": total, "metrics": metrics})
        print(rows, total)

    Path(args.out).write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
