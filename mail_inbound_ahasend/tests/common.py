# Copyright 2026 AhaSend B.V.
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import base64

from odoo.addons.mail_ahasend.tests.common import configure as configure_base

ROUTE_SECRET = "aha-whsec-route-secret"
SENDER = "customer@example.net"


def configure(env):
    configure_base(
        env,
        **{
            "ahasend.route_id": False,
            "ahasend.route_secret": ROUTE_SECRET,
            "ahasend.inbound_domain": False,
        },
    )


def route_payload(**data):
    """Return a message.routing event, as AhaSend posts it."""
    values = {
        "id": "019a0c3f-1d2e-7f3a-8b4c-5d6e7f8a9b0c",
        "from": f"Customer <{SENDER}>",
        "reply_to": "",
        "to": "inbound-test@odoo.example.com",
        "subject": "Help with my account",
        "message_id": "<unique-message-id@example.net>",
        "size": 2048,
        "spam_score": 0.1,
        "bounce": False,
        "cc": "",
        "date": "Mon, 06 May 2024 13:15:46 +0000",
        "in_reply_to": "",
        "references": "",
        "auto_submitted": "",
        "html_body": "<p>I need help with my account settings.</p>",
        "plain_body": "I need help with my account settings.",
        "reply_from_plain_body": "I need help with my account settings.",
        "attachments": [],
    }
    values.update(data)
    return {
        "type": "message.routing",
        "route_id": "abe11757-2886-4b55-96f1-0e0afc95795a",
        "timestamp": "2024-05-06T13:15:46.404433272Z",
        "data": values,
    }


def attachment(filename, content, content_type="text/plain", **values):
    return dict(
        {
            "filename": filename,
            "content_type": content_type,
            "content_id": "",
            "disposition": "attachment",
            "data": base64.b64encode(content).decode(),
        },
        **values,
    )
