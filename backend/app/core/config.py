"""
Core Configuration Module for FastAPI Backend

Manages application settings via Pydantic BaseSettings.
Extra env vars are ignored so the shared .env file doesn't cause validation errors.
"""

import os
import json
from typing import List, Optional
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",   # silently ignore unknown env vars (e.g. NEXT_PUBLIC_API_URL)
    )

    PROJECT_NAME: str = "Psychological Stress AI Enterprise API"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = "development"

    # Security / JWT
    SECRET_KEY: str = Field(
        default="super-secret-key-psychological-stress-ai-2026-production-change-me"
    )
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7   # 7 days
    REFRESH_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 30  # 30 days

    # Database
    DATABASE_URL: str = Field(
        default="sqlite+aiosqlite:///./stress_ai.db"
    )

    # CORS
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
    ]
    # Legacy alias supported by the shared .env file (JSON array string)
    ALLOWED_ORIGINS: Optional[str] = None

    # ML model artifacts directory
    ML_MODELS_DIR: str = Field(
        default=os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..", "..", "ml_engine", "models")
        )
    )

    @model_validator(mode="after")
    def _merge_legacy_cors(self) -> "Settings":
        if self.ALLOWED_ORIGINS:
            try:
                parsed = json.loads(self.ALLOWED_ORIGINS)
            except json.JSONDecodeError:
                parsed = [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]
            if isinstance(parsed, list):
                merged = [*self.BACKEND_CORS_ORIGINS, *[str(o) for o in parsed]]
                self.BACKEND_CORS_ORIGINS = list(dict.fromkeys(merged))
        return self


settings = Settings()