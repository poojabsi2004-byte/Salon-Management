# -*- coding: utf-8 -*-
"""Home page banner, live strip and services marquee from backend data.

BSI_HERO (injected by controllers/enrich_hero.py) carries:
  * the banner copy edited on the About Page record's "Home Banner" tab
    (bsi_salon_backend/models/bsi_salon_home_hero.py), each part falling back to
    the design's own wording when left blank;
  * the services marquee: every active catalogue service in backend order;
  * the "LIVE right now" strip's four facts (also served at runtime by
    /salon/api/live_pulse, because the page itself is cached until catalogue
    data changes, while these move minute by minute).

The banner's count-up numbers stay on the About page's Headline Numbers
(heroStats); this only makes them honour each number's "Live Value".
"""

import re
from datetime import timedelta

import pytz

from odoo import api, fields, models

from odoo.addons.bsi_salon_backend.models.bsi_salon_home_hero import HERO_DEFAULTS

# The design's service strip, used only while the catalogue is empty.
_DESIGN_MARQUEE = (
    'Haircut & Style', 'Global Colour', 'Keratin Treatment', 'Hair Spa', 'Bridal Makeup',
    'HD Makeup', 'Nail Art', 'Classic Facial', 'Manicure', 'Pedicure', 'Threading', 'Blowout',
)

# The design's four live facts, used for any fact there is no data for.
_DESIGN_PULSE = (
    {'value': '17', 'label': 'chairs occupied across the city right now'},
    {'value': '3 min', 'label': 'wait at Satellite — your nearest branch'},
    {'value': '9', 'label': 'artists free in the next hour'},
    {'value': '42', 'label': 'appointments booked today'},
)

# The rotating lines' CSS animation is a fixed 12 s cycle of four 3 s windows.
_WORD_SLOTS = 4
_WORD_STEP = 3


