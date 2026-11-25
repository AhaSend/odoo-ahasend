# Copyright 2026 AhaSend B.V.
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from email.message import EmailMessage
from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.modules.neutralize import neutralize_database
from odoo.tests import tagged

from odoo.addons.base.tests.common import BaseCommon
from odoo.addons.mail_ahasend.tests.common import REQUEST, configure, json_response

from ..models.ir_mail_server import NEUTRALIZATION_SERVER_NAME, SANDBOX_SERVER_NAME


@tagged("post_install", "-at_install")
class TestAhaSendSandbox(BaseCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        configure(cls.env)
        cls.icp = cls.env["ir.config_parameter"].sudo()
        cls.mail_servers = cls.env["ir.mail_server"].with_context(active_test=False)
        cls.production_server = cls.mail_servers.create(
            {
                "name": "AhaSend production",
                "smtp_host": "send.ahasend.com",
                "smtp_port": 587,
                "smtp_user": "production-user",
                "smtp_pass": "production-password",
            }
        )

    def _message(self):
        message = EmailMessage()
        message["From"] = "from@example.com"
        message["To"] = "to@example.com"
        message["Subject"] = "Test"
        message.set_content("Body")
        return message

    def _set_credential(self):
        self.icp.set_param("ahasend.sandbox_smtp_user", "sandbox-user")
        self.icp.set_param("ahasend.sandbox_smtp_password", "sandbox-password")

    def _neutralize(self):
        # The neutralization runs SQL: write the pending changes first
        self.env.flush_all()
        neutralize_database(self.env.cr)
        self.env.invalidate_all()

    def test_neutralize_with_credential(self):
        self._set_credential()
        self._neutralize()
        sandbox = self.mail_servers.search([("name", "=", SANDBOX_SERVER_NAME)])
        self.assertEqual(len(sandbox), 1)
        self.assertTrue(sandbox.active)
        self.assertEqual(sandbox.smtp_host, "send.ahasend.com")
        self.assertEqual(sandbox.smtp_user, "sandbox-user")
        self.assertEqual(sandbox.smtp_pass, "sandbox-password")
        dummy = self.mail_servers.search([("name", "=", NEUTRALIZATION_SERVER_NAME)])
        self.assertFalse(dummy.active)
        # Odoo's own neutralization still turns the other servers off
        self.assertFalse(self.production_server.active)
        self.assertFalse(self.production_server.smtp_pass)
        # A copy cannot act on the production account
        self.assertFalse(self.icp.get_param("ahasend.api_key"))

    def test_neutralize_without_credential(self):
        self.icp.set_param("ahasend.sandbox_smtp_user", False)
        self._neutralize()
        self.assertFalse(self.mail_servers.search([("name", "=", SANDBOX_SERVER_NAME)]))
        dummy = self.mail_servers.search([("name", "=", NEUTRALIZATION_SERVER_NAME)])
        self.assertTrue(dummy.active)

    def test_email_of_copy_is_sandboxed(self):
        self.icp.set_param("database.is_neutralized", True)
        message = self._message()
        self.env["ir.mail_server"].send_email(message)
        self.assertEqual(message["AhaSend-Sandbox"], "true")
        self.assertTrue(message["AhaSend-Tags"].startswith("odoo-"))

    def test_existing_tags_are_kept(self):
        message = self._message()
        message["AhaSend-Tags"] = "invoice"
        self.env["ir.mail_server"]._ahasend_sandbox_mark(message)
        self.assertEqual(message["AhaSend-Tags"], "invoice")
        self.assertEqual(message["AhaSend-Sandbox"], "true")

    def test_email_of_production_is_not_sandboxed(self):
        self.icp.set_param("database.is_neutralized", False)
        message = self._message()
        self.env["ir.mail_server"].send_email(message)
        self.assertIsNone(message["AhaSend-Sandbox"])

    def test_setup_button_in_copy(self):
        self._set_credential()
        self.icp.set_param("database.is_neutralized", True)
        settings = self.env["res.config.settings"].create({})
        self.assertTrue(settings.mail_sandbox_ahasend_is_copy)
        settings.action_ahasend_sandbox_server_setup()
        sandbox = self.mail_servers.search([("name", "=", SANDBOX_SERVER_NAME)])
        self.assertTrue(sandbox.active)
        # A second click updates the same server
        settings.action_ahasend_sandbox_server_setup()
        self.assertEqual(
            self.mail_servers.search_count([("name", "=", SANDBOX_SERVER_NAME)]), 1
        )

    def test_create_sandbox_credential(self):
        self.icp.set_param("ahasend.sandbox_smtp_user", False)
        self.icp.set_param("ahasend.domain", "example.com")
        settings = self.env["res.config.settings"].create({})
        created = {"id": "cred-1", "username": "sandbox-user", "password": "secret"}
        with patch(REQUEST, return_value=json_response(created)) as request:
            settings.action_ahasend_create_sandbox_credential()
        body = request.call_args.kwargs["json"]
        self.assertTrue(request.call_args.args[1].endswith("/smtp-credentials"))
        self.assertTrue(body["sandbox"])
        self.assertEqual(body["scope"], "scoped")
        self.assertEqual(body["domains"], ["example.com"])
        self.assertEqual(
            self.icp.get_param("ahasend.sandbox_smtp_user"), "sandbox-user"
        )
        self.assertEqual(self.icp.get_param("ahasend.sandbox_smtp_password"), "secret")
        settings = self.env["res.config.settings"].create({})
        with self.assertRaises(UserError):
            settings.action_ahasend_create_sandbox_credential()

    def test_setup_button_in_production(self):
        self._set_credential()
        self.icp.set_param("database.is_neutralized", False)
        settings = self.env["res.config.settings"].create({})
        with self.assertRaises(UserError):
            settings.action_ahasend_sandbox_server_setup()

    def test_clear_sandbox_credential(self):
        icp = self.env["ir.config_parameter"].sudo()
        icp.set_param("ahasend.sandbox_smtp_user", "sandbox-user")
        icp.set_param("ahasend.sandbox_smtp_password", "sandbox-password")
        settings = self.env["res.config.settings"].create({})
        settings.action_ahasend_clear_sandbox_credential()
        self.assertFalse(icp.get_param("ahasend.sandbox_smtp_user"))
        self.assertFalse(icp.get_param("ahasend.sandbox_smtp_password"))
