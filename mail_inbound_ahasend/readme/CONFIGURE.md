To configure this module, you need to:

1.  Set up the AhaSend account in *Settings \> General Settings \>
    AhaSend*, as the *AhaSend* module (`mail_ahasend`)
    describes. The API key needs the scopes `routes:write:all` and
    `routes:delete:all`.
2.  Point the MX records of the domain of Odoo's aliases to AhaSend, as
    the domain details in the AhaSend dashboard show.
3.  In AhaSend, set the message data retention of the account to 1 day
    or more: AhaSend discards inbound email at 0 days.
4.  In the *Inbound email* box, check the *Inbound domain*. It is
    filled in with the alias domain of the company.
5.  Click *Connect inbound email*. Odoo creates a route in AhaSend that
    posts all email for that domain to Odoo, with attachments and
    headers, once per email.

To create the route in the AhaSend dashboard instead, turn on developer
mode and use *Manual route setup* in the *Inbound email* box: copy the *Route
endpoint URL* (`https://<your-odoo>/mail/inbound/ahasend/<database>`)
into the route's endpoint URL, turn on attachments, headers and
deduplication by Message ID, and copy the route's secret into *Route
secret*.
