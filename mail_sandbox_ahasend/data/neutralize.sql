-- send the email of the copy to the AhaSend sandbox, when the production
-- database holds a sandbox SMTP credential: AhaSend never delivers it
UPDATE ir_mail_server
   SET active = false
 WHERE name = 'neutralization - disable emails'
   AND EXISTS (SELECT 1 FROM ir_config_parameter
                WHERE key = 'ahasend.sandbox_smtp_user' AND value <> '')
   AND EXISTS (SELECT 1 FROM ir_config_parameter
                WHERE key = 'ahasend.sandbox_smtp_password' AND value <> '');

INSERT INTO ir_mail_server(name, smtp_host, smtp_port, smtp_encryption,
                           smtp_authentication, smtp_user, smtp_pass,
                           sequence, active)
SELECT 'AhaSend sandbox', 'send.ahasend.com', 587, 'starttls_strict',
       'login', sandbox_user.value, sandbox_password.value, 1, true
  FROM ir_config_parameter sandbox_user,
       ir_config_parameter sandbox_password
 WHERE sandbox_user.key = 'ahasend.sandbox_smtp_user'
   AND sandbox_user.value <> ''
   AND sandbox_password.key = 'ahasend.sandbox_smtp_password'
   AND sandbox_password.value <> '';
