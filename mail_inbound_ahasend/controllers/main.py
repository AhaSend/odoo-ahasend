# Copyright 2026 AhaSend B.V.
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import http

from odoo.addons.mail_ahasend.controllers.main import ahasend_dispatch


class AhaSendInboundController(http.Controller):
    @http.route(
        "/mail/inbound/ahasend/<string:db>",
        type="http",
        auth="none",
        methods=["POST"],
        csrf=False,
        save_session=False,
        readonly=False,
    )
    def mail_inbound_ahasend(self, db, **kwargs):
        """Receive the inbound email of an AhaSend route.

        Odoo's mail gateway ignores an email whose Message-ID it already has,
        so a delivery that AhaSend retries is posted once.
        """
        return ahasend_dispatch(db, "ahasend.route_secret", self._ahasend_receive)

    def _ahasend_receive(self, env, payload, delivery_id):
        env["ahasend.inbound"]._ahasend_process(payload)
