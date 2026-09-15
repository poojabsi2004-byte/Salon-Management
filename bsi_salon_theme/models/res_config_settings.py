from odoo import models, fields, api

# ir.config_parameter.set_param() treats a literal Python False (or None) as "delete this
# parameter" rather than "store False" — so the generic Boolean + config_parameter= field
# mechanism silently loses a toggle the moment it's switched off (set_values() ends up
# calling set_param(key, False), which unlinks the row instead of storing it, and the next
# read falls back to the default — appearing to have never changed). Handling storage
# ourselves, always writing the literal strings 'True'/'False', sidesteps that entirely.
BSI_SHOW_PARAM_KEYS = {
    'bsi_show_membership': 'bsi_salon_theme.show_membership',
    'bsi_show_packages': 'bsi_salon_theme.show_packages',
    'bsi_show_loyalty_points': 'bsi_salon_theme.show_loyalty_points',
    'bsi_show_referral': 'bsi_salon_theme.show_referral',
    'bsi_show_gift_card': 'bsi_salon_theme.show_gift_card',
}

# Backend menus toggled alongside each setting (ir.ui.menu.active, not a security group —
# the menu genuinely disappears from Salon Management for everyone, same as the website
# section vanishing). Gift Card has no dedicated backend menu of its own yet, so it only
# ever affects the website.
BSI_MENU_XMLIDS = {
    'bsi_show_membership': [
        'bsi_salon_theme.bsi_salon_membership_group_menu',
        'bsi_salon_theme.bsi_salon_membership_menu',
        'bsi_salon_theme.bsi_salon_membership_subscription_menu',
    ],
    'bsi_show_packages': ['bsi_salon_theme.bsi_salon_package_menu'],
    'bsi_show_loyalty_points': ['bsi_salon_theme.bsi_salon_loyalty_point_menu'],
    'bsi_show_referral': ['bsi_salon_theme.bsi_salon_referral_wizard_menu'],
    'bsi_show_gift_card': [],
}


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    bsi_show_membership = fields.Boolean(
        string='Show Membership', default=True,
        help='Show the Membership plans section on the website Packages page.')
    bsi_show_packages = fields.Boolean(
        string='Show Packages', default=True,
        help='Show the Bundle Packages section on the website Packages page.')
    bsi_show_loyalty_points = fields.Boolean(
        string='Show Loyalty Points', default=True,
        help='Show the Loyalty Wallet section on the website Packages page.')
    bsi_show_referral = fields.Boolean(
        string='Show Refer a Friend', default=True,
        help='Show the Refer a Friend section on the website Packages page.')
    bsi_show_gift_card = fields.Boolean(
        string='Show Gift Card', default=True,
        help='Show the Gift Cards section on the website Packages page.')

    def set_values(self):
        super().set_values()
        ICP = self.env['ir.config_parameter'].sudo()
        for fname, key in BSI_SHOW_PARAM_KEYS.items():
            ICP.set_param(key, 'True' if self[fname] else 'False')
            for xmlid in BSI_MENU_XMLIDS.get(fname, []):
                menu = self.env.ref(xmlid, raise_if_not_found=False)
                if menu:
                    menu.sudo().active = bool(self[fname])

    @api.model
    def get_values(self):
        res = super().get_values()
        ICP = self.env['ir.config_parameter'].sudo()
        for fname, key in BSI_SHOW_PARAM_KEYS.items():
            res[fname] = ICP.get_param(key, 'True') == 'True'
        return res
