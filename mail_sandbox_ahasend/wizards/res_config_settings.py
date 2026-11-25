# Copyright 2026 AhaSend B.V.
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models
from odoo.exceptions import UserError


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    mail_sandbox_ahasend_smtp_user = fields.Char(
        string="AhaSend sandbox SMTP username",
        config_parameter="ahasend.sandbox_smtp_user",
        help="Username of an AhaSend SMTP credential in sandbox mode. Copies "
        "of this database send their email with it.",
    )
    mail_sandbox_ahasend_smtp_password = fields.Char(
        string="AhaSend sandbox SMTP password",
        config_parameter="ahasend.sandbox_smtp_password",
    )
    mail_sandbox_ahasend_is_copy = fields.Boolean(
        string="This database is a neutralized copy",
        compute="_compute_mail_sandbox_ahasend_is_copy",
    )

    def _compute_mail_sandbox_ahasend_is_copy(self):
        is_copy = self.env["ir.mail_server"]._ahasend_is_copy()
        for settings in self:
            settings.mail_sandbox_ahasend_is_copy = is_copy

    def action_ahasend_create_sandbox_credential(self):
        """Create a sandbox SMTP credential in AhaSend for the test copies."""
        self.ensure_one()
        self.execute()
        icp = self.env["ir.config_parameter"].sudo()
        if icp.get_param("ahasend.sandbox_smtp_user"):
            raise UserError(
                self.env._("A sandbox credential is already set. Clear it first.")
            )
        api_helper = self.env["ahasend.api"]
        domain = api_helper._ahasend_values().domain
        body = {
            "name": f"Odoo test copies ({self.env.cr.dbname})",
            "sandbox": True,
            "scope": "scoped" if domain else "global",
        }
        if domain:
            body["domains"] = [domain]
        credential = api_helper._ahasend_request("POST", "/smtp-credentials", json=body)
        icp.set_param("ahasend.sandbox_smtp_user", credential.get("username"))
        icp.set_param("ahasend.sandbox_smtp_password", credential.get("password"))
        return {"type": "ir.actions.client", "tag": "reload"}

    def action_ahasend_clear_sandbox_credential(self):
        """Forget the sandbox credential, so that copies send nothing again."""
        self.ensure_one()
        icp = self.env["ir.config_parameter"].sudo()
        icp.set_param("ahasend.sandbox_smtp_user", False)
        icp.set_param("ahasend.sandbox_smtp_password", False)
        return {"type": "ir.actions.client", "tag": "reload"}

    def action_ahasend_sandbox_server_setup(self):
        """Send the email of this copy through the AhaSend sandbox now."""
        self.ensure_one()
        self.execute()
        mail_servers = self.env["ir.mail_server"]
        if not mail_servers._ahasend_is_copy():
            raise UserError(
                self.env._(
                    "This database is not a neutralized copy. Its email keeps "
                    "going out normally."
                )
            )
        if not mail_servers._ahasend_sandbox_server_setup():
            raise UserError(
                self.env._("Set the username and password of the sandbox credential.")
            )
        return {"type": "ir.actions.client", "tag": "reload"}
