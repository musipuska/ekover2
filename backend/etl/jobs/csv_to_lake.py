from backend.etl.jobs.full_pipeline import main, run_pipeline


def run_etl(dataset_id: str, version_id: str, job_id: str, batch_id: str, force: bool = False) -> dict:
    return run_pipeline(
        dataset_id=dataset_id,
        version_id=version_id,
        job_id=job_id,
        batch_id=batch_id,
        force=force,
    )


if __name__ == "__main__":
    main()
