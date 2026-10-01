# -*- coding: utf-8 -*-
"""Loyalty points on the website: what a customer sees, applies and spends.

Applied by BsiSalonWeb._build_site right after enrich_hero.apply (and before the
Confirm-step redesign in enrich_confirm), so the anchors below match the fully
patched template. A missing anchor only logs "not found, left as designed".

What it changes on the page (the server re-checks every figure -- see
_bsi_booking_quote / bsi_salon_api_booking in main.py):

  * Service points are opt-in per service: "Book · use N pts" on the Services page,
    or "Use N pts" next to the service on the Confirm step, adds that service to
    state.bookingPointsServiceIds, which is sent as points_service_ids. Only
    services switched on for the website (bsi_loyalty_website) carry points in
    SERVICES_DATA at all (see bsi.enrich.data._bsi_services).
  * Rewards cover several services: applying one (wallet "Book with it" or the
    Confirm step's reward list) adds all of its services; removing it takes them
    off again. Only rewards with "Show on Website" are listed (WALLET_REWARDS is
    always replaced, even when empty, so the design's sample rewards never show).
  * The balance shown everywhere (wallet, Services page, Confirm step) is the
    AVAILABLE balance: the real one minus what the booking in progress uses.
    It is restored when that booking is abandoned for a new one, and re-read from
    the server once a booking is confirmed (the points are only spent then).
  * Applying / removing a reward or service points calls window.bsiToast(msg,
    'success'|'error') when the page defines it (see enrich_confirm).

Stable hooks for styling: .bsi-perk-balance (+ -k / -v / -note), .bsi-perk-svc-line,
.bsi-perk-svc-label, .bsi-perk-svc-btn (.is-applied / .is-locked), #bsiPerkBalance.
"""

import logging

_logger = logging.getLogger(__name__)

CSS_LINK = ('<link rel="stylesheet" '
            'href="/bsi_salon_web/static/src/css/bsi_loyalty.css?v=1"/>\n</helmet>')

# ---------------------------------------------------------------------------
# State: new-booking resets, request params, balance bookkeeping
# ---------------------------------------------------------------------------

