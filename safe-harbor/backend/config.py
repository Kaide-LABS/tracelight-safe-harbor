import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    openai_api_key: str = "sk-mock-key"
    gemini_api_key: str = ""
    max_file_size_mb: int = 25
    max_retries: int = 3
    generation_timeout_s: int = 600
    gpt4o_model: str = "gpt-4o"
    gemini_model: str = "gemini-3.1-pro-preview"
    gemini_fast_model: str = "gemini-3-flash-preview"
    generation_temperature: float = 0.3
    google_service_account_path: str = "./service-account.json"
    google_drive_folder_id: str = "1RANk3O4ilPsHwtNqHDK4IBzDtRpL4276"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

def get_settings() -> Settings:
    return Settings()
