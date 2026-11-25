# Copyright 2026 AhaSend B.V.
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import base64
import binascii
import logging
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from odoo import api, models

_logger = logging.getLogger(__name__)

# Headers that describe the body: the rebuilt message sets its own
BODY_HEADERS = {
    "content-type",
    "content-transfer-encoding",
    "content-disposition",
    "content-id",
    "mime-version",
}

# Payload fields that stand in for headers when the route sends no headers
HEADER_FIELDS = (
    ("From", "from"),
    ("To", "to"),
    ("Cc", "cc"),
    ("Reply-To", "reply_to"),
    ("Subject", "subject"),
    ("Date", "date"),
    ("Message-ID", "message_id"),
    ("In-Reply-To", "in_reply_to"),
    ("References", "references"),
    ("Auto-Submitted", "auto_submitted"),
)


def _header_value(value):
    """Keep a header value on one line, so it cannot add headers."""
    return " ".join(str(value).split())


class AhaSendInbound(models.AbstractModel):
    _name = "ahasend.inbound"
    _description = "AhaSend inbound email"

    @api.model
    def _ahasend_build_message(self, data):
        """Rebuild the RFC 2822 email of an AhaSend route payload.

        AhaSend posts inbound email as parsed JSON. Odoo's mail gateway reads
        raw email, so this puts the email back together: the headers, the text
        and HTML bodies, and the attachments, inline images included.

        :param data: the ``data`` object of a ``message.routing`` event
        :return: the email as bytes
        """
        body = MIMEMultipart("alternative")
        body.attach(MIMEText(data.get("plain_body") or "", "plain", "utf-8"))
        if data.get("html_body"):
            body.attach(MIMEText(data["html_body"], "html", "utf-8"))
        attachments = data.get("attachments") or []
        if attachments:
            message = MIMEMultipart("mixed")
            message.attach(body)
            for attachment in attachments:
                message.attach(self._ahasend_attachment_part(attachment))
        else:
            message = body
        headers = []
        for name, value in (data.get("headers") or {}).items():
            if name.lower() not in BODY_HEADERS and value:
                headers.append((name, value))
        present = {name.lower() for name, _value in headers}
        for name, field in HEADER_FIELDS:
            if data.get(field) and name.lower() not in present:
                headers.append((name, data[field]))
        # Header values arrive decoded and can hold any character, so they
        # are written as UTF-8, which Odoo's parser reads.
        head = "".join(
            f"{name}: {_header_value(value)}\n" for name, value in headers
        ).encode()
        return head + message.as_bytes()

    @api.model
    def _ahasend_attachment_part(self, attachment):
        maintype, _sep, subtype = (
            attachment.get("content_type") or "application/octet-stream"
        ).partition("/")
        part = MIMEBase(maintype or "application", subtype or "octet-stream")
        try:
            part.set_payload(base64.b64decode(attachment.get("data") or ""))
        except (binascii.Error, ValueError):
            part.set_payload(b"")
        encoders.encode_base64(part)
        content_id = attachment.get("content_id")
        disposition = attachment.get("disposition") or (
            "inline" if content_id else "attachment"
        )
        if attachment.get("filename"):
            part.add_header(
                "Content-Disposition", disposition, filename=attachment["filename"]
            )
        else:
            part.add_header("Content-Disposition", disposition)
        if content_id:
            part["Content-ID"] = f"<{content_id}>"
        return part

    @api.model
    def _ahasend_process(self, payload):
        """Hand an inbound email from an AhaSend route to Odoo's mail gateway.

        :return: the ID of the record the email was posted on, or False when
            the payload is no inbound email or Odoo found no record or alias
            for it
        """
        if payload.get("type") != "message.routing":
            _logger.debug("AhaSend: ignoring route event %s", payload.get("type"))
            return False
        data = payload.get("data") or {}
        raw = self._ahasend_build_message(data)
        try:
            return self.env["mail.thread"].message_process(False, raw)
        except ValueError as error:
            # No alias or record matches: answering an error would make
            # AhaSend retry an email that can never be routed.
            _logger.info(
                "AhaSend: no route in Odoo for inbound email %s: %s",
                data.get("message_id"),
                error,
            )
            return False
