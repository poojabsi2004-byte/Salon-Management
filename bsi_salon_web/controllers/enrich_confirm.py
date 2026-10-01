# -*- coding: utf-8 -*-
"""Booking wizard -- Confirm step v2, guest contact details, toasts, feature toggles.

Applied LAST by BsiSalonWeb._build_site (after enrich_hero / enrich_loyalty), so
every anchor below matches the fully patched template, never the raw export.

What lives here
---------------
* ``window.bsiToast(message, type)`` -- one site-wide, on-brand notification
  helper ('success' | 'error' | 'info'), stacked, auto-dismissing, aria-live.
  Other patches (e.g. enrich_loyalty) may call it; it is defined at the top of
  the x-dc script so it exists before any component code runs.
* The Confirm step (step 6) and the "Appointment pass" after it, re-laid out
  with class-based markup (styles in static/src/css/bsi_confirm_v2.css). The
  Perks & payment list itself is left exactly as the earlier patches render it
  (only wrapped), so loyalty/gift-card logic owned elsewhere keeps working.
* "Your details" -- a signed-in customer's own name / mobile / email, read-only
  from their account (a mobile can be added when the account has none), stored
  on the crm.lead by /salon/api/booking via resolve_contact below. Booking needs
  an account (sign-in gate owned by the Auth work): a guest sees the stable
  ``.bsi-cf-signin`` card in the same slot instead, and Confirm is guarded.
* Required data -- branch, date, time and at least one service / package / look
  / colour consultation -- checked in the page (checklist, inline + toast) and
  again server-side in /salon/api/booking.
* A state-diff toaster (componentDidUpdate) that announces whatever was just
  applied/removed: services, package, look, colour consultation, chair, time,
  membership discount, loyalty points, rewards, gift card, booking result.
* Backend Settings toggles (bsi_salon_backend.show_membership /
  show_loyalty_points / show_gift_card / show_packages) collapse their sections
  cleanly: the Perks card disappears when nothing in it can show, the service
  step's package column releases its grid track, and the Membership page drops
  the tiers / loyalty wallet / gift card blocks (and its nav entry when all
  three are off).
"""

import json
import logging
import re

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)

CSS_HREF = '/bsi_salon_web/static/src/css/bsi_confirm_v2.css?v=8'


# ---------------------------------------------------------------------------
# Server-side contact validation (used by main.py's /salon/api/booking)
# ---------------------------------------------------------------------------

_EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]{2,}$')
_PHONE_CHARS_RE = re.compile(r'^\+?[\d\s().\-]+$')
_CTRL_RE = re.compile(r'[\x00-\x1f\x7f]')


def _clean(value, limit):
    return _CTRL_RE.sub(' ', str(value or '')).strip()[:limit].strip()


def normalize_phone(raw):
    """(normalised phone, error). Indian mobiles are the default; +CC numbers pass."""
    raw = _clean(raw, 24)
    if not raw:
        return '', 'Please enter your mobile number.'
    if not _PHONE_CHARS_RE.match(raw):
        return '', 'Please enter a valid 10-digit mobile number.'
    digits = re.sub(r'\D', '', raw)
    national = None
    if len(digits) == 10:
        national = digits
    elif len(digits) == 12 and digits.startswith('91'):
        national = digits[2:]
    elif len(digits) == 11 and digits.startswith('0'):
        national = digits[1:]
    if national is not None:
        if not re.match(r'^[6-9]\d{9}$', national):
            return '', 'Please enter a valid 10-digit mobile number.'
        return '+91 %s %s' % (national[:5], national[5:]), None
    if raw.startswith('+') and 8 <= len(digits) <= 15:
        return '+' + digits, None
    return '', 'Please enter a valid 10-digit mobile number.'


def resolve_contact(partner, params):
    """The contact a website booking is recorded with -> (contact, errors).

    Booking requires a signed-in customer (the sign-in gate itself is enforced
    separately), so the contact is the customer's own account: name and email
    from their partner, shown read-only on the page and never taken from the
    request. The one exception is a mobile number when the account has none --
    the page offers an optional field for it; when given it is validated here
    (never trust the client) and stored on the lead, and crm.lead's own inverse
    then copies it onto the partner for next time.

    A guest (no partner) gets an empty contact and no errors: refusing guests is
    the sign-in gate's job, not this helper's.
    """
    params = params or {}
    contact = {'name': '', 'phone': '', 'email': ''}
    if not partner:
        return contact, {}
    errors = {}
    contact['name'] = _clean(partner.name, 120)
    contact['email'] = _clean(partner.email, 120)
    account_phone = _clean(partner.phone, 32)
    given = _clean(params.get('contact_phone'), 24)
    if account_phone:
        contact['phone'] = account_phone
    elif given:
        phone, error = normalize_phone(given)
        if error:
            errors['phone'] = error
        contact['phone'] = phone
    return contact, errors


# ---------------------------------------------------------------------------
# Runtime endpoint: the signed-in customer's own contact details
# ---------------------------------------------------------------------------

class BsiSalonConfirm(http.Controller):

    @http.route('/salon/api/booking_contact', type='jsonrpc', auth='public', website=True)
    def bsi_salon_api_booking_contact(self, **kwargs):
        """Prefill for the Confirm step's "Your details" card.

        Per-visitor, so it can never be baked into the cached page (see
        main._PAGE_CACHE) -- asked for at runtime instead.
        """
        user = request.env.user
        if user._is_public():
            return {'logged_in': False, 'name': '', 'email': '', 'phone': ''}
        partner = user.partner_id.sudo()
        return {
            'logged_in': True,
            'name': partner.name or user.name or '',
            'email': partner.email or '',
            'phone': partner.phone or '',
        }


# ---------------------------------------------------------------------------
# Page patches
# ---------------------------------------------------------------------------

def _features():
    ICP = request.env['ir.config_parameter'].sudo()

    def on(key):
        return ICP.get_param('bsi_salon_backend.show_%s' % key, 'True') == 'True'
    return {
        'membership': on('membership'),
        'loyalty': on('loyalty_points'),
        'gift_card': on('gift_card'),
        'packages': on('packages'),
    }


