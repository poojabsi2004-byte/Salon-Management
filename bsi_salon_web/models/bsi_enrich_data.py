# -*- coding: utf-8 -*-
"""PHASE 1 BRIDGE -- live salon data in the shapes the Enrich design expects.

The compiled site ships every city, branch, service, stylist, tier and time slot
as a JavaScript literal. This provider reads the same information out of
bsi_salon_backend so the served page shows real records while rendering exactly as
the design was approved.

Shapes here are deliberately not tidied up. The design indexes into its own
CITY_IDENTITY map by city id and into its slot caption map by slot label, so
those two keys must keep their original values or the page loses its city
artwork and its availability captions. Where a backend field has no counterpart
in the design it is dropped rather than appended, for the same reason.

Nothing in bsi_salon_backend is modified; this reads through the public access
rules that module already grants on all seven models.
"""

import re
from odoo import api, fields, models

# The About hero's own two paragraphs, shown until the backend story is filled in.
_DESIGN_ABOUT_STORY = (
    "Founded in 1997 as a venture among friends with no background in the beauty industry, "
    "Enrich has grown into one of India's largest company-owned salon chains \u2014 built on "
    "trust between our artists and the guests they serve.",
    "Today we partner with global names like L'Or\u00e9al Professionnel to bring international "
    "technique to every chair, in every city we operate in.",
)

# PHASE 1 BRIDGE -- the design's service pills are fixed in its markup: five
# categories where the backend has six. Mapping keeps every backend service
# reachable instead of silently hiding colour and bridal work.
_CATEGORY_MAP = {
    'hair': 'hair',
    'colour': 'hair',
    'skin': 'skin',
    'bridal': 'makeup',
    'body': 'waxing',
    'nails': 'handsfeet',
}
_SPA_CATEGORIES = ('hair', 'skin', 'makeup', 'waxing', 'handsfeet')

# Colour Lab pricing: (key the page reads, bsi.salon.colour.lab.config field, the
# design's own figure used when the field is unset).
_LAB_PRICING_FIELDS = (
    ('baseLighter', 'bsi_base_lighter', 2900),
    ('baseDarker', 'bsi_base_darker', 2400),
    ('perLevel', 'bsi_price_per_level', 420),
    ('perExtraSession', 'bsi_price_per_extra_session', 1600),
    ('minutesLighter', 'bsi_minutes_lighter', 110),
    ('minutesDarker', 'bsi_minutes_darker', 90),
    ('minutesPerLevel', 'bsi_minutes_per_level', 12),
    ('minutesToner', 'bsi_minutes_toner', 30),
    ('riskPerLevel', 'bsi_risk_per_level', 9),
    ('riskMultiSession', 'bsi_risk_multi_session', 8),
    ('weeksBetween', 'bsi_weeks_between_sessions', 6),
)

# The design filters its stylist grid on these four labels.
_STYLIST_CATEGORIES = (
    ('Makeup', ('makeup', 'bridal', 'mua')),
    ('Skin', ('skin', 'facial', 'spa', 'derma')),
    ('Nails', ('nail', 'manicure', 'pedicure')),
)


