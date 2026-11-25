-- the route belongs to the production database: a copy must not
-- disconnect it, nor accept its email
DELETE FROM ir_config_parameter
 WHERE key IN ('ahasend.route_id', 'ahasend.route_secret');
