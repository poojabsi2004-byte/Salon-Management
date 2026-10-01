# -*- coding: utf-8 -*-
"""Sign-in gate: guests can browse and configure, but committing needs an account.

A visitor who is not signed in may NOT:

* book services -- /salon/api/booking (every flavour: services, package, Design
  Your Look, Colour Lab consultation, stylist-seeded, reward/points-seeded);
* buy a membership -- /salon/api/membership_product, then the standard cart;
* buy a gift card -- /salon/api/gift_card_product, then the standard cart (the
  denominations' products are also published in /shop, so the cart itself and
  checkout refuse them too);
* use loyalty points, rewards or gift cards -- stripped from /salon/api/booking_quote
  for guests; /salon/api/gift_card_validate already refuses them.

Everything read-only (pages, catalogue, prices, slot availability, the contact
form, customer_city, live_pulse, status endpoints) stays public.

Two halves:

1. Server (the real gate) -- controller overrides below. Refusals carry
   ``login_required: True`` and a ``login_url`` so the page can react.
2. Page -- ``apply(page, data)``, hooked LAST in BsiSalonWeb._build_site. Adds
   ``window.bsiAuth`` (who is signed in, the on-brand "Sign in to continue" dialog,
   sessionStorage hand-off of an in-progress booking across the login round trip),
   guards every committing handler, and extends enrich_confirm's ``.bsi-cf-signin``
   card with a "Create account" button. Styles: static/src/css/bsi_signin_gate.css (bsi_auth.css is the
   login/registration pages' own stylesheet -- not linked here).

Loaded from controllers/__init__.py after main (it subclasses main.BsiSalonWeb);
main._build_site imports it lazily for apply().
"""

import logging
from urllib.parse import quote

from odoo import http
from odoo.exceptions import UserError, ValidationError
from odoo.http import request

from odoo.addons.website_sale.controllers.cart import Cart
from odoo.addons.website_sale.controllers.main import WebsiteSale
from odoo.addons.website_sale.controllers.payment import PaymentPortal

from .main import BsiSalonWeb

_logger = logging.getLogger(__name__)

CSS_HREF = '/bsi_salon_web/static/src/css/bsi_signin_gate.css?v=1'

LOGIN_PATH = '/web/login'
SIGNUP_PATH = '/web/signup'

MESSAGES = {
    'book': 'Please sign in to book your appointment.',
    'membership': 'Please sign in to buy a membership.',
    'gift': 'Please sign in to buy a gift card.',
    'points': 'Please sign in to use loyalty points, rewards or gift cards.',
    'shop': 'Please sign in to buy memberships and gift cards.',
}


def _is_guest():
    return request.env.user._is_public()


def login_url(path):
    return '%s?redirect=%s' % (LOGIN_PATH, quote(path or '/salon', safe='/'))


def refusal(what, path, **extra):
    """The JSON a gated endpoint answers a guest with."""
    payload = {
        'ok': False,
        'error': MESSAGES[what],
        'login_required': True,
        'login_url': login_url(path),
    }
    payload.update(extra)
    return payload


def gated_product_ids(env):
    """Products that only a signed-in customer may buy: membership tiers (both
    billing periods) and gift card denominations, archived ones included."""
    env = env(su=True)
    ids = set()
    tiers = env['bsi.salon.membership'].with_context(active_test=False).search([])
    ids.update(tiers.mapped('bsi_product_monthly_id').ids)
    ids.update(tiers.mapped('bsi_product_yearly_id').ids)
    # Gift denominations removed — gift cards now use loyalty.program products directly
    return ids


def order_has_gated_lines(order_sudo):
    if not order_sudo:
        return False
    gated = gated_product_ids(order_sudo.env)
    return any(line.product_id.id in gated for line in order_sudo.order_line)


# Booking-quote parameters that spend or apply something of the customer's own.
_REDEMPTION_KEYS = ('loyalty_points', 'gift_card_code', 'reward_id', 'reward_service_id',
                    'auto_loyalty', 'auto_gift_card', 'points_service_ids',
                    'entered_code', 'promo_code')


# ---------------------------------------------------------------------------
# Server-side gate -- /salon/api/*
# ---------------------------------------------------------------------------

