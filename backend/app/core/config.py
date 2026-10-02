from dataclasses import dataclass
import os

from dotenv import load_dotenv


load_dotenv()


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class Settings:
    app_name: str = "Académie des Créatifs SaaS API"
    app_version: str = "0.3.0"
    api_prefix: str = "/api/v1"
    environment: str = os.getenv("APP_ENV", "development").strip().lower()
    database_url: str = os.getenv(
        "DATABASE_URL",
        "sqlite:///./academie_saas.db",
    ).strip()
    frontend_url: str = os.getenv(
        "FRONTEND_URL",
        "http://localhost:5173",
    ).rstrip("/")
    backend_public_url: str = os.getenv(
        "BACKEND_PUBLIC_URL",
        "http://localhost:8000",
    ).rstrip("/")

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

    tara_api_base_url: str = os.getenv(
        "TARAMONEY_API_BASE_URL",
        "https://www.dklo.co",
    ).rstrip("/")
    tara_create_payment_path: str = os.getenv(
        "TARAMONEY_CREATE_PAYMENT_PATH",
        "/api/tara/paymentlinks",
    )
    tara_verify_payment_path: str = os.getenv(
        "TARAMONEY_VERIFY_PAYMENT_PATH",
        "/api/tara/transactions/status",
    )
    tara_api_key: str = os.getenv("TARAMONEY_API_KEY", "").strip()
    tara_business_id: str = os.getenv("TARAMONEY_BUSINESS_ID", "").strip()
    tara_webhook_secret: str = os.getenv("TARAMONEY_WEBHOOK_SECRET", "").strip()
    tara_webhook_secret_header: str = os.getenv(
        "TARAMONEY_WEBHOOK_SECRET_HEADER",
        "",
    ).strip().lower()
    tara_product_picture_url: str = os.getenv(
        "TARAMONEY_PRODUCT_PICTURE_URL",
        "",
    ).strip()
    tara_timeout_seconds: float = max(
        1.0,
        float(os.getenv("TARAMONEY_TIMEOUT_SECONDS", "8")),
    )

    billing_grace_period_days: int = max(
        0,
        int(os.getenv("BILLING_GRACE_PERIOD_DAYS", "7")),
    )
    billing_cron_secret: str = os.getenv(
        "BILLING_CRON_SECRET",
        "",
    ).strip()

    saas_base_domain: str = os.getenv(
        "SAAS_BASE_DOMAIN",
        "",
    ).strip().lower().strip(".")
    saas_cname_target: str = os.getenv(
        "SAAS_CNAME_TARGET",
        "",
    ).strip().lower().strip(".")
    storage_provider: str = os.getenv("STORAGE_PROVIDER", "local").strip().lower()
    r2_endpoint_url: str = os.getenv("R2_ENDPOINT_URL", "").rstrip("/")
    r2_bucket_name: str = os.getenv("R2_BUCKET_NAME", "").strip()
    r2_access_key_id: str = os.getenv("R2_ACCESS_KEY_ID", "").strip()
    r2_secret_access_key: str = os.getenv("R2_SECRET_ACCESS_KEY", "").strip()
    r2_public_base_url: str = os.getenv("R2_PUBLIC_BASE_URL", "").rstrip("/")

    @property
    def r2_configured(self) -> bool:
        return bool(self.r2_endpoint_url and self.r2_bucket_name and self.r2_access_key_id and self.r2_secret_access_key and self.r2_public_base_url)

    organization_name_change_cooldown_days: int = max(
        1,
        int(os.getenv("ORGANIZATION_NAME_CHANGE_COOLDOWN_DAYS", "30")),
    )

    @property
    def demo_payments_enabled(self) -> bool:
        return (
            self.environment != "production"
            and self.payment_mode == "demo"
            and self.allow_demo_payments
        )

    @property
    def tara_configured(self) -> bool:
        return bool(
            self.tara_api_key
            and self.tara_business_id
            and self.tara_webhook_secret
        )


settings = Settings()