TOAST_JS = r"""
(function () {
  if (typeof window === 'undefined' || window.bsiToast) { return; }
  var ICONS = {
    success: '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6L9 17l-5-5"/></svg>',
    error: '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M12 8v5M12 16.5v.5"/><circle cx="12" cy="12" r="9.5"/></svg>',
    info: '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M12 11v6M12 7.5v.5"/><circle cx="12" cy="12" r="9.5"/></svg>'
  };
  var recent = {};
  var MAX = 4;
  function host() {
    var h = document.getElementById('bsi-toasts');
    if (!h || !document.body || !document.body.contains(h)) {
      h = document.createElement('section');
      h.id = 'bsi-toasts';
      h.className = 'bsi-toasts';
      h.setAttribute('aria-label', 'Notifications');
      h.setAttribute('aria-live', 'polite');
      h.setAttribute('aria-relevant', 'additions');
      (document.body || document.documentElement).appendChild(h);
    }
    return h;
  }
  function dismiss(el) {
    if (!el || el.__bsiGone) { return; }
    el.__bsiGone = true;
    clearTimeout(el.__bsiTimer);
    el.classList.remove('is-in');
    el.classList.add('is-out');
    setTimeout(function () { if (el.parentNode) { el.parentNode.removeChild(el); } }, 280);
  }
  window.bsiToast = function (message, type, opts) {
    message = String(message == null ? '' : message).replace(/\s+/g, ' ').trim();
    if (!message) { return null; }
    type = (type === 'success' || type === 'error' || type === 'info') ? type : 'info';
    var key = type + '|' + message, now = Date.now();
    if (recent[key] && now - recent[key] < 2500) { return null; }
    recent[key] = now;
    var h = host();
    var el = document.createElement('div');
    el.className = 'bsi-toast bsi-toast--' + type;
    el.setAttribute('role', type === 'error' ? 'alert' : 'status');
    el.innerHTML = '<span class="bsi-toast__ico" aria-hidden="true">' + ICONS[type] + '</span>'
      + '<span class="bsi-toast__msg"></span>'
      + '<button type="button" class="bsi-toast__x" aria-label="Dismiss notification">&times;</button>'
      + '<span class="bsi-toast__bar" aria-hidden="true"></span>';
    el.querySelector('.bsi-toast__msg').textContent = message;
    var ttl = (opts && opts.duration) || (type === 'error' ? 6500 : 4000);
    el.querySelector('.bsi-toast__bar').style.animationDuration = ttl + 'ms';
    el.querySelector('.bsi-toast__x').addEventListener('click', function () { dismiss(el); });
    var left = ttl, started = Date.now();
    var arm = function () { started = Date.now(); el.__bsiTimer = setTimeout(function () { dismiss(el); }, left); };
    var hold = function () { clearTimeout(el.__bsiTimer); left = Math.max(900, left - (Date.now() - started)); el.classList.add('is-held'); };
    var go = function () { el.classList.remove('is-held'); arm(); };
    el.addEventListener('mouseenter', hold); el.addEventListener('mouseleave', go);
    el.addEventListener('focusin', hold); el.addEventListener('focusout', go);
    h.appendChild(el);
    var live = h.querySelectorAll('.bsi-toast:not(.is-out)');
    for (var i = 0; i < live.length - MAX; i++) { dismiss(live[i]); }
    requestAnimationFrame(function () { requestAnimationFrame(function () { el.classList.add('is-in'); }); });
    arm();
    return { dismiss: function () { dismiss(el); } };
  };
})();
"""


