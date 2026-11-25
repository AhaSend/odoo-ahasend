# Copyright 2026 AhaSend B.V.
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models
from odoo.exceptions import UserError


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    mail_ahasend_enabled = fields.Boolean(
        string="Connect Odoo to AhaSend",
        config_parameter="ahasend.enabled",
    )
    mail_ahasend_account_id = fields.Char(
        string="AhaSend account ID",
        config_parameter="ahasend.account_id",
    )
    mail_ahasend_api_key = fields.Char(
        string="AhaSend secret key",
        config_parameter="ahasend.api_key",
        help="Secret key of an AhaSend API key. The scopes it needs depend "
        "on the AhaSend features you use; the setup guide lists them.",
    )
    mail_ahasend_domain = fields.Char(
        string="AhaSend sending domain",
        config_parameter="ahasend.domain",
        help="Limit the webhook and the suppression actions to this sending "
        "domain. Leave empty for all domains of the account.",
    )
    mail_ahasend_base_url = fields.Char(
        string="Odoo URL for AhaSend",
        config_parameter="ahasend.webhooks_base_url",
        help="The public https:// address AhaSend sends events and email to. "
        "Filled in with the base URL of this Odoo; change it when AhaSend "
        "must reach Odoo on another address.",
    )
    mail_ahasend_url_is_public = fields.Boolean(
        string="Odoo URL is public",
        compute="_compute_mail_ahasend_url_is_public",
    )

    @api.depends("mail_ahasend_base_url")
    def _compute_mail_ahasend_url_is_public(self):
        for settings in self:
            settings.mail_ahasend_url_is_public = bool(
                settings.mail_ahasend_base_url
                and settings.mail_ahasend_base_url.startswith("https://")
            )

    @api.onchange("mail_ahasend_enabled")
    def _onchange_mail_ahasend_enabled(self):
        if self.mail_ahasend_enabled:
            return
        connections = self._mail_ahasend_connections()
        if connections:
            self.mail_ahasend_enabled = True
            return {
                "warning": {
                    "title": self.env._("AhaSend is still connected"),
                    "message": self._mail_ahasend_disconnect_first(connections),
                }
            }

    def get_values(self):
        res = super().get_values()
        icp = self.env["ir.config_parameter"].sudo()
        res["mail_ahasend_base_url"] = icp.get_param(
            "ahasend.webhooks_base_url"
        ) or icp.get_param("web.base.url")
        return res

    def set_values(self):
        for settings in self:
            if not settings.mail_ahasend_enabled:
                connections = settings._mail_ahasend_connections()
                if connections:
                    raise UserError(
                        settings._mail_ahasend_disconnect_first(connections)
                    )
        # Store the Odoo URL only when it differs from the base URL, so a
        # later change of the base URL is followed.
        base_url = self.env["ir.config_parameter"].sudo().get_param("web.base.url")
        for settings in self:
            url = settings.mail_ahasend_base_url
            if url and base_url and url.rstrip("/") == base_url.rstrip("/"):
                settings.mail_ahasend_base_url = False
        return super().set_values()

    def _mail_ahasend_endpoint(self, path):
        """Return the address of ``path`` for this database, as shown."""
        self.ensure_one()
        if not self.mail_ahasend_base_url:
            return False
        base_url = self.mail_ahasend_base_url.rstrip("/")
        return f"{base_url}{path}/{self.env.cr.dbname}"

    def _mail_ahasend_connections(self):
        """Return the names of the features that Odoo connected in AhaSend.

        Modules that create a webhook, a route or the like in AhaSend add
        theirs, so that AhaSend cannot be turned off while they are active.
        """
        return []

    def _mail_ahasend_disconnect_first(self, connections):
        return self.env._(
            "Disconnect %(features)s first. Turning AhaSend off would leave "
            "them active in your AhaSend account.",
            features=", ".join(connections),
        )
