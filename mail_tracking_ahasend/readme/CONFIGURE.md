To configure this module, you need to:

1.  In AhaSend, verify your sending domain and create SMTP credentials.
    Set them up as the outgoing mail server in Odoo.
2.  Set up the AhaSend account in *Settings \> General Settings \>
    AhaSend*, as the *AhaSend* module (`mail_ahasend`)
    describes. The API key needs these scopes: `messages:read:all`,
    `suppressions:read`, `suppressions:write`, `suppressions:delete`,
    `webhooks:write:all` and `webhooks:delete:all`.
3.  In the *Delivery tracking* box, click *Connect tracking*. Odoo creates the
    webhook in AhaSend and stores its signing secret. *Disconnect
    tracking* deletes it again. With a *Sending domain* set, the webhook
    and the suppression actions are limited to that domain.

To create the webhook in the AhaSend dashboard instead, turn on
developer mode and use *Manual webhook setup* in the *Delivery tracking* box:
copy the *Endpoint URL*
(`https://<your-odoo>/mail/tracking/ahasend/<database>`) into the
webhook's endpoint URL, send all events or at least the message events,
and copy the webhook's secret into *Webhook secret*.

The full setup guide is at <https://ahasend.com/docs/guides/odoo>.
