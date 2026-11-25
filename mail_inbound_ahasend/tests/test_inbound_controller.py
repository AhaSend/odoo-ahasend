# Copyright 2026 AhaSend B.V.
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import json

from odoo.tests import HttpCase, tagged
from odoo.tools import mute_logger

from odoo.addons.mail_ahasend.tests.common import sign

from .common import ROUTE_SECRET, configure, route_payload


@tagged("post_install", "-at_install")
class TestAhaSendInboundController(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        configure(cls.env)
        alias_domain = cls.env["mail.alias.domain"].create({"name": "odoo.example.com"})
        cls.env["mail.alias"].create(
            {
                "alias_name": "inbound-test",
                "alias_domain_id": alias_domain.id,
                "alias_model_id": cls.env["ir.model"]._get_id("res.partner"),
                "alias_contact": "everyone",
            }
        )
        cls.url = f"/mail/inbound/ahasend/{cls.env.cr.dbname}"

    def _post(self, body, headers):
        return self.url_open(
            self.url,
            data=body,
            headers=dict(headers, **{"Content-Type": "application/json"}),
        )

    def test_inbound_email(self):
        body = json.dumps(route_payload()).encode()
        response = self._post(body, sign(body, ROUTE_SECRET))
        self.assertEqual(response.status_code, 200)
        message = self.env["mail.message"].search(
            [("message_id", "=", "<unique-message-id@example.net>")]
        )
        self.assertEqual(message.model, "res.partner")

    @mute_logger("odoo.addons.mail_ahasend.controllers.main")
    def test_bad_signature(self):
        body = json.dumps(route_payload()).encode()
        headers = sign(body, "aha-whsec-other")
        response = self._post(body, headers)
        self.assertEqual(response.status_code, 401)
        self.assertFalse(
            self.env["mail.message"].search(
                [("message_id", "=", "<unique-message-id@example.net>")]
            )
        )

    def test_tracking_secret_is_refused(self):
        # A delivery signed with another endpoint's secret is not accepted
        self.env["ir.config_parameter"].sudo().set_param(
            "ahasend.webhook_secret", "aha-whsec-tracking"
        )
        body = json.dumps(route_payload()).encode()
        with mute_logger("odoo.addons.mail_ahasend.controllers.main"):
            response = self._post(body, sign(body, "aha-whsec-tracking"))
        self.assertEqual(response.status_code, 401)
