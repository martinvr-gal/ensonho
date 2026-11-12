from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL


class Settings(BaseSettings):
    app_env: str = "development"
    cors_origins: str = "http://localhost:3000"
    database_url: str = "sqlite:///./data/ensonho.db"
    supabase_url: str | None = None
    supabase_project_ref: str | None = None
    supabase_db_host: str = "aws-1-eu-west-1.pooler.supabase.com"
    supabase_db_port: int = 5432
    supabase_db_password: SecretStr | None = None
    supabase_jwt_secret: str | None = None
    supabase_service_role_key: SecretStr | None = None
    supabase_storage_bucket: str = "instagram-import-media"
    instagram_graph_access_token: str | None = None
    instagram_graph_api_version: str = "v27.0"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def effective_database_url(self) -> str | URL:
        password = (
            self.supabase_db_password.get_secret_value()
            if self.supabase_db_password is not None
            else ""
        )
        if not password:
            return self.database_url
        if not self.supabase_project_ref:
            raise ValueError("SUPABASE_PROJECT_REF é necesario para conectar con Supabase")
        return URL.create(
            "postgresql+psycopg",
            username=f"postgres.{self.supabase_project_ref}",
            password=password,
            host=self.supabase_db_host,
            port=self.supabase_db_port,
            database="postgres",
            query={"sslmode": "require"},
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
