from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    APP_NAME: str = "Ekover API"
    API_PREFIX: str = "/api/v1"

    DATABASE_URL: str = (
        f"sqlite:///{PROJECT_ROOT / 'data' / 'ekover.db'}"
    )

    STORAGE_TYPE: str = "local"
    DATA_LAKE_PATH: str = str(PROJECT_ROOT / "data")

    MAX_UPLOAD_SIZE: int = 50 * 1024 * 1024

    ORCHESTRATOR: str = "local"
    AIRFLOW_API_URL: str = "http://localhost:8080/api/v1"
    AIRFLOW_USERNAME: str = "airflow"
    AIRFLOW_PASSWORD: str = ""
    AIRFLOW_ETL_DAG_ID: str = "ekover_etl"
    AIRFLOW_ML_DAG_ID: str = "ekover_ml"
    AIRFLOW_TIMEOUT_SECONDS: float = 10.0

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )


settings = Settings()