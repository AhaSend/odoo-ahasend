# Copyright 2026 AhaSend B.V.
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import time
from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests import tagged

from odoo.addons.base.tests.common import BaseCommon

from .common import ACCOUNT_ID, REQUEST, configure, json_response, sign

SECRET = "aha-whsec-test-secret"


@tagged("post_install", "-at_install")
class TestAhaSendApi(BaseCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        configure(cls.env)
        cls.api = cls.env["ahasend.api"]

    def _valid(self, headers, body, secret=SECRET, signature=None):
        return self.api._ahasend_signature_valid(
            secret,
            headers["webhook-id"],
            headers["webhook-timestamp"],
            signature or headers["webhook-signature"],
            body,
        )

    # Signature

    def test_valid_signature(self):
        body = b'{"type": "message.delivered"}'
        self.assertTrue(self._valid(sign(body, SECRET), body))

    def test_one_of_several_signatures(self):
        body = b"{}"
        headers = sign(body, SECRET)
        signature = "v1,bm90LXZhbGlk " + headers["webhook-signature"]
        self.assertTrue(self._valid(headers, body, signature=signature))

    def test_tampered_body(self):
        self.assertFalse(self._valid(sign(b'{"a": 1}', SECRET), b'{"a": 2}'))

    def test_old_timestamp(self):
        body = b"{}"
        headers = sign(body, SECRET, timestamp=time.time() - 3600)
        self.assertFalse(self._valid(headers, body))

    def test_wrong_secret(self):
        body = b"{}"
        self.assertFalse(self._valid(sign(body, "aha-whsec-other"), body))

    def test_no_secret(self):
        body = b"{}"
        self.assertFalse(self._valid(sign(body, SECRET), body, secret=False))

    # Management API

    def test_request(self):
        with patch(REQUEST, return_value=json_response({"data": []})) as request:
            result = self.api._ahasend_request("GET", "/suppressions")
        self.assertEqual(result, {"data": []})
        self.assertEqual(
            request.call_args.args[1],
            f"https://api.ahasend.com/v2/accounts/{ACCOUNT_ID}/suppressions",
        )
        self.assertEqual(
            request.call_args.kwargs["headers"]["Authorization"], "Bearer aha-sk-test"
        )

    def test_request_error(self):
        answer = json_response({"message": "Unauthorized"}, status=401)
        with (
            patch(REQUEST, return_value=answer),
            self.assertRaisesRegex(UserError, "Unauthorized"),
        ):
            self.api._ahasend_request("GET", "/suppressions")

    def test_request_without_settings(self):
        self.env["ir.config_parameter"].sudo().set_param("ahasend.api_key", "")
        with self.assertRaises(UserError):
            self.api._ahasend_request("GET", "/suppressions")

    def test_public_url(self):
        icp = self.env["ir.config_parameter"].sudo()
        icp.set_param("ahasend.webhooks_base_url", "https://odoo.example.com/")
        self.assertEqual(
            self.api._ahasend_public_url("/mail/test"),
            f"https://odoo.example.com/mail/test/{self.env.cr.dbname}",
        )
        icp.set_param("ahasend.webhooks_base_url", "http://localhost:8069")
        with self.assertRaises(UserError):
            self.api._ahasend_public_url("/mail/test")