STATE_PATCHES = (
    # Every booking entry point goes through setPage(..., {bookingConfirmed: false, ...}).
    # A fresh booking forgets the previous one's points choices, reward and quote, and
    # gives back the points that booking was holding.
    ('loyalty: reset points on a new booking',
     "    if (extra && ('bookingConfirmed' in extra) && !('bookingColourLab' in extra)) "
     "{ extra = { ...extra, bookingColourLab: null }; }\n",
     "    if (extra && ('bookingConfirmed' in extra) && !('bookingColourLab' in extra)) "
     "{ extra = { ...extra, bookingColourLab: null }; }\n"
     "    if (extra && ('bookingConfirmed' in extra) && !extra.bookingConfirmed) { extra = { "
     "bookingPointsServiceIds: [], bookingRewardId: null, bookingRewardAddedSvc: [], bookingQuote: null, "
     "loyaltyPoints: (this.state.loyaltyBalance != null ? this.state.loyaltyBalance : (this.state.loyaltyPoints || 0)), "
     "...extra }; }\n"),

    ('loyalty: send the services paid with points',
     "      use_service_points: s.bookingUseServicePoints !== false,\n",
     "      use_service_points: s.bookingUseServicePoints !== false,\n"
     "      points_service_ids: (s.bookingPointsServiceIds || []).slice(),\n"),

    # The quote says how many points this booking uses; what is shown as the
    # customer's points is what they would have left.
    ('loyalty: available balance from the quote',
     "loyaltyPoints: L.balance || 0,",
     "loyaltyPoints: (L.available != null ? L.available : (L.balance || 0)), loyaltyBalance: L.balance || 0,"),

    ('loyalty: real balance on page load',
     "this.setState({ loyaltyPoints: res.points || 0, loyaltyPointValue: res.point_value || 1 });",
     "this.setState({ loyaltyPoints: res.points || 0, loyaltyBalance: res.points || 0, "
     "loyaltyPointValue: res.point_value || 1 });"),

    # Wallet / Services page start at "Book with it" and "Book · use N pts": both open
    # a booking with that choice already applied.
    ('loyalty: wallet reward opens a booking with all its services',
     "  redeemReward = (rewardId) => { const rpc = (url, params) => fetch(url, { method: \"POST\", "
     "credentials: \"same-origin\", headers: { \"Content-Type\": \"application/json\" }, body: "
     "JSON.stringify({ id: 1, jsonrpc: \"2.0\", method: \"call\", params: params }) }).then((r) => "
     "r.json()); void rpc; const rw = (WALLET_REWARDS || []).find((x) => x.id === rewardId) || {}; "
     "this.setPage('booking', { booking: { cityId: null, storeId: null, step: 1 }, selectedChairIds: [], "
     "selectedTime: null, bookingConfirmed: false, bookingRewardId: rewardId, bookingRewardAddedSvc: "
     "rw.service_id || null, bookingServiceIds: rw.service_id ? [rw.service_id] : [], bookingServiceId: "
     "null, bookingPackageId: null }); };\n",
     "  redeemReward = (rewardId) => { const rw = (WALLET_REWARDS || []).find((x) => x.id === rewardId) || {}; "
     "const ids = (rw.service_ids && rw.service_ids.length) ? rw.service_ids.slice() : (rw.service_id ? [rw.service_id] : []); "
     "this.setPage('booking', { booking: { cityId: null, storeId: null, step: 1 }, selectedChairIds: [], "
     "selectedTime: null, bookingConfirmed: false, bookingRewardId: rewardId, bookingRewardAddedSvc: ids.slice(), "
     "bookingServiceIds: ids, bookingServiceId: null, bookingPackageId: null, bookingPackageName: null, "
     "bookingPackagePrice: null, bookingPointsServiceIds: [] }); "
     "if (window.bsiToast) { window.bsiToast((rw.benefit || rw.name || 'Reward') + ' added to your booking · ' "
     "+ (rw.cost || 0) + ' pts are used when you confirm', 'success'); } };\n"),

    ('loyalty: "Book · use N pts" opens a booking paying with points',
     "  redeemServicePoints = (serviceId) => { const rpc = (url, params) => fetch(url, { method: \"POST\", "
     "credentials: \"same-origin\", headers: { \"Content-Type\": \"application/json\" }, body: "
     "JSON.stringify({ id: 1, jsonrpc: \"2.0\", method: \"call\", params: params }) }).then((r) => "
     "r.json()); void rpc; const svAll = [].concat.apply([], Object.keys(SERVICES_DATA).map((k) => "
     "SERVICES_DATA[k])); const sv = svAll.find((x) => x.id === serviceId) || {}; "
     "this.goBookingWithService(serviceId, sv.name || ''); };\n",
     "  redeemServicePoints = (serviceId) => { const svAll = [].concat.apply([], Object.keys(SERVICES_DATA).map((k) => "
     "SERVICES_DATA[k])); const sv = svAll.find((x) => x.id === serviceId) || {}; "
     "this.setPage('booking', { booking: { cityId: null, storeId: null, step: 1 }, selectedChairIds: [], "
     "selectedTime: null, bookingConfirmed: false, bookingServiceId: null, bookingServiceIds: [serviceId], "
     "bookingServiceName: sv.name || '', bookingPackageId: null, bookingPackageName: null, bookingPackagePrice: null, "
     "bookingPointsServiceIds: [serviceId] }); "
     "if (window.bsiToast) { window.bsiToast((sv.name || 'Service') + ' · ' + (sv.points || 0) + "
     "' pts will be applied to this booking', 'success'); } };\n"),

    # "Book ->" on one service used to keep whatever services an earlier, unfinished
    # booking had picked (bookingServiceIds wins over bookingServiceId on the Service step).
    ('loyalty: "Book" on a service starts from that service only',
     "  goBookingWithService = (serviceId, serviceName) => this.setPage('booking', { booking: { cityId: "
     "null, storeId: null, step: 1 }, selectedChairIds: [], selectedTime: null, bookingConfirmed: false, "
     "bookingServiceId: serviceId, bookingServiceName: serviceName });\n",
     "  goBookingWithService = (serviceId, serviceName) => this.setPage('booking', { booking: { cityId: "
     "null, storeId: null, step: 1 }, selectedChairIds: [], selectedTime: null, bookingConfirmed: false, "
     "bookingServiceId: serviceId, bookingServiceIds: serviceId ? [serviceId] : [], bookingServiceName: serviceName });\n"),
)

# ---------------------------------------------------------------------------
# Confirm step actions: rewards, per-service points, toasts
# ---------------------------------------------------------------------------

