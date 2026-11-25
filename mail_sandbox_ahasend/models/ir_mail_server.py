# Copyright 2026 AhaSend B.V.
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import re

from odoo import api, models

SANDBOX_SERVER_NAME = "AhaSend sandbox"
SANDBOX_HOST = "send.ahasend.com"
SANDBOX_PORT = 587
# The connection encryption of the sandbox server, as Odoo names it
SANDBOX_ENCRYPTION = "starttls"
# Odoo's neutralization adds this server so that no email leaves the copy
NEUTRALIZATION_SERVER_NAME = "neutralization - disable emails"


class IrMailServer(models.Model):
    _inherit = "ir.mail_server"

    @api.model
    def _ahasend_is_copy(self):
        icp = self.env["ir.config_parameter"].sudo()
        return bool(icp.get_param("database.is_neutralized"))

    @api.model
    def _ahasend_sandbox_tag(self):
        """Tag the email of this database, to tell copies apart in AhaSend."""
        return re.sub(r"[^A-Za-z0-9_-]", "-", f"odoo-{self.env.cr.dbname}")[:64]

    @api.model
    def _ahasend_sandbox_mark(self, message):
        """Mark an email for the AhaSend sandbox, which never delivers it."""
        del message["AhaSend-Sandbox"]
        message["AhaSend-Sandbox"] = "true"
        if not message["AhaSend-Tags"]:
            message["AhaSend-Tags"] = self._ahasend_sandbox_tag()
        return message

    def send_email(self, message, *args, **kwargs):
        # In a neutralized copy, every email is a sandbox email, also through
        # another mail server than the sandbox server
        if self._ahasend_is_copy():
            self._ahasend_sandbox_mark(message)
        return super().send_email(message, *args, **kwargs)

    @api.model
    def _ahasend_sandbox_server_setup(self):
        """Send the email of this copy through the AhaSend sandbox.

        Odoo's neutralization turns every mail server off and adds one that
        sends nothing. This turns that one off and adds a server with the
        sandbox SMTP credential.

        :return: the sandbox mail server, or an empty recordset when no
            sandbox credential is set
        """
        icp = self.env["ir.config_parameter"].sudo()
        user = icp.get_param("ahasend.sandbox_smtp_user")
        password = icp.get_param("ahasend.sandbox_smtp_password")
        servers = self.sudo().with_context(active_test=False)
        if not user or not password:
            return servers.browse()
        servers.search([("name", "=", NEUTRALIZATION_SERVER_NAME)]).active = False
        values = {
            "name": SANDBOX_SERVER_NAME,
            "smtp_host": SANDBOX_HOST,
            "smtp_port": SANDBOX_PORT,
            "smtp_encryption": SANDBOX_ENCRYPTION,
            "smtp_authentication": "login",
            "smtp_user": user,
            "smtp_pass": password,
            "sequence": 1,
            "active": True,
        }
        server = servers.search([("name", "=", SANDBOX_SERVER_NAME)], limit=1)
        if server:
            server.write(values)
        else:
            server = servers.create(values)
        return server
