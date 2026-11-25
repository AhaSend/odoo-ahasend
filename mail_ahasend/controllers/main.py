# Copyright 2026 AhaSend B.V.
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import json
import logging

from odoo import SUPERUSER_ID, api, http
from odoo.http import request
from odoo.modules.registry import Registry

_logger = logging.getLogger(__name__)


def ahasend_response(status, text):
    return request.make_response(
        text, headers=[("Content-Type", "text/plain")], status=status
    )


def ahasend_dispatch(db, secret_param, handler):
    """Verify a signed AhaSend delivery and pass it to ``handler``.

    The database is part of the URL, so one AhaSend account can feed several
    Odoo databases on the same server. A delivery that fails the signature
    check is answered 401; AhaSend then retries it a few times and disables
    the endpoint after many failures in a row.

    :param secret_param: the system parameter that holds the signing secret
    :param handler: called as ``handler(env, payload, delivery_id)`` with a
        superuser environment
    """
    if db not in http.db_list(force=True):
        return ahasend_response(404, "Unknown database")
    httprequest = request.httprequest
    body = httprequest.get_data()
    headers = httprequest.headers

    def run(env):
        delivery_id = headers.get("webhook-id")
        secret = env["ir.config_parameter"].sudo().get_param(secret_param)
        if not env["ahasend.api"]._ahasend_signature_valid(
            secret,
            delivery_id,
            headers.get("webhook-timestamp"),
            headers.get("webhook-signature"),
            body,
        ):
            _logger.warning("AhaSend: delivery %s failed verification", delivery_id)
            return ahasend_response(401, "Invalid signature")
        try:
            payload = json.loads(body)
        except ValueError:
            return ahasend_response(400, "Invalid JSON")
        if not isinstance(payload, dict):
            return ahasend_response(400, "Invalid payload")
        handler(env, payload, delivery_id)
        return ahasend_response(200, "OK")

    if request.db == db:
        return run(request.env(su=True))
    with Registry(db).cursor() as cr:
        return run(api.Environment(cr, SUPERUSER_ID, {}))