USE_REWARD_SRC = (
    "  bsiUseReward = (r) => {\n"
    "    const s = this.state; const patch = { bookingRewardId: r.id, bookingRewardAddedSvc: null };\n"
    "    const ov = { reward_id: r.id };\n"
    "    if (r.service_id && !s.bookingPackageId) {\n"
    "      const ids = (s.bookingServiceIds && s.bookingServiceIds.length) ? s.bookingServiceIds.slice() : (s.bookingServiceId ? [s.bookingServiceId] : []);\n"
    "      if (ids.indexOf(r.service_id) < 0) { ids.push(r.service_id); patch.bookingRewardAddedSvc = r.service_id; }\n"
    "      patch.bookingServiceIds = ids; ov.selected_service_ids = ids;\n"
    "    }\n"
    "    this.setState(patch);\n"
    "    this.bsiFetchQuote(ov);\n"
    "  };\n"
    "  bsiClearReward = () => {\n"
    "    const s = this.state; const patch = { bookingRewardId: null, bookingRewardAddedSvc: null };\n"
    "    const ov = { reward_id: null };\n"
    "    if (s.bookingRewardAddedSvc) {\n"
    "      patch.bookingServiceIds = (s.bookingServiceIds || []).filter((id) => id !== s.bookingRewardAddedSvc);\n"
    "      ov.selected_service_ids = patch.bookingServiceIds;\n"
    "    }\n"
    "    this.setState(patch);\n"
    "    this.bsiFetchQuote(ov);\n"
    "  };\n"
    "  bsiToggleServicePoints = () => {\n"
    "    const on = this.state.bookingUseServicePoints === false;\n"
    "    this.setState({ bookingUseServicePoints: on });\n"
    "    this.bsiFetchQuote({ use_service_points: on });\n"
    "  };\n"
)
USE_REWARD_DST = (
    # Re-price, then report the outcome through the page's toast (if it has one).
    "  bsiQuoteToast = (ov, pick) => this.bsiFetchQuote(ov).then(() => { if (!pick) { return; } "
    "setTimeout(() => { const t = pick(this.state.bookingQuote || {}); "
    "if (t && window.bsiToast) { window.bsiToast(t[1], t[0]); } }, 0); });\n"
    "  bsiRewardServiceIds = (r) => (r && r.service_ids && r.service_ids.length) ? r.service_ids.slice() : ((r && r.service_id) ? [r.service_id] : []);\n"
    # Applying a reward adds every one of its services (switching from another reward
    # first drops the services that one added).
    "  bsiUseReward = (r) => {\n"
    "    const s = this.state; const prev = [].concat(s.bookingRewardAddedSvc || []);\n"
    "    const want = (r.type === 'service' && !s.bookingPackageId) ? this.bsiRewardServiceIds(r) : [];\n"
    "    let ids = (s.bookingServiceIds && s.bookingServiceIds.length) ? s.bookingServiceIds.slice() : (s.bookingServiceId ? [s.bookingServiceId] : []);\n"
    "    ids = ids.filter((id) => prev.indexOf(id) < 0 || want.indexOf(id) >= 0);\n"
    "    const added = [];\n"
    "    want.forEach((id) => { if (ids.indexOf(id) < 0) { ids.push(id); added.push(id); } else if (prev.indexOf(id) >= 0) { added.push(id); } });\n"
    "    const patch = { bookingRewardId: r.id, bookingRewardAddedSvc: added, bookingServiceIds: ids, bookingServiceId: null };\n"
    "    const ov = { reward_id: r.id, selected_service_ids: ids };\n"
    "    this.setState(patch);\n"
    "    this.bsiQuoteToast(ov, (q) => {\n"
    "      const RW = q.reward || {};\n"
    "      if (RW.id === r.id) { return ['success', (r.benefit || r.name) + ' applied · ' + (RW.points || r.cost || 0) + ' pts used on this booking']; }\n"
    "      this.bsiClearReward(true);\n"
    "      return ['error', RW.error || 'That reward could not be applied.'];\n"
    "    });\n"
    "  };\n"
    "  bsiClearReward = (silent) => {\n"
    "    const s = this.state; const added = [].concat(s.bookingRewardAddedSvc || []);\n"
    "    const patch = { bookingRewardId: null, bookingRewardAddedSvc: [] };\n"
    "    const ov = { reward_id: null };\n"
    "    if (added.length) {\n"
    "      patch.bookingServiceIds = (s.bookingServiceIds || []).filter((id) => added.indexOf(id) < 0);\n"
    "      ov.selected_service_ids = patch.bookingServiceIds;\n"
    "    }\n"
    "    this.setState(patch);\n"
    "    this.bsiQuoteToast(ov, silent === true ? null : () => ['success', 'Reward removed · the points are back in your balance']);\n"
    "  };\n"
    # One service's own points, on or off.
    "  bsiToggleServicePointsFor = (id) => {\n"
    "    const cur = (this.state.bookingPointsServiceIds || []).slice(); const at = cur.indexOf(id); const on = at < 0;\n"
    "    if (on) { cur.push(id); } else { cur.splice(at, 1); }\n"
    "    this.setState({ bookingPointsServiceIds: cur, bookingUseServicePoints: true });\n"
    "    this.bsiQuoteToast({ points_service_ids: cur, use_service_points: true }, (q) => {\n"
    "      const line = ((q.service_points || {}).lines || []).find((l) => l.id === id) || {};\n"
    "      const name = line.name || 'Service';\n"
    "      if (!on) { return ['success', name + ': points removed · back in your balance']; }\n"
    "      if (line.applied) { return ['success', name + ': ' + line.points + ' pts applied · −₹' + Math.round(line.amount || 0)]; }\n"
    "      const left = (this.state.bookingPointsServiceIds || []).filter((x) => x !== id);\n"
    "      this.setState({ bookingPointsServiceIds: left }); this.bsiFetchQuote({ points_service_ids: left });\n"
    "      return ['error', 'Not enough points for ' + name + ' (' + (line.points || 0) + ' pts needed)'];\n"
    "    });\n"
    "  };\n"
    # The panel's own "use / don't use service points" link: all eligible services, or none.
    "  bsiToggleServicePoints = () => {\n"
    "    const q = this.state.bookingQuote || {}; const lines = ((q.service_points || {}).lines || []);\n"
    "    const anyOn = (this.state.bookingPointsServiceIds || []).length > 0;\n"
    "    const cur = anyOn ? [] : lines.map((l) => l.id);\n"
    "    this.setState({ bookingPointsServiceIds: cur, bookingUseServicePoints: true });\n"
    "    this.bsiQuoteToast({ points_service_ids: cur, use_service_points: true }, (q2) => {\n"
    "      const SP = q2.service_points || {};\n"
    "      if (anyOn) { return ['success', 'Service points removed · back in your balance']; }\n"
    "      if (SP.points) { return ['success', SP.points + ' pts applied to your services']; }\n"
    "      this.setState({ bookingPointsServiceIds: [] });\n"
    "      return ['error', 'Not enough points for these services yet.'];\n"
    "    });\n"
    "  };\n"
    # Once a booking is confirmed its points really are spent: read the real balance back.
    "  bsiLoyaltyAfterConfirm = (s) => {\n"
    "    if (!s.bookingConfirmed || !s.bookingQuote || this._bsiLoyaltySynced === s.bookingQuote) { return ''; }\n"
    "    this._bsiLoyaltySynced = s.bookingQuote;\n"
    "    setTimeout(() => { this.bsiRpc('/salon/api/loyalty_status', {}).then((res) => {\n"
    "      if (res && res.points != null) { this.setState({ loyaltyPoints: res.points || 0, loyaltyBalance: res.points || 0 }); }\n"
    "    }).catch(function () {}); }, 0);\n"
    "    return '';\n"
    "  };\n"
)

