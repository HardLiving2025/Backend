import json
import base64
import hmac
import hashlib
import time

SECRET_KEY = "SUPER_SECRET_KEY"   # 나중에 꼭 환경변수로 변경 (중요)
ALGORITHM = "HS256"
EXPIRE_MINUTES = 60 * 24 * 7   # 7일


def base64_url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def base64_url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def create_access_token(data: dict) -> str:
    header = {"alg": ALGORITHM, "typ": "JWT"}
    payload = data.copy()
    payload["exp"] = int(time.time()) + EXPIRE_MINUTES * 60

    # Encode header & payload
    header_encoded = base64_url_encode(json.dumps(header).encode())
    payload_encoded = base64_url_encode(json.dumps(payload).encode())

    # Signature = HMACSHA256(header + "." + payload)
    message = f"{header_encoded}.{payload_encoded}".encode()
    signature = hmac.new(
        SECRET_KEY.encode(), message, hashlib.sha256
    ).digest()

    signature_encoded = base64_url_encode(signature)

    return f"{header_encoded}.{payload_encoded}.{signature_encoded}"


def decode_access_token(token: str) -> dict:
    try:
        header_b64, payload_b64, signature_b64 = token.split(".")

        message = f"{header_b64}.{payload_b64}".encode()
        expected_signature = hmac.new(
            SECRET_KEY.encode(), message, hashlib.sha256
        ).digest()

        if base64_url_encode(expected_signature) != signature_b64:
            raise ValueError("Invalid signature")

        payload = json.loads(base64_url_decode(payload_b64))

        if payload.get("exp") < int(time.time()):
            raise ValueError("Token expired")

        return payload

    except Exception as e:
        raise ValueError("Invalid token")
