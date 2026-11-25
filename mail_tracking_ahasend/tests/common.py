# Copyright 2026 AhaSend B.V.
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo.addons.mail_ahasend.tests.common import configure as configure_base
from odoo.addons.mail_ahasend.tests.common import json_response  # noqa: F401
from odoo.addons.mail_ahasend.tests.common import sign as sign_base

WEBHOOK_SECRET = "aha-whsec-test-secret"
MESSAGE_ID = "<test-ahasend-id@odoo.example.com>"
RECIPIENT = "to@example.com"


def sign(body, webhook_id="msg_test_1", timestamp=None, secret=WEBHOOK_SECRET):
    """Return the AhaSend webhook headers for a raw body."""
    return sign_base(body, secret, webhook_id=webhook_id, timestamp=timestamp)


def payload(event_type, **data):
    values = {
        "account_id": "4cdd7bdd-294e-4762-892f-83d40abf5a87",
        "event": "on_" + event_type.split(".")[1],
        "from": "from@example.com",
        "recipient": RECIPIENT,
        "subject": "Test subject",
        "message_id_header": MESSAGE_ID,
        "id": "019a0c3e-7c3e-7b2a-9d4e-5f6a7b8c9d0e",
        "is_bot": False,
    }
    values.update(data)
    return {
        "type": event_type,
        "webhook_id": "abe11757-2886-4b55-96f1-0e0afc95795a",
        "timestamp": "2026-11-25T09:50:16.687031577Z",
        "data": values,
    }


def configure(env):
    """Set known AhaSend settings, whatever the database already holds."""
    configure_base(
        env,
        **{"ahasend.webhook_id": False, "ahasend.webhook_secret": WEBHOOK_SECRET},
    )


def create_tracking(env, recipient=RECIPIENT):
    """Create a mail.mail with a known Message-ID and its tracking record."""
    mail = env["mail.mail"].create(
        {
            "subject": "Test subject",
            "email_from": "from@example.com",
            "email_to": recipient,
            "body_html": "<p>This is a test message</p>",
            "message_id": MESSAGE_ID,
        }
    )
    mail.send()
    tracking = env["mail.tracking.email"].search([("mail_id", "=", mail.id)])
    if not tracking:
        # In test mode sending stops early, so the tracking record is made here
        tracking = (
            env["mail.tracking.email"]
            .sudo()
            .create(mail._tracking_email_prepare({"email_to": [recipient]}))
        )
    return mail, tracking