ACTION_PATCHES = (
    ('loyalty: reward / service points actions', USE_REWARD_SRC, USE_REWARD_DST),
)

# ---------------------------------------------------------------------------
# Render values: wallet, Services page, Confirm step
# ---------------------------------------------------------------------------

VALUE_PATCHES = (
    ('loyalty: sync balance after confirm',
     "walletPoints: (s.loyaltyPoints || 0),",
     "bsiLoyaltySync: this.bsiLoyaltyAfterConfirm(s), walletPoints: (s.loyaltyPoints || 0),"),

    # A reward already applied to the booking in progress holds its own cost -- it
    # still counts as affordable for that reward's own card.
    ('loyalty: wallet reward affordability',
     "const can = (s.loyaltyPoints || 0) >= r.cost;",
     "const bsiHeld = (s.bookingRewardId === r.id && s.bookingQuote && !s.bookingConfirmed) ? r.cost : 0; "
     "const can = ((s.loyaltyPoints || 0) + bsiHeld) >= r.cost;"),

    ('loyalty: services page points button',
     "canRedeemPoints: !!(sv.points && (s.loyaltyPoints || 0) >= sv.points), redeemPointsLabel: sv.points ? "
     "('Book · use ' + sv.points + ' pts') : '',",
     "canRedeemPoints: !!(sv.points && s.userLoggedIn && (s.loyaltyPoints || 0) >= sv.points), "
     "redeemPointsLabel: sv.points ? (!s.userLoggedIn ? ('Sign in to use ' + sv.points + ' pts') "
     ": ((s.loyaltyPoints || 0) >= sv.points ? ('Book · use ' + sv.points + ' pts') "
     ": ('Need ' + (sv.points - (s.loyaltyPoints || 0)) + ' more pts'))) : '',"),

    ('loyalty: confirm available points',
     "const ptsLeft = (L.remaining != null) ? L.remaining : (L.balance || 0);",
     "const ptsLeft = (L.remaining != null) ? L.remaining : (L.balance || 0);\n"
     "        const ptsAvail = (L.available != null) ? L.available : ptsLeft;\n"
     "        const ptsUsed = (L.used != null) ? L.used : Math.max(0, (L.balance || 0) - ptsAvail);"),

    ('loyalty: confirm free reward services',
     "const rwFreeSvc = rwApplied && rwApplied.type === 'service' ? rwApplied.service_id : null;",
     "const rwFreeIds = rwApplied && rwApplied.type === 'service' ? ((rwApplied.service_ids && rwApplied.service_ids.length) "
     "? rwApplied.service_ids : [rwApplied.service_id]) : [];\n"
     "        const spById = {}; (SP.lines || []).forEach((l) => { if (l.applied) { spById[l.id] = l; } });"),

    ('loyalty: confirm service lines',
     "meta: (rwFreeSvc === rec.id ? ('Free with your ' + pts(rwApplied.cost) + '-pt reward') : (rec.duration || '')), "
     "price: (rwFreeSvc === rec.id ? 'FREE' : money(rec.price_amount || 0))",
     "meta: (rwFreeIds.indexOf(rec.id) >= 0 ? ('Free with your ' + pts(rwApplied.cost) + '-pt reward') "
     ": (spById[rec.id] ? ((rec.duration ? rec.duration + ' · ' : '') + pts(spById[rec.id].points) + ' pts applied · −' + money(spById[rec.id].amount)) "
     ": (rec.duration || ''))), "
     "price: (rwFreeIds.indexOf(rec.id) >= 0 ? 'FREE' : money(rec.price_amount || 0))"),

    ('loyalty: confirm reward sub-line',
     "cfRewardSub: RW.id ? (pts(RW.points) + ' pts used · ' + RW.name) : ('You have ' + pts(L.balance) + ' pts — use a reward on this booking'),",
     "cfRewardSub: RW.id ? (pts(RW.points) + ' pts used · ' + RW.name) : ('You have ' + pts(ptsAvail) + ' pts available — use a reward on this booking'),"),

    ('loyalty: confirm reward points needed',
     "(pts(Math.max(0, r.cost - (L.balance || 0))) + ' more pts')",
     "('Need ' + pts(r.needed != null ? r.needed : Math.max(0, r.cost - (L.balance || 0))) + ' more pts')"),

    ('loyalty: confirm balance summary values',
     "bsiRewardError: RW.error || '',",
     "bsiRewardError: RW.error || '',\n"
     "          bsiPtsShow: !!F.loyalty && loggedIn && ((L.balance || 0) > 0 || ptsUsed > 0),\n"
     "          bsiPtsLeft: pts(ptsAvail) + ' pts',\n"
     "          bsiPtsNote: ptsUsed > 0 ? (pts(ptsUsed) + ' of your ' + pts(L.balance) + ' pts go on this booking · used when you confirm') "
     ": ('available · worth ' + money(ptsAvail * (L.point_value || 1))),"),

    ('loyalty: confirm service points lines',
     "          cfSvcPtsLines: (SP.lines || []).map((l) => ({ label: l.name + ' · ' + pts(l.points) + ' pts = ' + money(l.amount) + ' off'\n"
     "            + (l.applied ? '' : (SP.enabled ? ' · needs ' + pts(l.points) + ' pts' : '')) })),\n"
     "          cfSvcPtsToggle: SP.enabled ? 'Don’t use service points' : 'Use service points',\n",
     "          cfSvcPtsLines: (SP.lines || []).map((l) => { const can = l.applied || l.points <= ptsAvail; return {\n"
     "            label: l.name + ' · ' + pts(l.points) + ' pts = ' + money(l.amount) + ' off'\n"
     "              + (l.applied ? ' · applied' : (can ? '' : (' · need ' + pts(l.points - ptsAvail) + ' more pts'))),\n"
     "            cls: 'bsi-perk-svc-btn' + (l.applied ? ' is-applied' : (can ? '' : ' is-locked')),\n"
     "            action: l.applied ? 'Remove' : ('Use ' + pts(l.points) + ' pts'),\n"
     "            disabled: !l.applied && !can,\n"
     "            onClick: (l.applied || can) ? (() => this.bsiToggleServicePointsFor(l.id)) : null }; }),\n"
     "          cfSvcPtsToggle: SP.points ? 'Don’t use service points' : 'Use points on all',\n"),

    # "N more to go" counts from what is left after this booking's reward / service
    # points, not from the whole balance.
    ('loyalty: confirm points still needed to redeem',
     "+ pts(Math.max(0, (L.min_points || 0) - (L.balance || 0))) + ' more to go.')",
     "+ pts(Math.max(0, (L.min_points || 0) - ptsLeft)) + ' more to go.')"),

    ('loyalty: confirm service points tag',
     "cfSvcPtsTag: SP.points ? 'Applied' : (SP.enabled ? 'Not enough points' : 'Not used'),",
     "cfSvcPtsTag: SP.points ? 'Applied' : ((SP.lines || []).some((l) => l.points <= ptsAvail) ? 'Available' : 'Not enough points'),"),
)

