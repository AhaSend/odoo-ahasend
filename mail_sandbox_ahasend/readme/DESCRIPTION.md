Copies of a production database, for testing, staging or trying an
upgrade, hold the email addresses of real customers. Odoo's
neutralization keeps them from emailing anyone by turning all outgoing
mail off, so testers cannot see what Odoo would have sent.

With this module, a neutralized copy sends its email to the
[AhaSend](https://ahasend.com) sandbox instead. AhaSend accepts every
email, never delivers it, and shows it in the AhaSend dashboard, with
its HTML and text content and its headers. Each email is tagged with
the name of the database it came from, so the email of several copies
can be told apart.

The copy uses a sandbox SMTP credential that the production database
holds. AhaSend never delivers email sent with a sandbox credential, so
this credential cannot send real email, also when a database dump
with it ends up elsewhere. Every email of a neutralized copy also
carries AhaSend's sandbox header.

The neutralization also removes the AhaSend API key, and the IDs and
secrets of the webhook and inbound route, so that a copy cannot act on
the production account.
