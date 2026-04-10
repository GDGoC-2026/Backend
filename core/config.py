from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_name: str = "FastAPI Starter"
    environment: str = "development"
    secret_key: str = ""
    access_token_expire_minutes: int = 60

    database_url: str = ""
    redis_url: str = ""

    oauth_provider: str = "google"
    google_client_id: str | None = None
    google_client_secret: str | None = None
    google_redirect_uri: str | None = None

    github_client_id: str | None = None
    github_client_secret: str | None = None
    github_redirect_uri: str | None = None

    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_username: str = "neo4j"
    neo4j_password: str = "password"

    milvus_uri: str = "http://localhost:19530"

    # --- LightRAG / Gemini ---
    gemini_api_key: str = ""
    lightrag_working_dir: str = "./lightrag_data"

    model_config = SettingsConfigDict(
        env_file=("Backend/.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

@lru_cache
def get_settings() -> Settings:
    return Settings()

settings = get_settings()
