# Copyright 2026 AhaSend B.V.
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import base64
import hashlib
import hmac
import json
import time
from unittest.mock import MagicMock

ACCOUNT_ID = "4cdd7bdd-294e-4762-892f-83d40abf5a87"
REQUEST = "odoo.addons.mail_ahasend.models.ahasend_api.requests.request"


def sign(body, secret, webhook_id="msg_test_1", timestamp=None):
    """Return the headers AhaSend signs a delivery of ``body`` with."""
    timestamp = str(int(timestamp or time.time()))
    signed = b".".join([webhook_id.encode(), timestamp.encode(), body])
    signature = base64.b64encode(
        hmac.new(secret.encode(), signed, hashlib.sha256).digest()
    ).decode()
    return {
        "webhook-id": webhook_id,
        "webhook-timestamp": timestamp,
        "webhook-signature": f"v1,{signature}",
    }


def json_response(data, status=200):
    response = MagicMock()
    response.status_code = status
    response.content = json.dumps(data).encode() if data is not None else b""
    response.text = response.content.decode()
    response.json.return_value = data
    return response


def configure(env, **params):
    """Set known AhaSend settings, whatever the database already holds."""
    icp = env["ir.config_parameter"].sudo()
    for key in (
        "ahasend.api_url",
        "ahasend.domain",
        "ahasend.webhooks_base_url",
        "ahasend.timeout",
    ):
        icp.set_param(key, False)
    icp.set_param("ahasend.api_key", "aha-sk-test")
    icp.set_param("ahasend.account_id", ACCOUNT_ID)
    for key, value in params.items():
        icp.set_param(key, value)
