# Copyright 2026 AhaSend B.V.
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import logging

from odoo import api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

WEBHOOK_PATH = "/mail/tracking/ahasend"

# Message events the Odoo webhook listens to
WEBHOOK_EVENTS = (
    "on_delivered",
    "on_transient_error",
    "on_failed",
    "on_bounced",
    "on_suppressed",
    "on_opened",
    "on_clicked",
    "on_unsubscribed",
    "on_complained",
)


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    mail_tracking_ahasend_webhook_secret = fields.Char(
        string="AhaSend webhook secret",
        config_parameter="ahasend.webhook_secret",
        help="Filled in when you connect tracking from Odoo. When you create "
        "the webhook in the AhaSend dashboard instead, copy its secret here.",
    )
    mail_tracking_ahasend_webhook_id = fields.Char(
        string="AhaSend webhook ID",
        config_parameter="ahasend.webhook_id",
        readonly=True,
    )
    mail_tracking_ahasend_webhook_url = fields.Char(
        string="AhaSend webhook endpoint URL",
        compute="_compute_mail_tracking_ahasend_webhook_url",
        help="The address AhaSend sends tracking events to. Connect tracking "
        "registers it; when you create the webhook in the AhaSend dashboard, "
        "use it as the endpoint URL.",
    )

    @api.depends("mail_ahasend_base_url")
    def _compute_mail_tracking_ahasend_webhook_url(self):
        for settings in self:
            settings.mail_tracking_ahasend_webhook_url = (
                settings._mail_ahasend_endpoint(WEBHOOK_PATH)
            )

    def action_ahasend_register_webhook(self):
        """Create the AhaSend webhook that feeds Odoo's mail tracking."""
        self.ensure_one()
        self.execute()
        icp = self.env["ir.config_parameter"].sudo()
        if icp.get_param("ahasend.webhook_id"):
            raise UserError(
                self.env._("Tracking is already connected. Disconnect it first.")
            )
        api_helper = self.env["ahasend.api"]
        values = api_helper._ahasend_values()
        body = {
            "name": f"Odoo mail tracking ({self.env.cr.dbname})",
            "url": api_helper._ahasend_public_url(WEBHOOK_PATH),
            "enabled": True,
            "scope": "scoped" if values.domain else "global",
            **dict.fromkeys(WEBHOOK_EVENTS, True),
        }
        if values.domain:
            body["domains"] = [values.domain]
        webhook = api_helper._ahasend_request("POST", "/webhooks", json=body)
        icp.set_param("ahasend.webhook_id", webhook.get("id"))
        icp.set_param("ahasend.webhook_secret", webhook.get("secret"))
        _logger.info("AhaSend: registered webhook %s", webhook.get("id"))
        return {"type": "ir.actions.client", "tag": "reload"}

    def action_ahasend_unregister_webhook(self):
        """Delete the AhaSend webhook that Odoo registered."""
        self.ensure_one()
        icp = self.env["ir.config_parameter"].sudo()
        webhook_id = icp.get_param("ahasend.webhook_id")
        if webhook_id:
            self.env["ahasend.api"]._ahasend_request(
                "DELETE", f"/webhooks/{webhook_id}"
            )
            _logger.info("AhaSend: deleted webhook %s", webhook_id)
        icp.set_param("ahasend.webhook_id", False)
        icp.set_param("ahasend.webhook_secret", False)
        return {"type": "ir.actions.client", "tag": "reload"}

    def action_ahasend_sync(self):
        """Fetch the AhaSend status of the recent emails."""
        self.ensure_one()
        days, checked, updated = self.env["mail.tracking.email"]._ahasend_sync()
        if days == 1:
            message = self.env._(
                "Checked %(checked)s emails of the last day: %(updated)s got a "
                "new status.",
                checked=checked,
                updated=updated,
            )
        else:
            message = self.env._(
                "Checked %(checked)s emails of the last %(days)s days: "
                "%(updated)s got a new status.",
                checked=checked,
                days=days,
                updated=updated,
            )
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": self.env._("Sync from AhaSend"),
                "message": message,
                "type": "success",
                "sticky": False,
            },
        }

    def _mail_ahasend_connections(self):
        connections = super()._mail_ahasend_connections()
        if self.env["ir.config_parameter"].sudo().get_param("ahasend.webhook_id"):
            connections.append(self.env._("delivery tracking"))
        return connections
