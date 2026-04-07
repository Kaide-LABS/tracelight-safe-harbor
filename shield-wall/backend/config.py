import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class ShieldWallSettings(BaseSettings):
    openai_api_key: str = "sk-mock-key"
    google_cloud_project: str = "tracelight-demo"
    google_cloud_location: str = "us-central1"
    max_file_size_mb: int = 50
    max_questions: int = 500
    generation_timeout_s: int = 300
    gpt4o_model: str = "gpt-4o"
    gemini_model: str = "gemini-2.0-flash"
    demo_mode: bool = True
    
    aws_region: str = "eu-west-1"
    aws_athena_database: str = "cloudtrail_logs"
    aws_athena_output_bucket: str = ""
    
    chroma_persist_dir: str = "./data/chroma_db"
    policy_chunk_size: int = 512
    policy_chunk_overlap: int = 64
    policy_top_k: int = 5

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

def get_settings() -> ShieldWallSettings:
    return ShieldWallSettings()