# Class fields appended to the component (placed after confirmBooking / bsiRpc /
# bsiBookingParams / bsiFetchQuote exist, so they can be wrapped at construction).
LOGIC_JS = r"""
  // ── enrich_confirm: Confirm step v2 ─────────────────────────────────────
  bsiCf2Toast = (msg, type) => { try { if (window.bsiToast) { window.bsiToast(msg, type); } } catch (e) { /* never break the page */ } };
  bsiCf2Money = (n) => '₹' + Math.round(n || 0).toLocaleString('en-IN');
  bsiCf2Features = () => Object.assign({}, BSI_FEATURES, (this.state.bookingQuote && this.state.bookingQuote.features) || {});
  bsiCf2SignedIn = () => {
    const s = this.state;
    if (s.bsiAcct) { return !!s.bsiAcct.logged_in; }
    if (s.bookingQuote) { return !!s.bookingQuote.logged_in; }
    return !!s.userLoggedIn;
  };
  bsiCf2Contact = () => {
    const s = this.state; const a = s.bsiAcct || {};
    const acctIn = this.bsiCf2SignedIn();
    const acctPhone = String(a.phone || '').trim();
    return {
      acctIn, loaded: !!s.bsiAcct,
      name: String(a.name || s.userName || '').trim(),
      email: String(a.email || '').trim(),
      acctPhone,
      phone: acctPhone || String(s.bookingContactPhone || '').trim(),
      needsPhone: acctIn && !!s.bsiAcct && !acctPhone,
    };
  };
  bsiCf2PhoneError = (raw) => {
    const v = String(raw || '').trim();
    if (!v) { return 'Please enter your mobile number.'; }
    if (!/^\+?[\d\s().\-]+$/.test(v)) { return 'Please enter a valid 10-digit mobile number.'; }
    const d = v.replace(/\D/g, '');
    let nat = null;
    if (d.length === 10) { nat = d; } else if (d.length === 12 && d.indexOf('91') === 0) { nat = d.slice(2); } else if (d.length === 11 && d[0] === '0') { nat = d.slice(1); }
    if (nat !== null) { return /^[6-9]\d{9}$/.test(nat) ? '' : 'Please enter a valid 10-digit mobile number.'; }
    if (v[0] === '+' && d.length >= 8 && d.length <= 15) { return ''; }
    return 'Please enter a valid 10-digit mobile number.';
  };
  bsiCf2Check = () => {
    const s = this.state; const c = this.bsiCf2Contact();
    const srv = s.bsiCfServerErr || {};
    const errors = {};
    if (c.needsPhone && c.phone) { const pe = this.bsiCf2PhoneError(c.phone); if (pe) { errors.phone = pe; } }
    if (!errors.phone && srv.phone) { errors.phone = srv.phone; }
    const hasSvc = !!(s.bookingPackageId || (s.bookingServiceIds && s.bookingServiceIds.length) || s.bookingServiceId
      || s.bookingLookLength || s.bookingColourLab || s.rewardServiceId);
    const missing = [];
    if (!c.acctIn) { missing.push({ key: 'signin', short: 'sign in', msg: 'Please sign in to book your appointment.', field: 'bsi-cf-signin' }); }
    if (!s.booking || !s.booking.storeId) { missing.push({ key: 'branch', short: 'a branch', msg: 'Please choose a branch.', step: 2 }); }
    if (!hasSvc) { missing.push({ key: 'service', short: 'a service', msg: 'Please add at least one service.', step: 3 }); }
    if (!s.bookingDate) { missing.push({ key: 'date', short: 'a date', msg: 'Please choose a date.', step: 5 }); }
    // A chair and a time are optional -- the salon confirms both with the customer.
    if (errors.phone) { missing.push({ key: 'phone', short: 'a valid mobile number', msg: errors.phone, field: 'cf2-phone' }); }
    return { ok: !missing.length, errors, missing, hasSvc, contact: c };
  };
  bsiCf2OnPhone = (e) => {
    const v = e && e.target ? e.target.value : '';
    this.setState((s) => ({ bookingContactPhone: v, bsiCfServerErr: Object.assign({}, s.bsiCfServerErr || {}, { phone: '' }) }));
  };
  bsiCf2Focus = (id) => { setTimeout(() => { const el = document.getElementById(id); if (el) { try { el.scrollIntoView({ block: 'center', behavior: 'smooth' }); } catch (e) { el.scrollIntoView(); } try { el.focus({ preventScroll: true }); } catch (e) { el.focus(); } } }, 80); };
  bsiCf2Fix = (m) => { if (m.field) { this.setState({ bsiCfShowErr: true }); this.bsiCf2Focus(m.field); } else if (m.step) { this.bsiGoStep(m.step); } };
  bsiCf2LoadAcct = () => {
    if (this._bsiAcctReq) { return; }
    this._bsiAcctReq = true;
    this.bsiRpc('/salon/api/booking_contact', {}).then((res) => { if (res && typeof res === 'object') { this.setState({ bsiAcct: res }); } }).catch(() => { this._bsiAcctReq = false; });
  };
  _bsiCf2Setup = (() => {
    const origConfirm = this.confirmBooking;
    const origParams = this.bsiBookingParams;
    const origRpc = this.bsiRpc;
    this.bsiBookingParams = (ov) => {
      const p = origParams(ov);
      if (this._bsiCfSending) {
        const c = this.bsiCf2Contact();
        if (c.needsPhone && c.phone) { p.contact_phone = c.phone; }
      }
      return p;
    };
    this.bsiRpc = (url, params) => {
      const p = origRpc(url, params);
      if (url !== '/salon/api/booking') { return p; }
      return p.then((res) => {
        if (res && res.ok) { this.setState({ bsiLeadId: res.lead_id || null, bsiCfServerErr: {} }); }
        else if (res && res.fields && typeof res.fields === 'object') { this.setState({ bsiCfServerErr: res.fields, bsiCfShowErr: true }); }
        return res;
      });
    };
    this.confirmBooking = () => {
      if (this.state.bookingSubmitting) { return; }
      const v = this.bsiCf2Check();
      if (!v.ok) {
        this.setState({ bsiCfShowErr: true });
        const first = v.missing[0];
        this.bsiCf2Toast(v.missing.length === 1 ? first.msg : ('Almost there — please add ' + v.missing.map((m) => m.short).join(', ') + '.'), 'error');
        if (first.field) { this.bsiCf2Focus(first.field); } else { this.bsiCf2Focus('cf2-checks'); }
        return;
      }
      this._bsiCfSending = true;
      try { origConfirm(); } finally { this._bsiCfSending = false; }
    };
    return true;
  })();
  _bsiCfDiff = () => {
    const s = this.state; const p = this._bsiSnap;
    const q = s.bookingQuote || null;
    const svc = ((s.bookingServiceIds && s.bookingServiceIds.length) ? s.bookingServiceIds : (s.bookingServiceId ? [s.bookingServiceId] : [])).slice();
    const snap = {
      page: s.page, step: (s.booking && s.booking.step) || 1, conf: !!s.bookingConfirmed,
      svc, pkg: s.bookingPackageId || null, pkgName: s.bookingPackageName || '',
      look: s.bookingLookLength || null, lab: s.bookingColourLab ? (s.bookingColourLab.name || 'Colour consultation') : null,
      chairs: (s.selectedChairIds || []).slice(), time: s.selectedTime || null, date: s.bookingDate || null,
      q, qErr: s.bookingQuoteError || '', bErr: s.bookingError || '', store: (s.booking && s.booking.storeId) || null,
    };
    this._bsiSnap = snap;
    if (!p) { this.bsiCf2LoadAcct(); return; }
    const T = this.bsiCf2Toast; const money = this.bsiCf2Money;
    const all = [].concat.apply([], Object.keys(SERVICES_DATA).map((k) => SERVICES_DATA[k]));
    const nameOf = (id) => { const r = all.find((x) => x.id === id); return r ? r.name : 'Service'; };
    const when = () => (snap.date ? this.bsiDateLabel(snap.date) + (snap.time ? ' at ' : '') : '') + (snap.time || '');
    if (snap.conf && !p.conf) { T('Booking confirmed — see you ' + when() + '!', 'success'); this._bsiPerkSig = null; return; }
    if (snap.bErr && snap.bErr !== p.bErr) { T(typeof snap.bErr === 'string' ? snap.bErr : 'We could not confirm this booking. Please try again.', 'error'); }
    if (snap.qErr && snap.qErr !== p.qErr) { T(snap.qErr, 'error'); }
    if (snap.page !== 'booking' || snap.conf || p.conf) { if (snap.page !== 'booking') { this._bsiPerkSig = null; } return; }
    const entered = p.page !== 'booking';
    const reset = !entered && snap.step === 1 && p.step > 1 && !snap.svc.length;
    if (reset) { this._bsiPerkSig = null; return; }
    // what is being booked
    if (snap.look && !p.look) { T('Your custom look is on this booking', 'success'); }
    else if (!snap.look && p.look && !entered) { T('Custom look removed', 'info'); }
    if (snap.lab && !p.lab) { T('Colour consultation added to your booking', 'success'); }
    else if (!snap.lab && p.lab && !entered) { T('Colour consultation removed', 'info'); }
    if (snap.pkg && snap.pkg !== p.pkg) { T((snap.pkgName || 'Package') + ' applied', 'success'); }
    else if (!snap.pkg && p.pkg && !entered) { T((p.pkgName || 'Package') + ' removed', 'info'); }
    else if (!snap.pkg && !p.pkg) {
      // Services a loyalty reward adds/removes are announced by the reward's own toast (enrich_loyalty).
      const rewardSvc = [].concat(s.bookingRewardAddedSvc || []);
      const lastRw = [].concat(this._bsiLastRewardSvc || []);
      const rwTouched = (s.bookingRewardId || null) !== (this._bsiLastRewardId || null);
      const added = rwTouched ? [] : snap.svc.filter((id) => p.svc.indexOf(id) < 0 && rewardSvc.indexOf(id) < 0);
      const removed = (entered || rwTouched) ? [] : p.svc.filter((id) => snap.svc.indexOf(id) < 0 && rewardSvc.indexOf(id) < 0 && lastRw.indexOf(id) < 0);
      if (added.length === 1) { T(nameOf(added[0]) + (entered ? ' added to your booking' : ' added'), 'success'); }
      else if (added.length > 1) { T(added.length + ' services added', 'success'); }
      if (removed.length === 1) { T(nameOf(removed[0]) + ' removed', 'info'); }
      else if (removed.length > 1) { T(removed.length + ' services removed', 'info'); }
      this._bsiLastRewardSvc = rewardSvc;
    }
    this._bsiLastRewardId = s.bookingRewardId || null;
    // where & when
    if (!entered && snap.store === p.store) {
      const addC = snap.chairs.filter((id) => p.chairs.indexOf(id) < 0);
      const remC = p.chairs.filter((id) => snap.chairs.indexOf(id) < 0);
      if (addC.length) { T('Chair ' + addC.join(', ') + ' selected', 'success'); }
      else if (remC.length && snap.chairs.length) { T('Chair ' + remC.join(', ') + ' deselected', 'info'); }
    }
    if (snap.time && snap.time !== p.time) { T(when() + ' selected', 'success'); }
    // perks, from the priced quote
    if (q && q !== p.q) {
      const L = q.loyalty || {}; const G = q.gift_card || {}; const RW = q.reward || {}; const SP = q.service_points || {}; const M = q.membership || {};
      const sig = { m: M.active ? Math.round(M.percent || 0) : 0, mTier: M.tier || '', pts: L.points || 0, ptsAmt: L.amount || 0,
        gift: G.code || '', giftAmt: G.applied || 0, rw: RW.id || null, rwName: RW.benefit || RW.name || '', rwAmt: RW.amount || 0,
        sp: SP.points || 0, spAmt: SP.amount || 0, promo: (q.promo || {}).code || '', promoAmt: (q.promo || {}).amount || 0 };
      const o = this._bsiPerkSig;
      if (!o) {
        const bits = [];
        if (sig.m) { bits.push((sig.mTier ? sig.mTier + ' membership ' : 'Membership ') + sig.m + '% off'); }
        if (sig.rw) { bits.push('reward: ' + sig.rwName); }
        if (sig.sp) { bits.push(sig.sp + ' service pts'); }
        if (sig.pts) { bits.push(sig.pts + ' loyalty pts'); }
        if (sig.gift) { bits.push('gift card ' + sig.gift); }
        if (bits.length) { T('Applied automatically: ' + bits.join(' · '), 'success'); }
      } else {
        if (sig.m && !o.m) { T('Membership discount applied · ' + sig.m + '% off', 'success'); }
        // Rewards and service points: toasted by their own handlers (enrich_loyalty).
        if (sig.pts !== o.pts) {
          if (sig.pts && !o.pts) { T(sig.pts.toLocaleString('en-IN') + ' loyalty points applied · ' + money(sig.ptsAmt) + ' off', 'success'); }
          else if (!sig.pts && o.pts) { T('Loyalty points removed', 'info'); }
          else { T('Now using ' + sig.pts.toLocaleString('en-IN') + ' points · ' + money(sig.ptsAmt) + ' off', 'success'); }
        }
        if (sig.gift !== o.gift) { if (sig.gift) { T('Gift card ' + sig.gift + ' applied' + (sig.giftAmt ? ' · ' + money(sig.giftAmt) + ' off' : ''), 'success'); } else if (o.gift) { T('Gift card removed', 'info'); } }
        if (sig.promo !== o.promo) { if (sig.promo) { T('Discount code ' + sig.promo + ' applied · ' + money(sig.promoAmt) + ' off', 'success'); } else if (o.promo) { T('Discount code removed', 'info'); } }
      }
      this._bsiPerkSig = sig;
      const P = p.q || {};
      const le = L.error || ''; const ge = G.error || '';
      if (le && le !== ((P.loyalty || {}).error || '')) { T(le, 'error'); }
      if (ge && ge !== ((P.gift_card || {}).error || '')) { T(ge, 'error'); }
      const pe = (q.promo || {}).error || '';
      if (pe && pe !== ge && pe !== ((P.promo || {}).error || '')) { T(pe, 'error'); }
    }
  };
  bsiCf2Vals = () => {
    const s = this.state;
    const q = s.bookingQuote || null;
    const F = this.bsiCf2Features();
    const v = this.bsiCf2Check();
    const c = v.contact;
    const show = !!s.bsiCfShowErr;
    const loggedIn = c.acctIn;
    const busy = !!s.bookingSubmitting || !!s.bookingQuoteLoading;
    const phoneErr = show ? (v.errors.phone || '') : '';
    const d = s.bookingDate ? new Date(s.bookingDate + 'T00:00:00') : null;
    const MON = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC'];
    const DOW = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
    const rel = d ? (() => { const t = new Date(); t.setHours(0, 0, 0, 0); const n = Math.round((d - t) / 86400000); return n === 0 ? 'Today' : (n === 1 ? 'Tomorrow' : 'In ' + n + ' days'); })() : '';
    const miss = {}; v.missing.forEach((m) => { miss[m.key] = m; });
    const detailsOk = !miss.signin && !miss.phone;
    const chk = (label, ok, value, m, fixLabel) => ({ label, value, cls: 'cf2-ck' + (ok ? ' is-ok' : (show ? ' is-bad' : ' is-todo')),
      canFix: !ok && !!m, fixLabel: fixLabel || 'Add', onFix: m ? (() => this.bsiCf2Fix(m)) : (() => {}) });
    const svcCount = s.bookingPackageId ? 1 : ((s.bookingServiceIds || []).length + (s.bookingLookLength ? 1 : 0) + ((s.bookingColourLab && !s.bookingLookLength) ? 1 : 0));
    const firstDetail = miss.signin || miss.phone;
    const checks = [
      chk('Date & time', !miss.date, s.bookingDate ? (this.bsiDateLabel(s.bookingDate) + ' · ' + (s.selectedTime || 'Any time')) : 'Not chosen yet', miss.date, 'Choose'),
      chk('Branch', !miss.branch, miss.branch ? 'Not chosen yet' : '', miss.branch, 'Choose'),
      chk('Services', !miss.service, miss.service ? 'Nothing added yet' : (svcCount > 1 ? svcCount + ' selected' : '1 selected'), miss.service, 'Add'),
      chk('Your details', detailsOk, detailsOk ? [c.name, c.phone || c.email].filter(Boolean).join(' · ') : (miss.signin ? 'Sign in to book' : firstDetail.msg), firstDetail, miss.signin ? 'Sign in' : 'Fix'),
    ];
    const store = (() => { const city = CITIES.find((x) => x.id === (s.booking || {}).cityId); const b = city ? (city.branches || []).find((x) => x.id === (s.booking || {}).storeId) : null; return b ? b.name : ''; })();
    checks[1].value = miss.branch ? 'Not chosen yet' : store;
    const readyN = checks.filter((x) => x.cls.indexOf('is-ok') >= 0).length;
    const mins = (() => {
      if (s.bookingPackageId) { return 0; }
      const all = [].concat.apply([], Object.keys(SERVICES_DATA).map((k) => SERVICES_DATA[k]));
      let t = 0; (s.bookingServiceIds || []).forEach((id) => { const r = all.find((x) => x.id === id); const n = r ? parseInt(r.duration, 10) : NaN; if (!isNaN(n)) { t += n; } });
      if (s.bookingColourLab && !s.bookingLookLength && s.bookingColourLab.minutes) { t += parseInt(s.bookingColourLab.minutes, 10) || 0; }
      return t;
    })();
    const dur = mins ? ((mins >= 60 ? Math.floor(mins / 60) + ' h' : '') + (mins % 60 ? ((mins >= 60 ? ' ' : '') + (mins % 60) + ' min') : '')) : '';
    const guestName = c.name;
    const first = guestName.split(/\s+/)[0] || '';
    const ref = s.bsiLeadId ? ('ENR-' + String(s.bsiLeadId).padStart(6, '0'))
      : ('ENR-' + (1000 + (s.selectedChairIds || []).reduce((a, b) => a + b, 0) * 37 + (s.chairs || []).length));
    const perksOn = F.membership !== false || !!F.loyalty || !!F.gift_card;
    const redeemOn = !!F.loyalty || !!F.gift_card;
    const phoneShown = c.phone;
    return {
      cf2ShowPerks: perksOn && loggedIn,
      cf2PerksSub: (loggedIn && redeemOn) ? 'Your best perks are applied for you — change them any time before you confirm.'
        : (redeemOn ? 'Members, loyalty points and gift cards all count here.' : 'Member discounts are applied automatically.'),
      cf2ShowPerkNote: redeemOn,
      cf2SignedIn: loggedIn, cf2GuestMode: !loggedIn,
      cf2DetailsSub: 'From your Enrich account — the salon uses these to confirm your slot.',
      cf2Contact: {
        name: c.name || '—', email: c.email || 'No email on your account',
        phone: c.phone || '', acctPhone: c.acctPhone || '',
        hasPhone: !!c.acctPhone, needsPhone: !!c.needsPhone,
        phoneCls: 'cf2-field' + (phoneErr ? ' is-bad' : '') + (c.phone && !v.errors.phone ? ' is-ok' : ''),
        phoneErr, phoneInvalid: phoneErr ? 'true' : 'false',
      },
      cf2OnPhone: this.bsiCf2OnPhone,
      cf2SigninHref: '/web/login?redirect=' + encodeURIComponent('/salon/booking'),
      cf2Checks: checks,
      cf2ReadyCount: readyN + ' of 4 ready',
      cf2ProgressW: Math.round(readyN / 4 * 100) + '%',
      cf2ProgressCls: 'cf2-progress' + (readyN === 4 ? ' is-done' : ''),
      cf2ProgressHint: readyN === 4 ? 'Everything looks good' : 'Complete the steps below',
      cf2ShowMissing: show && !v.ok,
      cf2MissingText: v.ok ? '' : ('Still needed: ' + v.missing.map((m) => m.short).join(', ') + '.'),
      cfConfirmDisabled: busy,
      cfConfirmState: busy ? 'is-busy' : (v.ok ? 'is-ready' : 'is-blocked'),
      cf2AriaDisabled: (!v.ok || busy) ? 'true' : 'false',
      confirmBtnLabel: s.bookingSubmitting ? 'Confirming…' : (v.ok ? 'Confirm booking' : 'Confirm booking'),
      cf2TotalCls: 'cf-total-v' + (s.bookingQuoteLoading ? ' is-loading' : ''),
      cf2Mon: d ? MON[d.getMonth()] : '—', cf2DayNum: d ? String(d.getDate()) : '?', cf2Dow: d ? DOW[d.getDay()].slice(0, 3).toUpperCase() : '',
      cf2TimeOnly: s.selectedTime || 'Any time',
      cf2DateLong: d ? (DOW[d.getDay()] + ', ' + d.getDate() + ' ' + d.toLocaleDateString('en-GB', { month: 'long' }) + (rel ? ' · ' + rel : '')) : 'No date chosen yet',
      cf2ChairLabel: (s.selectedChairIds || []).length ? ('Chair ' + s.selectedChairIds.join(', ')) : 'Any free chair',
      cf2HasDuration: !!dur, cf2Duration: dur ? ('About ' + dur) : '',
      cf2SvcCount: String(svcCount || 1),
      cf2GuestName: guestName || 'Guest',
      cf2GuestPhone: phoneShown || c.email || '—',
      cf2GuestPhoneK: phoneShown ? 'MOBILE' : 'CONTACT',
      cf2Ref: ref,
      cf2DoneTitle: first ? ('You’re booked, ' + first + '!') : 'You’re booked!',
      cf2DoneLead: 'Booking ' + ref + ' is with the ' + (store || 'salon') + ' team. Keep this pass handy — it’s your check-in at reception.',
      cf2NextCall: phoneShown ? ('The salon will call ' + phoneShown + ' shortly to confirm your slot.') : ('The salon will contact you' + (c.email ? ' at ' + c.email : '') + ' to confirm your slot.'),
      cf2NextPay: 'Pay after your service — cash, card or UPI.',
      // Membership page (backend toggles -- see enrich_confirm.apply)
      bsiMbTitle: BSI_FEATURES.membership ? 'Enrich Membership' : 'Enrich Rewards',
      bsiMbSub: BSI_FEATURES.membership ? 'One membership, every branch, every city.'
        : ((BSI_FEATURES.loyalty && BSI_FEATURES.gift_card) ? 'Loyalty points and gift cards, valid at every branch.'
          : (BSI_FEATURES.loyalty ? 'Earn points on every visit, at every branch.'
            : (BSI_FEATURES.gift_card ? 'Gift cards valid at every branch, in every city.' : 'Rewards are not available online right now.'))),
    };
  };
"""


