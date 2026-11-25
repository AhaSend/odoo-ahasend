# Copyright 2026 AhaSend B.V.
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import logging

from odoo import api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

ROUTE_PATH = "/mail/inbound/ahasend"


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    mail_inbound_ahasend_domain = fields.Char(
        string="AhaSend inbound domain",
        config_parameter="ahasend.inbound_domain",
        help="The domain of Odoo's aliases, whose MX records point to "
        "AhaSend. Filled in with the alias domain of the company.",
    )
    mail_inbound_ahasend_route_id = fields.Char(
        string="AhaSend route ID",
        config_parameter="ahasend.route_id",
        readonly=True,
    )
    mail_inbound_ahasend_route_secret = fields.Char(
        string="AhaSend route secret",
        config_parameter="ahasend.route_secret",
        help="Filled in when you connect inbound email from Odoo. When you "
        "create the route in the AhaSend dashboard instead, copy its secret "
        "here.",
    )
    mail_inbound_ahasend_route_url = fields.Char(
        string="AhaSend route endpoint URL",
        compute="_compute_mail_inbound_ahasend_route_url",
        help="The address AhaSend posts inbound email to.",
    )

    @api.depends("mail_ahasend_base_url")
    def _compute_mail_inbound_ahasend_route_url(self):
        for settings in self:
            settings.mail_inbound_ahasend_route_url = settings._mail_ahasend_endpoint(
                ROUTE_PATH
            )

    def get_values(self):
        res = super().get_values()
        icp = self.env["ir.config_parameter"].sudo()
        res["mail_inbound_ahasend_domain"] = (
            icp.get_param("ahasend.inbound_domain")
            or self._mail_inbound_ahasend_alias_domain()
        )
        return res

    def set_values(self):
        # Store the domain only when it differs from the alias domain, so a
        # later change of the alias domain is followed.
        alias_domain = self._mail_inbound_ahasend_alias_domain()
        for settings in self:
            if settings.mail_inbound_ahasend_domain == alias_domain:
                settings.mail_inbound_ahasend_domain = False
        return super().set_values()

    def action_ahasend_connect_inbound(self):
        """Create the AhaSend route that posts inbound email to Odoo."""
        self.ensure_one()
        self.execute()
        icp = self.env["ir.config_parameter"].sudo()
        if icp.get_param("ahasend.route_id"):
            raise UserError(
                self.env._("Inbound email is already connected. Disconnect it first.")
            )
        domain = self._mail_inbound_ahasend_domain()
        if not domain:
            raise UserError(
                self.env._(
                    "Set the inbound domain: the domain of Odoo's aliases, "
                    "whose MX records point to AhaSend."
                )
            )
        api_helper = self.env["ahasend.api"]
        body = {
            "name": f"Odoo inbound email ({self.env.cr.dbname})",
            "url": api_helper._ahasend_public_url(ROUTE_PATH),
            "recipient": f"*@{domain}",
            "attachments": True,
            "headers": True,
            # One delivery per email, with its complete To and Cc headers, so
            # Odoo routes it to every alias it was sent to
            "group_by_message_id": True,
            "strip_replies": False,
            "enabled": True,
        }
        route = api_helper._ahasend_request("POST", "/routes", json=body)
        icp.set_param("ahasend.route_id", route.get("id"))
        icp.set_param("ahasend.route_secret", route.get("secret"))
        _logger.info("AhaSend: created route %s for %s", route.get("id"), domain)
        return {"type": "ir.actions.client", "tag": "reload"}

    def action_ahasend_disconnect_inbound(self):
        """Delete the AhaSend route that Odoo created."""
        self.ensure_one()
        icp = self.env["ir.config_parameter"].sudo()
        route_id = icp.get_param("ahasend.route_id")
        if route_id:
            self.env["ahasend.api"]._ahasend_request("DELETE", f"/routes/{route_id}")
            _logger.info("AhaSend: deleted route %s", route_id)
        icp.set_param("ahasend.route_id", False)
        icp.set_param("ahasend.route_secret", False)
        return {"type": "ir.actions.client", "tag": "reload"}

    def _mail_inbound_ahasend_alias_domain(self):
        return self.env.company.alias_domain_id.name or False

    def _mail_inbound_ahasend_domain(self):
        icp = self.env["ir.config_parameter"].sudo()
        return (
            icp.get_param("ahasend.inbound_domain")
            or self._mail_inbound_ahasend_alias_domain()
        )

    def _mail_ahasend_connections(self):
        connections = super()._mail_ahasend_connections()
        if self.env["ir.config_parameter"].sudo().get_param("ahasend.route_id"):
            connections.append(self.env._("inbound email"))
        return connections
