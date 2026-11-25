This module connects Odoo to [AhaSend](https://ahasend.com), the
European transactional email service. It holds the AhaSend account
settings and the connection to the AhaSend Management API, which the
other AhaSend modules use:

- *Mail tracking for AhaSend* (`mail_tracking_ahasend`) shows delivery,
  bounce, open and click events in Odoo's mail tracking.
- *Inbound email for AhaSend* (`mail_inbound_ahasend`) receives email for
  Odoo's aliases from AhaSend, without a mail server to poll.
- *AhaSend sandbox for test copies* (`mail_sandbox_ahasend`) sends the
  email of neutralized copies to the AhaSend sandbox, where it can be
  viewed but is never delivered.

On its own, this module adds no feature. Install one of the modules
above.

When a database is neutralized, this module removes the AhaSend API key
from the copy, so that the copy cannot act on the production account.
