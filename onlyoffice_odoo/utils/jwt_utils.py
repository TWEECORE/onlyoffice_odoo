# Copyright (C) 2026 Ascensio System SIA

import datetime

import jwt

from odoo.addons.onlyoffice_odoo.utils import config_utils


def is_jwt_enabled(env):
    return bool(config_utils.get_jwt_secret(env))


def encode_payload(env, payload, secret=None, operation=None):
    """Sign a payload; ``operation`` ("command", "converter", "docbuilder") restricts the token
    to that service of ONLYOFFICE Docs 10+, which checks it (services.CoAuthoring.token.purposeCheck).
    """
    if secret is None:
        secret = config_utils.get_jwt_secret(env)
    now = datetime.datetime.now(datetime.timezone.utc)
    exp = now + datetime.timedelta(hours=24)
    payload["iat"] = int(now.timestamp())
    payload["exp"] = int(exp.timestamp())
    claims = {**payload, "operation": operation} if operation else payload
    return jwt.encode(claims, secret, algorithm="HS256")


def decode_token(env, token, secret=None):
    if secret is None:
        secret = config_utils.get_jwt_secret(env)
    return jwt.decode(token, secret, algorithms=["HS256"])
