# Copyright 2026 AhaSend B.V.
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import json

from odoo.tests import HttpCase, tagged
from odoo.tools import mute_logger

from .common import configure, create_tracking, payload, sign


@tagged("post_install", "-at_install")
class TestAhaSendController(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        configure(cls.env)
        cls.mail, cls.tracking = create_tracking(cls.env)
        cls.url = f"/mail/tracking/ahasend/{cls.env.cr.dbname}"

    def _post(self, body, headers):
        return self.url_open(
            self.url,
            data=body,
            headers=dict(headers, **{"Content-Type": "application/json"}),
        )

    def test_webhook_delivered(self):
        body = json.dumps(payload("message.delivered")).encode()
        response = self._post(body, sign(body, webhook_id="msg_http_1"))
        self.assertEqual(response.status_code, 200)
        self.env.invalidate_all()
        self.assertEqual(self.tracking.state, "delivered")
        self.assertIn(
            "msg_http_1", self.tracking.tracking_event_ids.mapped("ahasend_event_id")
        )

    @mute_logger("odoo.addons.mail_ahasend.controllers.main")
    def test_webhook_bad_signature(self):
        body = json.dumps(payload("message.delivered")).encode()
        headers = sign(body)
        headers["webhook-signature"] = "v1,bm90LXZhbGlk"
        response = self._post(body, headers)
        self.assertEqual(response.status_code, 401)
        self.env.invalidate_all()
        self.assertNotEqual(self.tracking.state, "delivered")

    def test_webhook_invalid_json(self):
        body = b"not json"
        response = self._post(body, sign(body))
        self.assertEqual(response.status_code, 400)

    def test_webhook_unknown_database(self):
        body = b"{}"
        response = self.url_open(
            "/mail/tracking/ahasend/no-such-database",
            data=body,
            headers=sign(body),
        )
        self.assertEqual(response.status_code, 404)
