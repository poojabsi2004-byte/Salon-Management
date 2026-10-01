# -*- coding: utf-8 -*-
"""Stylist data (cards, portfolio, ratings) for the /salon site, added to bsi.enrich.data's payload.

Everything the Stylists page, the home spotlight carousel, the booking flow's artist
picker and the guest-reviews widget show for a stylist now comes from
bsi.salon.team.member / rating.rating, not from the design's own sample arrays:

- Only active, website-published team members are listed (bsi_website_published, new
  field on bsi.salon.team.member -- see that model).
- `photo` is a real data: URI built from the uploaded Photo (bsi_image) or, failing
  that, the Photo URL text field -- the same fallback order _bsi_transformations
  already uses for before/after photos (bsi_enrich_data._bsi_image_data_uri).
- `portfolio` is this artist's own "recent work" photos (bsi.salon.team.portfolio,
  new model -- see bsi_salon_team_member.py), each a {label, src} pair.
- `rating`/`rating_count` come straight off bsi_display_rating/bsi_rating_count,
  which the team member model itself computes from real rating.rating rows and
  only falls back to the website's own default-rating field (bsi_website_rating,
  itself defaulted to the design's old flat 4.8) when the artist has no reviews yet.
"""

from odoo import api, fields, models


class BsiEnrichStylists(models.AbstractModel):
    _inherit = 'bsi.enrich.data'

    # The design's four Stylists-page filter chips -- used when a team member has no
    # explicit bsi_website_category and the free-text heuristic has to guess instead.
    _BSI_WEBSITE_CATEGORY_LABELS = {
        'hair': 'Hair', 'makeup': 'Makeup', 'skin': 'Skin', 'nails': 'Nails',
    }

    @api.model
    def _bsi_stylists(self):
        """STYLISTS: [{id, location_id, name, specialty, cat, years, rating, rating_count,
        city, open, bio, skills, photo, highlights, portfolio}]

        `photo`/`portfolio` are PHASE DEV additions on top of the Phase 1/2 bridge shape:
        the site's STYLIST_PHOTOS/portfolio "recent work" arrays were the design's own
        fixed sample images, keyed only by the stylist's array position, so a stylist
        added or reordered in the backend could end up wearing someone else's photo. The
        site (see bsi_salon_web/controllers/enrich_stylists.py) uses `photo`/`portfolio`
        when set and only falls back to its own sample art when a stylist has neither.
        """
        members = self.env['bsi.salon.team.member'].sudo().search(
            [('bsi_website_published', '=', True)], order='sequence, id')
        this_year = fields.Date.context_today(self).year
        rows = []
        for member in members:
            years = 0
            if member.bsi_since_year and str(member.bsi_since_year).isdigit():
                years = max(0, this_year - int(member.bsi_since_year))
            cat = (self._BSI_WEBSITE_CATEGORY_LABELS.get(member.bsi_website_category)
                   or self._bsi_stylist_category(member.bsi_specialty, member.bsi_role))
            rows.append({
                'id': member.id,
                'location_id': member.bsi_location_id.id or None,
                'name': member.name,
                'specialty': member.bsi_specialty or member.bsi_role or '',
                'cat': cat,
                'years': years,
                'rating': member.bsi_display_rating,
                'rating_count': member.bsi_rating_count,
                'city': member.bsi_location_id.bsi_city or '',
                'open': bool(member.bsi_is_available_now),
                'bio': member.bsi_bio or '',
                'skills': [
                    {'label': skill.name, 'pct': skill.bsi_percentage}
                    for skill in member.bsi_skill_ids
                ],
                'photo': (self._bsi_image_data_uri(member.bsi_image) or member.bsi_image_url or ''),
                'highlights': [
                    tag.strip() for tag in (member.bsi_highlights or '').split(',') if tag.strip()
                ],
                'portfolio': [
                    {'label': item.name, 'src': self._bsi_image_data_uri(item.bsi_image) or ''}
                    for item in member.bsi_portfolio_item_ids if item.bsi_image
                ],
            })
        return rows

    @api.model
    def _bsi_reviews(self):
        """REVIEWS: as the base bridge builds it, with `stylist` filled in.

        The base _bsi_reviews (bsi_enrich_data.py) always left `stylist` blank, so
        every real customer review showed "with " (no name) in the Reviews widget's
        "{{ t.city }} · with {{ t.stylist }}" line -- not a stylist concern there,
        but the one field in it that is, so it's filled in here rather than left for
        whichever module ends up owning city/service/photo on this same row.
        """
        rows = super()._bsi_reviews()
        reviews = self.env['rating.rating'].sudo().search([
            ('res_model', '=', 'bsi.salon.booking.request'),
            ('rating', '>=', 1),
            ('consumed', '=', True),
        ])
        for row, review in zip(rows, reviews):
            if review.bsi_artist_id:
                row['stylist'] = review.bsi_artist_id.name
        return rows

    @api.model
    def _bsi_cache_key(self):
        """Extend the bridge's cache key with the new per-stylist models.

        bsi.salon.team.member is already in the base stamp, but editing a *related*
        bsi.salon.team.portfolio row doesn't touch the member's own write_date, so a
        portfolio-only edit would otherwise keep serving the cached page.
        """
        key = super()._bsi_cache_key()
        Model = self.env['bsi.salon.team.portfolio'].sudo()
        latest = Model.search([], order='write_date desc', limit=1)
        return '%s|bsi.salon.team.portfolio:%s:%s' % (
            key, Model.search_count([]), latest.write_date or '-')
