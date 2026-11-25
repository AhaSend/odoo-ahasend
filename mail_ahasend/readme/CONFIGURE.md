To configure this module, you need to:

1.  In AhaSend, verify your sending domain and create an API key. The
    scopes it needs depend on the AhaSend modules you install; each
    module's configuration lists them. Note your account ID and the
    secret key of the API key.
2.  In Odoo, go to *Settings \> General Settings \> AhaSend \>
    Account* and turn it on.
3.  Fill in the account ID and the secret key. Optionally, fill in:
    - *Sending domain*: limits the AhaSend features to one sending
      domain.
    - *Odoo URL*: the public `https://` address AhaSend sends events
      and email to. It is filled in with the base URL of this Odoo;
      change it when AhaSend must reach Odoo on another address.

You can set the timeout of calls to the AhaSend API, in seconds, with
the system parameter `ahasend.timeout` (default: 10). The system
parameter `ahasend.api_url` changes the address of the API, for
testing against another server.

The full setup guide is at <https://ahasend.com/docs/guides/odoo>.