class BsiSalonAuthGate(BsiSalonWeb):

    @http.route()
    def bsi_salon_api_booking(self, **kwargs):
        if _is_guest():
            return refusal('book', '/salon/booking')
        return super().bsi_salon_api_booking(**kwargs)

    @http.route()
    def bsi_salon_api_booking_quote(self, **kwargs):
        # Pricing stays public (guests see their total), but nothing of a
        # customer's own can be applied without an account.
        if _is_guest():
            for key in _REDEMPTION_KEYS:
                kwargs.pop(key, None)
            kwargs['use_service_points'] = False
            kwargs['points_service_ids'] = []
        return super().bsi_salon_api_booking_quote(**kwargs)

    @http.route()
    def bsi_salon_api_gift_card_validate(self, code=None, **kwargs):
        if _is_guest():
            return refusal('points', '/salon/booking')
        return super().bsi_salon_api_gift_card_validate(code=code, **kwargs)

    @http.route()
    def bsi_salon_api_membership_product(self, membership_id=None, billing_period='monthly', **kwargs):
        if _is_guest():
            return refusal('membership', '/salon/membership', **{'error': True, 'message': MESSAGES['membership']})
        return super().bsi_salon_api_membership_product(
            membership_id=membership_id, billing_period=billing_period, **kwargs)

    @http.route()
    def bsi_salon_api_gift_card_product(self, amount=None, **kwargs):
        if _is_guest():
            return refusal('gift', '/salon/membership', **{'error': True, 'message': MESSAGES['gift']})
        return super().bsi_salon_api_gift_card_product(amount=amount, **kwargs)


# ---------------------------------------------------------------------------
# Server-side gate -- the standard cart / checkout (memberships, gift cards)
# ---------------------------------------------------------------------------

class BsiSalonAuthCart(Cart):

    @http.route()
    def add_to_cart(self, product_template_id, product_id, quantity=1.0, **kwargs):
        if _is_guest():
            try:
                pid = int(product_id or 0)
            except (TypeError, ValueError):
                pid = 0
            if pid and pid in gated_product_ids(request.env):
                raise UserError(MESSAGES['shop'])
        return super().add_to_cart(product_template_id, product_id, quantity=quantity, **kwargs)


class BsiSalonAuthPayment(PaymentPortal):

    def _validate_transaction_for_order(self, transaction, sale_order):
        # Last line before a payment is started for a cart (/shop/payment/transaction):
        # raising here rolls the just-created transaction back with the request.
        if _is_guest() and order_has_gated_lines(sale_order):
            raise ValidationError(MESSAGES['shop'])
        return super()._validate_transaction_for_order(transaction, sale_order)


class BsiSalonAuthCheckout(WebsiteSale):

    @http.route()
    def product(self, product, category=None, pricelist=None, **kwargs):
        # A membership / gift card product page is nothing but its "Add to cart"
        # button, which refuses guests (and website_sale's error dialog for that
        # refusal does not render on this theme) -- so a guest goes to sign-in
        # first and lands back on the same product page.
        if _is_guest() and product and \
                set(product.sudo().product_variant_ids.ids) & gated_product_ids(request.env):
            return request.redirect(login_url(request.httprequest.path))
        return super().product(product, category=category, pricelist=pricelist, **kwargs)

    def _check_cart(self, order_sudo):
        # Covers /shop/checkout, /shop/address, /shop/extra_info and /shop/payment:
        # a guest cart holding a membership or gift card goes to sign-in first and
        # comes straight back to checkout (the cart follows the session).
        redirection = super()._check_cart(order_sudo)
        if redirection:
            return redirection
        if _is_guest() and order_has_gated_lines(order_sudo):
            return request.redirect(login_url('/shop/checkout'))
        return None


# ---------------------------------------------------------------------------
# Page patches
# ---------------------------------------------------------------------------

