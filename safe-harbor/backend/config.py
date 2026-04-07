import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    openai_api_key: str = "sk-mock-key"
    google_cloud_project: str = "tracelight-demo"
    google_cloud_location: str = "us-central1"
    max_file_size_mb: int = 25
    max_retries: int = 3
    generation_timeout_s: int = 60
    gpt4o_model: str = "gpt-4o"
    gemini_model: str = "gemini-2.0-flash"
    generation_temperature: float = 0.3

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

def get_settings() -> Settings:
    return Settings()
