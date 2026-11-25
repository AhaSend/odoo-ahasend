# Copyright 2026 AhaSend B.V.
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from markupsafe import Markup

from odoo import models
from odoo.exceptions import UserError


class ResPartner(models.Model):
    _inherit = "res.partner"

    def _ahasend_suppressions(self):
        """Return the AhaSend suppressions of the partner's email address."""
        self.ensure_one()
        values = self.env["ahasend.api"]._ahasend_values()
        params = {"email": self.email_normalized or self.email, "limit": 100}
        if values.domain:
            params["domain"] = values.domain
        result = self.env["ahasend.api"]._ahasend_request(
            "GET", "/suppressions", params=params
        )
        return result.get("data") or []

    def _ahasend_require_email(self):
        missing = self.filtered(lambda partner: not partner.email)
        if missing:
            raise UserError(
                self.env._(
                    "These contacts have no email address: %s",
                    ", ".join(missing.mapped("display_name")),
                )
            )

    def action_ahasend_check_suppressed(self):
        """Mark the partner as bounced when AhaSend suppresses the address."""
        self._ahasend_require_email()
        for partner in self:
            suppressions = partner._ahasend_suppressions()
            if suppressions:
                reasons = ", ".join(
                    filter(None, (item.get("reason") for item in suppressions))
                )
                partner.email_bounced = True
                partner.message_post(
                    body=Markup(
                        self.env._(
                            "AhaSend suppresses %(email)s. Reason: %(reason)s",
                            email=partner.email,
                            reason=reasons or self.env._("unknown"),
                        )
                    )
                )
            elif partner.email_bounced:
                partner.email_bounced = False
                partner.message_post(
                    body=self.env._(
                        "AhaSend does not suppress %s. The bounce mark is removed.",
                        partner.email,
                    )
                )
        return True

    def action_ahasend_suppress(self):
        """Add the partner's address to the AhaSend suppressions."""
        self._ahasend_require_email()
        domain = self.env["ahasend.api"]._ahasend_values().domain
        for partner in self:
            body = {
                "email": partner.email_normalized or partner.email,
                "reason": self.env._("Suppressed from Odoo"),
            }
            if domain:
                body["domain"] = domain
            self.env["ahasend.api"]._ahasend_request("POST", "/suppressions", json=body)
            partner.email_bounced = True
            partner.message_post(
                body=self.env._(
                    "%s was added to the AhaSend suppressions.", partner.email
                )
            )
        return True

    def action_ahasend_unsuppress(self):
        """Remove the partner's address from the AhaSend suppressions."""
        self._ahasend_require_email()
        domain = self.env["ahasend.api"]._ahasend_values().domain
        for partner in self:
            params = {"email": partner.email_normalized or partner.email}
            if domain:
                params["domain"] = domain
            self.env["ahasend.api"]._ahasend_request(
                "DELETE", "/suppressions", params=params
            )
            partner.email_bounced = False
            partner.message_post(
                body=self.env._(
                    "%s was removed from the AhaSend suppressions.", partner.email
                )
            )
        return True
