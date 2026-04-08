from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")

    app_name: str = "Smart School API"
    app_env: str = "development"
    secret_key: str = "change-this-secret-key-in-production"
    access_token_expire_minutes: int = 1440
    database_url: str = "sqlite:///./smart_school.db"
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:5173"]


settings = Settings()
