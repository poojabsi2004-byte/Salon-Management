{
    'name': 'Enrich Beauty Website',
    'version': '19.0.2.0.0',
    'category': 'Website',
    'author': 'Botspot Infoware',
    'summary': 'The complete Enrich Beauty website — home, stores map, chair booking, membership, services, artists, about, contact, plus a themed retail shop',
    'description': """
Enrich Beauty Website
=====================

Ships the full Enrich Beauty single-page experience exactly as designed:

* Cinematic animated hero banner (illustrated artist + client, snipping scissors)
* Live store network with a real Leaflet/OpenStreetMap branch map per city
* Multi-step booking: city (landmark tiles) -> store (live map) -> 3D chair -> time -> confirm
* Four premium three.js chair models with multi-chair selection
* Colour Lab: level 1-10 lift maths, staged sessions, condition risk and honest pricing
* Membership tiers, services, artist spotlight, transformations, about and contact
* Full motion design: page-change blur transition, scroll choreography, custom cursor,
  magnetic buttons, 3D card tilt, scroll progress and ambient grain

Retail shop
-----------
The standard Odoo eCommerce shop is restyled to match the Enrich design — same
fonts, crimson-on-ink palette, card elevation and motion — and seeded with the
professional retail lines the salons stock, organised by category and brand.

The main site is served as one self-contained asset, so what you see in Odoo is
pixel-identical to the approved design — no re-implementation, no drift.
    """,
    # PHASE 1 BRIDGE -- bsi_salon_backend supplies the salon records the site now
    # renders. Depending on it also fixes the load order, so this module's
    # /salon routes are the ones Odoo registers.
    'depends': ['base', 'web', 'website', 'website_sale', 'sale', 'payment', 'bsi_salon_backend',
                # customer sign-up/sign-in on Odoo's own portal accounts + its password policy
                'auth_signup', 'auth_password_policy_signup'],
    'data': [
        'data/bsi_salon_web_data.xml',
        'data/bsi_shop_categories.xml',
        'data/bsi_shop_products.xml',
        'views/bsi_salon_web_menu.xml',
        'views/bsi_shop_templates.xml',
        'views/bsi_salon_account_templates.xml',
        'views/bsi_salon_auth_templates.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            # bsi_nav_dropdown.css is the ONE navbar stylesheet shared by every
            # frontend page (see the file's own header comment) -- registered
            # here for shop/cart/checkout/portal/contact, and linked to
            # directly by its static URL for /salon's own exported page, which
            # bypasses this bundle entirely.
            'bsi_salon_web/static/src/css/bsi_nav_dropdown.css',
            # PHASE 7 DEV -- scroll choreography and the footer redesign,
            # shared across every frontend page (same pattern as the navbar
            # CSS above: linked directly by URL from the SPA export, bundled
            # here for every other frontend page).
            'bsi_salon_web/static/src/css/bsi_scroll_fx.css',
            'bsi_salon_web/static/src/css/bsi_site_redesign.css',
            'bsi_salon_web/static/src/js/bsi_scroll_fx.js',
            'bsi_salon_web/static/src/scss/bsi_shop.scss',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': True,
    'license': 'LGPL-3',
}