# Top of the x-dc script: window.bsiAuth. Framework-free, so the dialog works on
# any page state and never depends on another patch's markup.
AUTH_JS = r"""
(function () {
  if (typeof window === 'undefined') { return; }
  // The bundler shell swaps the whole document once, which aborts a status call
  // made by the first evaluation -- a second evaluation just re-asks.
  if (window.bsiAuth) { if (!window.bsiAuth.state.known) { window.bsiAuth.reload(); } return; }
  var KEY = 'bsi_auth_resume';
  var TTL = 45 * 60 * 1000;
  var LOGIN = '/web/login', SIGNUP = '/web/signup';
  var st = { known: false, loggedIn: false };
  var waiters = [];
  var COPY = {
    book: { t: 'Sign in to book', s: 'Bookings are made from your Enrich account so the salon can confirm your slot. Your selection is saved: sign in or create a free account and you’ll come straight back to confirm it.', p: '/salon/booking' },
    membership: { t: 'Sign in to join', s: 'Memberships belong to your Enrich account, so your discount follows you to every branch. Sign in or create a free account to continue.', p: '/salon/membership' },
    gift: { t: 'Sign in to buy a gift card', s: 'Gift cards are issued from your Enrich account, so you can track the balance and send them on. Sign in or create a free account to continue.', p: '/salon/membership' },
    points: { t: 'Sign in to use your rewards', s: 'Loyalty points, rewards and gift cards live in your Enrich account. Sign in to apply them to this booking.', p: null }
  };
  function settle(v) {
    st.known = true; st.loggedIn = !!v;
    var w = waiters; waiters = [];
    w.forEach(function (fn) { try { fn(st.loggedIn); } catch (e) { /* ignore */ } });
  }
  var tries = 0, inflight = false;
  function load() {
    if (st.known || inflight) { return; }
    inflight = true; tries += 1;
    var retry = function () { inflight = false; if (!st.known && tries < 6) { setTimeout(load, 700 * tries); } };
    try {
      fetch('/salon/api/user_status', { method: 'POST', credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id: 1, jsonrpc: '2.0', method: 'call', params: {} }) })
        .then(function (r) { return r.json(); })
        .then(function (p) {
          inflight = false;
          if (p && p.result && typeof p.result.logged_in === 'boolean') { settle(p.result.logged_in); } else { retry(); }
        })
        .catch(retry);  // unknown meanwhile: the server still gates every commit
    } catch (e) { retry(); }
  }
  function here() {
    var m = (window.location.pathname || '').match(/^\/salon\/[a-z]+/);
    return m ? m[0] : '/salon';
  }
  function url(base, path) { return base + '?redirect=' + encodeURIComponent(path || here()); }
  function save(what, page, state) {
    try {
      window.sessionStorage.setItem(KEY, JSON.stringify({ v: 1, ts: Date.now(), what: what, page: page, state: state || {} }));
    } catch (e) { /* private mode: still returns to the right page */ }
  }
  function take(page) {
    var raw = null;
    try { raw = window.sessionStorage.getItem(KEY); } catch (e) { return null; }
    if (!raw) { return null; }
    var r = null;
    try { r = JSON.parse(raw); } catch (e) { r = null; }
    if (!r || !r.ts || Date.now() - r.ts > TTL) { try { window.sessionStorage.removeItem(KEY); } catch (e) { /* ignore */ } return null; }
    if (page && r.page !== page) { return null; }
    try { window.sessionStorage.removeItem(KEY); } catch (e) { /* ignore */ }
    return r;
  }
  var dlg = null, lastFocus = null;
  function close() {
    if (!dlg) { return; }
    dlg.classList.remove('is-in');
    var d = dlg; dlg = null;
    document.removeEventListener('keydown', onKey, true);
    setTimeout(function () { if (d.parentNode) { d.parentNode.removeChild(d); } }, 220);
    if (lastFocus && lastFocus.focus) { try { lastFocus.focus({ preventScroll: true }); } catch (e) { /* ignore */ } }
  }
  function onKey(e) {
    if (!dlg) { return; }
    if (e.key === 'Escape') { e.preventDefault(); close(); return; }
    if (e.key === 'Tab') {
      var f = dlg.querySelectorAll('a[href],button');
      if (!f.length) { return; }
      var first = f[0], last = f[f.length - 1];
      if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
    }
  }
  function prompt(what, opts) {
    opts = opts || {};
    var c = COPY[what] || COPY.points;
    var path = opts.path || c.p || here();
    if (dlg) { close(); }
    lastFocus = document.activeElement;
    var el = document.createElement('div');
    el.className = 'bsi-gate';
    el.setAttribute('role', 'dialog');
    el.setAttribute('aria-modal', 'true');
    el.setAttribute('aria-labelledby', 'bsi-gate-h');
    el.setAttribute('aria-describedby', 'bsi-gate-s');
    el.innerHTML = '<div class="bsi-gate__scrim" data-bsi-gate-close></div>'
      + '<div class="bsi-gate__card">'
      + '<button type="button" class="bsi-gate__x" aria-label="Close" data-bsi-gate-close>&times;</button>'
      + '<div class="bsi-gate__mark" aria-hidden="true"><svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/></svg></div>'
      + '<div class="bsi-gate__eyebrow">Enrich account</div>'
      + '<h2 class="bsi-gate__h" id="bsi-gate-h"></h2>'
      + '<p class="bsi-gate__s" id="bsi-gate-s"></p>'
      + '<div class="bsi-gate__actions">'
      + '<a class="bsi-gate__btn bsi-gate__btn--primary" data-bsi-gate-go="login">Sign in</a>'
      + '<a class="bsi-gate__btn bsi-gate__btn--ghost" data-bsi-gate-go="signup">Create account</a>'
      + '</div>'
      + '<button type="button" class="bsi-gate__later" data-bsi-gate-close>Keep browsing</button>'
      + '</div>';
    el.querySelector('.bsi-gate__h').textContent = opts.title || c.t;
    el.querySelector('.bsi-gate__s').textContent = opts.text || c.s;
    el.querySelector('[data-bsi-gate-go="login"]').setAttribute('href', url(LOGIN, path));
    el.querySelector('[data-bsi-gate-go="signup"]').setAttribute('href', url(SIGNUP, path));
    Array.prototype.forEach.call(el.querySelectorAll('[data-bsi-gate-close]'), function (b) {
      b.addEventListener('click', function (e) { e.preventDefault(); close(); });
    });
    (document.body || document.documentElement).appendChild(el);
    dlg = el;
    document.addEventListener('keydown', onKey, true);
    requestAnimationFrame(function () { requestAnimationFrame(function () { el.classList.add('is-in'); }); });
    setTimeout(function () { var b = el.querySelector('[data-bsi-gate-go="login"]'); if (b) { try { b.focus({ preventScroll: true }); } catch (e) { b.focus(); } } }, 60);
    return el;
  }
  window.bsiAuth = {
    state: st,
    reload: function () { tries = 0; inflight = false; load(); },
    loginUrl: function (p) { return url(LOGIN, p); },
    signupUrl: function (p) { return url(SIGNUP, p); },
    // true = definitely a guest. Unknown (status not back yet) counts as signed in
    // here: the server refuses a guest anyway and the page then prompts.
    isGuest: function (hint) {
      if (st.known) { return !st.loggedIn; }
      return hint === false;
    },
    // Signed-in state became known some other way (e.g. a server refusal).
    mark: function (v) { if (!st.known || st.loggedIn !== !!v) { settle(!!v); } },
    ready: function (fn) { if (st.known) { fn(st.loggedIn); } else { waiters.push(fn); } },
    prompt: prompt,
    close: close,
    save: save,
    take: take,
    // Guard a committing action: returns true (and prompts) when it must stop.
    guard: function (what, resume, hint) {
      if (!window.bsiAuth.isGuest(hint)) { return false; }
      var c = COPY[what] || COPY.points;
      var path = (resume && resume.path) || c.p || here();
      if (resume && resume.page) { save(what, resume.page, resume.state); }
      prompt(what, { path: path });
      return true;
    }
  };
  // The Confirm step's inline "Sign in to book" card (enrich_confirm) -- remember the
  // booking before following its links too.
  document.addEventListener('click', function (e) {
    var a = e.target && e.target.closest ? e.target.closest('.bsi-cf-signin a[href]') : null;
    if (a && window.bsiAuth.__snapshot) { try { window.bsiAuth.__snapshot(); } catch (err) { /* ignore */ } }
  }, true);
  load();
})();
"""

