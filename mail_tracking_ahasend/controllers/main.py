# Copyright 2026 AhaSend B.V.
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import http

from odoo.addons.mail_ahasend.controllers.main import ahasend_dispatch
from odoo.addons.mail_tracking.controllers import main


class MailTrackingController(main.MailTrackingController):
    @http.route(
        "/mail/tracking/ahasend/<string:db>",
        type="http",
        auth="none",
        methods=["POST"],
        csrf=False,
        save_session=False,
        readonly=False,
    )
    def mail_tracking_ahasend_webhook(self, db, **kwargs):
        """Receive the events of AhaSend's tracking webhook.

        Events for mail this database did not send are acknowledged and
        dropped.
        """
        return ahasend_dispatch(db, "ahasend.webhook_secret", self._ahasend_track)

    def _ahasend_track(self, env, payload, delivery_id):
        env["mail.tracking.email"]._ahasend_event_process(payload, delivery_id)
