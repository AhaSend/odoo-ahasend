This module connects the mail tracking of *mail_tracking* with
[AhaSend](https://ahasend.com), a European transactional email service.

Odoo sends its mail through AhaSend over SMTP. AhaSend then reports what
happened to each email through a webhook: delivered, deferred, bounced,
failed, suppressed, opened, clicked, unsubscribed or marked as spam. The
module turns these reports into mail tracking events, so the tracking
status in Odoo shows what happened after the email left Odoo.

It also adds a button to fetch the status of an email from AhaSend, and
buttons on contacts to check, add and remove an address in the AhaSend
suppression list.