# ── markup ────────────────────────────────────────────────────────────────

_ICO = '<svg sc-camel-view-box="0 0 24 24" style="fill:none;stroke:currentColor;stroke-width:1.8;stroke-linecap:round;stroke-linejoin:round;"><path d="%s"></path></svg>'
_PIN = _ICO % 'M12 21s-7-6.2-7-11.5A7 7 0 0 1 19 9.5C19 14.8 12 21 12 21zM12 12a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5z'
_CHAIR = _ICO % 'M7 11V5a2 2 0 0 1 2-2h6a2 2 0 0 1 2 2v6M5 11h14v4H5zM7 15v6M17 15v6M12 15v6'
_USER = _ICO % 'M20 21a8 8 0 0 0-16 0M12 13a5 5 0 1 0 0-10 5 5 0 0 0 0 10z'
_CLOCK = _ICO % 'M12 7v5l3 2M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0z'
_CHECK = _ICO % 'M20 6L9 17l-5-5'
_LOCK = _ICO % 'M6 11h12v10H6zM8.5 11V7.5a3.5 3.5 0 0 1 7 0V11'
_SHIELD = _ICO % 'M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6l8-3z'

HEAD_START = '<div class="cf">\n            <div class="cf-head">'
HEAD_END = '<div class="cf-grid">'
HEAD_NEW = (
    '<div class="cf cf2">\n'
    '            <div class="cf2-head">\n'
    '              <div class="cf2-head-main">\n'
    '                <div class="cf-eyebrow">Step 6 of 6 · Final check</div>\n'
    '                <h2 class="cf-title">{{ cfTitle }}</h2>\n'
    '                <p class="cf-lead">Give your appointment a last look, then confirm. Nothing is charged online &mdash; you pay at the salon.</p>\n'
    '              </div>\n'
    '              <div class="{{ cf2ProgressCls }}">\n'
    '                <div class="cf2-progress-top"><b>{{ cf2ReadyCount }}</b><span>{{ cf2ProgressHint }}</span></div>\n'
    '                <div class="cf2-progress-bar"><span style="width:{{ cf2ProgressW }};"></span></div>\n'
    '              </div>\n'
    '            </div>\n'
    '            <div class="cf-grid cf2-grid">'
)

