# Copyright 2026 AhaSend B.V.
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, models


class AhaSendApi(models.AbstractModel):
    _inherit = "ahasend.api"

    @api.model
    def _ahasend_webhook_verify(self, webhook_id, timestamp, signature, body):
        """Check a delivery of the tracking webhook against its secret."""
        secret = (
            self.env["ir.config_parameter"].sudo().get_param("ahasend.webhook_secret")
        )
        return self._ahasend_signature_valid(
            secret, webhook_id, timestamp, signature, body
        )
