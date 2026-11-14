import json

import httpx
import pytest

from backend.etl.common import publish
from backend.etl.common.exceptions import (
    InfrastructureError,
    QualityGateError,
    StorageError,
    ValidationError,
)
from backend.etl.common.run_context import RunContext
from backend.etl.common.source_validation import validate_source_file
from backend.etl.quality.gate import allows_downstream, evaluate_gate, quality_score
from backend.etl.storage.local import LocalStorageClient
from backend.etl.storage.s3 import S3StorageClient
from backend.etl.transformations.silver import normalize_column_name


def test_normalize_column_name():
    assert normalize_column_name("  Dissolved Oxygen (mg/L) ") == "dissolved_oxygen_mg_l"
    assert normalize_column_name("﻿Station ID") == "station_id"
    assert normalize_column_name("###") == "column"


def test_run_context_paths_and_key(tmp_path):
    ctx = RunContext("d", "v", "b", "j", data_root=str(tmp_path))
    other = RunContext("d", "v", "b", "other-job", data_root=str(tmp_path))
    assert ctx.run_key == other.run_key
    assert ctx.published_dir("silver") == tmp_path / "silver" / "dataset_id=d" / "batch_id=b" / "published"
    assert ctx.staging_dir("silver").parent.name == "_attempts"
    with pytest.raises(ValueError):
        ctx.layer_dir("platinum")
    assert RunContext.from_dict(ctx.to_dict()) == ctx
    with pytest.raises(ValueError):
        RunContext.from_ids("d", "", "j", "b")


def test_error_classification():
    assert StorageError("x").retryable and InfrastructureError("x").retryable
    assert not ValidationError("x").retryable and not QualityGateError("x").retryable
    assert QualityGateError("x").to_dict()["code"] == "QUALITY_GATE_FAILED"


def test_gate_levels():
    passed = {"status": "passed", "severity": "critical"}
    warn = {"status": "failed", "severity": "warning"}
    crit = {"status": "failed", "severity": "critical"}
    skipped = {"status": "skipped", "severity": "critical"}
    assert evaluate_gate([passed, skipped]) == "passed"
    assert evaluate_gate([passed, warn]) == "warning"
    assert evaluate_gate([warn, crit]) == "failed"
    assert quality_score([passed, warn, skipped]) == 0.5
    assert allows_downstream("warning") and not allows_downstream("warning", False)
    assert not allows_downstream("failed")


def test_local_storage_client(tmp_path):
    client = LocalStorageClient(tmp_path / "root")
    source = tmp_path / "a.txt"
    source.write_text("hello")
    uri = client.upload_file(source, "raw/x/a.txt")
    assert client.exists("raw/x/a.txt") and uri.endswith("a.txt")
    assert client.read_bytes("raw/x/a.txt") == b"hello"
    client.write_bytes("raw/x/b.bin", b"1")
    assert client.list_objects("raw") == ["raw/x/a.txt", "raw/x/b.bin"]
    client.download_file("raw/x/a.txt", tmp_path / "out" / "a.txt")
    assert (tmp_path / "out" / "a.txt").read_text() == "hello"
    client.delete("raw/x")
    assert client.list_objects("raw") == []
    with pytest.raises(StorageError):
        client.exists("../outside")
    with pytest.raises(StorageError):
        client.delete(".")


class FakeS3:
    def __init__(self):
        self.objects = {}

    def put_object(self, Bucket, Key, Body):
        self.objects[Key] = Body

    def get_object(self, Bucket, Key):
        import io
        return {"Body": io.BytesIO(self.objects[Key])}

    def head_object(self, Bucket, Key):
        if Key not in self.objects:
            error = Exception("missing")
            error.response = {"Error": {"Code": "404"}}
            raise error

    def delete_object(self, Bucket, Key):
        self.objects.pop(Key, None)

    def list_objects_v2(self, Bucket, Prefix, **kwargs):
        return {"Contents": [{"Key": k} for k in self.objects if k.startswith(Prefix)], "IsTruncated": False}