APPT_START = '<section class="cf-card cf-appt">'
APPT_END = '</section>'
APPT_NEW = (
    '<section class="cf-card cf2-appt" aria-label="Your appointment">\n'
    '                  <div class="cf2-slot">\n'
    '                    <div class="cf2-cal" aria-hidden="true"><span class="cf2-cal-m">{{ cf2Mon }}</span><span class="cf2-cal-d">{{ cf2DayNum }}</span><span class="cf2-cal-w">{{ cf2Dow }}</span></div>\n'
    '                    <div class="cf2-slot-body">\n'
    '                      <div class="cf2-kicker">Your appointment</div>\n'
    '                      <div class="cf2-slot-time">{{ cf2TimeOnly }}</div>\n'
    '                      <div class="cf2-slot-date">{{ cf2DateLong }}</div>\n'
    '                    </div>\n'
    '                    <button type="button" class="cf2-slot-edit" sc-camel-on-click="{{ cfEditTime }}">Change date &amp; time</button>\n'
    '                  </div>\n'
    '                  <div class="cf2-facts">\n'
    '                    <div class="cf2-fact"><span class="cf2-fact-ico">' + _PIN + '</span><div class="cf2-fact-body"><div class="cf2-fact-k">Branch</div><div class="cf2-fact-v">{{ summaryStore }}</div><div class="cf2-fact-s">{{ summaryCity }}</div></div><button type="button" class="cf-edit" sc-camel-on-click="{{ cfEditBranch }}">Change</button></div>\n'
    '                    <div class="cf2-fact"><span class="cf2-fact-ico">' + _CHAIR + '</span><div class="cf2-fact-body"><div class="cf2-fact-k">Chair</div><div class="cf2-fact-v">{{ cf2ChairLabel }}</div></div><button type="button" class="cf-edit" sc-camel-on-click="{{ cfEditChair }}">Change</button></div>\n'
    '                    <div class="cf2-fact"><span class="cf2-fact-ico">' + _USER + '</span><div class="cf2-fact-body"><div class="cf2-fact-k">Artist</div><div class="cf2-fact-v">{{ ticketStylistName }}</div></div></div>\n'
    '                    <sc-if value="{{ cf2HasDuration }}" hint-placeholder-val="{{ false }}"><div class="cf2-fact"><span class="cf2-fact-ico">' + _CLOCK + '</span><div class="cf2-fact-body"><div class="cf2-fact-k">Chair time</div><div class="cf2-fact-v">{{ cf2Duration }}</div></div></div></sc-if>\n'
    '                  </div>\n'
    '                  <div class="cf2-svcs">\n'
    '                    <div class="cf2-sec-row"><h3 class="cf2-h">Services <span class="cf2-count">{{ cf2SvcCount }}</span></h3><button type="button" class="cf-edit" sc-camel-on-click="{{ cfEditService }}">Edit services</button></div>\n'
    '                    <ul class="cf2-svc-list">\n'
    '                      <sc-for list="{{ cfServiceLines }}" as="sv" hint-placeholder-count="2">\n'
    '                        <li class="cf2-svc"><span class="cf2-svc-ico" aria-hidden="true">&#10022;</span><div class="cf2-svc-body"><div class="cf2-svc-name">{{ sv.name }}</div><div class="cf2-svc-meta">{{ sv.meta }}</div></div><div class="cf2-svc-price">{{ sv.price }}</div></li>\n'
    '                      </sc-for>\n'
    '                    </ul>\n'
    '                  </div>\n'
    '                </section>'
)

