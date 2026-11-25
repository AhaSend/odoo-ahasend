# Copyright 2026 AhaSend B.V.
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import email
from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.modules.neutralize import neutralize_database
from odoo.tests import tagged
from odoo.tools import mute_logger

from odoo.addons.base.tests.common import BaseCommon
from odoo.addons.mail_ahasend.tests.common import REQUEST, json_response

from .common import SENDER, attachment, configure, route_payload


@tagged("post_install", "-at_install")
class TestAhaSendInbound(BaseCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        configure(cls.env)
        cls.inbound = cls.env["ahasend.inbound"]
        alias_domain = cls.env["mail.alias.domain"].create({"name": "odoo.example.com"})
        cls.env["mail.alias"].create(
            {
                "alias_name": "inbound-test",
                "alias_domain_id": alias_domain.id,
                "alias_model_id": cls.env["ir.model"]._get_id("res.partner"),
                "alias_contact": "everyone",
            }
        )

    def _partner_for(self, message_id):
        message = self.env["mail.message"].search(
            [("message_id", "=", message_id)], limit=1
        )
        return self.env["res.partner"].browse(message.res_id)

    # Building the email

    def test_build_message_from_fields(self):
        raw = self.inbound._ahasend_build_message(route_payload()["data"])
        message = email.message_from_bytes(raw)
        self.assertEqual(message["Subject"], "Help with my account")
        self.assertEqual(message["Message-ID"], "<unique-message-id@example.net>")
        self.assertEqual(message["To"], "inbound-test@odoo.example.com")
        self.assertEqual(message.get_content_type(), "multipart/alternative")
        bodies = [part.get_content_type() for part in message.walk()]
        self.assertIn("text/plain", bodies)
        self.assertIn("text/html", bodies)

    def test_build_message_prefers_headers(self):
        data = route_payload(
            headers={
                "To": "inbound-test@odoo.example.com, other@example.com",
                "X-Mailer": "Test",
                "Content-Type": "text/plain",
            }
        )["data"]
        message = email.message_from_bytes(self.inbound._ahasend_build_message(data))
        self.assertEqual(
            message["To"], "inbound-test@odoo.example.com, other@example.com"
        )
        self.assertEqual(message["X-Mailer"], "Test")
        # The body headers of the rebuilt email win
        self.assertEqual(message.get_content_type(), "multipart/alternative")

    def test_header_values_stay_on_one_line(self):
        data = route_payload(subject="Hello\r\nBcc: victim@example.com")["data"]
        message = email.message_from_bytes(self.inbound._ahasend_build_message(data))
        self.assertIsNone(message["Bcc"])

    def test_build_message_with_attachments(self):
        data = route_payload(
            attachments=[
                attachment("notes.txt", b"Hello"),
                attachment(
                    "logo.png",
                    b"\x89PNG",
                    content_type="image/png",
                    content_id="logo-123",
                    disposition="",
                ),
            ]
        )["data"]
        message = email.message_from_bytes(self.inbound._ahasend_build_message(data))
        self.assertEqual(message.get_content_type(), "multipart/mixed")
        parts = {part.get_filename(): part for part in message.walk()}
        self.assertEqual(parts["notes.txt"].get_payload(decode=True), b"Hello")
        self.assertEqual(parts["logo.png"]["Content-ID"], "<logo-123>")
        self.assertTrue(parts["logo.png"]["Content-Disposition"].startswith("inline"))

    # Odoo's mail gateway

    def test_alias_creates_record(self):
        self.inbound._ahasend_process(route_payload())
        partner = self._partner_for("<unique-message-id@example.net>")
        self.assertEqual(partner.name, "Help with my account")
        self.assertIn("account settings", partner.message_ids[0].body)

    def test_reply_is_posted_on_thread(self):
        partner = self.env["res.partner"].create({"name": "Existing customer"})
        sent = partner.message_post(body="Our answer", message_type="comment")
        self.inbound._ahasend_process(
            route_payload(
                to="someone@odoo.example.com",
                subject="Re: Our answer",
                message_id="<reply-1@example.net>",
                in_reply_to=sent.message_id,
                references=sent.message_id,
            )
        )
        reply = self.env["mail.message"].search(
            [("message_id", "=", "<reply-1@example.net>")]
        )
        self.assertEqual(reply.model, "res.partner")
        self.assertEqual(reply.res_id, partner.id)

    def test_attachments_are_saved(self):
        self.inbound._ahasend_process(
            route_payload(attachments=[attachment("notes.txt", b"Hello")])
        )
        partner = self._partner_for("<unique-message-id@example.net>")
        self.assertEqual(
            partner.message_ids[0].attachment_ids.mapped("name"), ["notes.txt"]
        )

    def test_repeated_delivery_is_posted_once(self):
        self.inbound._ahasend_process(route_payload())
        self.inbound._ahasend_process(route_payload())
        messages = self.env["mail.message"].search(
            [("message_id", "=", "<unique-message-id@example.net>")]
        )
        self.assertEqual(len(messages), 1)

    @mute_logger("odoo.addons.mail.models.mail_thread")
    def test_unroutable_email_is_dropped(self):
        result = self.inbound._ahasend_process(
            route_payload(to="nobody@elsewhere.example.com")
        )
        self.assertFalse(result)

    def test_other_event_is_ignored(self):
        self.assertFalse(self.inbound._ahasend_process({"type": "message.opened"}))

    def test_sender_is_kept(self):
        self.inbound._ahasend_process(route_payload())
        message = self.env["mail.message"].search(
            [("message_id", "=", "<unique-message-id@example.net>")]
        )
        self.assertIn(SENDER, message.email_from)

    # Settings

    def test_connect_and_disconnect(self):
        self.env["ir.config_parameter"].sudo().set_param(
            "ahasend.webhooks_base_url", "https://odoo.example.com"
        )
        settings = self.env["res.config.settings"].create(
            {"mail_inbound_ahasend_domain": "odoo.example.com"}
        )
        created = {"id": "route-1", "secret": "aha-whsec-new"}
        with patch(REQUEST, return_value=json_response(created)) as request:
            settings.action_ahasend_connect_inbound()
        body = request.call_args.kwargs["json"]
        self.assertEqual(
            body["url"],
            f"https://odoo.example.com/mail/inbound/ahasend/{self.env.cr.dbname}",
        )
        self.assertEqual(body["recipient"], "*@odoo.example.com")
        self.assertTrue(body["attachments"])
        self.assertTrue(body["headers"])
        self.assertTrue(body["group_by_message_id"])
        icp = self.env["ir.config_parameter"].sudo()
        self.assertEqual(icp.get_param("ahasend.route_id"), "route-1")
        self.assertEqual(icp.get_param("ahasend.route_secret"), "aha-whsec-new")
        settings = self.env["res.config.settings"].create({})
        with patch(REQUEST, return_value=json_response(None)) as request:
            settings.action_ahasend_disconnect_inbound()
        self.assertEqual(request.call_args.args[0], "DELETE")
        self.assertTrue(request.call_args.args[1].endswith("/routes/route-1"))
        self.assertFalse(icp.get_param("ahasend.route_id"))

    def test_connect_needs_https(self):
        self.env["ir.config_parameter"].sudo().set_param(
            "ahasend.webhooks_base_url", "http://localhost:8069"
        )
        settings = self.env["res.config.settings"].create(
            {"mail_inbound_ahasend_domain": "odoo.example.com"}
        )
        with self.assertRaises(UserError):
            settings.action_ahasend_connect_inbound()

    def test_domain_defaults_to_alias_domain(self):
        alias_domain = self.env["mail.alias.domain"].search(
            [("name", "=", "odoo.example.com")]
        )
        self.env.company.alias_domain_id = alias_domain
        settings = self.env["res.config.settings"].create({})
        self.assertEqual(settings.mail_inbound_ahasend_domain, "odoo.example.com")
        settings.execute()
        icp = self.env["ir.config_parameter"].sudo()
        self.assertFalse(icp.get_param("ahasend.inbound_domain"))

    def test_neutralize_removes_route(self):
        icp = self.env["ir.config_parameter"].sudo()
        icp.set_param("ahasend.route_id", "route-1")
        # The neutralization runs SQL: write the pending changes first
        self.env.flush_all()
        neutralize_database(self.env.cr)
        self.env.invalidate_all()
        self.assertFalse(icp.get_param("ahasend.route_id"))
        self.assertFalse(icp.get_param("ahasend.route_secret"))

    def test_route_url(self):
        self.env["ir.config_parameter"].sudo().set_param(
            "ahasend.webhooks_base_url", "https://odoo.example.com"
        )
        settings = self.env["res.config.settings"].create({})
        self.assertEqual(
            settings.mail_inbound_ahasend_route_url,
            f"https://odoo.example.com/mail/inbound/ahasend/{self.env.cr.dbname}",
        )

    def test_cannot_turn_off_while_connected(self):
        icp = self.env["ir.config_parameter"].sudo()
        # Another installed AhaSend module may be connected in this database
        for key in ("ahasend.webhook_id", "ahasend.route_id"):
            icp.set_param(key, False)
        icp.set_param("ahasend.enabled", True)
        icp.set_param("ahasend.route_id", "connected-id")
        settings = self.env["res.config.settings"].create(
            {"mail_ahasend_enabled": False}
        )
        with self.assertRaisesRegex(UserError, "inbound email"):
            settings.execute()
        result = settings._onchange_mail_ahasend_enabled()
        self.assertTrue(settings.mail_ahasend_enabled)
        self.assertIn("inbound email", result["warning"]["message"])
        # Once disconnected, AhaSend can be turned off
        icp.set_param("ahasend.route_id", False)
        settings = self.env["res.config.settings"].create(
            {"mail_ahasend_enabled": False}
        )
        settings.execute()
        self.assertFalse(icp.get_param("ahasend.enabled"))
