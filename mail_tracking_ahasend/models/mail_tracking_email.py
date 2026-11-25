# Copyright 2026 AhaSend B.V.
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import logging
import re
from datetime import datetime, timedelta, timezone

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools import email_split

_logger = logging.getLogger(__name__)

# AhaSend webhook event type: mail.tracking.event type
AHASEND_EVENT_TYPES = {
    "message.delivered": "delivered",
    "message.transient_error": "deferral",
    "message.bounced": "hard_bounce",
    # Retries ran out: the address may still be valid, so it is not marked as
    # bounced on the partner.
    "message.failed": "soft_bounce",
    "message.suppressed": "reject",
    "message.opened": "open",
    "message.clicked": "click",
    "message.unsubscribed": "unsub",
    "message.complained": "spam",
}

# AhaSend message status (Management API): mail.tracking.event type
AHASEND_STATUS_TYPES = {
    "Delivered": "delivered",
    "Opened": "open",
    "Clicked": "click",
    "Deferred": "deferral",
    "Bounced": "hard_bounce",
    "Failed": "soft_bounce",
    "Suppressed": "reject",
}

# Webhooks can arrive out of order: an event of the key type that arrives while
# the tracking is in one of these states is older news, and would move the state
# backwards
STALE_STATES = {
    "deferral": {
        "delivered",
        "opened",
        "rejected",
        "spam",
        "unsub",
        "bounced",
        "soft-bounced",
    },
    "delivered": {"opened", "spam", "unsub"},
}


# Sync from AhaSend looks back this many days, or less when AhaSend keeps the
# messages of the account for a shorter time
SYNC_DAYS = 2
# Tracking states that a later AhaSend status can still change
SYNC_STATES = ("sent", "deferred", "delivered")


def _parse_timestamp(value):
    """Return the POSIX timestamp of an RFC 3339 date, or False."""
    if not value:
        return False
    # Python reads at most 6 fractional digits; AhaSend can send 9
    value = re.sub(r"(\.\d{6})\d+", r"\1", value).replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(value).timestamp()
    except ValueError:
        return False


