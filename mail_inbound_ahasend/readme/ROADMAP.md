- AhaSend sends one delivery per email, with its To and Cc headers. An
  email that reached an alias only through Bcc has no trace of that
  alias in its headers, so Odoo can route it only when it replies to a
  known message.
- AhaSend's spam score is not used yet: every email that reaches the
  route goes to Odoo.