# Component class fields, placed right before componentDidMount -- i.e. after every
# other class field (enrich_confirm's Confirm wrapper included), so these guards
# wrap the final handlers and run first.
LOGIC_JS = r"""
  // ── enrich_auth: sign-in gate ───────────────────────────────────────────
  bsiAuthHint = () => {
    const s = this.state;
    if (s.userLoggedIn) { return true; }
    if (s.bsiAcct && typeof s.bsiAcct.logged_in === 'boolean') { return s.bsiAcct.logged_in; }
    if (s.bookingQuote && typeof s.bookingQuote.logged_in === 'boolean') { return s.bookingQuote.logged_in; }
    return null;
  };
  bsiAuthBookingSnapshot = () => {
    const s = this.state; const out = {};
    const skip = { bookingQuote: 1, bookingQuoteLoading: 1, bookingQuoteError: 1, bookingSubmitting: 1,
      bookingConfirmed: 1, bookingError: 1, bookingLoyaltyAuto: 1, bookingGiftAuto: 1, bookingLoyaltyPoints: 1,
      bookingGiftCode: 1, bookingPromoCode: 1, bookingRewardId: 1, bookingRewardAddedSvc: 1, bookingPointsServiceIds: 1, bookingUseServicePoints: 1 };
    Object.keys(s).forEach((k) => {
      if (skip[k]) { return; }
      if (k.indexOf('booking') === 0 || ['booking', 'selectedChairIds', 'selectedTime', 'ritual', 'chairs',
        'selectedCityId', 'selectedBranchId', 'bsiCalMonth', 'bsiCalYear'].indexOf(k) >= 0) {
        const v = s[k];
        if (typeof v === 'function') { return; }
        try { JSON.stringify(v); out[k] = v; } catch (e) { /* not serialisable: skip */ }
      }
    });
    return out;
  };
  bsiAuthSaveBooking = () => {
    if (this.state.page !== 'booking' || this.state.bookingConfirmed) { return; }
    if (window.bsiAuth) { window.bsiAuth.save('book', 'booking', this.bsiAuthBookingSnapshot()); }
  };
  bsiAuthAsk = (what) => {
    if (!window.bsiAuth) { return; }
    if (what === 'book' || (what === 'points' && this.state.page === 'booking')) { this.bsiAuthSaveBooking(); }
    else if (what === 'gift') { window.bsiAuth.save('gift', 'membership', { giftAmount: this.state.giftAmount, giftMessage: this.state.giftMessage || null }); }
    window.bsiAuth.prompt(what, { path: what === 'points' ? ('/salon/' + (this.state.page || 'home')) : null });
  };
  bsiAuthBlocked = (what) => {
    if (!window.bsiAuth || !window.bsiAuth.isGuest(this.bsiAuthHint())) { return false; }
    this.bsiAuthAsk(what);
    return true;
  };
  _bsiAuthSetup = (() => {
    const gate = (name, what) => {
      const orig = this[name];
      if (typeof orig !== 'function') { return; }
      this[name] = (...args) => { if (this.bsiAuthBlocked(what)) { return undefined; } return orig(...args); };
    };
    gate('confirmBooking', 'book');
    gate('buyGiftCard', 'gift');
    ['bsiApplyLoyalty', 'bsiUseMaxPoints', 'bsiApplyGiftCard', 'bsiApplyOwnGiftCard', 'bsiUseReward',
      'bsiToggleServicePoints', 'bsiToggleServicePointsFor', 'redeemReward', 'redeemServicePoints']
      .forEach((n) => gate(n, 'points'));
    // A server refusal (e.g. the status call had not come back yet) prompts too.
    const origRpc = this.bsiRpc;
    if (typeof origRpc === 'function') {
      this.bsiRpc = (url, params) => {
        const p = origRpc(url, params);
        return (p && p.then) ? p.then((res) => {
          if (res && res.login_required && window.bsiAuth) {
            window.bsiAuth.mark(false);
            this.bsiAuthAsk(url === '/salon/api/booking' ? 'book' : 'points');
          }
          return res;
        }) : p;
      };
    }
    if (window.bsiAuth) { window.bsiAuth.__snapshot = () => this.bsiAuthSaveBooking(); }
    return true;
  })();
  _bsiAuthResume = () => {
    if (!window.bsiAuth) { return; }
    window.bsiAuth.ready((loggedIn) => {
      if (!loggedIn) { return; }
      const r = window.bsiAuth.take(this.state.page);
      if (!r) { return; }
      const T = (m) => { try { if (window.bsiToast) { window.bsiToast(m, 'success'); } } catch (e) { /* ignore */ } };
      // Let the page's own mount-time calls (membership, loyalty, city...) land first.
      setTimeout(() => {
        if (r.page === 'booking' && r.state && r.state.booking) {
          this.setState(Object.assign({}, r.state, { bookingConfirmed: false, bookingError: false, bookingSubmitting: false }), () => {
            if (typeof this.bsiFetchQuote === 'function') { try { this.bsiFetchQuote(); } catch (e) { /* ignore */ } }
          });
          T('Welcome back — your booking is just as you left it.');
        } else if (r.state && Object.keys(r.state).length) {
          this.setState(r.state);
          T('Welcome back — you’re signed in.');
        }
      }, 450);
    });
  };
"""

