# -*- coding: utf-8 -*-
"""哈希 / 密码加密工具（纯标准库，内网离线可用）。"""
import hashlib
import hmac
import secrets
import base64
from datetime import datetime

PBKDF2_ITERATIONS = 120000


def hash_password(password: str) -> str:
    """生成 pbkdf2_sha256$iterations$salt$hash 格式的密码哈希。"""
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), PBKDF2_ITERATIONS)
    return 'pbkdf2_sha256$%d$%s$%s' % (PBKDF2_ITERATIONS, salt, dk.hex())


def verify_password(password: str, stored: str) -> bool:
    if not stored or '$' not in stored:
        return False
    try:
        algo, iterations, salt, digest = stored.split('$', 3)
        if algo != 'pbkdf2_sha256':
            return False
        dk = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), int(iterations))
        return hmac.compare_digest(dk.hex(), digest)
    except Exception:
        return False


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            h.update(chunk)
    return h.hexdigest()


def new_token() -> str:
    return secrets.token_hex(16)


def decode_data_url(data_url: str) -> bytes:
    """把 data:image/png;base64,xxx 转为二进制。"""
    if not data_url:
        return b''
    if ',' in data_url and data_url.strip().startswith('data:'):
        data_url = data_url.split(',', 1)[1]
    try:
        return base64.b64decode(data_url)
    except Exception:
        return b''


def timestamp_str():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')
