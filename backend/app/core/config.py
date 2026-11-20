from dataclasses import dataclass
import os

from dotenv import load_dotenv


load_dotenv()


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _auth_cookie_domain() -> str:
    explicit = os.getenv("AUTH_COOKIE_DOMAIN", "").strip()
    if explicit:
        return explicit
    base_domain = os.getenv("SAAS_BASE_DOMAIN", "").strip().lower().strip(".")
    return f".{base_domain}" if base_domain else ""


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
    auth_cookie_name: str = os.getenv(
        "AUTH_COOKIE_NAME",
        "academie_saas_session",
    ).strip()
    auth_cookie_domain: str = _auth_cookie_domain()
    auth_cookie_secure: bool = _env_bool(
        "AUTH_COOKIE_SECURE",
        os.getenv("APP_ENV", "development").strip().lower() == "production",
    )
    auth_cookie_samesite: str = os.getenv(
        "AUTH_COOKIE_SAMESITE",
        "lax",
    ).strip().lower()

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
    commerce_grace_period_days: int = max(
        0,
        int(os.getenv("COMMERCE_GRACE_PERIOD_DAYS", "7")),
    )
    commerce_reservation_minutes: int = max(
        1,
        int(os.getenv("COMMERCE_RESERVATION_MINUTES", "30")),
    )
    billing_cron_secret: str = os.getenv(
        "BILLING_CRON_SECRET",
        "",
    ).strip()

    email_provider: str = os.getenv("EMAIL_PROVIDER", "brevo").strip().lower()
    brevo_api_key: str = os.getenv("BREVO_API_KEY", "").strip()
    brevo_api_base_url: str = os.getenv(
        "BREVO_API_BASE_URL",
        "https://api.brevo.com/v3",
    ).rstrip("/")
    brevo_timeout_seconds: float = max(
        1.0,
        float(os.getenv("BREVO_TIMEOUT_SECONDS", "15")),
    )
    smtp_host: str = os.getenv("SMTP_HOST", "").strip()
    smtp_port: int = int(os.getenv("SMTP_PORT", "587"))
    smtp_user: str = os.getenv("SMTP_USER", "").strip()
    smtp_password: str = os.getenv("SMTP_PASSWORD", "")
    smtp_from: str = os.getenv("SMTP_FROM", "").strip()
    smtp_from_name: str = os.getenv(
        "SMTP_FROM_NAME",
        "Académie des Créatifs",
    ).strip()
    support_email: str = os.getenv("SUPPORT_EMAIL", "").strip()
    # Queued e-mails leave within the minute, from the web process itself (communication_worker.py);
    # on by default in production only, so tests and local runs send nothing unless asked.
    communication_worker_enabled: bool = _env_bool(
        "COMMUNICATION_WORKER_ENABLED",
        os.getenv("APP_ENV", "development").strip().lower() == "production",
    )
    # The school shown, read only, to visitors of the landing page (docs/DEMO.md); empty: no demo.
    demo_organization_slug: str = os.getenv("DEMO_ORGANIZATION_SLUG", "").strip().lower()

    wapino_enabled: bool = _env_bool("WAPINO_ENABLED", False)
    wapino_base_url: str = os.getenv(
        "WAPINO_BASE_URL",
        "https://api.wapino.consolidis.com",
    ).rstrip("/")
    wapino_api_key: str = os.getenv("WAPINO_API_KEY", "").strip()
    wapino_instance: str = os.getenv("WAPINO_INSTANCE", "AcademieCreatifs").strip()
    wapino_text_endpoint: str = os.getenv(
        "WAPINO_TEXT_ENDPOINT",
        "/message/send-text",
    ).strip()
    wapino_timeout_seconds: float = max(
        1.0,
        float(os.getenv("WAPINO_TIMEOUT_SECONDS", "15")),
    )

    saas_base_domain: str = os.getenv(
        "SAAS_BASE_DOMAIN",
        "",
    ).strip().lower().strip(".")
    saas_cname_target: str = os.getenv(
        "SAAS_CNAME_TARGET",
        "",
    ).strip().lower().strip(".")
    # Other subdomains of SAAS_BASE_DOMAIN already in use (another site's), comma-separated:
    # no school can take them.
    saas_reserved_subdomains: frozenset[str] = frozenset(
        item.strip().lower() for item in os.getenv("SAAS_RESERVED_SUBDOMAINS", "").split(",") if item.strip()
    )
    # Built frontend (frontend/dist) served by the backend itself, as one origin per school domain.
    frontend_dist_dir: str = os.getenv("FRONTEND_DIST_DIR", "").strip()
    # Private teaching files and recordings use B2; public assets use Cloudinary.
    storage_provider: str = os.getenv("STORAGE_PROVIDER", "local").strip().lower()
    public_asset_provider: str = os.getenv("PUBLIC_ASSET_PROVIDER", "local").strip().lower()
    b2_endpoint_url: str = os.getenv("B2_ENDPOINT_URL", "").rstrip("/")
    b2_region: str = os.getenv("B2_REGION", "").strip()
    # Optional legacy public B2 bucket/base URL, kept only to read or migrate older objects.
    b2_bucket_name: str = os.getenv("B2_BUCKET_NAME", "").strip()
    b2_private_bucket_name: str = os.getenv("B2_PRIVATE_BUCKET_NAME", "").strip()
    b2_access_key_id: str = os.getenv("B2_ACCESS_KEY_ID", "").strip()
    b2_secret_access_key: str = os.getenv("B2_SECRET_ACCESS_KEY", "").strip()
    b2_public_base_url: str = os.getenv("B2_PUBLIC_BASE_URL", "").rstrip("/")
    cloudinary_cloud_name: str = os.getenv("CLOUDINARY_CLOUD_NAME", "").strip()
    cloudinary_api_key: str = os.getenv("CLOUDINARY_API_KEY", "").strip()
    cloudinary_api_secret: str = os.getenv("CLOUDINARY_API_SECRET", "").strip()
    # "jaas" (Jitsi hosted by 8x8) or "jitsi" (self-hosted Jitsi, see infra/live).
    live_provider: str = os.getenv("LIVE_PROVIDER", "jaas").strip().lower()
    jitsi_domain: str = os.getenv("JITSI_DOMAIN", "").strip().removeprefix("https://").rstrip("/")
    jitsi_app_id: str = os.getenv("JITSI_APP_ID", "").strip()
    jitsi_app_secret: str = os.getenv("JITSI_APP_SECRET", "").strip()
    jitsi_xmpp_domain: str = os.getenv("JITSI_XMPP_DOMAIN", "meet.jitsi").strip()
    # Students the live servers carry at once, all schools together; 0: no ceiling. Above it,
    # a new live class waits (live_classes.py). Raise it with each video relay (infra/live).
    live_platform_max_participants: int = max(0, int(os.getenv("LIVE_PLATFORM_MAX_PARTICIPANTS", "0") or 0))
    jaas_enabled: bool = _env_bool("JAAS_ENABLED", False)
    jaas_domain: str = os.getenv("JAAS_DOMAIN", "8x8.vc").strip().removeprefix("https://").rstrip("/")
    jaas_app_id: str = os.getenv("JAAS_APP_ID", "").strip()
    jaas_kid: str = os.getenv("JAAS_KID", "").strip()
    jaas_private_key: str = os.getenv("JAAS_PRIVATE_KEY", "").replace("\\n", "\n").strip()
    jaas_private_key_file: str = os.getenv("JAAS_PRIVATE_KEY_FILE", "").strip()
    jaas_webhook_secret: str = os.getenv("JAAS_WEBHOOK_SECRET", "").strip()
    jaas_branding_token: str = os.getenv("JAAS_BRANDING_TOKEN", "").strip()
    jaas_recording_enabled: bool = _env_bool("JAAS_RECORDING_ENABLED", False)
    live_replay_download_enabled: bool = _env_bool("LIVE_REPLAY_DOWNLOAD_ENABLED", True)

    @property
    def b2_configured(self) -> bool:
        return bool(
            self.b2_endpoint_url.startswith("https://")
            and self.b2_region
            and self.b2_private_bucket_name
            and self.b2_access_key_id
            and self.b2_secret_access_key
        )

    @property
    def cloudinary_configured(self) -> bool:
        return bool(self.cloudinary_cloud_name and self.cloudinary_api_key and self.cloudinary_api_secret)

    @property
    def cloudinary_public_base_url(self) -> str:
        if not self.cloudinary_cloud_name:
            return ""
        return f"https://res.cloudinary.com/{self.cloudinary_cloud_name}"

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

    def validate_production_security(self) -> None:
        if self.storage_provider not in {"local", "b2"}:
            raise RuntimeError("STORAGE_PROVIDER doit valoir local ou b2.")
        if self.public_asset_provider not in {"local", "cloudinary"}:
            raise RuntimeError("PUBLIC_ASSET_PROVIDER doit valoir local ou cloudinary.")
        if self.environment == "production" and (
            self.storage_provider != "b2"
            or not self.b2_configured
            or self.public_asset_provider != "cloudinary"
            or not self.cloudinary_configured
        ):
            raise RuntimeError(
                "La production exige un bucket B2 privé configuré et Cloudinary pour les médias publics."
            )
        if self.environment == "production" and (
            len(self.jwt_secret_key.strip()) < 32
            or self.jwt_secret_key == "academie-saas-development-secret-change-me"
        ):
            raise RuntimeError("JWT_SECRET_KEY doit être un secret unique d'au moins 32 caractères en production.")
        if self.auth_cookie_samesite not in {"lax", "strict", "none"}:
            raise RuntimeError("AUTH_COOKIE_SAMESITE doit valoir lax, strict ou none.")
        if self.live_provider not in {"jaas", "jitsi"}:
            raise RuntimeError("LIVE_PROVIDER doit valoir jaas ou jitsi.")
        if self.environment == "production" and self.live_provider == "jitsi" and (
            not self.jitsi_domain or not self.jitsi_app_id or len(self.jitsi_app_secret) < 32
        ):
            raise RuntimeError("Le Jitsi auto-hébergé exige JITSI_DOMAIN, JITSI_APP_ID et un JITSI_APP_SECRET d'au moins 32 caractères.")
        if self.environment == "production" and self.jaas_recording_enabled:
            if not all((
                self.jaas_enabled, self.jaas_app_id, self.jaas_kid,
                self.jaas_private_key or self.jaas_private_key_file,
                self.jaas_webhook_secret,
            )):
                raise RuntimeError("Les replays JaaS exigent une configuration JaaS complète et JAAS_WEBHOOK_SECRET en production.")
            if (
                self.storage_provider != "b2"
                or not self.b2_configured
            ):
                raise RuntimeError("Les replays JaaS exigent un bucket B2 privé configuré en production.")


settings = Settings()
