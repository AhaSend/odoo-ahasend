# Copyright 2026 AhaSend B.V.
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo.tests import tagged

from odoo.addons.base.tests.common import BaseCommon

from .common import configure


@tagged("post_install", "-at_install")
class TestAhaSendSettings(BaseCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        configure(cls.env)
        cls.icp = cls.env["ir.config_parameter"].sudo()

    def test_odoo_url_defaults_to_base_url(self):
        base_url = self.icp.get_param("web.base.url")
        settings = self.env["res.config.settings"].create({})
        self.assertEqual(settings.mail_ahasend_base_url, base_url)
        self.assertEqual(
            settings._mail_ahasend_endpoint("/mail/test"),
            f"{base_url.rstrip('/')}/mail/test/{self.env.cr.dbname}",
        )
        # Saving the base URL as is keeps the parameter empty
        settings.execute()
        self.assertFalse(self.icp.get_param("ahasend.webhooks_base_url"))

    def test_odoo_url_is_stored_when_different(self):
        settings = self.env["res.config.settings"].create(
            {"mail_ahasend_base_url": "https://public.example.com"}
        )
        settings.execute()
        self.assertEqual(
            self.icp.get_param("ahasend.webhooks_base_url"),
            "https://public.example.com",
        )

    def test_odoo_url_is_public(self):
        settings = self.env["res.config.settings"].create({})
        settings.mail_ahasend_base_url = "http://localhost:8069"
        self.assertFalse(settings.mail_ahasend_url_is_public)
        settings.mail_ahasend_base_url = "https://odoo.example.com"
        self.assertTrue(settings.mail_ahasend_url_is_public)