# The membership "Choose <tier>" button is an inline closure in the render values,
# not a class field, so it is guarded in place.
TIER_SRC = 'onClick: () => { if (isCurrentPlan || tierDisabled) { return; }'
TIER_DST = ("onClick: () => { if (window.bsiAuth && window.bsiAuth.guard('membership', "
            "{ page: 'membership', state: { billing: s.billing } }, this.bsiAuthHint ? this.bsiAuthHint() : null)) { return; } "
            "if (isCurrentPlan || tierDisabled) { return; }")

# Inline Confirm-step card (owned by enrich_confirm): add "Create account" beside
# its "Sign in" and make both return to the booking.
SIGNIN_BTN_SRC = '<a class="cf-btn cf-btn--gold bsi-cf-signin__btn" href="{{ cf2SigninHref }}">Sign in</a>'
SIGNIN_BTN_DST = (
    '<div class="bsi-gate-inline">'
    '<a class="cf-btn cf-btn--gold bsi-cf-signin__btn" href="{{ cf2SigninHref }}">Sign in</a>'
    '<a class="bsi-gate-inline__signup" href="/web/signup?redirect=%2Fsalon%2Fbooking">Create account</a>'
    '</div>'
)

PATCHES = [
    ('Auth: membership tier guard', TIER_SRC, TIER_DST),
    ('Auth: resume after sign-in', '  componentDidMount() {',
     LOGIC_JS + '\n  componentDidMount() {\n    if (this._bsiAuthResume) { try { this._bsiAuthResume(); } catch (e) { /* never break the page */ } }'),
]

