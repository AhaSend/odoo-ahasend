# Copyright 2026 AhaSend B.V.
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import json
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import UserError
from odoo.modules.neutralize import neutralize_database
from odoo.tests import tagged

from odoo.addons.base.tests.common import BaseCommon
from odoo.addons.mail_ahasend.tests.common import REQUEST

from .common import (
    MESSAGE_ID,
    RECIPIENT,
    configure,
    create_tracking,
    json_response,
    payload,
    sign,
)


@tagged("post_install", "-at_install")
class TestAhaSend(BaseCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        configure(cls.env)
        cls.mail, cls.tracking = create_tracking(cls.env)
        cls.tracking_model = cls.env["mail.tracking.email"]
        cls.api = cls.env["ahasend.api"]
        cls.partner = cls.env["res.partner"].create(
            {"name": "Recipient", "email": RECIPIENT}
        )

    def _process(self, event_type, event_id="msg_1", **data):
        return self.tracking_model._ahasend_event_process(
            payload(event_type, **data), event_id
        )

    # Signature

    def test_verify_valid_signature(self):
        body = json.dumps(payload("message.delivered")).encode()
        headers = sign(body)
        self.assertTrue(
            self.api._ahasend_webhook_verify(
                headers["webhook-id"],
                headers["webhook-timestamp"],
                headers["webhook-signature"],
                body,
            )
        )

    def test_verify_without_secret(self):
        self.env["ir.config_parameter"].sudo().set_param("ahasend.webhook_secret", "")
        body = b"{}"
        headers = sign(body)
        self.assertFalse(
            self.api._ahasend_webhook_verify(
                headers["webhook-id"],
                headers["webhook-timestamp"],
                headers["webhook-signature"],
                body,
            )
        )

    # Events

    def test_delivered(self):
        event = self._process(
            "message.delivered",
            delivery_attempt={"smtp_code": 250, "response": "OK"},
        )
        self.assertEqual(event.event_type, "delivered")
        self.assertEqual(event.ahasend_event_id, "msg_1")
        self.assertEqual(self.tracking.state, "delivered")

    def test_duplicate_delivery_is_ignored(self):
        self._process("message.delivered")
        self.assertFalse(self._process("message.delivered"))
        self.assertEqual(
            len(self.tracking.tracking_event_ids.filtered("ahasend_event_id")), 1
        )

    def test_hard_bounce_marks_partner(self):
        event = self._process(
            "message.bounced",
            delivery_attempt={
                "smtp_code": 550,
                "enhanced_status_code": "5.1.1",
                "classification": "InvalidRecipient",
                "response": "User unknown",
            },
        )
        self.assertEqual(event.event_type, "hard_bounce")
        self.assertEqual(event.error_type, "InvalidRecipient")
        self.assertEqual(event.error_description, "User unknown")
        self.assertEqual(self.tracking.state, "bounced")
        self.assertEqual(self.tracking.bounce_type, "InvalidRecipient")
        self.assertTrue(self.partner.email_bounced)

    def test_failed_is_soft_bounce(self):
        event = self._process("message.failed")
        self.assertEqual(event.event_type, "soft_bounce")
        self.assertEqual(self.tracking.state, "soft-bounced")
        self.assertFalse(self.partner.email_bounced)

    def test_suppressed_is_reject(self):
        event = self._process("message.suppressed")
        self.assertEqual(event.event_type, "reject")
        self.assertEqual(self.tracking.state, "rejected")

    def test_complaint_is_spam(self):
        event = self._process("message.complained")
        self.assertEqual(event.event_type, "spam")
        self.assertEqual(self.tracking.state, "spam")

    def test_unsubscribe(self):
        event = self._process("message.unsubscribed")
        self.assertEqual(event.event_type, "unsub")

    def test_open_and_click(self):
        self._process("message.delivered", event_id="msg_1")
        opened = self._process(
            "message.opened", event_id="msg_2", ip="192.0.2.1", user_agent="Mail"
        )
        self.assertEqual(opened.event_type, "open")
        self.assertEqual(opened.ip, "192.0.2.1")
        clicked = self._process(
            "message.clicked", event_id="msg_3", url="https://example.com"
        )
        self.assertEqual(clicked.url, "https://example.com")
        self.assertEqual(self.tracking.state, "opened")

    def test_bot_open_is_ignored(self):
        self.assertFalse(self._process("message.opened", is_bot=True))

    def test_late_deferral_is_ignored(self):
        self._process("message.delivered", event_id="msg_1")
        self.assertFalse(self._process("message.transient_error", event_id="msg_2"))
        self.assertEqual(self.tracking.state, "delivered")

    def test_late_delivered_after_open_is_ignored(self):
        self._process("message.opened", event_id="msg_1")
        self.assertFalse(self._process("message.delivered", event_id="msg_2"))
        self.assertEqual(self.tracking.state, "opened")

    def test_deferral(self):
        event = self._process(
            "message.transient_error",
            delivery_attempt={"smtp_code": 421, "response": "Try later"},
        )
        self.assertEqual(event.event_type, "deferral")
        self.assertEqual(self.tracking.state, "deferred")

    def test_unknown_message_is_ignored(self):
        self.assertFalse(
            self._process("message.delivered", message_id_header="<other@example>")
        )

    def test_other_recipient_is_ignored(self):
        self.assertFalse(
            self._process("message.delivered", recipient="someone@example.com")
        )

    def test_unknown_event_type_is_ignored(self):
        self.assertFalse(self._process("message.reception"))
        self.assertFalse(self._process("suppression.created"))

    def test_event_timestamp(self):
        event = self._process("message.delivered")
        self.assertEqual(str(event.time), "2026-11-25 09:50:16")

    # Manual check

    def test_manual_check(self):
        answer = {
            "object": "list",
            "data": [
                {
                    "id": "019a0c3e-aaaa",
                    "status": "Delivered",
                    "recipient": RECIPIENT,
                    "message_id": MESSAGE_ID,
                    "delivered_at": "2026-11-25T09:50:16Z",
                }
            ],
        }
        with patch(REQUEST, return_value=json_response(answer)) as request:
            self.tracking.action_manual_check_ahasend()
        _method, url = request.call_args.args
        self.assertTrue(url.endswith("/messages"))
        self.assertEqual(
            request.call_args.kwargs["params"]["message_id_header"], MESSAGE_ID
        )
        self.assertEqual(self.tracking.state, "delivered")
        # A second check of the same status adds nothing
        with patch(REQUEST, return_value=json_response(answer)):
            self.tracking.action_manual_check_ahasend()
        self.assertEqual(
            len(self.tracking.tracking_event_ids.filtered("ahasend_event_id")), 1
        )

    def test_manual_check_not_found(self):
        with (
            patch(REQUEST, return_value=json_response({"data": []})),
            self.assertRaises(UserError),
        ):
            self.tracking.action_manual_check_ahasend()

    def _sync_request(self, retention, statuses=("Delivered",)):
        """Answer the account and message calls of a sync."""
        messages = [
            {
                "id": "019a0c3e-bbbb",
                "status": status,
                "recipient": RECIPIENT,
                "message_id": MESSAGE_ID,
                "delivered_at": "2026-11-25T09:50:16Z",
            }
            for status in statuses
        ]

        def answer(method, url, **kwargs):
            if url.endswith("/messages"):
                return json_response({"object": "list", "data": messages})
            return json_response(
                {
                    "message_data_retention": retention,
                    "message_metadata_retention": 30,
                }
            )

        return patch(REQUEST, side_effect=answer)

    def test_sync(self):
        self.tracking.write({"state": "sent", "time": fields.Datetime.now()})
        settings = self.env["res.config.settings"].create({})
        with self._sync_request(30) as request:
            action = settings.action_ahasend_sync()
        self.assertEqual(self.tracking.state, "delivered")
        self.assertEqual(action["tag"], "display_notification")
        self.assertIn("last 2 days", action["params"]["message"])
        urls = [call.args[1] for call in request.call_args_list]
        self.assertTrue(any(url.endswith("/messages") for url in urls))

    def test_sync_follows_retention(self):
        with self._sync_request(1):
            days, _checked, _updated = self.tracking_model._ahasend_sync()
        self.assertEqual(days, 1)

    def test_sync_without_retention(self):
        with self._sync_request(0), self.assertRaisesRegex(UserError, "0 days"):
            self.tracking_model._ahasend_sync()

    def test_sync_skips_final_states(self):
        # Also the emails this database sent before the test
        self.tracking_model.search([]).state = "bounced"
        with self._sync_request(30) as request:
            _days, checked, _updated = self.tracking_model._ahasend_sync()
        self.assertEqual(checked, 0)
        self.assertEqual(request.call_count, 1)

    def test_check_suppressed(self):
        answer = {"data": [{"email": RECIPIENT, "reason": "Hard bounce"}]}
        with patch(REQUEST, return_value=json_response(answer)):
            self.partner.action_ahasend_check_suppressed()
        self.assertTrue(self.partner.email_bounced)
        with patch(REQUEST, return_value=json_response({"data": []})):
            self.partner.action_ahasend_check_suppressed()
        self.assertFalse(self.partner.email_bounced)

    def test_suppress_and_unsuppress(self):
        self.env["ir.config_parameter"].sudo().set_param(
            "ahasend.domain", "example.com"
        )
        with patch(REQUEST, return_value=json_response({"data": []})) as request:
            self.partner.action_ahasend_suppress()
        self.assertEqual(request.call_args.args[0], "POST")
        self.assertEqual(request.call_args.kwargs["json"]["domain"], "example.com")
        self.assertTrue(self.partner.email_bounced)
        with patch(REQUEST, return_value=json_response(None)) as request:
            self.partner.action_ahasend_unsuppress()
        self.assertEqual(request.call_args.args[0], "DELETE")
        self.assertFalse(self.partner.email_bounced)

    def test_suppress_without_email(self):
        partner = self.env["res.partner"].create({"name": "No email"})
        with self.assertRaises(UserError):
            partner.action_ahasend_suppress()

    # Settings

    def test_register_and_unregister_webhook(self):
        self.env["ir.config_parameter"].sudo().set_param(
            "ahasend.webhooks_base_url", "https://odoo.example.com"
        )
        settings = self.env["res.config.settings"].create({})
        created = {"id": "wh-1", "secret": "aha-whsec-new"}
        with patch(REQUEST, return_value=json_response(created)) as request:
            settings.action_ahasend_register_webhook()
        body = request.call_args.kwargs["json"]
        self.assertEqual(
            body["url"],
            f"https://odoo.example.com/mail/tracking/ahasend/{self.env.cr.dbname}",
        )
        self.assertTrue(body["on_bounced"])
        self.assertEqual(body["scope"], "global")
        icp = self.env["ir.config_parameter"].sudo()
        self.assertEqual(icp.get_param("ahasend.webhook_id"), "wh-1")
        self.assertEqual(icp.get_param("ahasend.webhook_secret"), "aha-whsec-new")
        settings = self.env["res.config.settings"].create({})
        with patch(REQUEST, return_value=json_response(None)) as request:
            settings.action_ahasend_unregister_webhook()
        self.assertEqual(request.call_args.args[0], "DELETE")
        self.assertFalse(icp.get_param("ahasend.webhook_id"))

    def test_neutralize_removes_webhook(self):
        icp = self.env["ir.config_parameter"].sudo()
        icp.set_param("ahasend.webhook_id", "wh-1")
        # The neutralization runs SQL: write the pending changes first
        self.env.flush_all()
        neutralize_database(self.env.cr)
        self.env.invalidate_all()
        self.assertFalse(icp.get_param("ahasend.webhook_id"))
        self.assertFalse(icp.get_param("ahasend.webhook_secret"))

    def test_webhook_url(self):
        self.env["ir.config_parameter"].sudo().set_param(
            "ahasend.webhooks_base_url", "https://odoo.example.com"
        )
        settings = self.env["res.config.settings"].create({})
        self.assertEqual(
            settings.mail_tracking_ahasend_webhook_url,
            f"https://odoo.example.com/mail/tracking/ahasend/{self.env.cr.dbname}",
        )

    def test_register_webhook_needs_https(self):
        self.env["ir.config_parameter"].sudo().set_param(
            "ahasend.webhooks_base_url", "http://localhost:8069"
        )
        settings = self.env["res.config.settings"].create({})
        with self.assertRaises(UserError):
            settings.action_ahasend_register_webhook()

    def test_cannot_turn_off_while_connected(self):
        icp = self.env["ir.config_parameter"].sudo()
        # Another installed AhaSend module may be connected in this database
        for key in ("ahasend.webhook_id", "ahasend.route_id"):
            icp.set_param(key, False)
        icp.set_param("ahasend.enabled", True)
        icp.set_param("ahasend.webhook_id", "connected-id")
        settings = self.env["res.config.settings"].create(
            {"mail_ahasend_enabled": False}
        )
        with self.assertRaisesRegex(UserError, "delivery tracking"):
            settings.execute()
        result = settings._onchange_mail_ahasend_enabled()
        self.assertTrue(settings.mail_ahasend_enabled)
        self.assertIn("delivery tracking", result["warning"]["message"])
        # Once disconnected, AhaSend can be turned off
        icp.set_param("ahasend.webhook_id", False)
        settings = self.env["res.config.settings"].create(
            {"mail_ahasend_enabled": False}
        )
        settings.execute()
        self.assertFalse(icp.get_param("ahasend.enabled"))