class BsiEnrichData(models.AbstractModel):
    """PHASE 1 BRIDGE -- read-only provider. Adds no tables and no fields."""

    _name = 'bsi.enrich.data'
    _description = 'Enrich Website Live Data Provider (Phase 1 bridge)'

    # -- helpers ---------------------------------------------------------

    @api.model
    def _bsi_city_slug(self, city_name):
        """Slug matching the design's own city ids, so the artwork keeps resolving.

        CITY_IDENTITY is keyed 'ahmedabad', 'pune', 'mumbai'... and falls back to
        a generic entry for anything it does not recognise, so a city added later
        degrades to a plain tile rather than breaking the page.
        """
        return ''.join(ch for ch in (city_name or '').lower() if ch.isalnum())

    @api.model
    def _bsi_stylist_category(self, specialty, role):
        haystack = ('%s %s' % (specialty or '', role or '')).lower()
        for label, keywords in _STYLIST_CATEGORIES:
            if any(word in haystack for word in keywords):
                return label
        return 'Hair'

    # -- datasets --------------------------------------------------------

    @api.model
    def _bsi_cities(self):
        """CITIES: [{id, name, lat, lng, branches: [{id, name, area, rating, wait, lat, lng, hours}]}]

        Branch ids are real database ids. The design only ever uses them to look a
        branch back up in its own list, never to index a static map, so integers
        are safe here where city ids are not.
        """
        locations = self.env['bsi.salon.location'].sudo().search(
            [], order='bsi_city, sequence, id')
        cities, order = {}, []
        for loc in locations:
            # A linked City record (bsi_city_id) is authoritative when set -- its own slug
            # and name, not the free-text bsi_city, so a branch grouped under a real City
            # record can never be split off by a typo mismatching that city's own name.
            slug = loc.bsi_city_id.bsi_slug if loc.bsi_city_id else self._bsi_city_slug(loc.bsi_city)
            if not slug:
                continue
            if slug not in cities:
                cities[slug] = {
                    'id': slug,
                    'name': loc.bsi_city_id.name if loc.bsi_city_id else loc.bsi_city,
                    'lat': loc.bsi_latitude or 0.0,
                    'lng': loc.bsi_longitude or 0.0,
                    'branches': [],
                }
                order.append(slug)
            cities[slug]['branches'].append({
                'id': loc.id,
                'name': loc.name,
                'area': loc.bsi_address or '',
                'rating': round(loc.bsi_rating or 4.8, 1),
                'wait': int(loc.bsi_wait_minutes or 0),
                'lat': loc.bsi_latitude or 0.0,
                'lng': loc.bsi_longitude or 0.0,
                'hours': loc.bsi_hours_weekdays or '',
                # PHASE 8 DEV -- shown on the Contact page's "Your salon" card.
                'phone': loc.bsi_phone or '',
            })

        # The design centres each city map on the city's own coordinates, which
        # only exist per branch, so average them.
        for slug in order:
            city = cities[slug]
            located = [b for b in city['branches'] if b['lat'] and b['lng']]
            if located:
                city['lat'] = sum(b['lat'] for b in located) / len(located)
                city['lng'] = sum(b['lng'] for b in located) / len(located)
        return [cities[slug] for slug in order]

    @api.model
    def _bsi_services(self):
        """SERVICES_DATA: {category: [{id, name, duration, price, points, description, price_amount}]}

        Price and duration stay as the backend's own display labels, because that
        is exactly the string the design prints. id/points are PHASE 2 DEV additions
        -- id lets the Services page redeem a specific service for loyalty points
        (see bsi.salon.service.bsi_loyalty_points), points is what that costs, 0
        meaning this service is never offered for points on the site.

        description/price_amount are PHASE 3 DEV additions for the booking
        wizard's own Service step: price_amount is the numeric price
        (bsi_get_effective_price) needed for real total/discount maths there,
        since the design's own price/duration strings are display-only.
        """
        services = self.env['bsi.salon.service'].sudo().search(
            [('bsi_is_custom_look', '=', False)], order='sequence, id')
        data = {key: [] for key in _SPA_CATEGORIES}
        for service in services:
            key = _CATEGORY_MAP.get(service.bsi_category)
            if not key:
                continue
            data[key].append({
                'id': service.id,
                'name': service.name,
                'duration': service.bsi_duration or '',
                'price': service.bsi_price or '',
                # Only a service switched on for points on the website carries them
                # here (see bsi.salon.service.bsi_loyalty_website); 0 hides the points.
                'points': (service.bsi_loyalty_points or 0) if service._bsi_points_on_website() else 0,
                'description': service.bsi_description or '',
                'price_amount': service._bsi_get_effective_price(),
            })
        # An empty category would render an empty pill panel.
        return {key: rows for key, rows in data.items() if rows}

    @api.model
    def _bsi_stylists(self):
        """STYLISTS: [{id, location_id, name, specialty, cat, years, rating, city, open, bio, skills}]

        `id` and `location_id` are extra -- the design's own stylist cards only
        ever used the array index and a plain city-name string. Booking from a
        stylist's profile (see enrich_patches.STYLIST_BOOK_DST) needs their
        real bsi.salon.team.member id for bsi_artist_id, and their real branch
        id to pre-fill the booking wizard's city/store with theirs specifically
        -- `city` alone can't do that: several branches can share one city.
        """
        members = self.env['bsi.salon.team.member'].sudo().search([], order='sequence, id')
        ratings = self._bsi_artist_ratings()
        this_year = fields.Date.context_today(self).year
        rows = []
        for member in members:
            years = 0
            if member.bsi_since_year and str(member.bsi_since_year).isdigit():
                years = max(0, this_year - int(member.bsi_since_year))
            rows.append({
                'id': member.id,
                'location_id': member.bsi_location_id.id or None,
                'name': member.name,
                'specialty': member.bsi_specialty or member.bsi_role or '',
                'cat': self._bsi_stylist_category(member.bsi_specialty, member.bsi_role),
                'years': years,
                'rating': ratings.get(member.id, 4.8),
                'city': member.bsi_location_id.bsi_city or '',
                'open': bool(member.bsi_is_available_now),
                # PHASE 2 DEV -- bio and skills now come off the record.
                'bio': member.bsi_bio or '',
                'skills': [
                    {'label': skill.name, 'pct': skill.bsi_percentage}
                    for skill in member.bsi_skill_ids
                ],
            })
        return rows

    @api.model
    def _bsi_artist_ratings(self):
        """Average customer rating per artist, for the stars on a stylist card.

        Aggregated in Python rather than through a grouped read: the row count is
        one per reviewed appointment, and the grouping API has changed shape
        across recent Odoo releases.
        """
        ratings = self.env['rating.rating'].sudo().search([
            ('bsi_artist_id', '!=', False),
            ('bsi_artist_rating', '>', 0),
        ])
        totals = {}
        for rating in ratings:
            artist_id = rating.bsi_artist_id.id
            running, count = totals.get(artist_id, (0.0, 0))
            totals[artist_id] = (running + rating.bsi_artist_rating, count + 1)
        return {
            artist_id: round(running / count, 1)
            for artist_id, (running, count) in totals.items() if count
        }

    @api.model
    def _bsi_tiers(self):
        """TIERS_DATA: [{id, name, monthly, yearly, popular, perks}]

        The design prints `yearly` as the full annual figure while the backend
        stores a per-month billed-annually rate, so multiply by twelve.
        """
        memberships = self.env['bsi.salon.membership'].sudo().search([], order='sequence, id')
        rows = []
        for tier in memberships:
            row = {
                # Ignored by the design's card markup; the purchase handler needs
                # it to resolve the tier's product.
                'id': tier.id,
                'name': tier.name,
                'monthly': int(round(tier.bsi_price_monthly or 0)),
                'yearly': int(round((tier.bsi_price_yearly or 0) * 12)),
                'perks': [line.strip() for line in (tier.bsi_perks or '').splitlines() if line.strip()],
            }
            if tier.bsi_featured:
                row['popular'] = True
            rows.append(row)
        return rows

    @api.model
    def _bsi_packages(self):
        """PACKAGES_DATA: [{id, name, description, price, price_amount, original_price,
        save_label, service_ids, service_names}]

        A package has no per-customer purchase/expiry/usage-tracking concept in the
        backend (unlike bsi.salon.membership.subscription for memberships) -- it is
        a static bundle catalogue item, always available to any customer while
        active and while the "Packages" feature itself is switched on
        (bsi_salon_backend.show_packages, the same setting
        bsi.salon.booking.mixin.bsi_packages_enabled reads). Picking one is
        exclusive with picking individual services (see
        bsi.salon.booking.mixin._bsi_onchange_package_common /
        _bsi_check_package_exclusive_common) -- service_ids here is exactly what
        the website has to auto-fill onto the booking when a package is applied,
        not a suggestion.
        """
        if self.env['ir.config_parameter'].sudo().get_param(
                'bsi_salon_backend.show_packages', 'True') != 'True':
            return []
        packages = self.env['bsi.salon.package'].sudo().search([], order='sequence, id')
        rows = []
        for package in packages:
            services = package.bsi_service_ids
            rows.append({
                'id': package.id,
                'name': package.name,
                'description': package.bsi_description or '',
                'price': package.bsi_bundle_price or '',
                'price_amount': package._bsi_get_effective_price(),
                'original_price': package.bsi_original_price or '',
                'save_label': package.bsi_save_label or '',
                'service_ids': services.ids,
                'service_names': services.mapped('name'),
            })
        return rows

    @api.model
    def _bsi_time_slots(self):
        """TIME_SLOTS plus the label -> id map the availability calls need.

        Only the opening time is handed to the design, because its slot caption
        map and its watch dial are both keyed on exactly that string.
        """
        slots = self.env['bsi.salon.time.slot'].sudo().search([], order='bsi_start_time, id')
        labels, lookup = [], {}
        for slot in slots:
            label = (slot.name or '').split('-')[0].strip()
            if not label or label in lookup:
                continue
            labels.append(label)
            lookup[label] = slot.id
        return labels, lookup


    # -- PHASE 2 DEV: datasets the design used to carry itself ------------

    @api.model
    def _bsi_city_identity(self):
        """CITY_IDENTITY: {slug: {motif, known, fact, skyA, skyB, landmark, landmarkFill}}

        The design falls back to a generic '_default' entry for a slug it does
        not recognise, so that key is kept even when every city is configured.
        """
        # The design does CITY_IDENTITY[slug] || CITY_IDENTITY._default and then
        # reads .skyA off the result, so dropping _default throws the moment any
        # lookup misses -- including the booking step before a city is chosen.
        identity = {
            '_default': {
                'motif': '\u2726',
                'known': 'An Enrich city',
                'fact': 'Same standards, same products, same care - '
                        'whichever branch you walk into.',
                'skyA': '#7a2748',
                'skyB': '#2c1020',
                'landmark': 'M30 100 V56 h140 v44 M30 56 h140 '
                            'M86 56 V42 a14 14 0 0 1 28 0 v14 M20 100 h160',
                'landmarkFill': '',
            },
        }
        for city in self.env['bsi.salon.city'].sudo().search([]):
            if not city.bsi_slug:
                continue
            fallback = identity['_default']
            identity[city.bsi_slug] = {
                'motif': city.bsi_motif or fallback['motif'],
                'known': city.bsi_known_for or fallback['known'],
                'fact': city.bsi_fact or fallback['fact'],
                'skyA': city.bsi_sky_a or fallback['skyA'],
                'skyB': city.bsi_sky_b or fallback['skyB'],
                'landmark': city.bsi_landmark_path or fallback['landmark'],
                'landmarkFill': city.bsi_landmark_fill_path or '',
            }
        return identity

    @api.model
    def _bsi_chair_styles(self):
        """CHAIR_STYLES: [{key, name, short, tagline, primary, accent, features}]"""
        rows = []
        for style in self.env['bsi.salon.chair.style'].sudo().search([]):
            rows.append({
                'key': style.bsi_key,
                'name': style.name,
                'short': style.bsi_short_name or style.name,
                'tagline': style.bsi_tagline or '',
                'primary': style.bsi_primary_color or '#141416',
                'accent': style.bsi_accent_color or '#8a2332',
                'features': [f.strip() for f in (style.bsi_features or '').splitlines() if f.strip()],
                'specs': [
                    {'k': 'UPHOLSTERY', 'v': style.bsi_upholstery or ''},
                    {'k': 'FRAME', 'v': style.bsi_frame or ''},
                    {'k': 'RECLINE', 'v': style.bsi_recline or ''},
                ],
            })
        return rows

    # A base64 string's leading characters are a deterministic encoding of the
    # raw file's magic bytes, so the format can be read off the text directly
    # without decoding it -- Odoo's Image field keeps whatever format was
    # uploaded (png/jpeg/webp/gif), it does not normalise to one.
    _BSI_IMAGE_MIME_PREFIXES = (
        ('iVBORw0KG', 'image/png'),
        ('/9j/', 'image/jpeg'),
        ('R0lGOD', 'image/gif'),
        ('UklGR', 'image/webp'),
    )

    @api.model
    def _bsi_image_data_uri(self, value):
        """An Image/Binary field's value as a data URI, or '' if unset."""
        if not value:
            return ''
        if isinstance(value, bytes):
            value = value.decode('ascii')
        mimetype = next(
            (mime for prefix, mime in self._BSI_IMAGE_MIME_PREFIXES if value.startswith(prefix)),
            'image/png')
        return 'data:%s;base64,%s' % (mimetype, value)

    @api.model
    def _bsi_transformations(self):
        """galleryItems: [{caption, service, beforeLabel, afterLabel, beforeSrc, afterSrc}]

        A photo uploaded straight into bsi_before_image/bsi_after_image is
        what the form actually invites staff to use, so it wins over the
        manually-typed URL fields -- those stay as a fallback for a transformation
        illustrated with an external/CDN image instead of an upload.
        """
        rows = []
        for item in self.env['bsi.salon.transformation'].sudo().search([]):
            rows.append({
                'caption': item.name,
                'service': item.bsi_service_id.name or '',
                'beforeLabel': item.bsi_before_label or 'Before',
                'afterLabel': item.bsi_after_label or 'After',
                'beforeSrc': self._bsi_image_data_uri(item.bsi_before_image) or item.bsi_before_url or '',
                'afterSrc': self._bsi_image_data_uri(item.bsi_after_image) or item.bsi_after_url or '',
            })
        return rows

    @api.model
    def _bsi_reviews(self):
        """REVIEWS: [{name, city, rating, service, stylist, text, photo}]

        `service` has to match one of the design's filter chips, so it comes from
        the review's own label rather than the linked service's name. `photo`
        prefers an uploaded bsi_photo the same way transformations prefer an
        uploaded image over a manually-typed URL (see _bsi_image_data_uri).
        """
        rows = []
        reviews = self.env['rating.rating'].sudo().search([
            ('res_model', '=', 'bsi.salon.booking.request'),
            ('rating', '>=', 1),
            ('consumed', '=', True),
        ])
        for review in reviews:
            rows.append({
                'name': review.partner_id.name or '',
                'city': '',
                'rating': review.rating,
                'photo': '',
                'service': '',
                'stylist': '',
                'text': review.feedback or '',
            })
        return rows

    @api.model
    def _bsi_about(self):
        """The About page: story, headline numbers, timeline, awards and values."""
        about = self.env['bsi.salon.about'].sudo().search([], limit=1)
        stats = [{'n': stat.bsi_value, 'l': stat.name} for stat in about.bsi_stat_ids]
        milestones = self.env['bsi.salon.milestone'].sudo().search([])
        awards = self.env['bsi.salon.award'].sudo().search([])
        values = self.env['bsi.salon.value'].sudo().search([])
        return {
            'stats': stats,
            'timeline': [
                {'year': m.bsi_year, 'title': m.name, 'body': m.bsi_body or '',
                 'delay': '%.1f' % (index * 0.15)}
                for index, m in enumerate(milestones)
            ],
            'awards': [
                {'year': a.bsi_year, 'title': a.name, 'delay': '%.1f' % (index * 0.15)}
                for index, a in enumerate(awards)
            ],
            'values': [
                {'icon': v.bsi_icon or '✦', 'title': v.name, 'body': v.bsi_description or ''}
                for v in values
            ],
        }

    @api.model
    def _bsi_about_page(self):
        """BSI_ABOUT: the About hero copy plus its numbers, timeline, awards and values.

        Every part falls back to the design's own copy when the backend holds
        nothing for it, so an empty database still renders the page as designed.
        """
        about = self.env['bsi.salon.about'].sudo().search([], limit=1)
        data = self._bsi_about()
        stats = data['stats']
        # The floating badge on the hero photo shows the "years" number, or else the first.
        badge = next((st for st in stats if 'year' in (st['l'] or '').lower()), stats[0] if stats else None)
        story1 = (about.bsi_story_1 or '').strip()
        story2 = (about.bsi_story_2 or '').strip()
        if not story1 and not story2:
            story1, story2 = _DESIGN_ABOUT_STORY
        return {
            'eyebrow': (about.bsi_eyebrow or '').strip() or 'OUR STORY',
            'title1': (about.bsi_title_line1 or '').strip() or 'Born from a love',
            'title2': (about.bsi_title_line2 or '').strip() or 'of the craft.',
            'story1': story1 or story2,
            'story2': story2 if story1 else '',
            'hasStory2': bool(story1 and story2),
            'badgeN': badge['n'] if badge else '25+',
            'badgeL': (badge['l'] if badge else 'Years of Excellence').upper(),
            'stats': stats,
            'timeline': data['timeline'],
            'awards': data['awards'],
            'values': [dict(v, delay='%.2f' % (i * 0.08)) for i, v in enumerate(data['values'])],
            'hasValues': bool(data['values']),
            'heroStats': self._bsi_hero_stats(about),
        }

    @api.model
    def _bsi_hero_stats(self, about):
        """heroStats: the home banner's count-up numbers, from the About page's
        Headline Numbers ticked "Show on Home" (first four). "4.8★" -> 4.8 with a
        "★" suffix and one decimal; a value with no number just shows as written."""
        stats = []
        for stat in about.bsi_stat_ids.filtered('bsi_show_home')[:4]:
            value = (stat.bsi_value or '').strip()
            match = re.match(r'^(\D*?)(\d+(?:\.\d+)?)(.*)$', value)
            if match:
                prefix, number, suffix = match.groups()
                dec = len(number.split('.')[1]) if '.' in number else 0
                stats.append({'n': value, 'prefix': prefix, 'num': float(number) if dec else int(number),
                              'suffix': suffix, 'dec': dec, 'l': stat.name})
            else:
                stats.append({'n': value, 'prefix': '', 'num': '', 'suffix': value, 'dec': 0, 'l': stat.name})
        return stats

    @api.model
    def _bsi_contact(self):
        """BSI_CONTACT: customer-care details for the Contact page and footer.

        Phone, email and social links come from the brand's main company, the
        hours from Salon settings; the branch/city counts and rating are live.
        """
        company = self.env['res.company'].sudo()._bsi_brand_company()
        ICP = self.env['ir.config_parameter'].sudo()

        def hours(key, default):
            try:
                return float(ICP.get_param(key) or default)
            except ValueError:
                return default

        def clock(value):
            h, m = int(value) % 24, int(round((value % 1) * 60)) % 60
            return '%02d:%02d' % (h, m)

        def clock12(value):
            h, m = int(value) % 24, int(round((value % 1) * 60)) % 60
            label = '%d%s' % (h % 12 or 12, (':%02d' % m) if m else '')
            return label + (' AM' if h < 12 else ' PM')

        open_at = hours('bsi_salon_backend.contact_open_time', 10.0)
        close_at = hours('bsi_salon_backend.contact_close_time', 20.0)
        days = (ICP.get_param('bsi_salon_backend.contact_days') or '').strip() or 'Mon–Sun'
        phone = (company.phone or '').strip() or '1800-266-5300'
        email = (company.email or '').strip() or 'care@enrichbeauty.com'
        digits = re.sub(r'[^\d+]', '', phone)
        locations = self.env['bsi.salon.location'].sudo().search([])
        rated = [loc.bsi_rating for loc in locations if loc.bsi_rating]
        cities = {loc.bsi_city_id.id or loc.bsi_city for loc in locations if loc.bsi_city_id or loc.bsi_city}
        address = ', '.join(filter(None, [
            company.street, company.street2, company.city,
            company.state_id.name, company.zip, company.country_id.name,
        ]))
        branches = len(locations)
        return {
            'company': company.name or 'Enrich',
            'phone': phone,
            'phoneHref': 'tel:' + (digits or phone),
            'tollFree': phone.replace(' ', '').startswith('1800'),
            'email': email,
            'emailHref': 'mailto:' + email,
            'days': days,
            'hours': '%s %s–%s' % (days, clock(open_at), clock(close_at)),
            'openLabel': clock12(open_at),
            'closeLabel': clock12(close_at),
            'openMin': int(round(open_at * 60)),
            'closeMin': int(round(close_at * 60)),
            'address': address,
            'website': company.website or '',
            'instagram': getattr(company, 'social_instagram', '') or '',
            'facebook': getattr(company, 'social_facebook', '') or '',
            'no_instagram': not getattr(company, 'social_instagram', ''),
            'no_facebook': not getattr(company, 'social_facebook', ''),
            'branches': branches,
            'branchesLabel': ('%d salon%s' % (branches, '' if branches == 1 else 's')) if branches else '100+ salons',
            'cities': len(cities),
            'citiesLabel': ('across %d cit%s' % (len(cities), 'y' if len(cities) == 1 else 'ies')) if cities else 'across India',
            'rating': ('%.1f' % (sum(rated) / len(rated))) if rated else '4.8',
        }

    @api.model
    def _bsi_addons(self):
        """ADDONS: [{id, key, icon, name, meta, price, mins}]"""
        return [{
            'id': addon.id,
            'key': addon.bsi_key or '',
            'icon': addon.bsi_icon or '✦',
            'name': addon.name,
            'meta': addon.bsi_meta or '',
            'price': int(round(addon.bsi_price or 0)),
            'mins': addon.bsi_duration_minutes or 0,
        } for addon in self.env['bsi.salon.addon'].sudo().search([])]

    @api.model
    def _bsi_colour_lab(self):
        """LEVELS, TONES and CONDITIONS, plus the pricing the maths applies."""
        config = self.env['bsi.salon.colour.lab.config'].sudo().search([], limit=1)
        levels = [{
            'level': level.bsi_level,
            'name': level.name,
            'tone': level.bsi_tone or '',
            'under': level.bsi_undertone or '',
        } for level in self.env['bsi.salon.colour.level'].sudo().search([])]
        tones = [{
            'id': tone.bsi_key,
            'name': tone.name,
            'dot': tone.bsi_dot_color or '',
            'toner': int(round(tone.bsi_toner_price or 0)),
            'note': tone.bsi_note or '',
            'extraRisk': int(round(tone.bsi_extra_risk or 0)),
        } for tone in self.env['bsi.salon.colour.tone'].sudo().search([])]
        conditions = [{
            'id': cond.bsi_key,
            'name': cond.name,
            'risk': int(round(cond.bsi_base_risk or 0)),
            'maxLift': cond.bsi_max_lift,
            'note': cond.bsi_note or '',
        } for cond in self.env['bsi.salon.hair.condition'].sudo().search([])]
        # The one price/time table both sides use: the Colour Lab's labPlan() reads it
        # as BSI_LAB_PRICING (see enrich_redesign.COLOUR_LAB_PATCHES) and a "Book a
        # colour consultation" booking is re-priced from it server-side (main.py's
        # _bsi_resolve_colour_lab) -- so the estimate shown is the price booked. An
        # unset (zero) figure falls back to the design's own number, same as `||` does
        # in the page.
        pricing = {
            key: (config[field] if config and config[field] else default)
            for key, field, default in _LAB_PRICING_FIELDS
        }
        pricing = {key: int(round(value)) if isinstance(value, float) else value
                   for key, value in pricing.items()}
        return levels, tones, conditions, pricing

    @api.model
    def _bsi_look_shades(self):
        """LOOK_SHADES: [{id, name, hair, light, deep, dot, surcharge}]"""
        return [{
            'id': shade.bsi_key,
            'name': shade.name,
            'hair': shade.bsi_hair_color or '',
            'light': shade.bsi_light_color or '',
            'deep': shade.bsi_deep_color or '',
            'dot': shade.bsi_dot_color or '',
            'surcharge': int(round(shade.bsi_surcharge or 0)),
        } for shade in self.env['bsi.salon.look.shade'].sudo().search([])]

    @api.model
    def _bsi_look_finishes(self):
        """BSI_LOOK_FINISHES: [{id, label, surcharge}]

        The finish picker's colours and click handling stay design-authored;
        only the catalogue of finishes and what each one adds to the price
        comes from here.
        """
        return [{
            'id': finish.bsi_key,
            'label': finish.name,
            'surcharge': int(round(finish.bsi_surcharge or 0)),
        } for finish in self.env['bsi.salon.look.finish'].sudo().search([])]

    @api.model
    def _bsi_look_lengths(self):
        """BSI_LOOK_LENGTHS: [{id, label, sub, surcharge, basePrice}]

        `basePrice` is set on at most one length -- the one the salon prices a
        look from -- and picked up separately as the configurator's starting
        price.
        """
        return [{
            'id': length.bsi_key,
            'label': length.name,
            'sub': ('+₹%d' % length.bsi_surcharge) if length.bsi_surcharge else '',
            'surcharge': int(round(length.bsi_surcharge or 0)),
            'basePrice': int(round(length.bsi_base_price or 0)),
        } for length in self.env['bsi.salon.look.length'].sudo().search([])]

    @api.model
    def _bsi_consult_questions(self):
        """Q: [{ask, opts: [{label, v, max}]}] -- the consultation simulator's script.

        A question with no answers is left out: the simulator can only move on by a
        button press, so an answer-less question used to leave the visitor stuck on it
        with nothing to click. `max` (extra) is the answer's own cap on how many
        treatments the recommended plan may hold (0 = no cap) -- what the design used
        to hard-code for the "t1"/"t2" time answers.
        """
        rows = []
        for question in self.env['bsi.salon.consult.question'].sudo().search([]):
            opts = [
                {'label': option.name, 'v': (option.bsi_value or '').strip().lower(),
                 'max': option.bsi_max_services or 0}
                for option in question.bsi_option_ids if (option.bsi_value or '').strip()
            ]
            if opts:
                rows.append({'ask': question.name, 'opts': opts})
        return rows

    @api.model
    def _bsi_consult_rules(self):
        """BSI_CONSULT_RULES: [{trigger, service_id, name, why, price, amount, mins}]

        The simulator matches every rule whose trigger is among the answers
        given, in the order a salon manager set on the rule -- not a fixed
        priority baked into the page. `amount`/`mins` are numeric so the plan's
        total and duration never have to be parsed back out of a display label,
        and `service_id` lets "Book this plan" pre-select the real services.
        Rules whose service is archived are skipped: the site must never
        recommend a treatment that can no longer be booked.
        """
        rows = []
        for rule in self.env['bsi.salon.consult.rule'].sudo().search([]):
            service = rule.bsi_service_id
            trigger = (rule.bsi_trigger_value or '').strip().lower()
            if not trigger or not service or not service.active:
                continue
            duration = re.search(r'\d+', service.bsi_duration or '')
            rows.append({
                'trigger': trigger,
                'service_id': service.id,
                'name': service.name or rule.name,
                'why': rule.bsi_reason or '',
                'price': service.bsi_price or '',
                'amount': service._bsi_get_effective_price() or 0.0,
                'mins': int(duration.group(0)) if duration else 45,
            })
        return rows

    @api.model
    def _bsi_gift_options(self):
        """Gift card amounts from loyalty programs; messages are no longer a custom model."""
        programs = self.env['loyalty.program'].sudo().search(
            [('program_type', '=', 'gift_card')], limit=1)
        amounts = []
        if programs:
            amounts = sorted(set(
                int(round(prod.lst_price))
                for prod in programs.mapped('mail_template_id')
                if False  # no denomination products without the old model
            ))
        messages = []
        return amounts, messages

    @api.model
    def _bsi_loyalty_rewards(self):
        """WALLET_REWARDS: [{id, name, cost, benefit, type, service_id, service_ids, service_names}]

        Uses base loyalty.reward (v19). reward_type is 'discount' or 'product'.
        """
        rewards = self.env['loyalty.reward'].sudo().search(
            [('program_id.name', '=', 'Salon Loyalty Points')])
        result = []
        for reward in rewards:
            if reward.reward_type == 'discount':
                benefit = '%s%% off' % int(reward.discount) if reward.discount_mode == 'percent' else '₹%s off' % int(reward.discount)
                service_ids = []
                service_names = []
            else:
                products = reward.reward_product_ids
                benefit = ', '.join(products.mapped('name')) if products else (reward.description or '')
                service_ids = []
                service_names = products.mapped('name') if products else []
            result.append({
                'id': reward.id,
                'name': reward.description or reward.display_name or '',
                'cost': int(reward.required_points),
                'benefit': benefit,
                'type': reward.reward_type,
                'service_id': None,
                'service_ids': service_ids,
                'service_names': service_names,
            })
        return result

    # -- payload ---------------------------------------------------------

    @api.model
    def _bsi_payload(self):
        """Everything the injector substitutes into the served page."""
        labels, lookup = self._bsi_time_slots()
        levels, tones, conditions, lab_pricing = self._bsi_colour_lab()
        gift_amounts, gift_messages = self._bsi_gift_options()
        look_lengths = self._bsi_look_lengths()
        look_base_price = next(
            (length['basePrice'] for length in look_lengths if length.get('basePrice')), 0)
        return {
            'cities': self._bsi_cities(),
            'services': self._bsi_services(),
            'stylists': self._bsi_stylists(),
            'tiers': self._bsi_tiers(),
            'packages': self._bsi_packages(),
            'slot_labels': labels,
            'slot_lookup': lookup,
            # PHASE 2 DEV
            'city_identity': self._bsi_city_identity(),
            'chair_styles': self._bsi_chair_styles(),
            'transformations': self._bsi_transformations(),
            'reviews': self._bsi_reviews(),
            'about': self._bsi_about(),
            'about_page': self._bsi_about_page(),
            'contact': self._bsi_contact(),
            'addons': self._bsi_addons(),
            'colour_levels': levels,
            'colour_tones': tones,
            'hair_conditions': conditions,
            'lab_pricing': lab_pricing,
            'look_shades': self._bsi_look_shades(),
            'look_finishes': self._bsi_look_finishes(),
            'look_lengths': look_lengths,
            'look_base_price': look_base_price,
            'consult_questions': self._bsi_consult_questions(),
            'consult_rules': self._bsi_consult_rules(),
            'gift_amounts': gift_amounts,
            'gift_messages': gift_messages,
            'loyalty_rewards': self._bsi_loyalty_rewards(),
        }

    @api.model
    def _bsi_cache_key(self):
        """Cheap version stamp: rebuild the page only when its data moves."""
        stamp = []
        for model in ('bsi.salon.location', 'bsi.salon.service', 'bsi.salon.team.member',
                      'bsi.salon.membership', 'bsi.salon.package', 'bsi.salon.time.slot',
                      # PHASE 2 DEV -- editing any of these must rebuild the page too
                      'bsi.salon.city', 'bsi.salon.chair.style', 'bsi.salon.team.skill',
                      'bsi.salon.transformation', 'rating.rating',
                      'bsi.salon.addon', 'bsi.salon.colour.level', 'bsi.salon.colour.tone',
                      'bsi.salon.hair.condition', 'bsi.salon.look.shade',
                      'bsi.salon.look.finish', 'bsi.salon.look.length',
                      'bsi.salon.consult.question', 'bsi.salon.consult.option',
                      'bsi.salon.consult.rule',
                      'loyalty.program', 'loyalty.reward',
                      'bsi.salon.about', 'bsi.salon.about.stat', 'bsi.salon.milestone',
                      'bsi.salon.award', 'bsi.salon.value'):
            records = self.env[model].sudo().search([], order='write_date desc', limit=1)
            stamp.append('%s:%s:%s' % (
                model,
                self.env[model].sudo().search_count([]),
                records.write_date or '-',
            ))
        # Include section-visibility config params so toggling them invalidates the cache.
        ICP = self.env['ir.config_parameter'].sudo()
        for cfg_key in (
            'bsi_salon_backend.show_transformation',
            'bsi_salon_backend.show_design_your_look',
            'bsi_salon_backend.show_colour_lab',
            # Baked into the page too (packages catalogue, BSI_FEATURES -- see
            # controllers/enrich_confirm.py), so a Settings flip must rebuild it.
            'bsi_salon_backend.show_packages',
            'bsi_salon_backend.show_membership',
            'bsi_salon_backend.show_loyalty_points',
            'bsi_salon_backend.show_gift_card',
        ):
            stamp.append('cfg:%s:%s' % (cfg_key, ICP.get_param(cfg_key, 'True')))
        # Contact page / footer details (see _bsi_contact).
        for cfg_key in ('bsi_salon_backend.contact_days', 'bsi_salon_backend.contact_open_time',
                        'bsi_salon_backend.contact_close_time'):
            stamp.append('cfg:%s:%s' % (cfg_key, ICP.get_param(cfg_key, '')))
        company = self.env['res.company'].sudo()._bsi_brand_company()
        stamp.append('company:%s:%s' % (company.id, company.write_date or '-'))
        return '|'.join(stamp)
