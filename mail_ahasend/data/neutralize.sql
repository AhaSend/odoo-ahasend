-- a copy must not act on the production AhaSend account
DELETE FROM ir_config_parameter
 WHERE key = 'ahasend.api_key';
