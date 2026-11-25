To configure this module, you need to:

1.  Set up the AhaSend account in *Settings \> General Settings \>
    AhaSend*, as the *AhaSend* module (`mail_ahasend`)
    describes. To create the credential from Odoo, the API key needs
    the scope `smtp-credentials:write:all`, or
    `smtp-credentials:write:{domain}` for the sending domain.
2.  In the production database, in the *Test copies* box, click
    *Create sandbox credential*. Odoo creates an SMTP credential in
    sandbox mode in AhaSend, limited to the sending domain when one is
    set, and stores its username and password.

To use a credential that you created in the AhaSend dashboard instead,
turn on *Sandbox* for it and fill in its username and password in the
same box.

From then on, neutralizing a copy of the database, for example with
`odoo-bin neutralize`, sets up the *AhaSend sandbox* mail server in
the copy.

For a copy that was neutralized before the credential was set, fill in
the credential in the copy and click *Use the AhaSend sandbox*.

*Disconnect test copies* removes the username and password from Odoo,
so that copies made from then on send no email at all, as with Odoo's
own neutralization. The credential stays in the AhaSend account, where
you can delete it.
