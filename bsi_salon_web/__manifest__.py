{
    'name': 'Enrich Beauty Website',
    'version': '19.0.2.0.0',
    'category': 'Website',
    'author': 'Botspot Infoware',
    'summary': 'The complete Enrich Beauty website — home, stores map, chair booking, membership, services, stylists, about, contact, plus a themed retail shop',
    'description': """
Enrich Beauty Website
=====================

Ships the full Enrich Beauty single-page experience exactly as designed:

* Cinematic animated hero banner (illustrated stylist + client, snipping scissors)
* Live store network with a real Leaflet/OpenStreetMap branch map per city
* Multi-step booking: city (landmark tiles) -> store (live map) -> 3D chair -> time -> confirm
* Four premium three.js chair models with multi-chair selection
* Colour Lab: level 1-10 lift maths, staged sessions, condition risk and honest pricing
* Membership tiers, services, stylist spotlight, transformations, about and contact
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
    'depends': ['base', 'web', 'website', 'website_sale', 'sale', 'payment', 'bsi_salon_backend'],
    'data': [
        'data/bsi_salon_web_data.xml',
        'data/bsi_shop_categories.xml',
        'data/bsi_shop_products.xml',
        'views/bsi_salon_web_menu.xml',
        'views/bsi_shop_templates.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'bsi_salon_web/static/src/scss/bsi_shop.scss',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
