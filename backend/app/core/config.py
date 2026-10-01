from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Settings:
    app_name: str = "Académie des Créatifs SaaS API"
    app_version: str = "0.2.0"
    api_prefix: str = "/api/v1"
    environment: str = os.getenv("APP_ENV", "development").strip().lower()
    database_url: str = os.getenv(
        "DATABASE_URL",
        "sqlite:///./academie_saas.db",
    ).strip()
    jwt_secret_key: str = os.getenv(
        "JWT_SECRET_KEY",
        "academie-saas-development-secret-change-me",
    )
    jwt_algorithm: str = os.getenv("JWT_ALGORITHM", "HS256")
    jwt_issuer: str = os.getenv("JWT_ISSUER", "academie-des-creatifs-saas")
    tenant_header: str = "X-Organization-Id"


settings = Settings()