_MAIL = _ICO % 'M4 6h16v12H4zM4 7l8 6 8-6'
_PHONE = _ICO % 'M6.5 3h3l1.5 4.5-2 1.5a11 11 0 0 0 6 6l1.5-2 4.5 1.5v3a2 2 0 0 1-2 2A17 17 0 0 1 4.5 5a2 2 0 0 1 2-2z'

# The guest slot: `.bsi-cf-signin` (id bsi-cf-signin) is the stable hook the
# sign-in gate styles/extends; it is only rendered when nobody is signed in.
DETAILS_CARD = (
    '<sc-if value="{{ cf2GuestMode }}" hint-placeholder-val="{{ false }}">\n'
    '                <section class="cf-card bsi-cf-signin" id="bsi-cf-signin" tabindex="-1" aria-labelledby="bsi-cf-signin-h">\n'
    '                  <span class="bsi-cf-signin__ico" aria-hidden="true">' + _LOCK + '</span>\n'
    '                  <div class="bsi-cf-signin__body">\n'
    '                    <h3 class="cf2-h" id="bsi-cf-signin-h">Sign in to book</h3>\n'
    '                    <p class="cf2-sub">Bookings are made from your Enrich account, so the salon can confirm your slot &mdash; and your points, rewards and gift cards apply automatically.</p>\n'
    '                  </div>\n'
    '                  <a class="cf-btn cf-btn--gold bsi-cf-signin__btn" href="{{ cf2SigninHref }}">Sign in</a>\n'
    '                </section>\n'
    '                </sc-if>\n'
    '                <sc-if value="{{ cf2SignedIn }}" hint-placeholder-val="{{ false }}">\n'
    '                <section class="cf-card cf2-details" id="cf2-details" aria-labelledby="cf2-details-h">\n'
    '                  <div class="cf2-sec-row">\n'
    '                    <h3 class="cf2-h" id="cf2-details-h">Your details</h3>\n'
    '                    <span class="cf2-badge">' + _CHECK + 'Signed in</span>\n'
    '                  </div>\n'
    '                  <p class="cf2-sub">{{ cf2DetailsSub }}</p>\n'
    '                  <div class="cf2-who">\n'
    '                    <div class="cf2-who-row"><span class="cf2-who-ico">' + _USER + '</span><div class="cf2-who-body"><div class="cf2-who-k">Name</div><div class="cf2-who-v">{{ cf2Contact.name }}</div></div></div>\n'
    '                    <sc-if value="{{ cf2Contact.hasPhone }}" hint-placeholder-val="{{ true }}"><div class="cf2-who-row"><span class="cf2-who-ico">' + _PHONE + '</span><div class="cf2-who-body"><div class="cf2-who-k">Mobile</div><div class="cf2-who-v">{{ cf2Contact.acctPhone }}</div></div></div></sc-if>\n'
    '                    <div class="cf2-who-row"><span class="cf2-who-ico">' + _MAIL + '</span><div class="cf2-who-body"><div class="cf2-who-k">Email</div><div class="cf2-who-v">{{ cf2Contact.email }}</div></div></div>\n'
    '                  </div>\n'
    '                  <sc-if value="{{ cf2Contact.needsPhone }}" hint-placeholder-val="{{ false }}">\n'
    '                    <div class="{{ cf2Contact.phoneCls }}">\n'
    '                      <label for="cf2-phone">Add a mobile number <span class="cf2-opt">optional &middot; so the salon can call you</span></label>\n'
    '                      <div class="cf2-input"><input id="cf2-phone" name="phone" type="tel" inputmode="tel" autocomplete="tel" maxlength="20" placeholder="98765 43210" aria-invalid="{{ cf2Contact.phoneInvalid }}" aria-describedby="cf2-phone-err" sc-camel-on-input="{{ cf2OnPhone }}"><i class="cf2-ok" aria-hidden="true">' + _CHECK + '</i></div>\n'
    '                      <div class="cf2-err" id="cf2-phone-err">{{ cf2Contact.phoneErr }}</div>\n'
    '                    </div>\n'
    '                  </sc-if>\n'
    '                  <p class="cf2-privacy">' + _SHIELD + '<span>Used only for this appointment. <a href="/my/account">Update your details</a></span></p>\n'
    '                </section>\n'
    '                </sc-if>\n'
    '                '
)

PERKS_OPEN_SRC = (
    '<section class="cf-card">\n'
    '                  <div class="cf-sec-head"><span>Perks &amp; payment</span><sc-if value="{{ cfLoading }}" '
    'hint-placeholder-val="{{ false }}"><span class="cf-updating">Updating</span></sc-if></div>'
)
PERKS_OPEN_DST = (
    DETAILS_CARD
    + '<sc-if value="{{ cf2ShowPerks }}" hint-placeholder-val="{{ true }}">\n'
    '                <section class="cf-card cf2-perks" aria-labelledby="cf2-perks-h">\n'
    '                  <div class="cf2-sec-row"><h3 class="cf2-h" id="cf2-perks-h">Perks &amp; payment</h3><sc-if value="{{ cfLoading }}" '
    'hint-placeholder-val="{{ false }}"><span class="cf-updating">Updating</span></sc-if></div>\n'
    '                  <p class="cf2-sub">{{ cf2PerksSub }}</p>'
)
PERKS_CLOSE_SRC = '</div>\n                </section>\n              </div>\n              <aside class="cf-side">'
PERKS_CLOSE_DST = '</div>\n                </section>\n                </sc-if>\n              </div>\n              <aside class="cf-side">'

ASIDE_START = '<aside class="cf-side">'
ASIDE_END = '</aside>'
ASIDE_NEW = (
    '<aside class="cf-side cf2-side" aria-label="Price details and confirmation">\n'
    '                <div class="cf-receipt cf2-receipt">\n'
    '                  <div class="cf-receipt-head"><span class="cf-brand">enrich</span><span class="cf-receipt-k">Price details</span></div>\n'
    '                  <div class="cf2-lines">\n'
    '                  <sc-for list="{{ cfLines }}" as="ln" hint-placeholder-count="2">\n'
    '                    <div class="cf-line {{ ln.cls }}"><span>{{ ln.label }}</span><span>{{ ln.value }}</span></div>\n'
    '                  </sc-for>\n'
    '                  </div>\n'
    '                  <div class="cf-rule"></div>\n'
    '                  <div class="cf-total">\n'
    '                    <div class="cf-total-k">To pay<small>at the salon, after your service</small></div>\n'
    '                    <div class="{{ cf2TotalCls }}">{{ summaryPayable }}</div>\n'
    '                  </div>\n'
    '                  <sc-if value="{{ cfHasSavings }}" hint-placeholder-val="{{ false }}">\n'
    '                    <div class="cf-save">' + _CHECK + '{{ cfSavings }}</div>\n'
    '                  </sc-if>\n'
    '                  <div class="cf2-checks" id="cf2-checks" tabindex="-1">\n'
    '                    <div class="cf2-checks-head"><span>Ready to confirm</span><b>{{ cf2ReadyCount }}</b></div>\n'
    '                    <sc-for list="{{ cf2Checks }}" as="ck" hint-placeholder-count="4">\n'
    '                      <div class="{{ ck.cls }}"><span class="cf2-ck-ico" aria-hidden="true"></span><span class="cf2-ck-body"><b>{{ ck.label }}</b><small>{{ ck.value }}</small></span><sc-if value="{{ ck.canFix }}" hint-placeholder-val="{{ false }}"><button type="button" class="cf2-ck-fix" sc-camel-on-click="{{ ck.onFix }}">{{ ck.fixLabel }}</button></sc-if></div>\n'
    '                    </sc-for>\n'
    '                  </div>\n'
    '                  <sc-if value="{{ bsiQuoteError }}" hint-placeholder-val="{{ false }}">\n'
    '                    <div class="cf-alert cf-alert--warn">{{ bsiQuoteError }}</div>\n'
    '                  </sc-if>\n'
    '                  <sc-if value="{{ bookingError }}" hint-placeholder-val="{{ false }}">\n'
    '                    <div class="cf-alert" role="alert">{{ bookingError }}</div>\n'
    '                  </sc-if>\n'
    '                  <button type="button" class="cf-confirm {{ cfConfirmState }}" sc-camel-on-click="{{ confirmBooking }}" disabled="{{ cfConfirmDisabled }}" aria-disabled="{{ cf2AriaDisabled }}">{{ confirmBtnLabel }}</button>\n'
    '                  <sc-if value="{{ cf2ShowMissing }}" hint-placeholder-val="{{ false }}">\n'
    '                    <p class="cf2-missing" role="alert">{{ cf2MissingText }}</p>\n'
    '                  </sc-if>\n'
    '                  <ul class="cf-assure">\n'
    '                    <li>' + _CHECK + '<span>No payment online &mdash; settle the balance at the salon</span></li>\n'
    '                    <li>' + _CHECK + '<span>Free reschedule up to 4 hours before your slot</span></li>\n'
    '                    <sc-if value="{{ cf2ShowPerkNote }}" hint-placeholder-val="{{ true }}"><li>' + _CHECK + '<span>Points, rewards and gift cards are only used once you confirm</span></li></sc-if>\n'
    '                  </ul>\n'
    '                </div>\n'
    '              </aside>'
)

