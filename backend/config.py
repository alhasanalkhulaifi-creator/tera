from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite:////opt/tera/tera.db"
    n8n_webhook_url: str = "http://localhost:5678/webhook/tera-event"
    log_level: str = "INFO"

    class Config:
        env_file = ".env"


settings = Settings()
