# Copyright 2026 AhaSend B.V.
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class MailTrackingEvent(models.Model):
    _inherit = "mail.tracking.event"

    _sql_constraints = [
        (
            "ahasend_event_id_unique",
            "UNIQUE(ahasend_event_id)",
            "AhaSend event IDs must be unique.",
        )
    ]

    ahasend_event_id = fields.Char(
        string="AhaSend Event ID",
        copy=False,
        readonly=True,
        index=True,
    )

    def _process_data(self, tracking_email, metadata, event_type, state):
        res = super()._process_data(tracking_email, metadata, event_type, state)
        res["ahasend_event_id"] = metadata.get("ahasend_event_id", False)
        return res
