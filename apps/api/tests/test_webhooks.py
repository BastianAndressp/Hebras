import hashlib
import hmac
from app.webhooks import inbound_messages, is_valid_signature
from app.config import settings


def test_signature_validation(monkeypatch):
    monkeypatch.setattr(settings, "whatsapp_app_secret", "a-real-app-secret-for-tests")
    raw = b'{"object":"whatsapp_business_account"}'
    digest = hmac.new(settings.whatsapp_app_secret.encode(), raw, hashlib.sha256).hexdigest()
    assert is_valid_signature(raw, f"sha256={digest}")
    assert not is_valid_signature(raw, "sha256=invalid")


def test_signature_rejected_when_missing_header(monkeypatch):
    monkeypatch.setattr(settings, "whatsapp_app_secret", "a-real-app-secret-for-tests")
    assert not is_valid_signature(b"{}", None)


def test_signature_rejected_when_secret_not_configured(monkeypatch):
    monkeypatch.setattr(settings, "whatsapp_app_secret", "change-me")
    raw = b'{"object":"whatsapp_business_account"}'
    digest = hmac.new(b"whatever", raw, hashlib.sha256).hexdigest()
    assert not is_valid_signature(raw, f"sha256={digest}")


def test_extracts_only_text_messages():
    payload = {"entry": [{"changes": [{"value": {"metadata": {"phone_number_id": "phone-1"}, "messages": [
        {"id": "message-1", "from": "56911111111", "type": "text", "text": {"body": "Hola"}},
        {"id": "message-2", "from": "56911111111", "type": "image"},
    ]}}]}]}
    messages = list(inbound_messages(payload))
    assert messages == [{"meta_message_id": "message-1", "phone_number_id": "phone-1", "contact_phone": "56911111111", "text": "Hola", "timestamp": None}]

