# Copyright 2026 AhaSend B.V.
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "Mail tracking for AhaSend",
    "summary": "Mail tracking and AhaSend webhooks integration",
    "version": "18.0.1.0.0",
    "category": "Social Network",
    "website": "https://github.com/AhaSend/odoo-ahasend",
    "author": "AhaSend B.V.",
    "maintainers": ["MarkNLD"],
    "license": "AGPL-3",
    "application": False,
    "installable": True,
    "depends": ["mail_ahasend", "mail_tracking"],
    "data": [
        "views/mail_tracking_email.xml",
        "views/res_partner.xml",
        "wizards/res_config_settings_views.xml",
    ],
}
