from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-6"
    anthropic_max_tokens: int = 4096
    anthropic_thinking_budget: int = 2048

    max_files_per_review: int = 50
    agent_timeout_seconds: int = 120
    max_retries: int = 3

    output_dir: str = "./output"
    default_format: str = "both"

    @property
    def output_path(self) -> Path:
        return Path(self.output_dir).resolve()


settings = Settings()
