{
    'name': 'Enrich Salon Management',
    'version': '19.0.4.0.0',
    'category': 'Website',
    'author': 'Botspot Infoware',
    'summary': 'Enrich Beauty website: home, about, services, membership, stores, stylists, booking, contact',
    'description': """
        Public website for Enrich Beauty (salon chain) — native Odoo pages (QWeb templates +
        SCSS + JS) backed by content models (services, packages, memberships, locations, team,
        testimonials) plus a live store map and a multi-step chair-booking wizard.

        Backend appointment desk: city/branch/services/chair/artist/date-or-fixed-slot
        appointment creation with artist-wise pricing, a draft → CRM lead → quotation →
        sale order flow, user-wise filters, and a website "My Appointments" status page.
    """,
    'depends': ['base', 'web', 'website', 'portal', 'crm', 'sale', 'sale_crm', 'website_sale', 'rating'],
    'data': [
        'security/bsi_salon_theme_security.xml',
        'security/ir.model.access.csv',
        'views/res_config_settings_views.xml',
        'views/bsi_salon_theme_templates.xml',
        'views/bsi_salon_home_templates.xml',
        'views/bsi_salon_about_templates.xml',
        'views/bsi_salon_offers_templates.xml',
        'views/bsi_salon_packages_templates.xml',
        'views/bsi_salon_stores_templates.xml',
        'views/bsi_salon_stylists_templates.xml',
        'views/bsi_salon_booking_templates.xml',
        'views/bsi_salon_contact_templates.xml',
        'views/bsi_salon_shop_templates.xml',
        'views/bsi_salon_checkout_views.xml',
        'views/bsi_salon_booking_request_views.xml',
        'views/bsi_salon_content_views.xml',
        'views/bsi_salon_chair_time_slot_views.xml',
        'views/bsi_salon_membership_subscription_views.xml',
        'views/bsi_salon_loyalty_views.xml',
        'views/bsi_salon_rating_views.xml',
        'views/bsi_salon_crm_lead_views.xml',
        'views/bsi_salon_sale_order_views.xml',
        'views/bsi_salon_ecommerce_views.xml',
        'views/bsi_salon_portal_templates.xml',
        'views/bsi_salon_dashboard_kpi_search_views.xml',
        'views/bsi_salon_dashboard_kpi_actions.xml',
        'views/bsi_salon_dashboard_templates.xml',
        'views/bsi_salon_reschedule_wizard_views.xml',
        'data/bsi_salon_theme_service_data.xml',
        'data/bsi_salon_theme_data.xml',
        'data/bsi_salon_theme_chair_data.xml',
        'data/bsi_salon_theme_time_slot_data.xml',
        'data/bsi_salon_theme_config_data.xml',
        'data/bsi_salon_membership_subscription_cron_data.xml',
        'data/bsi_salon_slot_conflict_mail_template.xml',
        'data/bsi_salon_discount_product_data.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'bsi_salon_theme/static/src/scss/bsi_salon_theme.scss',
            'bsi_salon_theme/static/src/lib/gsap/gsap.min.js',
            'bsi_salon_theme/static/src/lib/gsap/ScrollTrigger.min.js',
            'bsi_salon_theme/static/src/js/bsi_salon_theme.js',
            'bsi_salon_theme/static/src/js/bsi_salon_theme_motion.js',
        ],
        'bsi_salon_theme.dashboard_assets': [
            'bsi_salon_theme/static/src/scss/bsi_salon_dashboard.scss',
        ],
        'web.assets_backend': [
            'bsi_salon_theme/static/src/js/bsi_salon_dashboard_client_action.js',
            'bsi_salon_theme/static/src/scss/bsi_booking_kanban.scss',
            'bsi_salon_theme/static/src/scss/bsi_backend_kanban.scss',
        ],
        'web._assets_primary_variables': [
            ('before', 'web/static/src/scss/primary_variables.scss',
             'bsi_salon_theme/static/src/scss/bsi_backend_theme.scss'),
        ],
    },
    'application': False,
    'license': 'LGPL-3',
}