PASS_START = '<sc-if value="{{ isConfirmed }}" hint-placeholder-val="{{ false }}">'
PASS_END = '        </sc-if>\n      </sc-if>\n\n      <sc-if value="{{ showBookingBack }}"'
PASS_NEW = (
    '<sc-if value="{{ isConfirmed }}" hint-placeholder-val="{{ false }}">\n'
    '          <div class="cf2-done">\n'
    '            <div class="cf2-done-head">\n'
    '              <div class="cf2-done-check" aria-hidden="true"><svg sc-camel-view-box="0 0 52 52"><circle cx="26" cy="26" r="24"></circle><path d="M15 27l7 7 15-16"></path></svg></div>\n'
    '              <div class="cf2-done-eyebrow">Booking request received</div>\n'
    '              <h2 class="cf2-done-title">{{ cf2DoneTitle }}</h2>\n'
    '              <p class="cf2-done-lead">{{ cf2DoneLead }}</p>\n'
    '            </div>\n'
    '            <div class="cf2-pass">\n'
    '              <div class="cf2-pass-sheen" aria-hidden="true"><span></span></div>\n'
    '              <div class="cf2-pass-top">\n'
    '                <div class="cf2-pass-brand"><span class="cf2-pass-logo">enrich</span><span class="cf2-pass-k">APPOINTMENT PASS</span></div>\n'
    '                <span class="cf2-pass-status">CONFIRMED</span>\n'
    '              </div>\n'
    '              <div class="cf2-pass-body">\n'
    '                <div class="cf2-pass-info">\n'
    '                  <div class="cf2-pass-lbl">DATE &amp; TIME</div>\n'
    '                  <div class="cf2-pass-when">{{ summaryTime }}</div>\n'
    '                  <div class="cf2-pass-grid">\n'
    '                    <div><div class="cf2-pass-lbl">GUEST</div><div class="cf2-pass-val">{{ cf2GuestName }}</div></div>\n'
    '                    <div><div class="cf2-pass-lbl">{{ cf2GuestPhoneK }}</div><div class="cf2-pass-val">{{ cf2GuestPhone }}</div></div>\n'
    '                    <div><div class="cf2-pass-lbl">BRANCH</div><div class="cf2-pass-val">{{ summaryStore }}</div></div>\n'
    '                    <div><div class="cf2-pass-lbl">CHAIR</div><div class="cf2-pass-val">{{ cf2ChairLabel }}</div></div>\n'
    '                  </div>\n'
    '                  <ul class="cf2-pass-svcs">\n'
    '                    <sc-for list="{{ cfServiceLines }}" as="sv" hint-placeholder-count="2">\n'
    '                      <li><span>{{ sv.name }}</span><b>{{ sv.price }}</b></li>\n'
    '                    </sc-for>\n'
    '                  </ul>\n'
    '                  <div class="cf2-pass-row">\n'
    '                    <img src="{{ ticketStylistPhoto }}" alt="{{ ticketStylistName }}" class="cf2-pass-avatar">\n'
    '                    <div class="cf2-pass-sty"><div class="cf2-pass-lbl">YOUR ARTIST</div><div class="cf2-pass-val">{{ ticketStylistName }}</div></div>\n'
    '                    <div class="cf2-pass-total"><div class="cf2-pass-amt">{{ summaryPayable }}</div><div class="cf2-pass-lbl">PAY AT SALON</div></div>\n'
    '                  </div>\n'
    '                </div>\n'
    '                <div class="cf2-pass-qr">\n'
    '                  <div class="cf2-qr-box">\n'
    '                    <svg sc-camel-view-box="0 0 29 29" style="width:100%;height:100%;shape-rendering:crispEdges;">\n'
    '                      <rect width="29" height="29" fill="#fdf3ea"></rect>\n'
    '                      <g fill="#161213">\n'
    '                        <path d="M0 0h7v7H0zM22 0h7v7h-7zM0 22h7v7H0z"></path>\n'
    '                        <path d="M2 2h3v3H2zM24 2h3v3h-3zM2 24h3v3H2z" fill="#fdf3ea"></path>\n'
    '                        <sc-for list="{{ ticketQr }}" as="q" hint-placeholder-count="120">\n'
    '                          <rect x="{{ q.x }}" y="{{ q.y }}" width="1" height="1"></rect>\n'
    '                        </sc-for>\n'
    '                      </g>\n'
    '                    </svg>\n'
    '                  </div>\n'
    '                  <div class="cf2-pass-code">{{ cf2Ref }}</div>\n'
    '                  <div class="cf2-pass-qr-note">Show at reception to check in</div>\n'
    '                </div>\n'
    '              </div>\n'
    '              <div class="cf2-pass-bottom"><span>Arrive 10 minutes early &middot; Free reschedule up to 4 hours before</span><span class="cf2-pass-city">{{ summaryCity }}</span></div>\n'
    '              <span class="cf2-notch cf2-notch--l" aria-hidden="true"></span><span class="cf2-notch cf2-notch--r" aria-hidden="true"></span>\n'
    '              <div class="cf2-stamp" aria-hidden="true">BOOKED</div>\n'
    '            </div>\n'
    '            <ol class="cf2-next">\n'
    '              <li><span class="cf2-next-n">1</span><div><b>We&rsquo;ll confirm by phone</b><small>{{ cf2NextCall }}</small></div></li>\n'
    '              <li><span class="cf2-next-n">2</span><div><b>Save it to your calendar</b><small>One tap, so you never miss your slot.</small></div></li>\n'
    '              <li><span class="cf2-next-n">3</span><div><b>Pay at the salon</b><small>{{ cf2NextPay }}</small></div></li>\n'
    '            </ol>\n'
    '            <div class="cf2-done-actions">\n'
    '              <a class="cf2-btn cf2-btn--ink" href="{{ ticketCalendarHref }}" download="enrich-appointment.ics">Add to calendar</a>\n'
    '              <button type="button" class="cf2-btn cf2-btn--red" sc-camel-on-click="{{ resetBooking }}">Book another</button>\n'
    '            </div>\n'
    '          </div>\n'
    + PASS_END
)

