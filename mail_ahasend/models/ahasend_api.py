# Copyright 2026 AhaSend B.V.
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import base64
import hashlib
import hmac
import logging
import time
from collections import namedtuple

import requests

from odoo import api, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

DEFAULT_API_URL = "https://api.ahasend.com"
DEFAULT_TIMEOUT = 10
# Webhooks older or newer than this many seconds are refused
WEBHOOK_TOLERANCE = 5 * 60

AhaSendParameters = namedtuple(
    "AhaSendParameters",
    (
        "api_key",
        "account_id",
        "api_url",
        "domain",
        "webhooks_base_url",
        "timeout",
    ),
)


class AhaSendApi(models.AbstractModel):
    _name = "ahasend.api"
    _description = "AhaSend API helper"

    @api.model
    def _ahasend_values(self):
        """Read the AhaSend settings from the system parameters."""
        icp = self.env["ir.config_parameter"].sudo()
        try:
            timeout = int(icp.get_param("ahasend.timeout", DEFAULT_TIMEOUT))
        except ValueError:
            timeout = DEFAULT_TIMEOUT
        return AhaSendParameters(
            api_key=icp.get_param("ahasend.api_key") or False,
            account_id=icp.get_param("ahasend.account_id") or False,
            api_url=(icp.get_param("ahasend.api_url") or DEFAULT_API_URL).rstrip("/"),
            domain=icp.get_param("ahasend.domain") or False,
            webhooks_base_url=(
                icp.get_param("ahasend.webhooks_base_url")
                or icp.get_param("web.base.url")
                or ""
            ).rstrip("/"),
            timeout=timeout,
        )

    @api.model
    def _ahasend_request(self, method, path, params=None, json=None):
        """Call the AhaSend Management API.

        :param path: path after ``/v2/accounts/{account_id}``
        :return: the decoded JSON answer, or ``{}`` for an empty answer
        """
        values = self._ahasend_values()
        if not values.api_key or not values.account_id:
            raise UserError(
                self.env._("Set the AhaSend API key and account ID in the settings.")
            )
        url = f"{values.api_url}/v2/accounts/{values.account_id}{path}"
        try:
            response = requests.request(
                method,
                url,
                params=params,
                json=json,
                headers={
                    "Authorization": f"Bearer {values.api_key}",
                    "Accept": "application/json",
                },
                timeout=values.timeout,
            )
        except requests.RequestException as error:
            _logger.warning("AhaSend API request failed: %s", error)
            raise UserError(
                self.env._("AhaSend could not be reached: %s", error)
            ) from error
        if response.status_code >= 400:
            try:
                message = response.json().get("message") or response.text
            except ValueError:
                message = response.text
            raise UserError(
                self.env._(
                    "AhaSend answered %(status)s: %(message)s",
                    status=response.status_code,
                    message=message,
                )
            )
        if not response.content:
            return {}
        return response.json()

    @api.model
    def _ahasend_public_url(self, path):
        """Return the public address of this database for ``path``.

        :raise UserError: when the Odoo URL is not a public https:// address
        """
        base_url = self._ahasend_values().webhooks_base_url
        if not base_url.startswith("https://"):
            raise UserError(
                self.env._(
                    "AhaSend can only call a public https:// address. Set the "
                    "Odoo URL in the AhaSend settings."
                )
            )
        return f"{base_url}{path}/{self.env.cr.dbname}"

    @api.model
    def _ahasend_signature_valid(self, secret, webhook_id, timestamp, signature, body):
        """Check a signed AhaSend delivery (webhook or inbound route).

        AhaSend signs ``{webhook-id}.{webhook-timestamp}.{raw body}`` with
        HMAC-SHA256, keyed with the literal UTF-8 bytes of the secret, and sends
        the result as ``v1,<base64>``. Several signatures can be sent, separated
        by spaces.

        :param body: the raw request body as bytes
        :return: True when the delivery is authentic and recent
        """
        if not secret or not webhook_id or not timestamp or not signature:
            return False
        try:
            sent_at = int(timestamp)
        except ValueError:
            return False
        if abs(time.time() - sent_at) > WEBHOOK_TOLERANCE:
            return False
        signed = b".".join([webhook_id.encode(), timestamp.encode(), body])
        expected = base64.b64encode(
            hmac.new(secret.encode(), signed, hashlib.sha256).digest()
        ).decode()
        for candidate in signature.split(" "):
            version, _sep, value = candidate.partition(",")
            if version == "v1" and hmac.compare_digest(value, expected):
                return True
        return False