# ---------------------------------------------------------------------------
# Markup: balance line and per-service buttons in the Perks panel
# ---------------------------------------------------------------------------

MARKUP_PATCHES = (
    ('loyalty: perks balance line',
     '<div class="cf-perks-list">',
     '<div class="cf-perks-list">\n'
     '                  <sc-if value="{{ bsiPtsShow }}" hint-placeholder-val="{{ false }}">\n'
     '                    <div class="bsi-perk-balance" id="bsiPerkBalance">'
     '<span class="bsi-perk-balance-k">Your loyalty points</span>'
     '<span class="bsi-perk-balance-v">{{ bsiPtsLeft }}</span>'
     '<span class="bsi-perk-balance-note">{{ bsiPtsNote }}</span></div>\n'
     '                  </sc-if>'),

    ('loyalty: per-service points buttons',
     '<sc-for list="{{ cfSvcPtsLines }}" as="sp" hint-placeholder-count="1"><div class="cf-perk-sub">{{ sp.label }}</div></sc-for>',
     '<sc-for list="{{ cfSvcPtsLines }}" as="sp" hint-placeholder-count="1"><div class="cf-perk-sub bsi-perk-svc-line">'
     '<span class="bsi-perk-svc-label">{{ sp.label }}</span>'
     '<button type="button" class="{{ sp.cls }}" sc-camel-on-click="{{ sp.onClick }}" disabled="{{ sp.disabled }}">{{ sp.action }}</button>'
     '</div></sc-for>'),
)


def _patch(page, patches):
    for label, source, target in patches:
        if source in page:
            page = page.replace(source, target, 1)
        else:
            _logger.warning('Enrich site: %s not found, left as designed', label)
    return page


def apply(page, data):
    """Loyalty patches over the fully patched template (see module docstring)."""
    # WALLET_REWARDS is only substituted by _build_site when the backend has rewards
    # to show; with none switched on for the website the design's sample rewards
    # would stay -- replace them with the (empty) real list.
    if not data.get('loyalty_rewards'):
        from . import main as _main  # local: main imports this module
        page = _main._replace_literal(page, 'WALLET_REWARDS', [])

    page = _patch(page, STATE_PATCHES)
    page = _patch(page, ACTION_PATCHES)
    page = _patch(page, VALUE_PATCHES)
    page = _patch(page, MARKUP_PATCHES)

    if '</helmet>' in page:
        page = page.replace('</helmet>', CSS_LINK, 1)
    else:
        _logger.warning('Enrich site: loyalty stylesheet anchor not found, left as designed')
    return page