# Simple exact-string patches, applied in order.
PATCHES = [
    ('Confirm v2: logic fields',
     "  setBillingMonthly = () => this.setState({ billing: 'monthly' });",
     LOGIC_JS + "\n  setBillingMonthly = () => this.setState({ billing: 'monthly' });"),
    ('Confirm v2: state-diff toaster hook',
     'componentDidUpdate() { this._motion(); }',
     'componentDidUpdate() { this._motion(); if (this._bsiCfDiff) { try { this._bsiCfDiff(); } catch (e) { /* toasts must never break the page */ } } }'),
    ('Confirm v2: render values',
     '      finalPrice, confirmBooking: this.confirmBooking, resetBooking: this.resetBooking,',
     '      ...this.bsiCf2Vals(),\n      finalPrice, confirmBooking: this.confirmBooking, resetBooking: this.resetBooking,'),
    ('Confirm v2: perks card open', PERKS_OPEN_SRC, PERKS_OPEN_DST),
    ('Confirm v2: perks card close', PERKS_CLOSE_SRC, PERKS_CLOSE_DST),
    # Service step: the package column only takes a grid track when it renders.
    ('Confirm v2: service step grid',
     '<div style="display:grid;grid-template-columns:1fr 280px;gap:26px;align-items:start;">',
     '<div class="bsi-svc-grid" style="display:grid;grid-template-columns:1fr 280px;gap:26px;align-items:start;">'),
    # Membership page blocks, so the Settings toggles can hide each one cleanly.
    ('Confirm v2: membership title', 'Enrich Membership</h1>', '{{ bsiMbTitle }}</h1>'),
    ('Confirm v2: membership subtitle', 'One membership, every branch, every city.', '{{ bsiMbSub }}'),
    ('Confirm v2: membership billing toggle',
     '<div style="display:inline-flex;background:#eeeeec;border-radius:4px;padding:5px;">',
     '<div class="bsi-mb-billing" style="display:inline-flex;background:#eeeeec;border-radius:4px;padding:5px;">'),
    ('Confirm v2: membership active card',
     '<sc-if value="{{ hasActiveMembership }}" hint-placeholder-val="{{ false }}">\n      <div style="position:relative;border-radius:24px;',
     '<sc-if value="{{ hasActiveMembership }}" hint-placeholder-val="{{ false }}">\n      <div class="bsi-mb-active" style="position:relative;border-radius:24px;'),
    ('Confirm v2: membership tiers',
     '<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:22px;margin-bottom:60px;">\n        <sc-for list="{{ tiersDisplay }}"',
     '<div class="bsi-mb-tiers" style="display:grid;grid-template-columns:repeat(3,1fr);gap:22px;margin-bottom:60px;">\n        <sc-for list="{{ tiersDisplay }}"'),
    ('Confirm v2: membership perks row',
     '<div style="display:grid;grid-template-columns:1.3fr 1fr;gap:22px;margin-bottom:22px;">\n\n        <!-- Loyalty wallet',
     '<div class="bsi-mb-perks" style="display:grid;grid-template-columns:1.3fr 1fr;gap:22px;margin-bottom:22px;">\n\n        <!-- Loyalty wallet'),
    ('Confirm v2: membership loyalty wallet',
     '<!-- Loyalty wallet: points ring, tier progress, redeemable rewards -->\n        <div ',
     '<!-- Loyalty wallet: points ring, tier progress, redeemable rewards -->\n        <div class="bsi-mb-wallet" '),
    ('Confirm v2: membership gift cards',
     '<!-- Gift card: the card itself flips between face and message -->\n        <div ',
     '<!-- Gift card: the card itself flips between face and message -->\n        <div class="bsi-mb-gift" '),
    ('Confirm v2: membership calculator',
     '<!-- Savings calculator: your real usage against each tier -->\n      <div ',
     '<!-- Savings calculator: your real usage against each tier -->\n      <div class="bsi-mb-calc" '),
    # Nav: "Membership" becomes "Rewards" without memberships, and goes away when
    # the page would have nothing left on it.
    ('Confirm v2: nav membership entry',
     '    const navItems = NAV_DEFS.map((n) => {',
     "    const navItems = NAV_DEFS.filter((n) => n.key !== 'membership' || BSI_FEATURES.membership "
     "|| BSI_FEATURES.loyalty || BSI_FEATURES.gift_card).map((n) => (n.key === 'membership' && !BSI_FEATURES.membership) "
     "? Object.assign({}, n, { label: 'Rewards' }) : n).map((n) => {"),
]

# (label, start marker, end marker, replacement, keep_end) -- the replacement
# covers start..end (end included unless keep_end).
BLOCKS = [
    ('Confirm v2: header', HEAD_START, HEAD_END, HEAD_NEW, False),
    ('Confirm v2: appointment card', APPT_START, APPT_END, APPT_NEW, False),
    ('Confirm v2: receipt aside', ASIDE_START, ASIDE_END, ASIDE_NEW, False),
    ('Confirm v2: appointment pass', PASS_START, PASS_END, PASS_NEW, False),
]


def _swap_block(page, label, start, end, new):
    i = page.find(start)
    if i == -1:
        _logger.warning('Enrich site: %s not found, left as designed', label)
        return page
    j = page.find(end, i + len(start))
    if j == -1:
        _logger.warning('Enrich site: %s not found, left as designed', label)
        return page
    return page[:i] + new + page[j + len(end):]


def _hide_css(features):
    rules = []
    if not features['membership']:
        rules.append('.bsi-mb-tiers,.bsi-mb-billing,.bsi-mb-calc,.bsi-mb-active{display:none!important}')
    if not features['loyalty']:
        rules.append('.bsi-mb-wallet{display:none!important}')
    if not features['gift_card']:
        rules.append('.bsi-mb-gift{display:none!important}')
    if not features['loyalty'] and not features['gift_card']:
        rules.append('.bsi-mb-perks{display:none!important}')
    elif not features['loyalty'] or not features['gift_card']:
        rules.append('.bsi-mb-perks{grid-template-columns:minmax(0,1fr)!important;max-width:720px;margin-left:auto!important;margin-right:auto!important}')
    return ('<style id="bsi-feature-toggles">%s</style>' % ''.join(rules)) if rules else ''


def apply(page, data):
    """Confirm step v2 + toasts + toggle clean-up, on the fully patched template."""
    features = _features()
    for label, source, target in PATCHES:
        if source in page:
            page = page.replace(source, target, 1)
        else:
            _logger.warning('Enrich site: %s not found, left as designed', label)
    for label, start, end, new, _keep in BLOCKS:
        page = _swap_block(page, label, start, end, new)

    # Top of the component script: the toggles + the toast helper.
    anchor = '<script type="text/x-dc"'
    at = page.find(anchor)
    close = page.find('>', at) if at != -1 else -1
    if close == -1:
        _logger.warning('Enrich site: Confirm v2 x-dc script not found, toasts not injected')
    else:
        feats_js = 'const BSI_FEATURES = %s;\n' % json.dumps(features).replace('</', '<\\/')
        page = page[:close + 1] + feats_js + TOAST_JS + page[close + 1:]

    head = '<link rel="stylesheet" href="%s"/>\n%s' % (CSS_HREF, _hide_css(features))
    if '</helmet>' in page:
        page = page.replace('</helmet>', head + '</helmet>', 1)
    else:
        _logger.warning('Enrich site: Confirm v2 </helmet> not found, styles not linked')
    return page
