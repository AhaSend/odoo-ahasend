-- the webhook belongs to the production database: a copy must not
-- disconnect it, nor accept its events
DELETE FROM ir_config_parameter
 WHERE key IN ('ahasend.webhook_id', 'ahasend.webhook_secret');