# Optional: the Confirm card belongs to enrich_confirm; when it is not there the
# dialog still covers the guard, so a miss is only logged at info level.
OPTIONAL_PATCHES = [
    ('Auth: Confirm sign-in card sign-up link', SIGNIN_BTN_SRC, SIGNIN_BTN_DST),
]

# Membership page loyalty wallet (as rendered by enrich_loyalty): a guest's rewards
# read "N more pts" and do nothing -- offer sign-in instead.
WALLET_SRC = (
    "state: can ? 'Book with it →' : ((r.cost - (s.loyaltyPoints || 0)) + ' more pts'),\n"
    "          onClick: can ? (() => this.redeemReward(r.id)) : null,\n"
    "          cursor: can ? 'pointer' : 'not-allowed',"
)
WALLET_DST = (
    "state: can ? 'Book with it →' : (!s.userLoggedIn ? 'Sign in to use →' "
    ": ((r.cost - (s.loyaltyPoints || 0)) + ' more pts')),\n"
    "          onClick: can ? (() => this.redeemReward(r.id)) "
    ": (!s.userLoggedIn ? (() => this.bsiAuthAsk('points')) : null),\n"
    "          cursor: (can || !s.userLoggedIn) ? 'pointer' : 'not-allowed',"
)
PATCHES.append(('Auth: wallet rewards sign-in', WALLET_SRC, WALLET_DST))

# Services page: a guest's "Sign in to use N pts" button was disabled (it keyed off
# canRedeemPoints) -- keep it clickable so it opens the sign-in dialog.
PATCHES.extend([
    ('Auth: services points sign-in value',
     'redeemPointsOnClick: sv.points ? (() => this.redeemServicePoints(sv.id)) : null,',
     'redeemPointsOnClick: sv.points ? (() => this.redeemServicePoints(sv.id)) : null, '
     'pointsSignIn: !!(sv.points && !s.userLoggedIn), '
     'pointsLocked: !(sv.points && s.userLoggedIn && (s.loyaltyPoints || 0) >= sv.points) && !(sv.points && !s.userLoggedIn),'),
    ('Auth: services points sign-in button',
     '<button sc-camel-on-click="{{ s.redeemPointsOnClick }}" disabled="{{ !s.canRedeemPoints }}"',
     '<button sc-camel-on-click="{{ s.redeemPointsOnClick }}" disabled="{{ s.pointsLocked }}"'),
])


def apply(page, data):
    """Sign-in gate for the page -- run LAST in _build_site."""
    for label, source, target in PATCHES:
        if source in page:
            page = page.replace(source, target, 1)
        else:
            _logger.warning('Enrich site: %s not found, left as designed', label)
    for label, source, target in OPTIONAL_PATCHES:
        if source in page:
            page = page.replace(source, target, 1)
        else:
            _logger.info('Enrich site: %s not found, dialog-only gate', label)

    anchor = '<script type="text/x-dc"'
    at = page.find(anchor)
    close = page.find('>', at) if at != -1 else -1
    if close == -1:
        _logger.warning('Enrich site: Auth x-dc script not found, sign-in gate not injected')
    else:
        page = page[:close + 1] + AUTH_JS + page[close + 1:]

    if '</helmet>' in page:
        page = page.replace('</helmet>', '<link rel="stylesheet" href="%s"/>\n</helmet>' % CSS_HREF, 1)
    else:
        _logger.warning('Enrich site: Auth </helmet> not found, styles not linked')
    return page
