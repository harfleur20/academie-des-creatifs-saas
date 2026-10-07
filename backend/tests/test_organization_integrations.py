from cryptography.fernet import Fernet

from app.services.organization_integrations import decrypt_secret, encrypt_secret


def test_integration_secret_is_encrypted_at_rest(monkeypatch):
    monkeypatch.setenv("INTEGRATION_ENCRYPTION_KEY", Fernet.generate_key().decode("utf-8"))
    secret = "sk-test-this-is-a-private-school-key"

    encrypted = encrypt_secret(secret)

    assert encrypted != secret
    assert secret not in encrypted
    assert decrypt_secret(encrypted) == secret
