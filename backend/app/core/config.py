from dataclasses import dataclass
import os


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    app_name: str = "Académie des Créatifs SaaS API"
    app_version: str = "0.3.0"
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

    payment_mode: str = os.getenv("PAYMENT_MODE", "production").strip().lower()
    allow_demo_payments: bool = _env_bool("ALLOW_DEMO_PAYMENTS", False)
    demo_payment_amount_cents: int = max(
        1,
        int(os.getenv("DEMO_PAYMENT_AMOUNT_CENTS", "100")),
    )

    @property
    def demo_payments_enabled(self) -> bool:
        return (
            self.environment != "production"
            and self.payment_mode == "demo"
            and self.allow_demo_payments
        )


settings = Settings()
