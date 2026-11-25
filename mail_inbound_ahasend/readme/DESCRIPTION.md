This module receives email for Odoo's aliases from an
[AhaSend](https://ahasend.com) inbound route, instead of a mail server
that Odoo polls. AhaSend posts each inbound email to Odoo within
seconds of its arrival. Odoo's own mail gateway then handles it as any
other incoming email: a reply lands on the record it answers, and an
email to an alias creates a record, such as a lead or a ticket.

Attachments and inline images are kept. AhaSend signs every delivery,
and Odoo refuses a delivery whose signature does not match.