def test_s3_storage_client_with_fake():
    client = S3StorageClient("bucket", client=FakeS3())
    assert client.write_bytes("/a/b.txt", b"x") == "s3://bucket/a/b.txt"
    assert client.exists("a/b.txt") and not client.exists("a/c.txt")
    assert client.read_bytes("a/b.txt") == b"x"
    assert client.list_objects("a") == ["a/b.txt"]
    client.delete("a")
    assert client.list_objects("a") == []


def test_publish_requires_staging_and_archives(tmp_path):
    ctx = RunContext("d", "v", "b", "j", data_root=str(tmp_path))
    with pytest.raises(StorageError):
        publish.publish_layer(ctx, "silver")

    ctx.staging_dir("silver").mkdir(parents=True)
    (ctx.staging_dir("silver") / "part").write_text("1")
    first = publish.publish_layer(ctx, "silver", {"row_count": 1})
    assert publish.is_published(ctx, "silver") and first["row_count"] == 1

    second_ctx = RunContext("d", "v", "b", "j", data_root=str(tmp_path))
    second_ctx.staging_dir("silver").mkdir(parents=True)
    (second_ctx.staging_dir("silver") / "part").write_text("2")
    second = publish.publish_layer(second_ctx, "silver")
    assert second["archived_previous"]
    archived = list((ctx.layer_dir("silver") / "_archive").iterdir())
    assert (archived[0] / "part").read_text() == "1"
    assert (ctx.published_dir("silver") / "part").read_text() == "2"
    assert publish.apply_retention(ctx, "silver", keep=0) == [archived[0].name]


def test_source_validation(tmp_path):
    path = tmp_path / "a.csv"
    path.write_text("a,b\n1,2\n", encoding="utf-8")
    info = validate_source_file(path, required_columns=["A"])
    assert info["columns"] == ["a", "b"] and info["encoding"] == "UTF-8"

    path.write_text("a,a\n1,2\n", encoding="utf-8")
    assert validate_source_file(path)["duplicate_columns"] == ["a"]

    path.write_text("a,b\n", encoding="utf-8")
    with pytest.raises(ValidationError):
        validate_source_file(path)

    path.write_text("a,,c\n1,2,3\n", encoding="utf-8")
    with pytest.raises(Exception, match="пустые"):
        validate_source_file(path)


def test_airflow_trigger_uses_basic_auth(monkeypatch):
    from backend.app.services import orchestrator_service

    captured = {}

    def fake_post(url, json, auth, timeout):
        captured.update(url=url, json=json, auth=auth)
        return httpx.Response(200, json={"dag_run_id": "run-1"}, request=httpx.Request("POST", url))

    monkeypatch.setattr(orchestrator_service.httpx, "post", fake_post)
    result = orchestrator_service.trigger_airflow_dag("ekover_etl", {"a": "b"}, "api__1")
    assert result["dag_run_id"] == "run-1"
    assert captured["url"].endswith("/dags/ekover_etl/dagRuns")
    assert captured["json"] == {"conf": {"a": "b"}, "dag_run_id": "api__1"}


def test_orchestration_conf_validation():
    from backend.etl.orchestration import context_from_conf

    with pytest.raises(ValidationError, match="job_id"):
        context_from_conf({"dataset_id": "d", "version_id": "v", "batch_id": "b"})
    ctx = context_from_conf({"dataset_id": "d", "version_id": "v", "job_id": "j", "batch_id": "b"})
    assert ctx.batch_id == "b"


def test_json_logging_formatter():
    import logging

    from backend.etl.common.logging import JsonFormatter

    record = logging.LogRecord("silver", logging.INFO, "f", 1, "published", (), None)
    record.dataset_id = "d"
    payload = json.loads(JsonFormatter().format(record))
    assert payload["component"] == "silver" and payload["dataset_id"] == "d"
    assert payload["service"] == "data-storage"
