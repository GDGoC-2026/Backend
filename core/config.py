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

    milvus_uri: str = ""
    milvus_token: str = ""
    
    # AI & LLM
    gemini_api_key: str = ""
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dim: int = 384
    
    # Recommendation settings
    recommendation_threshold: float = 0.5  # Min score to trigger recommendation
    recommendation_trigger_lines: int = 10  # Lines of code/notes to trigger recommendation

    # --- LightRAG ---
    vertex_ai_project_id: str = ""
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