class BsiEnrichHero(models.AbstractModel):
    _inherit = 'bsi.enrich.data'

    # -- Headline Numbers honour their "Live Value" -------------------------

    @api.model
    def _bsi_about(self):
        data = super()._bsi_about()
        about = self.env['bsi.salon.about'].sudo().search([], limit=1)
        if about.bsi_stat_ids:
            counts = about._bsi_live_counts()
            data['stats'] = [{'n': stat._bsi_display_value(counts), 'l': stat.name}
                             for stat in about.bsi_stat_ids]
        return data

    @api.model
    def _bsi_hero_stats(self, about):
        """heroStats as before (first four ticked "Show on Home"), but reading each
        number's live value when it follows one."""
        shown = about.bsi_stat_ids.filtered('bsi_show_home')[:4]
        counts = about._bsi_live_counts() if shown else {}
        stats = []
        for stat in shown:
            value = stat._bsi_display_value(counts)
            match = re.match(r'^(\D*?)(\d+(?:\.\d+)?)(.*)$', value)
            if match:
                prefix, number, suffix = match.groups()
                dec = len(number.split('.')[1]) if '.' in number else 0
                stats.append({'n': value, 'prefix': prefix, 'num': float(number) if dec else int(number),
                              'suffix': suffix, 'dec': dec, 'l': stat.name})
            else:
                stats.append({'n': value, 'prefix': '', 'num': '', 'suffix': value, 'dec': 0, 'l': stat.name})
        return stats

    # -- banner copy + marquee ---------------------------------------------

    @api.model
    def _bsi_hero_marquee(self):
        """Active catalogue services, in backend order, each name once. Per-booking
        "custom look" / consultation services are not catalogue entries."""
        names, seen = [], set()
        for service in self.env['bsi.salon.service'].sudo().search(
                [('bsi_is_custom_look', '=', False)], order='sequence, id'):
            name = (service.name or '').strip()
            if name and name.lower() not in seen:
                seen.add(name.lower())
                names.append(name)
        return names

    @api.model
    def _bsi_hero(self):
        about = self.env['bsi.salon.about'].sudo().search([], limit=1)
        counts = about._bsi_live_counts()

        def text(value, default):
            return (value or '').strip() or default

        badge = text(about.bsi_hero_badge, HERO_DEFAULTS['badge'])
        branches = counts['branches']
        if branches:
            badge = badge.replace('{branches} LOCATIONS', '%d LOCATION%s' % (branches, '' if branches == 1 else 'S'))
        badge = badge.replace('{branches}', str(branches) if branches else '100+')
        badge = badge.replace('{cities}', str(counts['cities']) if counts['cities'] else '')

        lines = [line.strip() for line in (about.bsi_hero_words or '').splitlines() if line.strip()]
        lines = lines[:_WORD_SLOTS] or list(HERO_DEFAULTS['words'])
        # Fill all four animation windows, repeating a shorter list, so the line
        # under the headline is never blank for part of the cycle.
        words = [{'label': lines[i % len(lines)], 'delay': i * _WORD_STEP} for i in range(_WORD_SLOTS)]

        marquee, marquee_dur = self._bsi_hero_marquee_loop(self._bsi_hero_marquee() or list(_DESIGN_MARQUEE))
        return {
            'badge': badge,
            'title1': text(about.bsi_hero_title_line1, HERO_DEFAULTS['title1']),
            'title2': text(about.bsi_hero_title_line2, HERO_DEFAULTS['title2']),
            'bookLabel': text(about.bsi_hero_book_label, HERO_DEFAULTS['book']),
            'storesLabel': text(about.bsi_hero_stores_label, HERO_DEFAULTS['stores']),
            'words': words,
            'marquee': marquee,
            'marqueeDur': marquee_dur,
            'pulse': self._bsi_live_pulse(),
        }

    @api.model
    def _bsi_hero_marquee_loop(self, names):
        """One lap of the marquee (the page doubles it for the seamless loop) plus its
        duration. A short catalogue is repeated until a lap is at least as wide as the
        design's twelve names, so the strip never shows a gap on a wide screen; the
        duration scales with the lap's width so it scrolls at the design's speed
        (28 s for the design's lap)."""
        def width(items):
            # ~chars of Playfair 17px, plus the "✦" and the 44px gap after each name.
            return sum(len(name) + 7.5 for name in items)

        design = width(_DESIGN_MARQUEE)
        lap = list(names)
        while width(lap) < design:
            lap += names
        return lap, round(28 * width(lap) / design, 2)

    # -- live strip -----------------------------------------------------------

    @api.model
    def _bsi_salon_tz(self):
        tz = (self.env.ref('base.user_admin', raise_if_not_found=False) or self.env.user).sudo().tz
        tz = tz or self.env.company.partner_id.tz or 'Asia/Kolkata'
        try:
            return pytz.timezone(tz)
        except pytz.UnknownTimeZoneError:
            return pytz.timezone('Asia/Kolkata')

    @api.model
    def _bsi_live_pulse(self):
        """The four "LIVE right now" facts, in the design's order:
        chairs in use now, the shortest branch wait, stylists free in the next hour
        and appointments booked for today."""
        now = fields.Datetime.now()
        today = pytz.utc.localize(now).astimezone(self._bsi_salon_tz()).date()
        Appointment = self.env['bsi.salon.booking.request'].sudo()
        todays = Appointment.search([('bsi_preferred_date', '=', today),
                                     ('bsi_state', '!=', 'cancelled')])
        facts = [dict(f) for f in _DESIGN_PULSE]

        # 1. Chairs in use: started, unpaused visits today (the dashboard's "in use"
        #    rule); a visit with no chair assigned still occupies one seat.
        live = todays.filtered(lambda a: a.bsi_state == 'started' and not a.bsi_is_paused)
        chairs = len(live.mapped('bsi_chair_ids')) + len(live.filtered(lambda a: not a.bsi_chair_ids))
        facts[0] = {'value': str(chairs),
                    'label': 'chair%s occupied across the city right now' % ('' if chairs == 1 else 's')}

        # 2. Shortest current wait over all branches (0 = walk-ins welcome).
        branch = self.env['bsi.salon.location'].sudo().search(
            [], order='bsi_wait_minutes, sequence, id', limit=1)
        if branch:
            wait = int(branch.bsi_wait_minutes or 0)
            facts[1] = ({'value': '%d min' % wait, 'label': 'wait at %s — the shortest right now' % branch.name}
                        if wait else
                        {'value': 'No wait', 'label': 'at %s — walk-ins welcome right now' % branch.name})

        # 3. Stylists free in the next hour: active team members not in a visit now
        #    and not booked to start within the hour.
        staff = self.env['bsi.salon.team.member'].sudo().search([])
        if staff:
            soon = now + timedelta(hours=1)
            busy = todays.filtered(lambda a: a.bsi_state == 'started' or (
                a.bsi_state == 'draft' and a.bsi_calendar_start and a.bsi_calendar_start < soon
                and (a.bsi_calendar_stop or a.bsi_calendar_start) > now))
            free = len(staff - busy.mapped('bsi_artist_id'))
            facts[2] = {'value': str(free),
                        'label': 'artist%s free in the next hour' % ('' if free == 1 else 's')}

        # 4. Appointments for today: confirmed appointments plus website booking
        #    requests not yet turned into one.
        requests = self.env['crm.lead'].sudo().search_count([
            ('type', '=', 'opportunity'), ('bsi_preferred_date', '=', today),
            ('bsi_appointment_id', '=', False)])
        booked = len(todays) + requests
        facts[3] = {'value': str(booked),
                    'label': 'appointment%s booked today' % ('' if booked == 1 else 's')}
        return facts

    # -- payload --------------------------------------------------------------

    def _bsi_payload(self):
        data = super()._bsi_payload()
        data['hero'] = self._bsi_hero()
        return data