class MailTrackingEmail(models.Model):
    _inherit = "mail.tracking.email"

    @api.model
    def _ahasend_find_tracking(self, message_id_header, recipient):
        """Find the tracking record of the email AhaSend reports on.

        Odoo sends over SMTP with its own Message-ID header, which AhaSend
        keeps, so the Message-ID and the recipient identify the tracking record.
        """
        recipients = email_split(recipient or "")
        if not message_id_header or not recipients:
            return self.browse()
        messages = (
            self.env["mail.message"]
            .sudo()
            .with_context(active_test=False)
            .search([("message_id", "=", message_id_header)])
        )
        if not messages:
            return self.browse()
        return self.sudo().search(
            [
                ("mail_message_id", "in", messages.ids),
                ("recipient_address", "=", recipients[0].lower()),
            ],
            order="id desc",
            limit=1,
        )

    @api.model
    def _ahasend_metadata(self, event_type, data, timestamp):
        """Map an AhaSend message event to mail.tracking.event metadata."""
        metadata = {"recipient": data.get("recipient")}
        ts = _parse_timestamp(timestamp)
        if ts:
            dt = datetime.fromtimestamp(ts, timezone.utc)
            metadata.update(
                {
                    "timestamp": ts,
                    "time": fields.Datetime.to_string(dt),
                    "date": fields.Date.to_string(dt),
                }
            )
        for key in ("ip", "user_agent", "url"):
            if data.get(key):
                metadata[key] = data[key]
        attempt = data.get("delivery_attempt") or {}
        if event_type in {"hard_bounce", "soft_bounce", "deferral", "reject"}:
            error_type = attempt.get("classification") or (
                str(attempt["smtp_code"]) if attempt.get("smtp_code") else False
            )
            description = attempt.get("response") or False
            details = attempt.get("description") or attempt.get("enhanced_status_code")
            if event_type == "reject":
                error_type = "suppressed"
                description = self.env._("AhaSend suppressed this recipient")
            elif event_type == "soft_bounce" and not description:
                error_type = error_type or "failed"
                description = self.env._("AhaSend stopped retrying delivery")
            metadata.update(
                {
                    "error_type": error_type,
                    "error_description": description,
                    "error_details": details or False,
                    "bounce_type": error_type,
                    "bounce_description": description,
                }
            )
        elif event_type == "spam":
            metadata.update(
                {
                    "error_type": "spam",
                    "error_description": self.env._(
                        "Recipient '%s' marked this email as spam",
                        data.get("recipient"),
                    ),
                }
            )
        return metadata

    @api.model
    def _ahasend_event_process(self, payload, event_id):
        """Turn one AhaSend message webhook into a mail.tracking.event.

        :param payload: the decoded webhook body
        :param event_id: the ``webhook-id`` header, stable across retries
        :return: the created events, or an empty recordset when the event is
            ignored
        """
        events = self.env["mail.tracking.event"]
        event_type = AHASEND_EVENT_TYPES.get(payload.get("type"))
        data = payload.get("data") or {}
        if not event_type:
            _logger.debug("AhaSend: ignoring event type %s", payload.get("type"))
            return events
        if event_type in {"open", "click"} and data.get("is_bot"):
            _logger.debug("AhaSend: ignoring bot %s", event_type)
            return events
        if event_id and events.sudo().search_count(
            [("ahasend_event_id", "=", event_id)], limit=1
        ):
            _logger.debug("AhaSend: event %s already processed", event_id)
            return events
        tracking = self._ahasend_find_tracking(
            data.get("message_id_header"), data.get("recipient")
        )
        if not tracking:
            # Mail sent by another system or another database on the account
            _logger.debug(
                "AhaSend: no tracking for %s to %s",
                data.get("message_id_header"),
                data.get("recipient"),
            )
            return events
        if tracking.state in STALE_STATES.get(event_type, ()):
            _logger.debug(
                "AhaSend: %s arrived after %s, ignored", event_type, tracking.state
            )
            return events
        metadata = self._ahasend_metadata(event_type, data, payload.get("timestamp"))
        metadata["ahasend_event_id"] = event_id
        _logger.info(
            "AhaSend: %s for tracking %s (%s)",
            payload.get("type"),
            tracking.id,
            data.get("recipient"),
        )
        return tracking.event_create(event_type, metadata)

    def action_manual_check_ahasend(self):
        """Fetch the message status from AhaSend, for a missed webhook."""
        for tracking in self.filtered("message_id"):
            if not tracking._ahasend_check():
                raise UserError(
                    self.env._(
                        "AhaSend has no message with this Message-ID and "
                        "recipient. It may be past its retention period."
                    )
                )
        return True

    def _ahasend_check(self):
        """Record the current AhaSend status of this email.

        :return: False when AhaSend has no message with this Message-ID and
            recipient
        """
        self.ensure_one()
        recipients = email_split(self.recipient or "")
        result = self.env["ahasend.api"]._ahasend_request(
            "GET",
            "/messages",
            params={
                "message_id_header": self.message_id,
                "recipient": recipients[0] if recipients else None,
                "limit": 1,
            },
        )
        messages = result.get("data") or []
        if not messages:
            return False
        message = messages[0]
        event_type = AHASEND_STATUS_TYPES.get(message.get("status"))
        if not event_type:
            return True
        event_id = f"api:{message.get('id')}:{message.get('status')}"
        payload = {
            "type": next(
                key for key, value in AHASEND_EVENT_TYPES.items() if value == event_type
            ),
            "timestamp": message.get("delivered_at") or message.get("updated_at"),
            "data": {
                "recipient": message.get("recipient"),
                "message_id_header": message.get("message_id"),
            },
        }
        self.sudo()._ahasend_event_process(payload, event_id)
        return True

    @api.model
    def _ahasend_sync_days(self):
        """Return how many days back AhaSend still knows the messages."""
        account = self.env["ahasend.api"]._ahasend_request("GET", "")
        days = SYNC_DAYS
        for key in ("message_data_retention", "message_metadata_retention"):
            retention = account.get(key)
            if isinstance(retention, int):
                days = min(days, retention)
        return days

    @api.model
    def _ahasend_sync(self):
        """Fetch the AhaSend status of the recent emails that can still change.

        This catches up on webhook events that Odoo missed, for example while
        it was down or before tracking was connected.

        :return: a tuple (days, checked, updated)
        """
        days = self._ahasend_sync_days()
        if days <= 0:
            raise UserError(
                self.env._(
                    "AhaSend keeps no message data for this account: its "
                    "retention is 0 days. There is nothing to sync."
                )
            )
        since = fields.Datetime.now() - timedelta(days=days)
        trackings = (
            self.sudo()
            .search(
                [
                    ("time", ">=", since),
                    ("state", "in", SYNC_STATES),
                    ("mail_message_id", "!=", False),
                ]
            )
            .filtered("message_id")
        )
        updated = 0
        for tracking in trackings:
            state = tracking.state
            tracking._ahasend_check()
            if tracking.state != state:
                updated += 1
        _logger.info(
            "AhaSend: synced %s emails of the last %s days, %s updated",
            len(trackings),
            days,
            updated,
        )
        return days, len(trackings), updated
