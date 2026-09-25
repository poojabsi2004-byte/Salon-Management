# -*- coding: utf-8 -*-
"""PHASE 1 BRIDGE -- handler patches applied to the design as it is served.

Each entry is an (anchor, replacement) pair against the design's own page source.
The design ships three controls that are wired to nothing: the booking confirm
button, the membership Choose-tier button, and the contact form. Phase 1 gives
each of them a real backend call without altering a pixel of markup or styling.

Anchors are exact strings taken from the export. If one stops matching -- after a
re-export, say -- that single patch is skipped and the design keeps its original
behaviour, rather than the page failing to load.

No Phase 1 patch adds, removes or restyles any element. Field additions to the
booking wizard (date, services, guest details) are Phase 3 and deliberately absent.
"""

# --- Deep-linkable pages -----------------------------------------------------
# Was: `page` lived only in memory -- every /salon/<page> route served the exact
# same HTML (see BsiSalonWeb.bsi_salon_pages) and the app always opened on
# Home regardless of the URL, so a refresh (or a shared link, or the back
# button) on Services/Stylists/etc. silently bounced back to Home. Now: the
# initial page is read off the URL the browser actually loaded, and every
# in-app navigation updates the URL to match (see NAV_URL_DST) -- refreshing
# on /salon/services now reopens on Services, exactly the routes
# bsi_salon_pages already registers server-side and always could have served.
NAV_INITIAL_SRC = "state = {\n    page: 'home',"
NAV_INITIAL_DST = (
    "state = {\n"
    "    page: (function () {\n"
    "      var m = (window.location.pathname || '').match(/^\\/salon\\/([a-z]+)/);\n"
    "      var known = ['home', 'stores', 'booking', 'membership', 'services', 'stylists', 'about', 'contact'];\n"
    "      return (m && known.indexOf(m[1]) !== -1) ? m[1] : 'home';\n"
    "    })(),"
)

NAV_URL_SRC = (
    "  setPage = (p, extra) => {\n"
    "    if (p === this.state.page && !extra) return;"
)
NAV_URL_DST = (
    "  setPage = (p, extra) => {\n"
    "    if (p === this.state.page && !extra) return;\n"
    "    try { if (window.history && window.history.pushState) { "
    "window.history.pushState({}, '', '/salon/' + p); } } catch (e) {}"
)

# --- Booking confirm ------------------------------------------------------
# Was: set a flag and show the ticket, unconditionally, the instant the click
# happened -- the actual /salon/api/booking call was fire-and-forget, its
# result never even read. A real, expected rejection (the shared slot-capacity
# constraint: this exact chair or artist already taken for this exact slot --
# see bsi_salon_booking_mixin._bsi_check_slot_capacity_common, which is common
# the instant two customers reach the same open-looking chair within seconds
# of each other) still showed the customer a "Confirmed" ticket with no lead
# ever created -- reproduced live, and matches a user report of appointments
# silently not being generated. Now: the ticket only ever appears once the
# server actually confirms res.ok; a rejection instead shows why, right on
# the Confirm screen, so the customer can go back and pick a different chair
# or time instead of walking in to a booking that was never made.
CONFIRM_SRC = 'confirmBooking = () => this.setState({ bookingConfirmed: true });'
CONFIRM_DST = (
    'confirmBooking = () => { const s = this.state; '
    'const city = CITIES.find((c) => c.id === s.booking.cityId) || null; '
    'const store = city ? (city.branches.find((b) => b.id === s.booking.storeId) || null) : null; '
    'const artist = (typeof s.bookingStylist === "number") ? STYLISTS[s.bookingStylist] : null; '
    'this.setState({ bookingError: false, bookingSubmitting: true }); '
    'fetch("/salon/api/booking", { method: "POST", credentials: "same-origin", '
    'headers: { "Content-Type": "application/json" }, body: JSON.stringify({ '
    'id: 1, jsonrpc: "2.0", method: "call", params: { '
    'location_id: store ? store.id : null, slot_label: s.selectedTime || null, '
    'chair_numbers: s.selectedChairIds || [], is_member: !!s.hasActiveMembership, '
    'city_name: city ? city.name : null, store_name: store ? store.name : null, '
    'reward_service_id: s.rewardServiceId || null, '
    'artist_id: artist ? artist.id : null, '
    'look_length: s.bookingLookLength || null, look_shade_index: s.bookingLookShadeIndex, '
    'look_finish: s.bookingLookFinish || null, addon_keys: s.ritual || [], '
    'selected_service_id: s.bookingServiceId || null, '
    'selected_service_ids: (s.bookingServiceIds && s.bookingServiceIds.length) ? s.bookingServiceIds : [], '
    'package_id: s.bookingPackageId || null } }) '
    '}).then(function (r) { return r.json(); }).then((payload) => { '
    'const res = (payload && payload.result) || {}; '
    'if (res.ok) { this.setState({ bookingConfirmed: true, bookingError: false, bookingSubmitting: false }); } '
    'else { this.setState({ bookingSubmitting: false, bookingError: res.error '
    '|| "That chair or time was just taken. Please go back and pick another." }); } '
    '}).catch(() => { this.setState({ bookingSubmitting: false, '
    'bookingError: "Something went wrong. Please try again." }); }); };'
)

BOOKING_ERROR_STATE_SRC = "    bookingConfirmed: false,"
BOOKING_ERROR_STATE_DST = (
    "    bookingConfirmed: false, bookingError: false, bookingSubmitting: false, bookingMaxStep: 1,"
)

# --- Booking Confirm screen -- show a real rejection instead of hiding it ---
# Was: the "Confirm Booking" button had no failure state to render at all --
# see CONFIRM_DST above for why one is now needed. Superseded by
# SUMMARY_TOTAL_SRC/DST below, which redesigns the whole total+button block
# together and fixes a ternary-in-markup bug this version had (see that
# patch's own comment) -- kept only as a reminder of why the error banner
# exists at all, not applied itself any more.

# --- Membership purchase --------------------------------------------------
# The Choose-tier button was an empty function. It now runs the salon's own
# purchase path: resolve the tier's product, add it to the standard cart, then
# hand over to Odoo checkout.
TIER_CTA_SRC = "btnLabel: 'Choose ' + t.name,\n        onClick: () => {},"
TIER_CTA_DST = (
    "btnLabel: 'Choose ' + t.name,\n        onClick: () => { if (!t.id) { return; } "
    'const rpc = (url, params) => fetch(url, { method: "POST", credentials: "same-origin", '
    'headers: { "Content-Type": "application/json" }, '
    'body: JSON.stringify({ id: 1, jsonrpc: "2.0", method: "call", params: params }) '
    '}).then((r) => r.json()); '
    'rpc("/salon/api/membership_product", { membership_id: t.id, billing_period: s.billing }) '
    '.then((payload) => { const res = (payload && payload.result) || {}; '
    'if (!res.product_id) { throw new Error("no product"); } '
    'return rpc("/shop/cart/add", { product_id: res.product_id, '
    'product_template_id: res.product_template_id, quantity: 1 }); }) '
    '.then(() => { window.location.href = "/shop/checkout"; }) '
    '.catch(() => {}); },'
)

# --- Membership page -- one active plan at a time, reflected on the site ----
# Was: every tier's "Choose" button worked identically regardless of whether the
# signed-in visitor already had a plan running -- nothing stopped them
# attempting (and paying for) a second one, which the backend then has to
# quietly leave in Draft until the first is cancelled/expires (see
# bsi.salon.membership.subscription._bsi_create_or_extend). Now: the same
# componentDidMount call that already asks /salon/api/membership_status for
# the booking wizard's discount checkbox (see MOUNT_DST) also drives this --
# the visitor's own active tier shows "Current Plan" and cannot be re-bought,
# every other tier is disabled with an explanatory label instead of silently
# accepting a payment that would only ever sit unused in Draft.
TIER_CURRENT_SRC = "const popular = !!t.popular;"
TIER_CURRENT_DST = (
    "const isCurrentPlan = !!(s.hasActiveMembership && t.name === s.membershipTierName); "
    "const tierDisabled = !!(s.hasActiveMembership && t.name !== s.membershipTierName); "
    "const popular = !!t.popular && !isCurrentPlan;"
)

TIER_CURRENT_FIELDS_SRC = "name: t.name, price, perks: t.perks, popular,"
TIER_CURRENT_FIELDS_DST = (
    "name: t.name, price, perks: t.perks, popular, isCurrentPlan, tierDisabled,"
)

TIER_GATE_SRC = TIER_CTA_DST
TIER_GATE_DST = (
    "btnLabel: isCurrentPlan ? 'Current Plan' "
    ": (tierDisabled ? 'Cancel Current Plan First' : ('Choose ' + t.name)),\n"
    "        onClick: () => { if (isCurrentPlan || tierDisabled) { return; } if (!t.id) { return; } "
    'const rpc = (url, params) => fetch(url, { method: "POST", credentials: "same-origin", '
    'headers: { "Content-Type": "application/json" }, '
    'body: JSON.stringify({ id: 1, jsonrpc: "2.0", method: "call", params: params }) '
    '}).then((r) => r.json()); '
    'rpc("/salon/api/membership_product", { membership_id: t.id, billing_period: s.billing }) '
    '.then((payload) => { const res = (payload && payload.result) || {}; '
    'if (!res.product_id) { throw new Error("no product"); } '
    'return rpc("/shop/cart/add", { product_id: res.product_id, '
    'product_template_id: res.product_template_id, quantity: 1 }); }) '
    '.then(() => { window.location.href = "/shop/checkout"; }) '
    '.catch(() => {}); },'
)

TIER_MARKUP_SRC = (
    '            <sc-if value="{{ t.popular }}" hint-placeholder-val="{{ false }}">\n'
    '              <div style="position:absolute;top:-13px;right:26px;background:#e8283f;color:#161213;'
    'font-size:11px;font-weight:800;letter-spacing:.4px;padding:5px 14px;border-radius:4px;">MOST POPULAR</div>\n'
    '            </sc-if>'
)
TIER_MARKUP_DST = (
    '            <sc-if value="{{ t.popular }}" hint-placeholder-val="{{ false }}">\n'
    '              <div style="position:absolute;top:-13px;right:26px;background:#e8283f;color:#161213;'
    'font-size:11px;font-weight:800;letter-spacing:.4px;padding:5px 14px;border-radius:4px;">MOST POPULAR</div>\n'
    '            </sc-if>\n'
    '            <sc-if value="{{ t.isCurrentPlan }}" hint-placeholder-val="{{ false }}">\n'
    '              <div style="position:absolute;top:-13px;right:26px;background:#161213;color:#fdf3ea;'
    'font-size:11px;font-weight:800;letter-spacing:.4px;padding:5px 14px;border-radius:4px;">CURRENT PLAN</div>\n'
    '            </sc-if>'
)

TIER_BUTTON_SRC = (
    '<button sc-camel-on-click="{{ t.onClick }}" style="width:100%;background:{{ t.btnBg }};'
    'color:{{ t.btnColor }};border:{{ t.btnBorder }};padding:14px;border-radius:4px;font-weight:700;'
    'cursor:pointer;">{{ t.btnLabel }}</button>'
)
TIER_BUTTON_DST = (
    '<button sc-camel-on-click="{{ t.onClick }}" disabled="{{ t.tierDisabled }}" '
    'style="width:100%;background:{{ t.tierDisabled ? \'rgba(20,17,17,.12)\' : t.btnBg }};'
    'color:{{ t.tierDisabled ? \'#9b9093\' : t.btnColor }};border:{{ t.btnBorder }};padding:14px;'
    'border-radius:4px;font-weight:700;cursor:{{ t.tierDisabled ? \'not-allowed\' : \'pointer\' }};">'
    '{{ t.btnLabel }}</button>'
)

# --- "Book this look" -- auto-fetch the customer's own city -----------------
# Was: goBookingNav, same as every other "Book Now" control -- always starts
# at step 1, city unset. Now: goBookingFromLook asks which city the signed-in
# customer is in (their contact address; guests get nothing back) and, when
# it is one the site knows, skips straight to branch selection there --
# branch itself stays a real choice, never auto-picked.
LOOK_METHOD_SRC = (
    "goBookingNav = () => this.setPage('booking', { booking: { cityId: null, storeId: null, "
    "step: 1 }, selectedChairIds: [], selectedTime: null, bookingConfirmed: false });"
)
LOOK_METHOD_DST = LOOK_METHOD_SRC + (
    "\n  goBookingFromLook = () => { "
    'const rpc = (url, params) => fetch(url, { method: "POST", credentials: "same-origin", '
    'headers: { "Content-Type": "application/json" }, '
    'body: JSON.stringify({ id: 1, jsonrpc: "2.0", method: "call", params: params }) '
    '}).then((r) => r.json()); '
    # Snapshot the configurator's own state right now -- length/shade/finish live on
    # this.state as design-your-look UI selections with no memory of their own past
    # this click, so they have to be copied into the booking's own state here or
    # they're gone the instant the page navigates away from Home.
    "const lookLength = this.state.lookLength || 'mid'; "
    "const lookShadeIndex = this.state.lookShade || 0; "
    "const lookFinish = this.state.lookFinish || 'gloss'; "
    # Same base + surcharge maths the "Your brief" card itself uses (see
    # PRICE_BASE_DST/LENGTH_SURCHARGE_DST/SHADE_SURCHARGE_DST/FINISH_SURCHARGE_DST
    # below) -- snapshotting the number now means the booking wizard's own
    # Confirm screen can show this real estimate instead of its generic ₹999
    # placeholder (see BASEPRICE_DST).
    "const lookLengthRec = (BSI_LOOK_LENGTHS.find(function (l) { return l.id === lookLength; }) || {}); "
    "const lookShadeRec = (LOOK_SHADES[lookShadeIndex] || {}); "
    "const lookFinishRec = (BSI_LOOK_FINISHES.find(function (f) { return f.id === lookFinish; }) || {}); "
    "const lookPriceTotal = BSI_LOOK_BASE_PRICE + (lookLengthRec.surcharge || 0) "
    "+ (lookShadeRec.surcharge || 0) + (lookFinishRec.surcharge || 0); "
    'const start = (cityId) => this.setPage("booking", { booking: { cityId: cityId || null, '
    'storeId: null, step: cityId ? 2 : 1 }, selectedChairIds: [], selectedTime: null, '
    "bookingConfirmed: false, bookingLookLength: lookLength, "
    "bookingLookShadeIndex: lookShadeIndex, bookingLookFinish: lookFinish, "
    "bookingLookPrice: lookPriceTotal }); "
    'rpc("/salon/api/customer_city", {}) '
    '.then((payload) => { const res = (payload && payload.result) || {}; start(res.city_id); }) '
    ".catch(() => start(null)); };"
)

LOOK_NAV_EXPOSE_SRC = (
    'goHome: this.goHome, goServices: this.goServices, goMembership: this.goMembership, '
    'goBookingNav: this.goBookingNav,'
)
LOOK_NAV_EXPOSE_DST = LOOK_NAV_EXPOSE_SRC + ' goBookingFromLook: this.goBookingFromLook,'

LOOK_BUTTON_SRC = (
    '<button sc-camel-on-click="{{ goBookingNav }}" style="background:#e8283f;color:#fff;'
    'border:none;padding:15px 26px;border-radius:11px;font-size:14px;font-weight:700;'
    'cursor:pointer;box-shadow:0 14px 32px -14px rgba(232,40,63,.95);transition:transform .2s;" '
    'style-hover="transform:translateY(-2px);">Book this look →</button>'
)
LOOK_BUTTON_DST = (
    '<button sc-camel-on-click="{{ goBookingFromLook }}" style="background:#e8283f;color:#fff;'
    'border:none;padding:15px 26px;border-radius:11px;font-size:14px;font-weight:700;'
    'cursor:pointer;box-shadow:0 14px 32px -14px rgba(232,40,63,.95);transition:transform .2s;" '
    'style-hover="transform:translateY(-2px);">Book this look →</button>'
)

# --- Booking step indicator -- clickable to jump back --------------------
# Was: 1-2-3-4-5 display only, no way back except the single-step Back
# button. Now: any step already reached (n <= current) jumps straight there
# on click, same as clicking "2" from step 4 goes directly to Store. A step
# not reached yet (n > current) stays inert -- nothing chosen for it yet to
# jump forward to.
STEPS_COMPUTE_SRC = (
    "const bookingSteps = bookingStepsDefs.map((b) => ({\n"
    "      ...b,\n"
    "      circleBg: b.n === step ? wine : (b.n < step ? '#e8283f' : '#f0e2d8'),\n"
    "      circleColor: b.n <= step ? '#ffffff' : '#a5898f',\n"
    "      labelColor: b.n === step ? wine : '#a5898f',\n"
    "    }));"
)
# PHASE 3 DEV: was keyed purely on the CURRENT step, so a step already reached
# and filled in (Chair, Time...) greyed back out and stopped being clickable
# the moment the customer stepped BACK past it -- reproduced live: fill in
# 1-5, jump back to 3, and 4/5 lose their colour and their click handler even
# though nothing about them was cleared (see the CHAIRS_STORE_DST/STEP_*_NEXT
# patches -- going back and forward again already keeps the data, this was
# only ever the indicator's own display/click logic). Now: bookingMaxStep (see
# each *_SRC/DST forward-transition patch bumping it, and the default state
# addition in BOOKING_ERROR_STATE_DST) tracks the furthest step ever reached
# this session, and reached (not the current step) drives colour/click, so
# stepping back never re-locks a step already filled in.
STEPS_COMPUTE_DST = (
    "const bookingReachedStep = Math.max(s.bookingMaxStep || 1, step);\n"
    "    const bookingSteps = bookingStepsDefs.map((b) => ({\n"
    "      ...b,\n"
    "      circleBg: b.n === step ? wine : (b.n <= bookingReachedStep ? '#e8283f' : '#f0e2d8'),\n"
    "      circleColor: b.n <= bookingReachedStep ? '#ffffff' : '#a5898f',\n"
    "      labelColor: b.n === step ? wine : '#a5898f',\n"
    "      onClick: b.n <= bookingReachedStep ? (() => this.setState((s2) => "
    "({ booking: { ...s2.booking, step: b.n } }))) : null,\n"
    "      cursor: b.n <= bookingReachedStep ? 'pointer' : 'default',\n"
    "    }));"
)

STEPS_MARKUP_SRC = (
    '<sc-for list="{{ bookingSteps }}" as="st" hint-placeholder-count="5">\n'
    '          <div style="flex:1;text-align:center;">\n'
    '            <div style="width:34px;height:34px;border-radius:50%;background:{{ st.circleBg }};'
    'color:{{ st.circleColor }};display:flex;align-items:center;justify-content:center;'
    'font-weight:700;font-size:14px;margin:0 auto 8px;">{{ st.n }}</div>\n'
    '            <div style="font-size:11.5px;color:{{ st.labelColor }};font-weight:600;">'
    '{{ st.label }}</div>\n'
    '          </div>\n'
    '        </sc-for>'
)
STEPS_MARKUP_DST = (
    '<sc-for list="{{ bookingSteps }}" as="st" hint-placeholder-count="5">\n'
    '          <div sc-camel-on-click="{{ st.onClick }}" style="flex:1;text-align:center;'
    'cursor:{{ st.cursor }};">\n'
    '            <div style="width:34px;height:34px;border-radius:50%;background:{{ st.circleBg }};'
    'color:{{ st.circleColor }};display:flex;align-items:center;justify-content:center;'
    'font-weight:700;font-size:14px;margin:0 auto 8px;">{{ st.n }}</div>\n'
    '            <div style="font-size:11.5px;color:{{ st.labelColor }};font-weight:600;">'
    '{{ st.label }}</div>\n'
    '          </div>\n'
    '        </sc-for>'
)

# --- Navbar hides on scroll down, reappears on scroll up --------------------
# Was: plain `position: sticky`, permanently visible once scrolled to. Now:
# slides up out of view while scrolling down past 80px (out of the way of
# whatever's being read), and slides back the moment the visitor scrolls up
# again -- the scroll listener only calls setState when the hidden/visible
# value actually flips (see MOUNT_DST), not on every scroll tick, so this
# doesn't add a re-render per pixel scrolled.
NAV_TRANSFORM_COMPUTE_SRC = (
    "const navItems = NAV_DEFS.map((n) => ({\n"
    "      ...n,\n"
    "      onClick: () => this.setPage(n.key),\n"
    "      color: s.page === n.key ? wine : '#2c2c2c',\n"
    "      weight: s.page === n.key ? 800 : 600,\n"
    "    }));"
)
NAV_TRANSFORM_COMPUTE_DST = NAV_TRANSFORM_COMPUTE_SRC + (
    "\n    const navTransform = s.navHidden ? 'translateY(-100%)' : 'translateY(0)';"
)

NAV_TRANSFORM_EXPOSE_SRC = "navItems, goHome: this.goHome,"
NAV_TRANSFORM_EXPOSE_DST = "navTransform, navItems, goHome: this.goHome,"

NAV_TAG_SRC = (
    '<nav style="position:sticky;top:0;z-index:100;display:flex;align-items:center;'
    'justify-content:space-between;padding:16px 48px;background:rgba(255,255,255,.94);'
    'backdrop-filter:blur(10px);border-bottom:1px solid rgba(20,17,17,.08);'
    'box-shadow:0 2px 16px rgba(20,17,17,.05);">'
)
NAV_TAG_DST = (
    '<nav style="position:sticky;top:0;z-index:100;display:flex;align-items:center;'
    'justify-content:space-between;padding:16px 48px;background:rgba(255,255,255,.94);'
    'backdrop-filter:blur(10px);border-bottom:1px solid rgba(20,17,17,.08);'
    'box-shadow:0 2px 16px rgba(20,17,17,.05);transform:{{ navTransform }};'
    'transition:transform .3s ease;">'
)

# --- "Book with this stylist" -- auto-fill their own branch -----------------
# Was: reset straight to city step 1, no connection at all to which branch the
# picked stylist actually works at -- easy to end up with an artist chosen for
# one branch and a chair/time chosen at a different one. Now: resolves the
# stylist's own branch out of CITIES and jumps straight to the chair step
# already scoped to it (and loads that branch's real chairs, same as picking
# it normally would -- see CHAIRS_FETCH_DST). No branch on file for them (a
# stylist not yet assigned one) falls back to the original step-1 behaviour.
STYLIST_BOOK_SRC = (
    "  bookWithStylist = (i) => this.setPage('booking', {\n"
    "    portfolioIdx: null, bookingStylist: i, spotlightIdx: i,\n"
    "    booking: { cityId: null, storeId: null, step: 1 },\n"
    "    selectedChairIds: [], selectedTime: null, bookingConfirmed: false,\n"
    "  });"
)
STYLIST_BOOK_DST = (
    "  bookWithStylist = (i) => {\n"
    "    const stylist = STYLISTS[i];\n"
    "    let cityId = null, storeId = null;\n"
    "    if (stylist && stylist.location_id) {\n"
    "      const city = CITIES.find((c) => c.branches.some((b) => b.id === stylist.location_id));\n"
    "      if (city) { cityId = city.id; storeId = stylist.location_id; }\n"
    "    }\n"
    "    this.setPage('booking', {\n"
    "      portfolioIdx: null, bookingStylist: i, spotlightIdx: i,\n"
    # PHASE 3 DEV originally skipped straight to Chair here (step 4) the same
    # way it always skipped Store -- but Service (step 3) didn't exist yet
    # when that was written. Once it did, this shortcut kept skipping it too,
    # so a customer arriving via "Book with this stylist" was never asked
    # which service they wanted at all, unlike every other path into the
    # wizard. Landing on Service (step 3) instead still skips City/Store
    # (the part actually implied by picking a specific stylist), but no
    # longer skips picking what to book.
    "      booking: { cityId, storeId, step: storeId ? 3 : 1 },\n"
    "      selectedChairIds: [], selectedTime: null, bookingConfirmed: false,\n"
    "    });\n"
    "    if (storeId) { this._bsiLoadChairs(storeId); }\n"
    "  };"
)

# --- Contact page city tiles -------------------------------------------------
# Was: clicking a city here navigated away to the Stores page, discarding
# whatever the customer was in the middle of doing on Contact. Now: just
# selects that city in place (highlighted, same on/off pattern as every other
# picker tile in the design) -- nothing to navigate to since the tile already
# shows everything Contact has to offer per city (branch count); Stores is
# still one click away in the main nav for anyone who wants the full map.
CONTACT_CITY_LIST_SRC = (
    "contactCityList: CITIES.map((c, i) => ({\n"
    "        name: c.name, count: c.branches.length, delay: (i * 0.05).toFixed(2),\n"
    "        onClick: () => this.setPage('stores', { selectedCityId: c.id, selectedBranchId: null }),\n"
    "      })),"
)
CONTACT_CITY_LIST_DST = (
    "contactCityList: CITIES.map((c, i) => {\n"
    "        const on = s.contactSelectedCityId === c.id;\n"
    "        return { name: c.name, count: c.branches.length, delay: (i * 0.05).toFixed(2),\n"
    "          onClick: () => this.setState({ contactSelectedCityId: c.id }),\n"
    "          bg: on ? '#161213' : '#ffffff', color: on ? '#fdf3ea' : '#161213',\n"
    "          border: on ? '1px solid #161213' : '1px solid rgba(20,17,17,.08)' };\n"
    "      }),"
)

CONTACT_TILE_MARKUP_SRC = (
    '<div sc-camel-on-click="{{ c.onClick }}" style="display:flex;justify-content:space-between;'
    'align-items:center;padding:14px 18px;background:#fff;border:1px solid rgba(20,17,17,.08);'
    'border-radius:14px;font-size:14px;color:#161213;cursor:pointer;box-shadow:0 3px 12px -10px '
    'rgba(20,17,17,.6);transition:transform .2s,box-shadow .2s;animation:fadeUp .5s ease-out '
    '{{ c.delay }}s both;" style-hover="transform:translateX(4px);'
    'box-shadow:0 14px 30px -20px rgba(20,17,17,.6);">'
)
CONTACT_TILE_MARKUP_DST = (
    '<div sc-camel-on-click="{{ c.onClick }}" style="display:flex;justify-content:space-between;'
    'align-items:center;padding:14px 18px;background:{{ c.bg }};border:{{ c.border }};'
    'border-radius:14px;font-size:14px;color:{{ c.color }};cursor:pointer;box-shadow:0 3px 12px -10px '
    'rgba(20,17,17,.6);transition:transform .2s,box-shadow .2s,background .2s,color .2s;'
    'animation:fadeUp .5s ease-out {{ c.delay }}s both;" '
    'style-hover="transform:translateX(4px);box-shadow:0 14px 30px -20px rgba(20,17,17,.6);">'
)

# --- Branch-specific chairs -------------------------------------------------
# Was: always the same 10 generic chairs with two hardcoded as "booked", no
# matter which branch was picked. Now: the real bsi.salon.chair roster for
# that branch (see /salon/api/branch_chairs), fetched the moment a branch is
# chosen -- from either place a branch can be picked (the wizard's own store
# step, or "Book" straight off a branch card on the Stores page).
CHAIRS_FETCH_SRC = (
    "  toggleChair = (id) => {\n"
    "    const chair = this.state.chairs.find((c) => c.id === id);"
)
CHAIRS_FETCH_DST = (
    "  _bsiLoadChairs = (locationId) => {\n"
    "    if (!locationId) { return; }\n"
    "    fetch('/salon/api/branch_chairs', { method: 'POST', credentials: 'same-origin', "
    "headers: { 'Content-Type': 'application/json' }, "
    "body: JSON.stringify({ id: 1, jsonrpc: '2.0', method: 'call', params: { location_id: locationId } }) })\n"
    "      .then((r) => r.json()).then((payload) => {\n"
    "        const rows = (payload && payload.result) || [];\n"
    "        if (!rows.length) { return; }\n"
    "        this.setState({ chairs: rows.map((c) => ({ id: c.id, "
    "style: CHAIR_STYLES.find((cs) => cs.key === c.style_key) || CHAIR_STYLES[0], "
    "status: 'available' })), selectedChairIds: [] });\n"
    "      }).catch(function () {});\n"
    "  };\n"
    "  toggleChair = (id) => {\n"
    "    const chair = this.state.chairs.find((c) => c.id === id);"
)

CHAIRS_STORE_SRC = (
    "bookingSelectStoreAndNext = (id) => this.setState((s) => "
    "({ booking: { ...s.booking, storeId: id, step: 3 } }));"
)
# PHASE 3 DEV: was unconditional -- re-entering Store (via the step indicator
# or the Back button) and re-picking the SAME branch reloaded its chairs from
# scratch every time, wiping any chairs already picked on the Chair step even
# though nothing about the branch had changed. Now: chairs only reload (and
# selectedChairIds only resets) when the branch actually changes, so stepping
# back to Store and forward again keeps whatever was already picked further
# along the wizard.
CHAIRS_STORE_DST = (
    "bookingSelectStoreAndNext = (id) => { "
    "if (this.state.booking.storeId !== id) { this._bsiLoadChairs(id); } "
    "this.setState((s) => ({ booking: { ...s.booking, storeId: id, step: 3 }, "
    "bookingMaxStep: Math.max(s.bookingMaxStep || 1, 3) })); };"
)

# City -> Store is the one forward transition with no other patch already
# touching it -- same bookingMaxStep bump as every other forward transition
# above/below, so the step indicator (see STEPS_COMPUTE_DST) never re-locks
# Store either once it's been reached.
CITY_MAXSTEP_SRC = (
    "bookingSelectCityAndNext = (id) => this.setState((s) => "
    "({ booking: { ...s.booking, cityId: id, storeId: null, step: 2 } }));"
)
CITY_MAXSTEP_DST = (
    "bookingSelectCityAndNext = (id) => this.setState((s) => "
    "({ booking: { ...s.booking, cityId: id, storeId: null, step: 2 }, "
    "bookingMaxStep: Math.max(s.bookingMaxStep || 1, 2) }));"
)

CHAIRS_BOOKFROM_SRC = (
    "bookFromBranch = (cityId, branchId) => this.setPage('booking', "
    "{ booking: { cityId, storeId: branchId, step: 3 }, "
    "selectedChairIds: [], selectedTime: null, bookingConfirmed: false });"
)
# PHASE 3 DEV: step 3 is now the new Service step (see the booking-step
# renumbering patches below) -- this shortcut always skipped straight past
# Store, same as it still does here past Service, landing on Chair, which is
# step 4 post-renumber.
# PHASE 5 DEV: this shortcut (a branch card's own "Book" button on the Stores
# page) skipped straight to Chair (step 4), bypassing Service entirely -- a
# customer picking a specific branch there never got asked which service
# they wanted, unlike City -> Store -> Service in the main wizard. Landing on
# Service (step 3) instead keeps the "branch already chosen, skip City/Store"
# behaviour this shortcut exists for, without also skipping what to book.
CHAIRS_BOOKFROM_DST = (
    "bookFromBranch = (cityId, branchId) => { this.setPage('booking', "
    "{ booking: { cityId, storeId: branchId, step: 3 }, "
    "selectedChairIds: [], selectedTime: null, bookingConfirmed: false }); "
    "this._bsiLoadChairs(branchId); };"
)

# --- Gift card purchase ----------------------------------------------------
# The Buy button had no click handler at all. Same purchase path as a
# membership tier: resolve the chosen amount to its product, add it to the
# standard cart, hand over to checkout. The card itself is drafted server-side
# once that order is paid (see sale.order._bsi_process_gift_card_lines) --
# staff still activate it by hand, same as one entered directly in the backend.
GIFT_METHOD_SRC = (
    "  setGiftAmount = (a) => this.setState({ giftAmount: a });\n"
    "  copyReferral = () => { this.setState({ referralCopied: true }); "
    "setTimeout(() => this.setState({ referralCopied: false }), 2000); };"
)
GIFT_METHOD_DST = (
    "  setGiftAmount = (a) => this.setState({ giftAmount: a });\n"
    "  buyGiftCard = () => { "
    'const rpc = (url, params) => fetch(url, { method: "POST", credentials: "same-origin", '
    'headers: { "Content-Type": "application/json" }, '
    'body: JSON.stringify({ id: 1, jsonrpc: "2.0", method: "call", params: params }) '
    '}).then((r) => r.json()); '
    'rpc("/salon/api/gift_card_product", { amount: this.state.giftAmount }) '
    '.then((payload) => { const res = (payload && payload.result) || {}; '
    'if (!res.product_id) { throw new Error("no product"); } '
    'return rpc("/shop/cart/add", { product_id: res.product_id, '
    'product_template_id: res.product_template_id, quantity: 1 }); }) '
    '.then(() => { window.location.href = "/shop/checkout"; }) '
    '.catch(() => {}); };\n'
    "  copyReferral = () => { this.setState({ referralCopied: true }); "
    "setTimeout(() => this.setState({ referralCopied: false }), 2000); };"
)

GIFT_STATE_SRC = (
    "giftAmounts, giftAmount: s.giftAmount,\n"
    "      giftMessage: s.giftMessage || GIFT_MESSAGES[0],"
)
GIFT_STATE_DST = (
    "giftAmounts, giftAmount: s.giftAmount, buyGiftCard: this.buyGiftCard,\n"
    "      myGiftCardCode: s.myGiftCardCode || '', myGiftCardBalance: s.myGiftCardBalance || 0,\n"
    "      giftMessage: s.giftMessage || GIFT_MESSAGES[0],"
)

# --- Gift Cards panel -- show the signed-in visitor's own active card too ---
# Was: this panel only ever sold a NEW gift card, with no way to see a card
# you already hold -- see /salon/api/gift_card_status (fetched on mount, see
# MOUNT_DST), which answers exactly that. A zero balance (spent down to
# nothing -- see bsi.salon.gift.card._bsi_redeem) naturally stops matching
# its own ('bsi_balance', '>', 0) domain, so the newest OTHER active card
# with money left takes its place here automatically -- no extra code needed
# for "the next one activates once this one is used up".
GIFT_STATUS_SRC = (
    '          <div style="font-size:10.5px;font-weight:800;letter-spacing:2px;color:#c81f36;'
    'margin-bottom:12px;">GIFT CARDS</div>'
)
GIFT_STATUS_DST = (
    '          <div style="font-size:10.5px;font-weight:800;letter-spacing:2px;color:#c81f36;'
    'margin-bottom:12px;">GIFT CARDS</div>\n'
    '          <sc-if value="{{ myGiftCardCode }}" hint-placeholder-val="{{ false }}">\n'
    '            <div style="display:flex;justify-content:space-between;align-items:center;'
    'background:rgba(232,40,63,.1);border:1px solid rgba(232,40,63,.3);border-radius:12px;'
    'padding:12px 14px;margin-bottom:16px;">\n'
    '              <span style="font-size:12px;font-weight:700;color:#161213;">Your card '
    '{{ myGiftCardCode }}</span>\n'
    '              <span style="font-size:13px;font-weight:800;color:#c81f36;">'
    '₹{{ myGiftCardBalance }} left</span>\n'
    '            </div>\n'
    '          </sc-if>'
)

GIFT_BUTTON_SRC = (
    '<button style="width:100%;background:#e8283f;color:#ffffff;border:none;'
    'padding:14px;border-radius:12px;font-weight:700;cursor:pointer;font-size:13.5px;'
    'box-shadow:0 12px 28px -14px rgba(232,40,63,.9);">Buy ₹{{ giftAmount }} Gift Card</button>'
)
GIFT_BUTTON_DST = (
    '<button sc-camel-on-click="{{ buyGiftCard }}" style="width:100%;background:#e8283f;'
    'color:#ffffff;border:none;padding:14px;border-radius:12px;font-weight:700;cursor:pointer;'
    'font-size:13.5px;box-shadow:0 12px 28px -14px rgba(232,40,63,.9);">'
    'Buy ₹{{ giftAmount }} Gift Card</button>'
)

# --- Loyalty Wallet -- the whole panel showed one hardcoded fake balance ----
# Was: WALLET_PTS = 1240 is a fixed design constant -- every visitor, signed
# in or not, saw the exact same "1240 points", the exact same "Redeem now"/
# "Locked" state on each reward, and could reach real redemption (see the
# loyalty redemption patches right below) for a reward the design's own fake
# number said they could afford, whether or not they actually held enough
# real points. Now: the same /salon/api/loyalty_status call already fetched
# on mount for the Services page (see MOUNT_DST) drives every one of these
# instead, so the wallet always reflects the signed-in visitor's real balance
# -- 0 for a guest, since loyaltyPoints defaults to 0 and nothing here is
# reachable without it anyway.
WALLET_POINTS_SRC = "walletPoints: WALLET_PTS, walletValue: Math.round(WALLET_PTS / 2),"
WALLET_POINTS_DST = (
    "walletPoints: (s.loyaltyPoints || 0), walletValue: Math.round((s.loyaltyPoints || 0) / 2),"
)

WALLET_DASH_SRC = "walletDash: Math.round(534 * (1 - Math.min(1, WALLET_PTS / 2000))),"
WALLET_DASH_DST = (
    "walletDash: Math.round(534 * (1 - Math.min(1, (s.loyaltyPoints || 0) / 2000))),"
)

WALLET_TONEXT_SRC = "walletToNext: 2000 - WALLET_PTS,"
WALLET_TONEXT_DST = "walletToNext: Math.max(0, 2000 - (s.loyaltyPoints || 0)),"

WALLET_TIERPCT_SRC = "walletTierPct: Math.round((WALLET_PTS / 2000) * 100),"
WALLET_TIERPCT_DST = (
    "walletTierPct: Math.min(100, Math.round(((s.loyaltyPoints || 0) / 2000) * 100)),"
)

WALLET_CAN_SRC = "const can = WALLET_PTS >= r.cost;"
WALLET_CAN_DST = "const can = (s.loyaltyPoints || 0) >= r.cost;"

# --- Loyalty reward redemption ----------------------------------------------
# Was: "Redeem now" just navigated to the booking page -- it never actually
# spent the points, and the customer had to remember which service they'd
# meant to redeem for and re-pick their usual branch from scratch. Now: it
# spends the points for real first (server-checked balance, same guarded
# _bsi_redeem_for every other redemption path uses), and only on success
# carries the reward's service into a fresh booking (see CONFIRM_DST, which
# reads rewardServiceId back off state at the final Confirm step).
REDEEM_SRC = "onClick: can ? (() => this.setState({ page: 'booking' })) : null,"
REDEEM_DST = "onClick: can ? (() => this.redeemReward(r.id)) : null,"

REDEEM_METHOD_SRC = (
    "goBookingNav = () => this.setPage('booking', { booking: { cityId: null, storeId: null, "
    "step: 1 }, selectedChairIds: [], selectedTime: null, bookingConfirmed: false });"
)
REDEEM_METHOD_DST = REDEEM_METHOD_SRC + (
    "\n  redeemReward = (rewardId) => { "
    'const rpc = (url, params) => fetch(url, { method: "POST", credentials: "same-origin", '
    'headers: { "Content-Type": "application/json" }, '
    'body: JSON.stringify({ id: 1, jsonrpc: "2.0", method: "call", params: params }) '
    '}).then((r) => r.json()); '
    'rpc("/salon/api/loyalty_redeem", { reward_id: rewardId }) '
    '.then((payload) => { const res = (payload && payload.result) || {}; '
    "if (!res.ok) { window.alert(res.error || \"That reward could not be redeemed.\"); return; } "
    "this.setPage('booking', { booking: { cityId: null, storeId: null, step: 1 }, "
    "selectedChairIds: [], selectedTime: null, bookingConfirmed: false, "
    "rewardServiceId: res.service_id || null, rewardServiceName: res.service_name || null, "
    "loyaltyPoints: res.points || 0 }); }) "
    '.catch(() => {}); };'
)

# --- Services page -- redeem a plain service directly for loyalty points ----
# Was: the loyalty ledger only ever paid for a curated bsi.salon.loyalty.reward,
# never a service picked straight off the Services page. Now: any service with
# its own bsi_loyalty_points (see bsi.salon.service) gets a "Redeem N pts"
# button there, enabled only once componentDidMount's own /salon/api/
# loyalty_status call confirms the signed-in visitor actually has enough --
# same "checkbox only ever reveals something server-verified" shape as the
# membership discount and gift card fields, never trusts the button being
# clickable at all as proof by itself.
SERVICE_POINTS_METHOD_SRC = REDEEM_METHOD_DST
SERVICE_POINTS_METHOD_DST = REDEEM_METHOD_DST + (
    "\n  redeemServicePoints = (serviceId) => { "
    'const rpc = (url, params) => fetch(url, { method: "POST", credentials: "same-origin", '
    'headers: { "Content-Type": "application/json" }, '
    'body: JSON.stringify({ id: 1, jsonrpc: "2.0", method: "call", params: params }) '
    '}).then((r) => r.json()); '
    'rpc("/salon/api/loyalty_redeem", { service_id: serviceId }) '
    '.then((payload) => { const res = (payload && payload.result) || {}; '
    "if (!res.ok) { window.alert(res.error || \"That service could not be redeemed.\"); return; } "
    "this.setPage('booking', { booking: { cityId: null, storeId: null, step: 1 }, "
    "selectedChairIds: [], selectedTime: null, bookingConfirmed: false, "
    "rewardServiceId: res.service_id || null, rewardServiceName: res.service_name || null, "
    "loyaltyPoints: res.points || 0 }); }) "
    '.catch(() => {}); };'
    # --- Services page "Book" -- a plain, full-price service selection ------
    # Was: "Book →" under each service was inert text, no handler at all -- the
    # only ways a specific service ever reached bsi_service_ids were the look
    # configurator, a stylist's own booking button, or spending loyalty points
    # above. Now: clicking it carries this exact service into the wizard like
    # those do, priced normally (see CONFIRM_DST's selected_service_id and
    # main.py's own resolution of it) -- no server round trip needed first,
    # unlike redeemServicePoints/redeemReward, since nothing has to be
    # verified or spent to simply pick a service to book.
    "\n  goBookingWithService = (serviceId, serviceName) => this.setPage('booking', { "
    "booking: { cityId: null, storeId: null, step: 1 }, selectedChairIds: [], "
    "selectedTime: null, bookingConfirmed: false, "
    "bookingServiceId: serviceId, bookingServiceName: serviceName });\n"
    # --- Services page "Apply Package" -- same entry, package auto-filled ----
    # Mirrors goBookingWithService, but seeds bookingPackageId/bookingServiceIds
    # from the package's own services (see bsi.salon.package.bsi_service_ids)
    # so the Service step opens with them already applied instead of asking
    # the customer to re-pick what the package already promised.
    "  goBookingWithPackage = (packageId, serviceIds, priceAmount, name) => this.setPage('booking', { "
    "booking: { cityId: null, storeId: null, step: 1 }, selectedChairIds: [], "
    "selectedTime: null, bookingConfirmed: false, "
    "bookingPackageId: packageId, bookingPackageName: name, bookingPackagePrice: priceAmount, "
    "bookingServiceIds: (serviceIds || []).slice(), bookingServiceId: null });"
)

SERVICE_POINTS_LIST_SRC = (
    "      filteredServices: (SERVICES_DATA[s.activeServiceCat] || []).map((sv, i) => "
    "({ ...sv, delay: (i * 0.06).toFixed(2) })),"
)
SERVICE_POINTS_LIST_DST = (
    "      filteredServices: (SERVICES_DATA[s.activeServiceCat] || []).map((sv, i) => ({ "
    "...sv, delay: (i * 0.06).toFixed(2), "
    "canRedeemPoints: !!(sv.points && (s.loyaltyPoints || 0) >= sv.points), "
    "redeemPointsLabel: sv.points ? ('Redeem ' + sv.points + ' pts') : '', "
    "redeemPointsOnClick: sv.points ? (() => this.redeemServicePoints(sv.id)) : null, "
    "bookOnClick: () => this.goBookingWithService(sv.id, sv.name), "
    "})),"
)

# --- Services page -- Packages listing --------------------------------------
# Was: no package listing on the website at all -- bsi.salon.package is a
# static bundle catalogue (name/included services/bundle price/savings
# label, see bsi_enrich_data._bsi_packages) with no per-customer eligibility
# concept in the backend (only its own active flag and the site-wide
# bsi_salon_backend.show_packages toggle, both already reflected in whether
# BSI_PACKAGES has anything in it at all -- see main.py's own PHASE 5 DEV
# comment). Computed the same place filteredServices already is, chained onto
# its own patched output so this lands right alongside it.
PACKAGES_LIST_SRC = SERVICE_POINTS_LIST_DST
PACKAGES_LIST_DST = SERVICE_POINTS_LIST_DST + (
    "\n      servicePackages: (BSI_PACKAGES || []).map((p) => ({\n"
    "        id: p.id, name: p.name, description: p.description, price: p.price,\n"
    "        originalPrice: p.original_price, saveLabel: p.save_label,\n"
    "        serviceRows: (p.service_names || []).map((name) => ({ name })),\n"
    "        onClick: () => this.goBookingWithPackage(p.id, p.service_ids, p.price_amount, p.name),\n"
    "      })),"
)

# Markup section itself -- same card-grid language as the Membership page's
# tier cards (rounded white cards, red Playfair price, "MOST POPULAR"-style
# ribbon reused here as the savings ribbon), inserted right after the
# services grid/sidebar section closes and before Colour Lab.
PACKAGES_SECTION_SRC = (
    'Book the Offer</button>\n'
    '            </div>\n'
    '          </div>\n'
    '        </div>\n'
    '      </div>\n'
    '    </section>\n'
    '\n'
    '    <!-- ── Colour Lab: real lift maths, honest session count and pricing ── -->'
)
PACKAGES_SECTION_DST = (
    'Book the Offer</button>\n'
    '            </div>\n'
    '          </div>\n'
    '        </div>\n'
    '      </div>\n'
    '    </section>\n'
    '\n'
    '    <sc-if value="{{ servicePackages.length }}" hint-placeholder-val="{{ false }}">\n'
    '    <section data-screen-label="Packages" style="background:#fdf9f6;padding:74px 48px 84px;'
    'border-top:1px solid rgba(20,17,17,.07);">\n'
    '      <div style="max-width:1180px;margin:0 auto;">\n'
    '        <div style="text-align:center;margin-bottom:40px;">\n'
    '          <div style="font-size:11.5px;font-weight:800;letter-spacing:2px;color:#c81f36;'
    'margin-bottom:12px;">BUNDLE &amp; SAVE</div>\n'
    '          <h2 style="font-family:\'Playfair Display\',serif;font-weight:600;font-size:42px;'
    'line-height:1.06;color:#161213;margin:0 0 14px;">Packages built<br>'
    '<em style="color:#e8283f;">for real routines.</em></h2>\n'
    '          <p style="font-size:15px;color:#767676;max-width:520px;margin:0 auto;line-height:1.7;">'
    'Bundle the services you always book together, at one flat price.</p>\n'
    '        </div>\n'
    '        <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:24px;">\n'
    '          <sc-for list="{{ servicePackages }}" as="pkg" hint-placeholder-count="3">\n'
    '            <div style="position:relative;background:#fff;border:1px solid rgba(20,17,17,.08);'
    'border-radius:22px;padding:28px;box-shadow:0 14px 34px -24px rgba(20,17,17,.5);">\n'
    '              <sc-if value="{{ pkg.saveLabel }}" hint-placeholder-val="{{ false }}">\n'
    '                <div style="position:absolute;top:-13px;right:24px;background:#3ddc84;'
    'color:#161213;font-size:11px;font-weight:800;letter-spacing:.4px;padding:5px 14px;'
    'border-radius:4px;">{{ pkg.saveLabel }}</div>\n'
    '              </sc-if>\n'
    '              <div style="font-family:\'Playfair Display\',serif;font-size:22px;color:#161213;'
    'margin-bottom:10px;">{{ pkg.name }}</div>\n'
    '              <sc-if value="{{ pkg.description }}" hint-placeholder-val="{{ false }}">\n'
    '                <div style="font-size:13px;color:#767676;line-height:1.6;margin-bottom:16px;">'
    '{{ pkg.description }}</div>\n'
    '              </sc-if>\n'
    '              <div style="margin-bottom:20px;">\n'
    '                <div style="font-size:10.5px;font-weight:800;letter-spacing:1.2px;color:#9b9093;'
    'margin-bottom:10px;">INCLUDES</div>\n'
    '                <sc-for list="{{ pkg.serviceRows }}" as="sv2" hint-placeholder-count="3">\n'
    '                  <div style="display:flex;align-items:center;gap:8px;font-size:13px;'
    'color:#454545;margin-bottom:7px;">\n'
    '                    <span style="color:#e8283f;flex-shrink:0;">✓</span><span>{{ sv2.name }}</span>\n'
    '                  </div>\n'
    '                </sc-for>\n'
    '              </div>\n'
    '              <div style="display:flex;align-items:baseline;gap:10px;margin-bottom:18px;">\n'
    '                <sc-if value="{{ pkg.originalPrice }}" hint-placeholder-val="{{ false }}">\n'
    '                  <span style="font-size:14px;color:#9b9093;text-decoration:line-through;">'
    '{{ pkg.originalPrice }}</span>\n'
    '                </sc-if>\n'
    '                <span style="font-family:\'Playfair Display\',serif;font-size:26px;'
    'color:#e8283f;">{{ pkg.price }}</span>\n'
    '              </div>\n'
    '              <button sc-camel-on-click="{{ pkg.onClick }}" style="width:100%;'
    'background:#161213;color:#fff;border:none;padding:14px;border-radius:4px;font-weight:700;'
    'cursor:pointer;transition:background .2s;" style-hover="background:#e8283f;">'
    'Apply Package</button>\n'
    '            </div>\n'
    '          </sc-for>\n'
    '        </div>\n'
    '      </div>\n'
    '    </section>\n'
    '    </sc-if>\n'
    '\n'
    '    <!-- ── Colour Lab: real lift maths, honest session count and pricing ── -->'
)

SERVICE_POINTS_MARKUP_SRC = (
    '                <div style="text-align:right;flex-shrink:0;">\n'
    '                  <div style="font-size:16px;font-weight:800;color:#161213;">{{ s.price }}</div>\n'
    '                  <div style="font-size:11px;color:#c81f36;font-weight:700;margin-top:2px;">Book →</div>\n'
    '                </div>'
)
SERVICE_POINTS_MARKUP_DST = (
    '                <div style="text-align:right;flex-shrink:0;">\n'
    '                  <div style="font-size:16px;font-weight:800;color:#161213;">{{ s.price }}</div>\n'
    '                  <button sc-camel-on-click="{{ s.bookOnClick }}" style="background:none;border:none;'
    'padding:0;font-size:11px;color:#c81f36;font-weight:700;margin-top:2px;cursor:pointer;">Book →</button>\n'
    '                  <sc-if value="{{ s.points }}" hint-placeholder-val="{{ false }}">\n'
    '                    <div style="font-size:10px;color:#9b9093;font-weight:700;margin-top:5px;">{{ s.points }} pts</div>\n'
    '                    <button sc-camel-on-click="{{ s.redeemPointsOnClick }}" '
    'disabled="{{ !s.canRedeemPoints }}" style="margin-top:4px;font-size:10px;font-weight:800;'
    'border:none;border-radius:999px;padding:5px 11px;cursor:pointer;'
    "background:{{ s.canRedeemPoints ? '#e8283f' : 'rgba(20,17,17,.08)' }};"
    "color:{{ s.canRedeemPoints ? '#ffffff' : '#9b9093' }};\">{{ s.redeemPointsLabel }}</button>\n"
    '                  </sc-if>\n'
    '                </div>'
)

# --- Contact form ---------------------------------------------------------
# The four inputs carry no name attributes, so their values are read positionally
# off the submitted form rather than by editing the markup.
CONTACT_SRC = (
    'sendContact = (e) => { if (e && e.preventDefault) e.preventDefault(); '
    'this.setState({ contactSent: true }); };'
)
CONTACT_DST = (
    'sendContact = (e) => { if (e && e.preventDefault) e.preventDefault(); '
    'try { const form = e && e.target ? e.target : null; '
    'const vals = form ? Array.prototype.map.call('
    'form.querySelectorAll("input, textarea"), (el) => el.value || "") : []; '
    'if (vals.length) { fetch("/salon/api/contact", { method: "POST", credentials: "same-origin", '
    'headers: { "Content-Type": "application/json" }, '
    'body: JSON.stringify({ id: 1, jsonrpc: "2.0", method: "call", params: { '
    'name: vals[0] || "", email: vals[1] || "", phone: vals[2] || "", notes: vals[3] || "" } }) '
    '}).catch(function () {}); } } catch (err) {} '
    'this.setState({ contactSent: true }); };'
)


# --- Look configurator pricing ---------------------------------------------
# The finish and length pickers themselves are pointed at the live
# BSI_LOOK_FINISHES / BSI_LOOK_LENGTHS catalogue in main.py (see
# _replace_property_ref); these four patches point the name captions and the
# price maths at the same catalogue instead of the design's original
# three-of-each maps, and the shade surcharge at the value LOOK_SHADES already
# carries instead of a hardcoded "3rd swatch onward" rule.
FINISH_NAME_SRC = (
    "{ gloss: 'High Gloss', matte: 'Soft Matte', wave: 'Beach Wave' }"
    "[s.lookFinish || 'gloss']"
)
FINISH_NAME_DST = (
    "((BSI_LOOK_FINISHES.find(function (f) { return f.id === (s.lookFinish || 'gloss'); }) "
    "|| {}).label || 'High Gloss')"
)

FINISH_SURCHARGE_SRC = "{ gloss: 400, matte: 0, wave: 900 }[s.lookFinish || 'gloss']"
FINISH_SURCHARGE_DST = (
    "((BSI_LOOK_FINISHES.find(function (f) { return f.id === (s.lookFinish || 'gloss'); }) "
    "|| {}).surcharge || 0)"
)

LENGTH_NAME_SRC = (
    "{ long: 'Long', mid: 'Shoulder-length', short: 'Short' }[s.lookLength || 'mid']"
)
LENGTH_NAME_DST = (
    "((BSI_LOOK_LENGTHS.find(function (l) { return l.id === (s.lookLength || 'mid'); }) "
    "|| {}).label || 'Shoulder-length')"
)

LENGTH_SURCHARGE_SRC = "{ long: 600, mid: 300, short: 0 }[s.lookLength || 'mid']"
LENGTH_SURCHARGE_DST = (
    "((BSI_LOOK_LENGTHS.find(function (l) { return l.id === (s.lookLength || 'mid'); }) "
    "|| {}).surcharge || 0)"
)

SHADE_SURCHARGE_SRC = "(s.lookShade || 0) >= 3 ? 800 : 0"
SHADE_SURCHARGE_DST = (
    "(LOOK_SHADES[s.lookShade || 0] ? (LOOK_SHADES[s.lookShade || 0].surcharge || 0) : 0)"
)

## NOTE: anchors below match the *served* JS text, which spells non-ASCII
## characters as literal "\uXXXX" escape sequences (six characters each), not
## the glyphs themselves -- this is JS *source code*, not decoded text.
PRICE_BASE_SRC = "lookPrice: '\\u20b9' + (2999"
PRICE_BASE_DST = "lookPrice: '\\u20b9' + (BSI_LOOK_BASE_PRICE"

# --- "Design Your Look" illustration -- crashes on an unrecognised length key ---
# Was: paintLook's hand-drawn illustration only ever had art for exactly three
# hardcoded length keys ('short'/'mid'/'long' -- see the four `{ short: ..., mid:
# ..., long: ... }[lenKey]` lookups inside it), with no fallback if lenKey is
# anything else. BSI_LOOK_LENGTHS' bsi_key is free text (see bsi_salon_look_length),
# so a length record added or edited in the backend with any other key crashes
# every one of those lookups the instant a customer picks it -- reproduced live:
# a stray "Too long" record (bsi_key "too long") threw "Cannot read properties of
# undefined (reading 'w')" on click, taking the whole Design Your Look panel down.
# Now: an unrecognised key falls back to the 'mid' illustration -- customers still
# see a picture and a price, the site never crashes, whatever bsi_key ends up
# being typed into a length record.
LENKEY_SRC = "const lenKey = S.lookLength || 'mid';"
LENKEY_DST = (
    "const lenKey = ['short', 'mid', 'long'].indexOf(S.lookLength) !== -1 ? S.lookLength : 'mid';"
)

# --- Booking wizard Confirm screen -- real estimate for a Design-Your-Look ---
# Was: the wizard's own Confirm-step total (`finalPrice`, ₹{{ finalPrice }} in
# the Booking Summary and the confirmed appointment pass) always priced off a
# generic `basePrice = 999` placeholder, regardless of what got booked -- so a
# ₹4,199 look configured on the homepage still showed ₹999 (or ₹799 with
# membership), and any chair-side add-ons picked on the Chair step (see the
# ritual builder patches above) were shown a real price there and then
# silently dropped from this total, however many were picked. Now: when the
# booking started from the look configurator, goBookingFromLook has already
# snapshotted its real total onto state.bookingLookPrice (see LOOK_METHOD_DST)
# -- used here instead of the placeholder whenever present -- and whatever
# add-ons are on state.ritual are priced from the same BSI_ADDONS catalogue
# the ritual builder itself reads (see _inject_look_consts) and added on top,
# both before the membership multiplier, matching exactly how
# bsi_salon_booking_mixin._bsi_compute_bsi_amounts_common prices a real
# booking server-side (add-ons and the look estimate both inside subtotal,
# discounted together with everything else). PHASE 3 DEV: the same placeholder
# also stood in for a normally-booked service's own price -- the sum of every
# service in bookingServiceIds (or the legacy singular bookingServiceId, for a
# service carried in from an entry point that predates multi-select) is
# checked next, so picking real catalogue services on the new Service step
# prices the total off their own bsi_price_amount instead of ₹999 too, the
# same sum-of-selected-services shape
# bsi_salon_booking_mixin._bsi_compute_bsi_amounts_common uses server-side.
BASEPRICE_SRC = "const basePrice = 999;"
BASEPRICE_DST = (
    "const ritualAddonCost = (s.ritual || []).reduce(function (t, k) { "
    "var a = BSI_ADDONS.find(function (x) { return x.key === k; }); "
    "return t + (a ? (a.price || 0) : 0); }, 0); "
    "const bsiSvcIds = (s.bookingServiceIds && s.bookingServiceIds.length) "
    "? s.bookingServiceIds : (s.bookingServiceId ? [s.bookingServiceId] : []); "
    "const bsiSvcAll = [].concat.apply([], Object.keys(SERVICES_DATA).map(function (k) "
    "{ return SERVICES_DATA[k]; })); "
    # A package prices the whole selection at its own flat bundle price
    # instead of a sum of its services (mirroring
    # bsi_salon_booking_mixin._bsi_compute_bsi_amounts_common's own
    # `if record.bsi_package_id: services_amount = ...bsi_package_id.
    # _bsi_get_effective_price()` branch) -- bookingApplyPackage already
    # snapshotted that price onto bookingPackagePrice when it was chosen.
    "const bsiSvcTotal = s.bookingPackageId ? (s.bookingPackagePrice || 0) "
    ": bsiSvcIds.reduce(function (t, id) { "
    "var rec = bsiSvcAll.find(function (x) { return x.id === id; }); "
    "return t + (rec ? (rec.price_amount || 0) : 0); }, 0); "
    "const basePrice = ((s.bookingLookPrice != null) ? s.bookingLookPrice "
    ": (bsiSvcTotal || 999)) + ritualAddonCost;"
)

# --- Chair-side ritual builder -- add-ons keyed on id, priced on nothing -----
# Was: the ADDONS array's own `id` field is a top-level literal (see the PHASE
# 1 BRIDGE substitution loop's ('ADDONS', 'addons') entry) -- so the design's
# own massage/towel/aroma/drink/music sample ids get replaced with the real
# bsi.salon.addon row ids the moment there is any real add-on data, which
# there always is. The ritual builder toggles and reads back `a.id`, so this
# already silently broke the per-add-on chair preview (steam, massage hands,
# aroma glow, drink cup, music bars all keyed to the ORIGINAL string ids and
# therefore permanently off) -- and separately, confirmBooking never sent the
# picks at all, so a chosen add-on's price was shown on the site and then
# thrown away instead of reaching the booking (see CONFIRM_DST's addon_keys).
# Now: the builder keys on `a.key` (bsi.salon.addon.bsi_key, added alongside
# id/icon/name/meta/price/mins in _bsi_addons) instead of `a.id`, which
# doubles as exactly the stable string the chair preview's animations were
# always keyed on and the string /salon/api/booking now resolves back to real
# bsi.salon.addon records.
RITUAL_PICKED_SRC = "const picked = ADDONS.filter((a) => on.includes(a.id));"
RITUAL_PICKED_DST = "const picked = ADDONS.filter((a) => on.includes(a.key));"

RITUAL_TOGGLE_SRC = (
    "          ritualOptions: ADDONS.map((a) => {\n"
    "            const active = on.includes(a.id);\n"
    "            return {\n"
    "              ...a, onClick: () => this.toggleRitual(a.id),"
)
RITUAL_TOGGLE_DST = (
    "          ritualOptions: ADDONS.map((a) => {\n"
    "            const active = on.includes(a.key);\n"
    "            return {\n"
    "              ...a, onClick: () => this.toggleRitual(a.key),"
)

# --- Consultation simulator recommendations ---------------------------------
# Was: a fixed decision tree keyed to the five questions the design shipped
# with, matching answer tokens like 'breaking' or 'virgin' that only that exact
# script produces. Now: every bsi.salon.consult.rule whose trigger is among the
# answers given, in the sequence a salon manager set -- so it recommends
# correctly however many questions are configured, in whatever order.
CONSULT_SRC = (
    "const [goal, condition, history, upkeep, time] = ans;\n"
    "        const plan = [];\n"
    "        if (condition === 'breaking' || history === 'both' || history === 'chemical') {\n"
    "          plan.push({ name: 'Bond repair treatment', why: 'Rebuilds broken bonds before anything else touches the hair', price: '\\u20b91,800' });\n"
    "        }\n"
    "        if (condition === 'dry') {\n"
    "          plan.push({ name: 'Deep-conditioning hair spa', why: 'Restores moisture and calms frizz', price: '\\u20b91,499' });\n"
    "        }\n"
    "        if (goal === 'cut' || goal === 'event') {\n"
    "          plan.push({ name: upkeep === 'low' ? 'Low-maintenance precision cut' : 'Precision cut and reshape',\n"
    "            why: upkeep === 'low' ? 'Shaped to fall right without daily styling' : 'Cut to your face shape and growth pattern', price: '\\u20b9899' });\n"
    "        }\n"
    "        if (goal === 'colour') {\n"
    "          plan.push({ name: history === 'virgin' ? 'First-time global colour' : 'Root touch-up and gloss',\n"
    "            why: history === 'virgin' ? 'Single-process on virgin hair \\u2014 the gentlest start' : 'Refreshes the base and revives faded lengths', price: history === 'virgin' ? '\\u20b92,999' : '\\u20b91,999' });\n"
    "        }\n"
    "        if (goal === 'repair') {\n"
    "          plan.push({ name: 'Keratin smoothing', why: 'Seals the cuticle for up to twelve weeks of control', price: '\\u20b94,999' });\n"
    "        }\n"
    "        if (goal === 'event') {\n"
    "          plan.push({ name: 'Blow-dry and finish', why: 'Styled on the day so it holds through the evening', price: '\\u20b9699' });\n"
    "        }\n"
    "        if (condition === 'limp' && time !== 't1') {\n"
    "          plan.push({ name: 'Volumising scalp ritual', why: 'Lifts at the root and clears build-up', price: '\\u20b91,299' });\n"
    "        }\n"
    "        if (!plan.length) plan.push({ name: 'Signature cut and finish', why: 'The right starting point for healthy hair', price: '\\u20b9899' });"
)
CONSULT_DST = (
    "const [goal, condition, history, upkeep, time] = ans;\n"
    "        const plan = (BSI_CONSULT_RULES || [])\n"
    "          .filter(function (r) { return ans.indexOf(r.trigger) !== -1; })\n"
    "          .map(function (r) { return { name: r.name, why: r.why, price: r.price }; });\n"
    "        if (!plan.length) plan.push({ name: 'Signature cut and finish', why: 'The right starting point for healthy hair', price: '\\u20b9899' });"
)


# --- Membership discount at booking -----------------------------------------
# Was: "isMember" was a checkbox anyone could tick, unconditionally taking 20%
# off -- no check that the visitor was ever a paying member. Then: the
# checkbox only appeared once componentDidMount asked /salon/api/
# membership_status whether the signed-in visitor actually had one, using
# their real tier and discount rather than a hardcoded "Gold Membership" name
# and rate. PHASE 4 DEV: the checkbox itself is gone now too -- a genuinely
# active membership (server-verified, same call) applies automatically with
# no code or toggle to remember (see MEMBER_PRICE_DST reading
# hasActiveMembership directly, and CONFIRM_DST sending is_member off the
# same flag) -- MEMBER_CHECKBOX_DST below is now a read-only "applied
# automatically" notice, not an input.
MOUNT_SRC = (
    "componentDidMount() {\n"
    "    this._motion();\n"
    "    this._initPolish();\n"
    "    this._introTimer = setTimeout(() => this.setState({ showIntro: false }), 3500);\n"
    "    this._pulseTimer = setInterval(() => this.setState((s) => "
    "({ pulseIdx: (s.pulseIdx + 1) % 4 })), 3600);\n"
    "  }"
)
MOUNT_DST = (
    "componentDidMount() {\n"
    "    this._motion();\n"
    "    this._initPolish();\n"
    "    this._introTimer = setTimeout(() => this.setState({ showIntro: false }), 3500);\n"
    "    this._pulseTimer = setInterval(() => this.setState((s) => "
    "({ pulseIdx: (s.pulseIdx + 1) % 4 })), 3600);\n"
    "    fetch('/salon/api/membership_status', { method: 'POST', credentials: 'same-origin', "
    "headers: { 'Content-Type': 'application/json' }, "
    "body: JSON.stringify({ id: 1, jsonrpc: '2.0', method: 'call', params: {} }) })\n"
    "      .then(function (r) { return r.json(); }).then((payload) => {\n"
    "        const res = (payload && payload.result) || {};\n"
    "        const fmtBsiDate = (iso) => { if (!iso) return ''; "
    "const d = new Date(iso + 'T00:00:00'); "
    "return isNaN(d.getTime()) ? iso : d.toLocaleDateString('en-GB', "
    "{ day: 'numeric', month: 'short', year: 'numeric' }); };\n"
    "        this.setState({\n"
    "          hasActiveMembership: !!res.active,\n"
    "          membershipDiscountPercent: res.discount_percent || 0,\n"
    "          membershipTierName: res.tier_name || '',\n"
    "          membershipStartDate: fmtBsiDate(res.start_date),\n"
    "          membershipExpiryDate: fmtBsiDate(res.expiry_date),\n"
    "          membershipPerks: res.perks || [],\n"
    "        });\n"
    "      }).catch(function () {});\n"
    "    fetch('/salon/api/loyalty_status', { method: 'POST', credentials: 'same-origin', "
    "headers: { 'Content-Type': 'application/json' }, "
    "body: JSON.stringify({ id: 1, jsonrpc: '2.0', method: 'call', params: {} }) })\n"
    "      .then(function (r) { return r.json(); }).then((payload) => {\n"
    "        const res = (payload && payload.result) || {};\n"
    "        this.setState({ loyaltyPoints: res.points || 0 });\n"
    "      }).catch(function () {});\n"
    "    fetch('/salon/api/gift_card_status', { method: 'POST', credentials: 'same-origin', "
    "headers: { 'Content-Type': 'application/json' }, "
    "body: JSON.stringify({ id: 1, jsonrpc: '2.0', method: 'call', params: {} }) })\n"
    "      .then(function (r) { return r.json(); }).then((payload) => {\n"
    "        const res = (payload && payload.result) || {};\n"
    "        this.setState({ myGiftCardCode: (res.active && res.code) || '', "
    "myGiftCardBalance: (res.active && res.balance) || 0 });\n"
    "      }).catch(function () {});\n"
    "    this._navLastY = window.scrollY || 0;\n"
    "    this._onNavScroll = () => {\n"
    "      const y = (window.scrollY !== undefined ? window.scrollY : "
    "document.documentElement.scrollTop) || 0;\n"
    "      const delta = y - this._navLastY;\n"
    "      if (Math.abs(delta) < 5 && y > 80) { return; }\n"
    "      let hidden;\n"
    "      if (y <= 80) { hidden = false; }\n"
    "      else if (delta > 0) { hidden = true; }\n"
    "      else { hidden = false; }\n"
    "      if (hidden !== !!this.state.navHidden) { this.setState({ navHidden: hidden }); }\n"
    "      this._navLastY = y;\n"
    "    };\n"
    "    window.addEventListener('scroll', this._onNavScroll, { passive: true });\n"
    "    window.addEventListener('touchmove', this._onNavScroll, { passive: true });\n"
    "  }"
)

MEMBER_STATE_SRC = "    isMember: false,\n    storeFilter: 'all',"
MEMBER_STATE_DST = (
    "    isMember: false, hasActiveMembership: false, membershipDiscountPercent: 0, "
    "membershipTierName: '', membershipStartDate: '', membershipExpiryDate: '', "
    "membershipPerks: [], loyaltyPoints: 0, myGiftCardCode: '', myGiftCardBalance: 0,"
    "\n    storeFilter: 'all',"
)

MEMBER_PRICE_SRC = "const finalPrice = Math.round(basePrice * (s.isMember ? 0.8 : 1));"
MEMBER_PRICE_DST = (
    "const finalPrice = Math.round(basePrice * (s.hasActiveMembership "
    "? (1 - (s.membershipDiscountPercent || 0) / 100) : 1));"
)

MEMBER_CHECKBOX_SRC = (
    '<label style="display:flex;align-items:center;gap:10px;'
    'background:rgba(232,40,63,.12);padding:14px 16px;border-radius:14px;'
    'margin-bottom:20px;cursor:pointer;font-size:13.5px;color:#454545;">\n'
    '              <input type="checkbox" checked="{{ isMember }}" '
    'sc-camel-on-change="{{ toggleMember }}">\n'
    '              Apply Gold Membership — 20% off this booking\n'
    '            </label>'
)
# PHASE 4 DEV: removed entirely -- the discount is automatic now (see
# MEMBER_PRICE_DST/CONFIRM_DST reading hasActiveMembership directly, no
# toggle involved), and the Booking Summary card's own "Services Subtotal" /
# "✓ <tier> Membership (−X%)" breakdown (see SUMMARY_TOTAL_DST) already
# states the same thing as its own line -- keeping this checkbox-turned-badge
# too would just repeat it a second time on the same card.
MEMBER_CHECKBOX_DST = ''


# --- Remove the Salon 360 tour section (Stores page) -----------------------
# Was: a self-contained "STEP INSIDE / A walk through an Enrich salon" room-by-
# room camera section on the Stores page, backed by a Salon Tour Rooms model in
# the backend that nothing else read (its data was shadowed by a hardcoded local
# ROOMS array in the render logic). Removed entirely per explicit request: the
# markup, its state/method, the render-time IIFE that computed tour* values, and
# the CSS/keyframes used only by it.

TOUR_CSS_SRC = "    /* ── Salon 360 tour ── */\n    @keyframes candleFlicker{ 0%,100%{ transform:scaleY(1) translateY(0); opacity:.95; } 30%{ transform:scaleY(1.18) translateY(-2px); opacity:1; } 62%{ transform:scaleY(.88) translateY(1px); opacity:.82; } }\n    /* authored inside the SVG, so these scale with the room art and can't drift */\n    .svg-ripple{ transform-box:fill-box; transform-origin:center; animation:svgRipple 3.2s ease-out infinite; }\n    .svg-steam{ transform-box:fill-box; transform-origin:center; animation:svgSteam 5s ease-out infinite; }\n    @keyframes svgRipple{ 0%{ transform:scale(.35); opacity:.65; } 100%{ transform:scale(1.6); opacity:0; } }\n    @keyframes svgSteam{ 0%{ transform:translateY(0) scale(.7); opacity:0; } 28%{ opacity:.55; } 100%{ transform:translateY(-58px) scale(1.6); opacity:0; } }\n    @keyframes pendantGlow{ 0%,100%{ opacity:.5; } 50%{ opacity:.9; } }\n    @keyframes steamRise{ 0%{ transform:translateY(0) scale(1); opacity:0; } 25%{ opacity:.5; } 100%{ transform:translateY(-46px) scale(1.5); opacity:0; } }\n    @keyframes dustFloat{ 0%,100%{ transform:translate(0,0); opacity:.25; } 50%{ transform:translate(14px,-20px); opacity:.6; } }"
TOUR_CSS_DST = ''

TOUR_SECTION_SRC = '    <!-- ── Salon 360 tour: scroll the camera room to room ── -->\n    <section data-screen-label="Salon Tour" style="background:linear-gradient(180deg,#0d0b0c,#141011);padding:0 0 70px;overflow:hidden;">\n      <div style="max-width:1280px;margin:0 auto;padding:64px 48px 0;display:flex;justify-content:space-between;align-items:flex-end;flex-wrap:wrap;gap:20px;">\n        <div>\n          <div style="font-size:11.5px;font-weight:800;letter-spacing:2px;color:#e8283f;margin-bottom:12px;">STEP INSIDE</div>\n          <h2 style="font-family:\'Playfair Display\',serif;font-weight:600;font-size:42px;line-height:1.06;color:#fdf3ea;margin:0;">A walk through<br><em style="color:#e8283f;">an Enrich salon.</em></h2>\n        </div>\n        <p style="max-width:340px;font-size:14.5px;line-height:1.7;color:#a79a9d;margin:0;">Every branch follows the same plan — reception to spa suite. Move the camera through it room by room.</p>\n      </div>\n\n      <div style="position:relative;height:540px;margin-top:34px;overflow:hidden;background:#0a0809;">\n        <div style="position:absolute;inset:0;display:flex;width:500%;transform:{{ tourTrack }};transition:transform 1.15s cubic-bezier(.62,0,.18,1);">\n\n          <!-- 1 · Reception -->\n          <div style="position:relative;flex:1 0 20%;height:100%;overflow:hidden;background:linear-gradient(175deg,#2a2024 0%,#1a1417 58%,#0f0c0d 100%);">\n            <div style="position:absolute;left:50%;top:8%;transform:translateX(-50%);width:330px;height:120px;border-radius:10px;background:rgba(232,40,63,.07);border:1px solid rgba(232,40,63,.3);display:flex;align-items:center;justify-content:center;">\n              <span style="font-family:\'Playfair Display\',serif;font-size:46px;color:#fdf3ea;letter-spacing:5px;text-shadow:0 0 26px rgba(232,40,63,.8);">enrich</span>\n            </div>\n            <div style="position:absolute;left:22%;top:0;width:2px;height:24%;background:rgba(253,243,234,.2);"></div>\n            <div style="position:absolute;left:78%;top:0;width:2px;height:24%;background:rgba(253,243,234,.2);"></div>\n            <div style="position:absolute;left:22%;top:24%;transform:translate(-50%,0);width:74px;height:74px;border-radius:50%;background:radial-gradient(circle at 50% 30%,#ffe7c2,#c98a3f);filter:blur(1px);animation:pendantGlow 4.6s ease-in-out infinite;"></div>\n            <div style="position:absolute;left:78%;top:24%;transform:translate(-50%,0);width:74px;height:74px;border-radius:50%;background:radial-gradient(circle at 50% 30%,#ffe7c2,#c98a3f);filter:blur(1px);animation:pendantGlow 4.6s ease-in-out 1.4s infinite;"></div>\n            <svg sc-camel-view-box="0 0 640 540" sc-camel-preserve-aspect-ratio="xMidYMax slice" style="position:absolute;inset:0;width:100%;height:100%;">\n              <rect x="0" y="398" width="640" height="142" fill="#0c0a0b"></rect>\n              <rect x="0" y="396" width="640" height="3" fill="rgba(253,243,234,.12)"></rect>\n              <rect x="186" y="300" width="268" height="98" rx="8" fill="#241c1f"></rect>\n              <rect x="186" y="294" width="268" height="12" rx="6" fill="#3a2c30"></rect>\n              <rect x="200" y="318" width="240" height="3" fill="rgba(232,40,63,.5)"></rect>\n              <rect x="470" y="336" width="120" height="62" rx="12" fill="#2d2529"></rect>\n              <rect x="478" y="326" width="104" height="18" rx="9" fill="#3a3034"></rect>\n              <g fill="#2e4034">\n                <path d="M62 398 q-16 -60 8 -96 q22 34 12 96 z"></path>\n                <path d="M74 398 q22 -52 48 -66 q-8 40 -34 66 z"></path>\n              </g>\n              <rect x="56" y="394" width="70" height="10" rx="4" fill="#241c1f"></rect>\n            </svg>\n            <div style="position:absolute;left:12%;top:36%;width:5px;height:5px;border-radius:50%;background:rgba(253,243,234,.5);animation:dustFloat 9s ease-in-out infinite;"></div>\n            <div style="position:absolute;left:64%;top:52%;width:4px;height:4px;border-radius:50%;background:rgba(253,243,234,.4);animation:dustFloat 11s ease-in-out 2s infinite;"></div>\n          </div>\n\n          <!-- 2 · Styling floor -->\n          <div style="position:relative;flex:1 0 20%;height:100%;overflow:hidden;background:linear-gradient(175deg,#241d20 0%,#181315 60%,#0e0b0c 100%);">\n            <svg sc-camel-view-box="0 0 640 540" sc-camel-preserve-aspect-ratio="xMidYMax slice" style="position:absolute;inset:0;width:100%;height:100%;">\n              <rect x="0" y="410" width="640" height="130" fill="#0d0a0b"></rect>\n              <g stroke="rgba(253,243,234,.05)" stroke-width="2">\n                <path d="M320 410 L60 540"></path><path d="M320 410 L200 540"></path>\n                <path d="M320 410 L440 540"></path><path d="M320 410 L580 540"></path>\n              </g>\n              <g>\n                <rect x="70" y="70" width="150" height="200" rx="74" fill="rgba(253,243,234,.06)" stroke="rgba(232,40,63,.3)" stroke-width="2.5"></rect>\n                <rect x="248" y="70" width="150" height="200" rx="74" fill="rgba(253,243,234,.06)" stroke="rgba(232,40,63,.3)" stroke-width="2.5"></rect>\n                <rect x="426" y="70" width="150" height="200" rx="74" fill="rgba(253,243,234,.06)" stroke="rgba(232,40,63,.3)" stroke-width="2.5"></rect>\n              </g>\n              <g fill="#fdf3ea">\n                <circle cx="86" cy="120" r="5" style="animation:bulbFlicker 4.4s ease-in-out infinite;"></circle>\n                <circle cx="104" cy="86" r="5" style="animation:bulbFlicker 4.4s ease-in-out .4s infinite;"></circle>\n                <circle cx="145" cy="66" r="5" style="animation:bulbFlicker 4.4s ease-in-out .8s infinite;"></circle>\n                <circle cx="186" cy="86" r="5" style="animation:bulbFlicker 4.4s ease-in-out 1.2s infinite;"></circle>\n                <circle cx="204" cy="120" r="5" style="animation:bulbFlicker 4.4s ease-in-out 1.6s infinite;"></circle>\n                <circle cx="264" cy="120" r="5" style="animation:bulbFlicker 4.4s ease-in-out .3s infinite;"></circle>\n                <circle cx="323" cy="66" r="5" style="animation:bulbFlicker 4.4s ease-in-out .9s infinite;"></circle>\n                <circle cx="382" cy="120" r="5" style="animation:bulbFlicker 4.4s ease-in-out 1.5s infinite;"></circle>\n                <circle cx="442" cy="120" r="5" style="animation:bulbFlicker 4.4s ease-in-out .6s infinite;"></circle>\n                <circle cx="501" cy="66" r="5" style="animation:bulbFlicker 4.4s ease-in-out 1.1s infinite;"></circle>\n                <circle cx="560" cy="120" r="5" style="animation:bulbFlicker 4.4s ease-in-out 1.9s infinite;"></circle>\n              </g>\n              <g fill="#241c1f">\n                <rect x="66" y="276" width="158" height="14" rx="7"></rect>\n                <rect x="244" y="276" width="158" height="14" rx="7"></rect>\n                <rect x="422" y="276" width="158" height="14" rx="7"></rect>\n              </g>\n              <g fill="#1b1618">\n                <rect x="118" y="330" width="56" height="18" rx="9"></rect><rect x="138" y="348" width="16" height="62"></rect>\n                <ellipse cx="146" cy="412" rx="42" ry="7"></ellipse>\n                <rect x="296" y="330" width="56" height="18" rx="9"></rect><rect x="316" y="348" width="16" height="62"></rect>\n                <ellipse cx="324" cy="412" rx="42" ry="7"></ellipse>\n                <rect x="474" y="330" width="56" height="18" rx="9"></rect><rect x="494" y="348" width="16" height="62"></rect>\n                <ellipse cx="502" cy="412" rx="42" ry="7"></ellipse>\n              </g>\n              <g fill="#8a2332">\n                <rect x="112" y="286" width="68" height="46" rx="16"></rect>\n                <rect x="290" y="286" width="68" height="46" rx="16"></rect>\n                <rect x="468" y="286" width="68" height="46" rx="16"></rect>\n              </g>\n              <g fill="#0a0809" opacity=".9">\n                <path d="M406 410 q-8 -108 26 -122 l20 -1 q30 18 22 123 z"></path>\n                <circle cx="432" cy="262" r="24"></circle>\n              </g>\n            </svg>\n          </div>\n\n          <!-- 3 · Colour bar -->\n          <div style="position:relative;flex:1 0 20%;height:100%;overflow:hidden;background:linear-gradient(175deg,#2b2029 0%,#1a1319 58%,#0f0b0e 100%);">\n            <svg sc-camel-view-box="0 0 640 540" sc-camel-preserve-aspect-ratio="xMidYMax slice" style="position:absolute;inset:0;width:100%;height:100%;">\n              <rect x="0" y="404" width="640" height="136" fill="#0d0a0c"></rect>\n              <g stroke="#3a2c33" stroke-width="6">\n                <path d="M56 130 H584"></path><path d="M56 208 H584"></path><path d="M56 286 H584"></path>\n              </g>\n              <g>\n                <rect x="72" y="88" width="22" height="40" rx="5" fill="#8a2332"></rect>\n                <rect x="104" y="82" width="22" height="46" rx="5" fill="#c94b3a"></rect>\n                <rect x="136" y="92" width="22" height="36" rx="5" fill="#c9a15a"></rect>\n                <rect x="168" y="80" width="22" height="48" rx="5" fill="#6b3a52"></rect>\n                <rect x="200" y="90" width="22" height="38" rx="5" fill="#2f4a55"></rect>\n                <rect x="232" y="84" width="22" height="44" rx="5" fill="#4a2b1c"></rect>\n                <rect x="264" y="92" width="22" height="36" rx="5" fill="#a83c4a"></rect>\n                <rect x="296" y="82" width="22" height="46" rx="5" fill="#3f6b57"></rect>\n                <rect x="328" y="88" width="22" height="40" rx="5" fill="#8a2332"></rect>\n                <rect x="360" y="86" width="22" height="42" rx="5" fill="#c9a15a"></rect>\n                <rect x="392" y="92" width="22" height="36" rx="5" fill="#6b3a52"></rect>\n                <rect x="424" y="80" width="22" height="48" rx="5" fill="#c94b3a"></rect>\n                <rect x="456" y="90" width="22" height="38" rx="5" fill="#2f4a55"></rect>\n                <rect x="488" y="84" width="22" height="44" rx="5" fill="#4a2b1c"></rect>\n                <rect x="520" y="92" width="22" height="36" rx="5" fill="#a83c4a"></rect>\n              </g>\n              <g>\n                <rect x="88" y="166" width="26" height="42" rx="6" fill="#c9a15a"></rect>\n                <rect x="130" y="160" width="26" height="48" rx="6" fill="#8a2332"></rect>\n                <rect x="172" y="170" width="26" height="38" rx="6" fill="#3f6b57"></rect>\n                <rect x="214" y="164" width="26" height="44" rx="6" fill="#c94b3a"></rect>\n                <rect x="256" y="168" width="26" height="40" rx="6" fill="#2f4a55"></rect>\n                <rect x="298" y="162" width="26" height="46" rx="6" fill="#6b3a52"></rect>\n                <rect x="340" y="170" width="26" height="38" rx="6" fill="#a83c4a"></rect>\n                <rect x="382" y="166" width="26" height="42" rx="6" fill="#4a2b1c"></rect>\n                <rect x="424" y="160" width="26" height="48" rx="6" fill="#c9a15a"></rect>\n                <rect x="466" y="168" width="26" height="40" rx="6" fill="#8a2332"></rect>\n                <rect x="508" y="164" width="26" height="44" rx="6" fill="#3f6b57"></rect>\n              </g>\n              <g>\n                <circle cx="120" cy="256" r="24" fill="#8a2332"></circle>\n                <circle cx="196" cy="256" r="24" fill="#c9a15a"></circle>\n                <circle cx="272" cy="256" r="24" fill="#6b3a52"></circle>\n                <circle cx="348" cy="256" r="24" fill="#2f4a55"></circle>\n                <circle cx="424" cy="256" r="24" fill="#c94b3a"></circle>\n                <circle cx="500" cy="256" r="24" fill="#3f6b57"></circle>\n              </g>\n              <rect x="120" y="332" width="400" height="72" rx="8" fill="#241b20"></rect>\n              <rect x="120" y="326" width="400" height="12" rx="6" fill="#3a2c33"></rect>\n              <ellipse cx="212" cy="326" rx="34" ry="12" fill="#0f0b0e"></ellipse>\n              <ellipse cx="212" cy="322" rx="34" ry="11" fill="#8a2332"></ellipse>\n              <ellipse cx="300" cy="326" rx="30" ry="11" fill="#0f0b0e"></ellipse>\n              <ellipse cx="300" cy="322" rx="30" ry="10" fill="#c9a15a"></ellipse>\n              <g stroke="#e9e2e3" stroke-width="5" stroke-linecap="round">\n                <path d="M386 318 L432 288"></path>\n              </g>\n              <rect x="374" y="312" width="26" height="12" rx="5" fill="#161213" transform="rotate(-33 387 318)"></rect>\n            </svg>\n            <div style="position:absolute;left:33%;top:56%;width:60px;height:60px;border-radius:50%;background:radial-gradient(circle,rgba(232,40,63,.4),transparent 70%);filter:blur(6px);animation:pendantGlow 5s ease-in-out infinite;"></div>\n          </div>\n\n          <!-- 4 · Wash bay -->\n          <div style="position:relative;flex:1 0 20%;height:100%;overflow:hidden;background:linear-gradient(175deg,#1b262b 0%,#131b1f 58%,#0a0e10 100%);">\n            <svg sc-camel-view-box="0 0 640 540" sc-camel-preserve-aspect-ratio="xMidYMax slice" style="position:absolute;inset:0;width:100%;height:100%;">\n              <rect x="0" y="414" width="640" height="126" fill="#090d0f"></rect>\n              <g fill="rgba(120,180,215,.07)">\n                <rect x="40" y="56" width="560" height="150" rx="16"></rect>\n              </g>\n              <g fill="#1e2b31">\n                <path d="M74 300 q0 -54 64 -54 h74 q40 0 40 40 v58 h-178 z"></path>\n                <path d="M242 300 q0 -54 64 -54 h74 q40 0 40 40 v58 h-178 z"></path>\n                <path d="M410 300 q0 -54 64 -54 h74 q40 0 40 40 v58 h-178 z"></path>\n              </g>\n              <g fill="#2b3c44">\n                <ellipse cx="130" cy="252" rx="46" ry="17"></ellipse>\n                <ellipse cx="298" cy="252" rx="46" ry="17"></ellipse>\n                <ellipse cx="466" cy="252" rx="46" ry="17"></ellipse>\n              </g>\n              <g fill="#101a1e">\n                <ellipse cx="130" cy="252" rx="34" ry="11"></ellipse>\n                <ellipse cx="298" cy="252" rx="34" ry="11"></ellipse>\n                <ellipse cx="466" cy="252" rx="34" ry="11"></ellipse>\n              </g>\n              <g fill="#16232a">\n                <rect x="74" y="300" width="178" height="112" rx="10"></rect>\n                <rect x="242" y="300" width="178" height="112" rx="10"></rect>\n                <rect x="410" y="300" width="178" height="112" rx="10"></rect>\n              </g>\n              <g fill="#e9e2e3" opacity=".82">\n                <rect x="452" y="336" width="54" height="14" rx="7"></rect>\n                <rect x="452" y="356" width="54" height="14" rx="7"></rect>\n                <rect x="452" y="376" width="54" height="14" rx="7"></rect>\n              </g>\n              <defs>\n                <radialGradient id="enrSteam" cx=".5" cy=".5" r=".5">\n                  <stop offset="0" stop-color="rgba(210,236,248,.75)"></stop>\n                  <stop offset="1" stop-color="rgba(210,236,248,0)"></stop>\n                </radialGradient>\n              </defs>\n              <g fill="none" stroke="rgba(170,215,242,.7)" stroke-width="2">\n                <circle class="svg-ripple" cx="130" cy="252" r="26"></circle>\n                <circle class="svg-ripple" cx="298" cy="252" r="26" style="animation-delay:1.1s;"></circle>\n                <circle class="svg-ripple" cx="466" cy="252" r="26" style="animation-delay:2.2s;"></circle>\n              </g>\n              <g fill="url(#enrSteam)">\n                <circle class="svg-steam" cx="130" cy="240" r="17"></circle>\n                <circle class="svg-steam" cx="298" cy="240" r="17" style="animation-delay:1.7s;"></circle>\n                <circle class="svg-steam" cx="466" cy="240" r="15" style="animation-delay:3.2s;"></circle>\n              </g>\n            </svg>\n          </div>\n\n          <!-- 5 · Spa suite -->\n          <div style="position:relative;flex:1 0 20%;height:100%;overflow:hidden;background:linear-gradient(175deg,#2b2620 0%,#1a1713 58%,#0e0c0a 100%);">\n            <svg sc-camel-view-box="0 0 640 540" sc-camel-preserve-aspect-ratio="xMidYMax slice" style="position:absolute;inset:0;width:100%;height:100%;">\n              <rect x="0" y="412" width="640" height="128" fill="#0c0a08"></rect>\n              <g fill="#241f18" stroke="#3a3227" stroke-width="3">\n                <rect x="42" y="96" width="86" height="230" rx="6"></rect>\n                <rect x="134" y="76" width="86" height="250" rx="6"></rect>\n                <rect x="226" y="96" width="86" height="230" rx="6"></rect>\n              </g>\n              <rect x="300" y="292" width="290" height="30" rx="15" fill="#e9e2e3"></rect>\n              <rect x="300" y="318" width="290" height="60" rx="10" fill="#3a3227"></rect>\n              <rect x="316" y="270" width="76" height="26" rx="13" fill="#f4eeea"></rect>\n              <g fill="#241f18">\n                <rect x="318" y="378" width="16" height="38"></rect>\n                <rect x="556" y="378" width="16" height="38"></rect>\n              </g>\n              <g fill="#2e4034">\n                <path d="M470 96 q-26 54 -6 96 q30 -30 26 -96 z"></path>\n                <path d="M494 96 q28 52 10 96 q-32 -28 -30 -96 z"></path>\n              </g>\n              <rect x="466" y="60" width="34" height="40" rx="6" fill="#3a3227"></rect>\n            </svg>\n            <div style="position:absolute;left:56%;bottom:22%;width:16px;height:34px;border-radius:4px;background:#f4eeea;"></div>\n            <div style="position:absolute;left:56.6%;bottom:28%;width:11px;height:19px;border-radius:50% 50% 42% 42%;background:radial-gradient(circle at 50% 74%,#fff3c4,#ff9d3c 62%,rgba(255,120,30,0));transform-origin:50% 100%;animation:candleFlicker 1.6s ease-in-out infinite;"></div>\n            <div style="position:absolute;left:62%;bottom:22%;width:14px;height:26px;border-radius:4px;background:#e4ded9;"></div>\n            <div style="position:absolute;left:62.5%;bottom:26.5%;width:10px;height:17px;border-radius:50% 50% 42% 42%;background:radial-gradient(circle at 50% 74%,#fff3c4,#ff9d3c 62%,rgba(255,120,30,0));transform-origin:50% 100%;animation:candleFlicker 1.9s ease-in-out .5s infinite;"></div>\n            <div style="position:absolute;left:52%;bottom:14%;width:180px;height:120px;border-radius:50%;background:radial-gradient(circle,rgba(255,170,80,.22),transparent 70%);filter:blur(8px);animation:pendantGlow 5.4s ease-in-out infinite;"></div>\n          </div>\n        </div>\n\n        <!-- camera furniture -->\n        <div style="position:absolute;inset:0;pointer-events:none;background:radial-gradient(ellipse at 50% 45%,transparent 42%,rgba(6,5,5,.72) 100%);"></div>\n        <div style="position:absolute;left:0;right:0;top:0;height:80px;pointer-events:none;background:linear-gradient(180deg,rgba(10,8,9,.85),transparent);"></div>\n\n        <div style="position:absolute;left:48px;bottom:36px;z-index:4;max-width:330px;background:rgba(10,8,9,.72);backdrop-filter:blur(14px);border:1px solid rgba(253,243,234,.14);border-radius:18px;padding:20px 22px;box-shadow:0 26px 56px -26px rgba(0,0,0,.95);">\n          <div style="display:flex;align-items:baseline;gap:11px;margin-bottom:8px;">\n            <span style="font-family:\'Playfair Display\',serif;font-size:28px;color:#e8283f;line-height:1;">{{ tourNum }}</span>\n            <span style="font-family:\'Playfair Display\',serif;font-size:23px;color:#fdf3ea;">{{ tourName }}</span>\n          </div>\n          <p style="font-size:13.5px;line-height:1.65;color:#b9acaf;margin:0 0 14px;">{{ tourCaption }}</p>\n          <div style="display:flex;gap:8px;flex-wrap:wrap;">\n            <sc-for list="{{ tourTags }}" as="tg" hint-placeholder-count="3">\n              <span style="font-size:10.5px;font-weight:700;letter-spacing:.6px;color:#fdf3ea;background:rgba(253,243,234,.1);border:1px solid rgba(253,243,234,.16);padding:5px 11px;border-radius:999px;">{{ tg.label }}</span>\n            </sc-for>\n          </div>\n        </div>\n\n        <button sc-camel-on-click="{{ tourPrev }}" aria-label="Previous room" style="position:absolute;left:48px;top:50%;transform:translateY(-50%);z-index:5;width:48px;height:48px;border-radius:50%;background:rgba(10,8,9,.6);backdrop-filter:blur(8px);border:1px solid rgba(253,243,234,.22);color:#fdf3ea;font-size:19px;cursor:pointer;transition:background .2s,border-color .2s;" style-hover="background:#e8283f;border-color:#e8283f;">←</button>\n        <button sc-camel-on-click="{{ tourNext }}" aria-label="Next room" style="position:absolute;right:48px;top:50%;transform:translateY(-50%);z-index:5;width:48px;height:48px;border-radius:50%;background:rgba(10,8,9,.6);backdrop-filter:blur(8px);border:1px solid rgba(253,243,234,.22);color:#fdf3ea;font-size:19px;cursor:pointer;transition:background .2s,border-color .2s;" style-hover="background:#e8283f;border-color:#e8283f;">→</button>\n\n        <div style="position:absolute;right:48px;bottom:40px;z-index:5;display:flex;gap:10px;align-items:center;">\n          <sc-for list="{{ tourDots }}" as="d" hint-placeholder-count="5">\n            <button sc-camel-on-click="{{ d.onClick }}" aria-label="{{ d.name }}" style="width:{{ d.w }}px;height:8px;border-radius:999px;border:none;padding:0;cursor:pointer;background:{{ d.bg }};transition:width .3s cubic-bezier(.2,.9,.2,1),background .3s;"></button>\n          </sc-for>\n        </div>\n      </div>\n    </section>'
TOUR_SECTION_DST = ''

TOUR_STATE_SRC = '    tourIdx: 0,\n'
TOUR_STATE_DST = ''

TOUR_METHOD_SRC = '  setTour = (i) => this.setState({ tourIdx: Math.max(0, Math.min(4, i)) });\n'
TOUR_METHOD_DST = ''

TOUR_RENDER_SRC = "      ...(() => {\n        const ROOMS = [\n          { num: '01', name: 'Reception', caption: 'Warm ink walls, a backlit wordmark and a seat while we bring you chai. Your stylist meets you here, not at the chair.',\n            tags: ['Welcome chai', 'Consultation', 'Cloakroom'] },\n          { num: '02', name: 'Styling Floor', caption: 'Six mirror stations under bulb arcs, spaced so no two clients share an elbow. Every chair faces its own light.',\n            tags: ['6 stations', 'Ring-lit mirrors', 'Adjustable chairs'] },\n          { num: '03', name: 'Colour Bar', caption: 'The full L\\u2019Or\\u00e9al Professionnel shade library, weighed and mixed to the gram in front of you \\u2014 never pre-batched.',\n            tags: ['120+ shades', 'Weighed to gram', 'Patch tested'] },\n          { num: '04', name: 'Wash Bay', caption: 'Reclining ceramic basins with neck support and warmed towels. The head massage is included, not an upsell.',\n            tags: ['Recline basins', 'Warm towels', 'Free head massage'] },\n          { num: '05', name: 'Spa Suite', caption: 'A separate room behind a screen \\u2014 candles, low light and no mirrors. For facials, threading and anything that needs quiet.',\n            tags: ['Private room', 'Facials', 'Aromatherapy'] },\n        ];\n        const i = s.tourIdx || 0;\n        return {\n          tourTrack: `translateX(-${i * 20}%)`,\n          tourNum: ROOMS[i].num, tourName: ROOMS[i].name, tourCaption: ROOMS[i].caption,\n          tourTags: ROOMS[i].tags.map((label) => ({ label })),\n          tourPrev: () => this.setTour(i - 1),\n          tourNext: () => this.setTour(i === 4 ? 0 : i + 1),\n          tourDots: ROOMS.map((r, k) => ({\n            name: r.name, onClick: () => this.setTour(k),\n            w: k === i ? 30 : 8,\n            bg: k === i ? '#e8283f' : 'rgba(253,243,234,.32)',\n          })),\n        };\n      })(),\n"
TOUR_RENDER_DST = ''

# --- Transformations gallery -- before/after photos crop off the top of the face ---
# Was: both photos are absolutely positioned to fill a fixed h:260px card with
# object-fit:cover and no object-position, so it defaults to center/center --
# cropping equally off the top and bottom. An uploaded photo taller (relative to
# its width) than the card's own ~1.6:1 aspect ratio needs more of that height
# cropped away than a photo would that already matches the card, and a center
# crop takes that difference from the top as often as the bottom, cutting into
# the hairline/forehead exactly like the reported "face is cut from top" --
# reproduced with the reported photo. Now: object-position:top keeps the crop
# anchored to the top of the photo, so a portrait taller than the card loses
# height off the bottom (chin/shoulders/background) instead of the face.
GALLERY_BEFORE_IMG_SRC = (
    '<img src="{{ g.beforeSrc }}" alt="{{ g.beforeLabel }}" '
    'style="position:absolute;inset:0;width:100%;height:100%;object-fit:cover;pointer-events:none;">'
)
GALLERY_BEFORE_IMG_DST = (
    '<img src="{{ g.beforeSrc }}" alt="{{ g.beforeLabel }}" '
    'style="position:absolute;inset:0;width:100%;height:100%;object-fit:cover;object-position:top;pointer-events:none;">'
)

GALLERY_AFTER_IMG_SRC = (
    '<img src="{{ g.afterSrc }}" alt="{{ g.afterLabel }}" '
    'style="position:absolute;inset:0;width:100%;height:100%;object-fit:cover;pointer-events:none;">'
)
GALLERY_AFTER_IMG_DST = (
    '<img src="{{ g.afterSrc }}" alt="{{ g.afterLabel }}" '
    'style="position:absolute;inset:0;width:100%;height:100%;object-fit:cover;object-position:top;pointer-events:none;">'
)


# --- PHASE 3 DEV: booking wizard Service step ------------------------------
# Was: City -> Store -> Chair -> Time -> Confirm, with no step that ever asked
# which service the customer wanted -- a service only ever reached the booking
# lead via three side doors (the Services page's own "Book" button, a stylist's
# profile, or a loyalty redemption), each of which skipped the wizard's own
# steps entirely and jumped straight to City with the service already tucked
# into state. A customer starting from Home/Stores -- the ordinary path --
# never got asked at all, and the Confirm screen's own "Estimated total" was a
# flat, hardcoded ₹999 regardless of what (if anything) got picked. Now: a new
# Service step sits between Store and Chair, reading the same live SERVICES_DATA
# the Services page already renders (see bsi.enrich.data._bsi_services) --
# same category pills, same card layout -- and picking a card carries the
# service's own real id/name/price into the booking the same way the other
# three entry points always did, before advancing to Chair. Every step after
# Store shifts up by one (Chair 3->4, Time 4->5, Confirm 5->6) to make room.
STEP_DEFS_SRC = (
    "const bookingStepsDefs = [{ n: 1, label: 'City' }, { n: 2, label: 'Store' }, "
    "{ n: 3, label: 'Chair' }, { n: 4, label: 'Time' }, { n: 5, label: 'Confirm' }];"
)
STEP_DEFS_DST = (
    "const bookingStepsDefs = [{ n: 1, label: 'City' }, { n: 2, label: 'Store' }, "
    "{ n: 3, label: 'Service' }, { n: 4, label: 'Chair' }, { n: 5, label: 'Time' }, "
    "{ n: 6, label: 'Confirm' }];"
)

STEP_IS6_SRC = (
    "bookingStepIs1: step === 1, bookingStepIs2: step === 2, bookingStepIs3: step === 3, "
    "bookingStepIs4: step === 4, bookingStepIs5: step === 5,"
)
STEP_IS6_DST = STEP_IS6_SRC + " bookingStepIs6: step === 6,"

# The template only ever sees a local const if it is also listed on the render
# function's own exposed-props object -- bookingCityChips/bookingStoreChips sit
# there as bare shorthand properties for exactly that reason, so
# bookingServiceCategories/bookingFilteredServices have to join them or the
# Service step's pills and cards render as empty (defining the const alone,
# see STEP_COMPUTE_DST below, silently isn't enough).
STEP_EXPOSE_SRC = "bookingCityChips, bookingStoreChips, bookingBranchesJson,"
STEP_EXPOSE_DST = (
    "bookingCityChips, bookingStoreChips, bookingBranchesJson, "
    "bookingServiceCategories, bookingFilteredServices, "
    "bookingServicesNext: this.bookingServicesNext, bookingServiceNextDisabled, "
    "bookingServiceNextBg, bookingServiceNextLabel, bookingPackages,"
)

# Cascading renumber of the three later steps' own sc-if gate -- highest
# number first, so each anchor is still unique and untouched when its own
# patch runs (renumbering low-to-high would have the Chair->4 patch's own
# output collide with Time's still-unrenumbered ==4 gate, and so on).
STEP_CONFIRM_TAG_SRC = '<sc-if value="{{ bookingStepIs5 }}" hint-placeholder-val="{{ false }}">'
STEP_CONFIRM_TAG_DST = '<sc-if value="{{ bookingStepIs6 }}" hint-placeholder-val="{{ false }}">'

STEP_TIME_TAG_SRC = '<sc-if value="{{ bookingStepIs4 }}" hint-placeholder-val="{{ false }}">'
STEP_TIME_TAG_DST = '<sc-if value="{{ bookingStepIs5 }}" hint-placeholder-val="{{ false }}">'

# The Chair step's own gate renumbers the same way, with the entire new
# Service step's markup prepended right in front of it -- same card layout as
# the Services page (see SERVICE_POINTS_MARKUP_DST above), minus the "Book"/
# redeem actions that page has no need for here: clicking a card selects it
# and advances to Chair in one step, the same "click to pick and move on"
# pattern the City step already uses.
STEP_CHAIR_TAG_SRC = '<sc-if value="{{ bookingStepIs3 }}" hint-placeholder-val="{{ false }}">'
STEP_CHAIR_TAG_DST = (
    '<sc-if value="{{ bookingStepIs3 }}" hint-placeholder-val="{{ false }}">\n'
    '        <div>\n'
    '          <p style="font-size:14.5px;color:#767676;margin:0 0 22px;">'
    'Choose the service you would like to book.</p>\n'
    '          <div style="display:grid;grid-template-columns:1fr 280px;gap:26px;align-items:start;">\n'
    '            <div>\n'
    '          <div style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:22px;">\n'
    '            <sc-for list="{{ bookingServiceCategories }}" as="c" hint-placeholder-count="5">\n'
    '              <button sc-camel-on-click="{{ c.onClick }}" style="border:1.5px solid {{ c.border }};'
    'background:{{ c.bg }};color:{{ c.color }};padding:9px 18px;border-radius:999px;font-size:12.5px;'
    'font-weight:700;cursor:pointer;transition:all .2s;box-shadow:{{ c.shadow }};">{{ c.name }}</button>\n'
    '            </sc-for>\n'
    '          </div>\n'
    '          <sc-for list="{{ bookingFilteredServices }}" as="sv" hint-placeholder-count="4">\n'
    '            <div sc-camel-on-click="{{ sv.onClick }}" style="position:relative;display:flex;'
    'justify-content:space-between;align-items:center;gap:20px;padding:20px 18px;border-radius:16px;'
    'background:{{ sv.cardBg }};border:{{ sv.cardBorder }};margin-bottom:10px;overflow:hidden;'
    'cursor:pointer;transition:transform .22s,box-shadow .22s;box-shadow:0 3px 12px -10px rgba(20,17,17,.6);'
    'animation:fadeUp .55s ease-out {{ sv.delay }}s both;" '
    'style-hover="transform:translateX(5px);box-shadow:0 18px 40px -22px rgba(20,17,17,.55);">\n'
    '              <div style="position:absolute;left:0;top:0;bottom:0;width:3px;'
    'background:linear-gradient(180deg,#e8283f,#8a2332);"></div>\n'
    '              <div style="display:flex;align-items:center;gap:16px;min-width:0;">\n'
    '                <div style="width:40px;height:40px;border-radius:12px;'
    'background:linear-gradient(140deg,#241b1e,#0f0c0d);color:#e8283f;display:flex;align-items:center;'
    'justify-content:center;font-size:16px;flex-shrink:0;">{{ sv.selected ? \'✓\' : \'✦\' }}</div>\n'
    '                <div style="min-width:0;">\n'
    '                  <div style="font-size:15.5px;font-weight:700;color:#161213;margin-bottom:3px;">'
    '{{ sv.name }}</div>\n'
    '                  <div style="font-size:12px;color:#767676;">{{ sv.duration }}</div>\n'
    '                  <sc-if value="{{ sv.description }}" hint-placeholder-val="{{ false }}">\n'
    '                    <div style="font-size:11.5px;color:#9b9093;margin-top:3px;max-width:360px;">'
    '{{ sv.description }}</div>\n'
    '                  </sc-if>\n'
    '                </div>\n'
    '              </div>\n'
    '              <div style="text-align:right;flex-shrink:0;">\n'
    '                <div style="font-size:15px;font-weight:800;color:#161213;">{{ sv.price }}</div>\n'
    '              </div>\n'
    '            </div>\n'
    '          </sc-for>\n'
    '          <button sc-camel-on-click="{{ bookingServicesNext }}" disabled="{{ bookingServiceNextDisabled }}" '
    'style="width:100%;background:{{ bookingServiceNextBg }};color:#fff;border:none;padding:15px;'
    'border-radius:12px;font-size:14.5px;font-weight:700;cursor:pointer;transition:transform .2s;'
    'margin-top:8px;" style-hover="transform:translateY(-2px);">{{ bookingServiceNextLabel }}</button>\n'
    '            </div>\n'
    '            <sc-if value="{{ bookingPackages.length }}" hint-placeholder-val="{{ false }}">\n'
    '            <div style="position:sticky;top:100px;">\n'
    '              <div style="font-size:11px;font-weight:800;letter-spacing:1.4px;color:#e8283f;'
    'margin-bottom:14px;">RECOMMENDED PACKAGES</div>\n'
    '              <sc-for list="{{ bookingPackages }}" as="pkg" hint-placeholder-count="2">\n'
    '                <div style="position:relative;background:{{ pkg.cardBg }};border:{{ pkg.cardBorder }};'
    'border-radius:16px;padding:18px;margin-bottom:14px;overflow:hidden;box-shadow:0 3px 12px -10px '
    'rgba(20,17,17,.5);">\n'
    '                  <sc-if value="{{ pkg.saveLabel }}" hint-placeholder-val="{{ false }}">\n'
    '                    <div style="position:absolute;top:14px;right:14px;background:#3ddc84;'
    'color:#161213;font-size:9px;font-weight:800;letter-spacing:.3px;padding:3px 9px;border-radius:999px;">'
    '{{ pkg.saveLabel }}</div>\n'
    '                  </sc-if>\n'
    '                  <div style="font-family:\'Playfair Display\',serif;font-size:16px;color:#161213;'
    'margin-bottom:6px;padding-right:50px;">{{ pkg.name }}</div>\n'
    '                  <div style="font-size:11.5px;color:#767676;margin-bottom:12px;line-height:1.5;">'
    '{{ pkg.servicesLabel }}</div>\n'
    '                  <div style="display:flex;align-items:baseline;gap:8px;margin-bottom:14px;">\n'
    '                    <sc-if value="{{ pkg.originalPrice }}" hint-placeholder-val="{{ false }}">\n'
    '                      <span style="font-size:12px;color:#9b9093;text-decoration:line-through;">'
    '{{ pkg.originalPrice }}</span>\n'
    '                    </sc-if>\n'
    '                    <span style="font-size:18px;font-weight:800;color:#e8283f;">{{ pkg.price }}</span>\n'
    '                  </div>\n'
    '                  <button sc-camel-on-click="{{ pkg.onClick }}" style="width:100%;'
    'background:{{ pkg.btnBg }};color:#ffffff;border:none;padding:11px;border-radius:10px;'
    'font-size:12.5px;font-weight:700;cursor:pointer;transition:transform .2s;" '
    'style-hover="transform:translateY(-2px);">{{ pkg.btnLabel }}</button>\n'
    '                </div>\n'
    '              </sc-for>\n'
    '            </div>\n'
    '            </sc-if>\n'
    '          </div>\n'
    '        </div>\n'
    '      </sc-if>\n'
    '\n'
    '      <sc-if value="{{ bookingStepIs4 }}" hint-placeholder-val="{{ false }}">'
)

# Category pills and card list for the new step, computed the same place the
# other booking-wizard values already are (right after bookingStoreChips) --
# same shape as the Services page's own serviceCategories/filteredServices,
# but keyed on the booking wizard's own activeServiceCat so browsing services
# mid-booking never disturbs the Services page's own filter if the visitor
# has that open in another tab. Price/discount maths mirror the Confirm
# screen's own membership multiplier (see MEMBER_PRICE_DST) so a member sees
# the same adjusted figure here that they will at Confirm.
#
# PHASE 3 DEV: multiple services per booking -- the backend already supports
# it (bsi_service_ids is a many2many, see bsi_salon_booking_mixin), the wizard
# just never asked for more than one. Cards toggle in/out of
# state.bookingServiceIds (same "tap to add/remove" pattern the Chair step's
# own toggleChair already uses for its own multi-select), with an explicit
# Continue button rather than the old click-and-auto-advance -- a customer
# picking three services needs to tap all three before moving on, not get
# bounced to Chair after the first tap. bookingServiceId (singular) is still
# read as a one-time fallback for a service carried in from an entry point
# that predates multi-select (Services page "Book", loyalty redemption).
STEP_COMPUTE_SRC = (
    "const bookingStoreChips = bookingCity ? bookingCity.branches.map((b, i) => ({\n"
    "      id: b.id, name: b.name, area: b.area, rating: b.rating, delay: (i * 0.06).toFixed(2),\n"
    "      ...waitOf(b), onClick: () => this.bookingSelectStoreAndNext(b.id),\n"
    "    })) : [];"
)
STEP_COMPUTE_DST = STEP_COMPUTE_SRC + (
    "\n    const bookingServiceCatDefs = [\n"
    "      { id: 'hair', name: 'Hair' }, { id: 'skin', name: 'Skin' }, { id: 'makeup', name: 'Makeup' },\n"
    "      { id: 'waxing', name: 'Waxing & Threading' }, { id: 'handsfeet', name: 'Hands & Feet' },\n"
    "    ].filter((c) => (SERVICES_DATA[c.id] || []).length);\n"
    "    const bookingActiveServiceCat = (s.bookingActiveServiceCat "
    "&& (SERVICES_DATA[s.bookingActiveServiceCat] || []).length) "
    "? s.bookingActiveServiceCat : ((bookingServiceCatDefs[0] || {}).id || 'hair');\n"
    "    const bookingServiceCategories = bookingServiceCatDefs.map((c) => ({\n"
    "      ...c, onClick: () => this.setState({ bookingActiveServiceCat: c.id }),\n"
    "      bg: bookingActiveServiceCat === c.id ? '#161213' : '#ffffff',\n"
    "      color: bookingActiveServiceCat === c.id ? '#fdf3ea' : '#454545',\n"
    "      border: bookingActiveServiceCat === c.id ? '#161213' : 'rgba(20,17,17,.14)',\n"
    "      shadow: bookingActiveServiceCat === c.id ? '0 12px 26px -14px rgba(20,17,17,.9)' "
    ": '0 3px 10px -8px rgba(20,17,17,.5)',\n"
    "    }));\n"
    "    const bookingSelectedServiceIds = (s.bookingServiceIds && s.bookingServiceIds.length) "
    "? s.bookingServiceIds : (s.bookingServiceId ? [s.bookingServiceId] : []);\n"
    # PHASE 4 DEV: services always show their own original price here, even
    # for a member -- the membership discount applies once, to the whole
    # booking subtotal, on the Confirm screen (see BASEPRICE_DST/
    # STEP_SUMMARY_COMPUTE_DST's summaryServicesAmount/membershipDiscount*),
    # not per service. Showing a second, already-discounted price on every
    # card here would double up with that and make the two screens disagree
    # on what a given service actually costs.
    "    const bookingFilteredServices = (SERVICES_DATA[bookingActiveServiceCat] || []).map((sv, i) => {\n"
    "      const selected = bookingSelectedServiceIds.indexOf(sv.id) !== -1;\n"
    "      return { ...sv, delay: (i * 0.06).toFixed(2), selected,\n"
    "        cardBorder: selected ? '2px solid #e8283f' : '1px solid rgba(20,17,17,.07)',\n"
    "        cardBg: selected ? 'rgba(232,40,63,.05)' : '#ffffff',\n"
    "        onClick: () => this.bookingToggleService(sv.id),\n"
    "      };\n"
    "    });\n"
    "    const bookingServiceNextDisabled = !bookingSelectedServiceIds.length;\n"
    "    const bookingServiceNextBg = bookingSelectedServiceIds.length ? wine : '#d9c3c9';\n"
    "    const bookingServiceNextLabel = bookingSelectedServiceIds.length > 1 "
    "? ('Continue with ' + bookingSelectedServiceIds.length + ' services \\u2192') : 'Continue to Chair \\u2192';\n"
    # PHASE 5 DEV: recommended packages sidebar. Packages have no per-customer
    # eligibility/expiry concept in the backend (see bsi.salon.package --
    # it's a static bundle catalogue, gated only by its own active flag and
    # the site-wide bsi_salon_backend.show_packages toggle already baked into
    # whether BSI_PACKAGES is non-empty at all), so every package is shown to
    # every customer -- there is nothing server-side yet to filter "eligible"
    # down further than that.
    "    const bookingPackages = (BSI_PACKAGES || []).map((p) => {\n"
    "      const applied = s.bookingPackageId === p.id;\n"
    "      return {\n"
    "        id: p.id, name: p.name, price: p.price, originalPrice: p.original_price, "
    "saveLabel: p.save_label, description: p.description,\n"
    "        servicesLabel: (p.service_names || []).join(' + '), applied,\n"
    "        cardBorder: applied ? '2px solid #e8283f' : '1px solid rgba(20,17,17,.08)',\n"
    "        cardBg: applied ? 'rgba(232,40,63,.04)' : '#ffffff',\n"
    "        btnBg: applied ? '#161213' : '#e8283f',\n"
    "        btnLabel: applied ? 'Applied \\u2713' : 'Apply Package',\n"
    "        onClick: () => this.bookingApplyPackage(p.id, p.service_ids, p.price_amount, p.name),\n"
    "      };\n"
    "    });"
)

# Toggle a service in/out of the multi-select, and the explicit Continue that
# advances once at least one is picked. Anchored onto CHAIRS_STORE_DST's own
# already-patched text (this file's own patches apply in order, and that one
# runs first -- see the PATCHES tuple below) so this lands right next to the
# sibling bookingSelectStoreAndNext method.
STEP_SERVICE_METHOD_SRC = CHAIRS_STORE_DST
STEP_SERVICE_METHOD_DST = CHAIRS_STORE_DST + (
    "\n  bookingToggleService = (id) => this.setState((s) => {\n"
    "    const current = (s.bookingServiceIds && s.bookingServiceIds.length) "
    "? s.bookingServiceIds.slice() : (s.bookingServiceId ? [s.bookingServiceId] : []);\n"
    "    const idx = current.indexOf(id);\n"
    "    if (idx === -1) { current.push(id); } else { current.splice(idx, 1); }\n"
    # A package requires bsi_service_ids to exactly equal its own services
    # server-side (bsi_salon_booking_mixin._bsi_check_package_exclusive_common)
    # -- picking/removing a service by hand breaks that, so it always drops
    # back to a normal a-la-carte booking rather than silently keeping a
    # "package" label the selection no longer matches.
    "    return { bookingServiceIds: current, bookingServiceId: null, "
    "bookingPackageId: null, bookingPackageName: null, bookingPackagePrice: null };\n"
    "  });\n"
    "  bookingServicesNext = () => this.setState((s) => {\n"
    "    const ids = (s.bookingServiceIds && s.bookingServiceIds.length) "
    "? s.bookingServiceIds : (s.bookingServiceId ? [s.bookingServiceId] : []);\n"
    "    if (!ids.length) { return {}; }\n"
    "    return { booking: { ...s.booking, step: 4 }, bookingServiceIds: ids, "
    "bookingMaxStep: Math.max(s.bookingMaxStep || 1, 4) };\n"
    "  });\n"
    # Applying a package auto-fills its own services (mirroring the backend's
    # own _bsi_onchange_package_common) and prices the booking at the
    # package's flat price instead of a sum of services (see BASEPRICE_DST) --
    # advances straight to Chair, same as picking services normally does.
    "  bookingApplyPackage = (packageId, serviceIds, priceAmount, name) => this.setState((s) => ({\n"
    "    booking: { ...s.booking, step: 4 }, bookingMaxStep: Math.max(s.bookingMaxStep || 1, 4),\n"
    "    bookingPackageId: packageId, bookingPackageName: name, bookingPackagePrice: priceAmount,\n"
    "    bookingServiceIds: (serviceIds || []).slice(), bookingServiceId: null,\n"
    "  }));"
)

STEP_CHAIRNEXT_SRC = (
    "chairNext = () => { if (this.state.selectedChairIds.length) this.setState((s) => "
    "({ booking: { ...s.booking, step: 4 } })); };"
)
STEP_CHAIRNEXT_DST = (
    "chairNext = () => { if (this.state.selectedChairIds.length) this.setState((s) => "
    "({ booking: { ...s.booking, step: 5 }, bookingMaxStep: Math.max(s.bookingMaxStep || 1, 5) })); };"
)

STEP_SELECTTIME_SRC = (
    "selectTimeAndNext = (t) => this.setState((s) => "
    "({ selectedTime: t, booking: { ...s.booking, step: 5 } }));"
)
STEP_SELECTTIME_DST = (
    "selectTimeAndNext = (t) => this.setState((s) => "
    "({ selectedTime: t, booking: { ...s.booking, step: 6 }, "
    "bookingMaxStep: Math.max(s.bookingMaxStep || 1, 6) }));"
)

STEP_TIMENEXT_SRC = (
    "timeNext = () => { if (this.state.selectedTime) this.setState((s) => "
    "({ booking: { ...s.booking, step: 5 } })); };"
)
STEP_TIMENEXT_DST = (
    "timeNext = () => { if (this.state.selectedTime) this.setState((s) => "
    "({ booking: { ...s.booking, step: 6 }, bookingMaxStep: Math.max(s.bookingMaxStep || 1, 6) })); };"
)

# Booking Summary (Confirm screen) -- show which service was booked alongside
# City/Branch/Chair/Time, not just the total (see BASEPRICE_DST for the total
# itself now pricing off the same selection).
STEP_SUMMARY_COMPUTE_SRC = (
    "summaryTime: s.selectedTime || '',\n"
    "      isMember: s.isMember, toggleMember: this.toggleMember,"
)
STEP_SUMMARY_COMPUTE_DST = (
    "summaryTime: s.selectedTime || '',\n"
    "      summaryService: (function () {\n"
    "        if (s.bookingPackageId) { return s.bookingPackageName + ' (Package)'; }\n"
    "        const ids = (s.bookingServiceIds && s.bookingServiceIds.length) "
    "? s.bookingServiceIds : (s.bookingServiceId ? [s.bookingServiceId] : []);\n"
    "        if (!ids.length) { return s.rewardServiceName || ''; }\n"
    "        const all = [].concat.apply([], Object.keys(SERVICES_DATA).map((k) => SERVICES_DATA[k]));\n"
    "        const names = ids.map((id) => { const rec = all.find((x) => x.id === id); "
    "return rec ? rec.name : null; }).filter(Boolean);\n"
    "        return names.length ? names.join(', ') : (s.rewardServiceName || '');\n"
    "      })(),\n"
    # PHASE 3 DEV: the Confirm button's own label/colour/cursor used to be
    # ternaries written directly inside {{ }} markup interpolation (see the
    # now-retired BOOKING_ERROR_BANNER_DST) -- for reasons this compiled
    # runtime doesn't surface an error for, a ternary *expression* evaluated
    # inline in markup silently comes back blank instead of picking a branch,
    # so the button rendered with no label and no colour even though
    # confirmBooking/bookingSubmitting/bookingError all worked correctly
    # underneath. A plain identifier interpolation of a JS-computed value
    # (exactly the pattern every other field on this card already uses, e.g.
    # summaryService just above) doesn't have that problem, so the ternary is
    # computed here instead and the markup just reads the plain result.
    "      confirmBtnLabel: s.bookingSubmitting ? 'Confirming…' : 'Confirm Booking',\n"
    "      confirmBtnBg: s.bookingSubmitting ? 'rgba(232,40,63,.35)' "
    ": 'linear-gradient(120deg,#ff3b57,#c81f36)',\n"
    "      confirmBtnCursor: s.bookingSubmitting ? 'not-allowed' : 'pointer',\n"
    # PHASE 4 DEV: services show their own original price everywhere (see
    # STEP_COMPUTE_DST above) -- the membership discount only ever appears as
    # its own line here, applied to the services subtotal, matching
    # bsi_salon_booking_mixin's own "services_amount stays undiscounted,
    # discount is a separate line against the subtotal" shape server-side.
    "      summaryHasServicesAmount: bsiSvcTotal > 0,\n"
    "      summaryServicesAmount: '₹' + Math.round(bsiSvcTotal),\n"
    "      summaryMembershipLabel: s.hasActiveMembership "
    "? (s.membershipTierName + ' Membership (−' + s.membershipDiscountPercent + '%)') : '',\n"
    "      summaryMembershipDiscountLabel: s.hasActiveMembership "
    "? ('−₹' + Math.round(bsiSvcTotal * (s.membershipDiscountPercent || 0) / 100)) : '',\n"
    "      isMember: s.isMember, toggleMember: this.toggleMember,"
)

# --- PHASE 4 DEV: Active Membership Plan banner (Membership page) ----------
# Was: the Membership page only ever showed the three tiers to compare/buy
# (with a "Current Plan" ribbon on whichever tier card matched, see
# TIER_CURRENT_SRC/DST above) -- no place on the site actually stated what a
# member's own plan was: since when, until when, or what its perks were, even
# though bsi.salon.membership.subscription already tracks exactly that.
# Reuses the same "membershipPerkRows" exposure pattern as tiersDisplay right
# next to it, mapping the plain string array /salon/api/membership_status
# already returns (see main.py's own PHASE 4 DEV comment) into the {label}
# shape sc-for needs, same as e.g. tourTags elsewhere in this file.
MEMBERSHIP_PERKS_EXPOSE_SRC = "      tiersDisplay,\n"
MEMBERSHIP_PERKS_EXPOSE_DST = (
    "      tiersDisplay,\n"
    "      membershipPerkRows: (s.membershipPerks || []).map((p) => ({ label: p })),\n"
)

# Banner markup itself -- same dark "Appointment Pass" ticket language used
# for the Booking Summary and confirmed-ticket screens (see SUMMARY_GRID_DST
# above), so a member sees one consistent premium visual identity for "this
# is your verified status" everywhere the site shows it, not a plain card
# here and a fancy ticket elsewhere. Sits above the tier-comparison grid,
# which stays exactly as it is (a member can still see/compare other tiers).
MEMBERSHIP_BANNER_SRC = (
    'Yearly · Save 25%</button>\n'
    '        </div>\n'
    '      </div>\n'
    '\n'
    '      <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:22px;margin-bottom:60px;">'
)
MEMBERSHIP_BANNER_DST = (
    'Yearly · Save 25%</button>\n'
    '        </div>\n'
    '      </div>\n'
    '\n'
    '      <sc-if value="{{ hasActiveMembership }}" hint-placeholder-val="{{ false }}">\n'
    '      <div style="position:relative;border-radius:24px;overflow:hidden;'
    'background:linear-gradient(150deg,#241b1e,#141013 62%,#0c0a0b);'
    'box-shadow:0 34px 74px -32px rgba(12,10,12,.95);margin-bottom:44px;'
    'animation:ticketIn .6s cubic-bezier(.2,.9,.2,1) both;">\n'
    '        <div style="position:absolute;inset:0;overflow:hidden;pointer-events:none;">'
    '<span style="position:absolute;top:-40%;bottom:-40%;width:30%;'
    'background:linear-gradient(90deg,transparent,rgba(255,255,255,.3),transparent);'
    'animation:ticketSheen 6s ease-in-out infinite;"></span></div>\n'
    '        <div style="position:relative;display:flex;align-items:center;'
    'justify-content:space-between;gap:14px;padding:24px 30px;flex-wrap:wrap;'
    'border-bottom:1px dashed rgba(253,243,234,.24);">\n'
    '          <div style="display:flex;align-items:center;gap:11px;">\n'
    '            <span style="font-family:\'Playfair Display\',serif;font-size:24px;'
    'color:#fdf3ea;">enrich</span>\n'
    '            <span style="font-size:9px;font-weight:800;letter-spacing:1.8px;'
    'color:#c9a15a;border-left:1px solid rgba(201,161,90,.4);padding-left:11px;">'
    'YOUR MEMBERSHIP</span>\n'
    '          </div>\n'
    '          <span style="font-size:10.5px;font-weight:800;letter-spacing:1.4px;'
    'color:#3ddc84;background:rgba(61,220,132,.14);padding:5px 12px;border-radius:999px;">'
    'ACTIVE</span>\n'
    '        </div>\n'
    '        <div style="position:relative;padding:30px;display:grid;'
    'grid-template-columns:1.2fr 1fr;gap:32px;">\n'
    '          <div>\n'
    '            <div style="font-size:10px;letter-spacing:1.8px;color:#a79a9d;'
    'margin-bottom:8px;">CURRENT PLAN</div>\n'
    '            <div style="font-family:\'Playfair Display\',serif;font-size:30px;'
    'color:#fdf3ea;margin-bottom:6px;">{{ membershipTierName }}</div>\n'
    '            <div style="font-size:13px;color:#c9a15a;font-weight:700;'
    'margin-bottom:24px;">{{ membershipDiscountPercent }}% off every booking, '
    'applied automatically</div>\n'
    '            <div style="display:flex;gap:32px;flex-wrap:wrap;">\n'
    '              <div>\n'
    '                <div style="font-size:9px;letter-spacing:1.6px;color:#a79a9d;'
    'margin-bottom:4px;">ACTIVE FROM</div>\n'
    '                <div style="font-size:14px;font-weight:700;color:#fdf3ea;">'
    '{{ membershipStartDate }}</div>\n'
    '              </div>\n'
    '              <div>\n'
    '                <div style="font-size:9px;letter-spacing:1.6px;color:#a79a9d;'
    'margin-bottom:4px;">EXPIRES ON</div>\n'
    '                <div style="font-size:14px;font-weight:700;color:#fdf3ea;">'
    '{{ membershipExpiryDate }}</div>\n'
    '              </div>\n'
    '            </div>\n'
    '          </div>\n'
    '          <div style="border-left:1px solid rgba(253,243,234,.12);padding-left:32px;">\n'
    '            <div style="font-size:10px;letter-spacing:1.8px;color:#a79a9d;'
    'margin-bottom:14px;">YOUR BENEFITS</div>\n'
    '            <sc-for list="{{ membershipPerkRows }}" as="pk" hint-placeholder-count="4">\n'
    '              <div style="display:flex;align-items:flex-start;gap:9px;'
    'margin-bottom:11px;animation:fadeUp .45s ease-out both;">\n'
    '                <span style="flex-shrink:0;color:#3ddc84;font-size:13px;'
    'line-height:1.4;">✓</span>\n'
    '                <span style="font-size:13px;color:#e3dbdd;line-height:1.4;">'
    '{{ pk.label }}</span>\n'
    '              </div>\n'
    '            </sc-for>\n'
    '          </div>\n'
    '        </div>\n'
    '      </div>\n'
    '      </sc-if>\n'
    '\n'
    '      <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:22px;margin-bottom:60px;">'
)

# Pre-existing bug found while testing the Service step end-to-end, unrelated
# to it: bookingSubmitting/bookingError (added to state by
# BOOKING_ERROR_STATE_DST/CONFIRM_DST above) were never added to the render
# function's own exposed-props object -- same class of bug as
# STEP_EXPOSE_SRC/DST above, just pre-dating this file's own booking-wizard
# work. Every expression reading them in BOOKING_ERROR_BANNER_DST's markup
# (the Confirm Booking button's label, its background colour, its disabled
# state, and the error banner itself) silently evaluated against undefined,
# so the button rendered with no label and no colour and the rejection banner
# never showed, even though confirmBooking/the submit and error states behind
# them all worked correctly.
# PHASE 4 DEV: same gap for the membership fields -- s.hasActiveMembership/
# membershipTierName/membershipDiscountPercent/membershipStartDate/
# membershipExpiryDate are all real, correctly-populated state (proven by
# TIER_CURRENT_DST's isCurrentPlan/tierDisabled, computed from them in JS and
# exposed via tiersDisplay, working fine) -- but nothing ever copied the raw
# identifiers themselves onto the props object, so every `sc-if value="{{
# hasActiveMembership }}"` and `{{ membershipTierName }}` written directly
# into markup (the Booking Summary's membership-discount line, the new
# Active Membership Plan banner) silently evaluated to undefined and stayed
# hidden, exactly like bookingSubmitting/bookingError above.
BOOKING_SUBMIT_EXPOSE_SRC = "showBookingBack: step > 1 && !s.bookingConfirmed,"
BOOKING_SUBMIT_EXPOSE_DST = (
    "showBookingBack: step > 1 && !s.bookingConfirmed, "
    "bookingSubmitting: s.bookingSubmitting, bookingError: s.bookingError, "
    "hasActiveMembership: s.hasActiveMembership, membershipTierName: s.membershipTierName, "
    "membershipDiscountPercent: s.membershipDiscountPercent, "
    "membershipStartDate: s.membershipStartDate, membershipExpiryDate: s.membershipExpiryDate,"
)

# --- Booking Summary card -- redesigned as a premium ticket banner ---------
# Was: a plain white card with a bare 2-column CSS grid (City/Branch/Chair/
# Time only -- Service had nowhere to go and had to be bolted on as an
# awkward 5th, half-empty grid cell). Now: the same dark gradient "Appointment
# Pass" ticket banner language the site already uses for the CONFIRMED screen
# right after this one (see the isConfirmed branch just below in the raw
# export -- same background gradient, same sheen sweep animation, same
# Playfair Display wordmark/dashed divider), so a customer sees one
# consistent premium ticket look through the entire Confirm step instead of a
# plain form card that suddenly becomes a fancy ticket only once booked.
# Chained across three patches (this one, the membership checkbox restyle,
# and SUMMARY_CARD_CLOSE_SRC/DST) because MEMBER_CHECKBOX_DST's own gating
# patch sits between the grid and the total in the page -- this patch opens
# the card and the padded content div and leaves both open; the membership
# patch keeps the sc-if gate but restyles for the dark background; the close
# patch renders the total/error/button and closes both divs.
SUMMARY_GRID_SRC = (
    '<div style="background:#ffffff;border:1px solid rgba(20,17,17,.1);border-radius:22px;'
    'padding:32px;box-shadow:0 12px 40px rgba(20,17,17,.08);">\n'
    '            <div style="font-family:\'Manrope\',sans-serif;font-weight:700;font-size:20px;'
    'color:#161213;margin-bottom:20px;">Booking Summary</div>\n'
    '            <div style="display:grid;grid-template-columns:1fr 1fr;gap:14px;'
    'margin-bottom:22px;font-size:14px;color:#2c2c2c;">\n'
    '              <div><b>City</b><br>{{ summaryCity }}</div>\n'
    '              <div><b>Branch</b><br>{{ summaryStore }}</div>\n'
    '              <div><b>Chair</b><br>{{ summaryChair }}</div>\n'
    '              <div><b>Time</b><br>{{ summaryTime }}</div>\n'
    '            </div>'
)
SUMMARY_GRID_DST = (
    '<div style="position:relative;border-radius:24px;overflow:hidden;'
    'background:linear-gradient(150deg,#241b1e,#141013 62%,#0c0a0b);'
    'box-shadow:0 34px 74px -32px rgba(12,10,12,.95);'
    'animation:ticketIn .6s cubic-bezier(.2,.9,.2,1) both;">\n'
    '            <div style="position:absolute;inset:0;overflow:hidden;pointer-events:none;">'
    '<span style="position:absolute;top:-40%;bottom:-40%;width:30%;'
    'background:linear-gradient(90deg,transparent,rgba(255,255,255,.3),transparent);'
    'animation:ticketSheen 6s ease-in-out infinite;"></span></div>\n'
    '            <div style="position:relative;display:flex;align-items:center;'
    'justify-content:space-between;gap:14px;padding:20px 26px;'
    'border-bottom:1px dashed rgba(253,243,234,.24);">\n'
    '              <div style="display:flex;align-items:center;gap:11px;">\n'
    '                <span style="font-family:\'Playfair Display\',serif;font-size:22px;'
    'color:#fdf3ea;">enrich</span>\n'
    '                <span style="font-size:9px;font-weight:800;letter-spacing:1.8px;'
    'color:#c9a15a;border-left:1px solid rgba(201,161,90,.4);padding-left:11px;">'
    'BOOKING SUMMARY</span>\n'
    '              </div>\n'
    '              <span style="font-size:10.5px;font-weight:800;letter-spacing:1.4px;'
    'color:#e8a71f;background:rgba(232,167,31,.14);padding:5px 12px;border-radius:999px;">'
    'REVIEW</span>\n'
    '            </div>\n'
    '            <div style="position:relative;padding:26px;">\n'
    '              <div style="display:grid;grid-template-columns:1fr 1fr;gap:18px 22px;'
    'margin-bottom:18px;">\n'
    '                <div><div style="font-size:9px;letter-spacing:1.6px;color:#a79a9d;'
    'margin-bottom:4px;">CITY</div><div style="font-size:14.5px;font-weight:700;'
    'color:#fdf3ea;">{{ summaryCity }}</div></div>\n'
    '                <div><div style="font-size:9px;letter-spacing:1.6px;color:#a79a9d;'
    'margin-bottom:4px;">BRANCH</div><div style="font-size:14.5px;font-weight:700;'
    'color:#fdf3ea;">{{ summaryStore }}</div></div>\n'
    '                <div><div style="font-size:9px;letter-spacing:1.6px;color:#a79a9d;'
    'margin-bottom:4px;">CHAIR</div><div style="font-size:14.5px;font-weight:700;'
    'color:#fdf3ea;">{{ summaryChair }}</div></div>\n'
    '                <div><div style="font-size:9px;letter-spacing:1.6px;color:#a79a9d;'
    'margin-bottom:4px;">TIME</div><div style="font-size:14.5px;font-weight:700;'
    'color:#fdf3ea;">{{ summaryTime }}</div></div>\n'
    '              </div>\n'
    '              <div style="padding-top:16px;border-top:1px solid rgba(253,243,234,.12);'
    'margin-bottom:20px;">\n'
    '                <div style="font-size:9px;letter-spacing:1.6px;color:#a79a9d;'
    'margin-bottom:4px;">SERVICE</div>\n'
    '                <div style="font-size:14.5px;font-weight:700;color:#fdf3ea;">'
    '{{ summaryService }}</div>\n'
    '              </div>'
)

# --- Booking Summary card -- total + Confirm button, redesigned + bug-fixed -
# Was: a plain "Estimated total" line, then (see BOOKING_ERROR_BANNER_DST,
# retired by this patch) a Confirm button whose label/background/cursor were
# written as ternaries directly inside {{ }} markup interpolation -- broken
# in this runtime (see STEP_SUMMARY_COMPUTE_DST's confirmBtn* fields, computed
# in JS instead precisely to route around it), so the button always rendered
# blank and colourless despite confirmBooking/the submit and error states
# behind it working correctly. Now: the total sits in its own tinted card to
# match its weight as the final figure, and the button reads three plain
# precomputed fields instead of evaluating ternaries itself.
# --- Booking Summary card -- membership checkbox removed entirely ---------
# PHASE 4 DEV: MEMBER_CHECKBOX_DST above now removes the checkbox outright
# (automatic application, no toggle -- see that patch's comment), so there is
# nothing left here to restyle for the dark banner. This patch is retired.

# --- Booking Summary card -- total + Confirm button, closes the ticket -----
# Was: a plain "Estimated total" line, then a Confirm button whose label/
# background/cursor were written as ternaries directly inside {{ }} markup
# interpolation -- broken in this runtime (see STEP_SUMMARY_COMPUTE_DST's
# confirmBtn* fields, computed in JS instead precisely to route around it),
# so the button always rendered blank and colourless despite confirmBooking/
# the submit and error states behind it working correctly. Now: the total
# sits in its own glowing red-tinted strip and the button carries the same
# gradient/glow/hover-lift treatment as the site's other primary CTAs (e.g.
# "Book this look →"), reading three plain precomputed fields instead of
# evaluating ternaries itself. Closes the two divs SUMMARY_GRID_DST opened
# (the padded content area, then the outer ticket card).
SUMMARY_TOTAL_SRC = (
    '<div style="display:flex;justify-content:space-between;align-items:baseline;'
    'margin-bottom:24px;">\n'
    '              <span style="font-size:14px;color:#767676;">Estimated total</span>\n'
    '              <span style="font-family:\'Manrope\',sans-serif;font-weight:800;font-size:26px;'
    'font-weight:600;color:#161213;">₹{{ finalPrice }}</span>\n'
    '            </div>\n'
    '            <button sc-camel-on-click="{{ confirmBooking }}" style="width:100%;'
    'background:#e8283f;color:#ffffff;border:none;padding:16px;border-radius:4px;'
    'font-size:15px;font-weight:700;cursor:pointer;box-shadow:0 6px 20px rgba(232,40,63,.3);">'
    'Confirm Booking</button>\n'
    '          </div>'
)
SUMMARY_TOTAL_DST = (
    # Services show their own original price on the Service step (see
    # STEP_COMPUTE_DST) -- this breakdown is the one place the membership
    # discount is shown at all, as its own line against the undiscounted
    # services subtotal, matching how bsi_salon_booking_mixin itself keeps
    # bsi_services_amount undiscounted and applies the percentage as a
    # separate step in _bsi_compute_bsi_amounts_common.
    '<sc-if value="{{ summaryHasServicesAmount }}" hint-placeholder-val="{{ false }}">\n'
    '              <div style="display:flex;justify-content:space-between;padding:0 2px;'
    'margin-bottom:8px;font-size:12.5px;color:#a79a9d;">\n'
    '                <span>Services Subtotal</span>\n'
    '                <span style="color:#fdf3ea;font-weight:600;">{{ summaryServicesAmount }}</span>\n'
    '              </div>\n'
    '              <sc-if value="{{ hasActiveMembership }}" hint-placeholder-val="{{ false }}">\n'
    '                <div style="display:flex;justify-content:space-between;padding:0 2px;'
    'margin-bottom:14px;font-size:12.5px;color:#3ddc84;font-weight:600;">\n'
    '                  <span>✓ {{ summaryMembershipLabel }}</span>\n'
    '                  <span>{{ summaryMembershipDiscountLabel }}</span>\n'
    '                </div>\n'
    '              </sc-if>\n'
    '            </sc-if>\n'
    '            <div style="display:flex;justify-content:space-between;align-items:center;'
    'background:linear-gradient(120deg,rgba(232,40,63,.24),rgba(138,35,50,.14));'
    'border:1px solid rgba(232,40,63,.4);border-radius:14px;padding:16px 18px;'
    'margin-bottom:18px;box-shadow:0 10px 26px -16px rgba(232,40,63,.5);">\n'
    '                <span style="font-size:11px;letter-spacing:1.4px;font-weight:700;'
    'color:#e3c9cd;">ESTIMATED TOTAL</span>\n'
    '                <span style="font-family:\'Playfair Display\',serif;font-weight:600;'
    'font-size:28px;color:#fdf3ea;">₹{{ finalPrice }}</span>\n'
    '              </div>\n'
    '              <sc-if value="{{ bookingError }}" hint-placeholder-val="{{ false }}">\n'
    '                <div style="background:rgba(232,40,63,.18);border:1px solid rgba(232,40,63,.5);'
    'color:#ffd7dc;border-radius:12px;padding:12px 14px;margin-bottom:16px;font-size:13px;'
    'font-weight:600;line-height:1.5;">{{ bookingError }}</div>\n'
    '              </sc-if>\n'
    '              <button sc-camel-on-click="{{ confirmBooking }}" disabled="{{ bookingSubmitting }}" '
    'style="width:100%;background:{{ confirmBtnBg }};color:#ffffff;border:none;padding:17px;'
    'border-radius:12px;font-size:15px;font-weight:800;letter-spacing:.3px;'
    'cursor:{{ confirmBtnCursor }};box-shadow:0 14px 32px -14px rgba(232,40,63,.85);'
    'transition:transform .2s;" style-hover="transform:translateY(-2px);">'
    '{{ confirmBtnLabel }}</button>\n'
    '            </div>\n'
    '          </div>'
)

# --- Reset every booking-wizard field before starting a fresh booking ------
# Was: "Book Another" (resetBooking) and the main "Book Now" nav CTA
# (goBookingNav) only ever cleared the five fields the original design
# tracked (city/store/step, selected chair(s)/time, bookingConfirmed) --
# every PHASE 3 DEV field added since (bookingServiceIds/bookingServiceId/
# bookingServiceName/bookingServicePrice/bookingActiveServiceCat for the new
# Service step, bookingMaxStep for the step indicator) and a few pre-existing
# ones with the same gap (rewardServiceId/rewardServiceName, the look
# configurator's snapshot, the chair-side ritual, isMember) all survived
# untouched -- reproduced live: confirm a two-service booking, click Book
# Another, and the new booking's Service step opens with both old services
# still checked and the old total still showing before a single new
# selection is made. Now: every field either flow sets gets explicitly reset
# to its own true default, not just the five the original design knew about.
RESET_BOOKING_SRC = (
    "resetBooking = () => this.setPage('stores', { bookingConfirmed: false, "
    "selectedChairIds: [], selectedTime: null, "
    "booking: { cityId: null, storeId: null, step: 1 } });"
)
RESET_BOOKING_DST = (
    "resetBooking = () => this.setPage('stores', { "
    "bookingConfirmed: false, bookingError: false, bookingSubmitting: false, "
    "selectedChairIds: [], selectedTime: null, "
    "booking: { cityId: null, storeId: null, step: 1 }, bookingMaxStep: 1, "
    "bookingServiceId: null, bookingServiceIds: [], bookingServiceName: null, "
    "bookingServicePrice: null, bookingActiveServiceCat: null, "
    "bookingPackageId: null, bookingPackageName: null, bookingPackagePrice: null, "
    "rewardServiceId: null, rewardServiceName: null, bookingStylist: null, "
    "bookingLookLength: null, bookingLookShadeIndex: null, bookingLookFinish: null, "
    "bookingLookPrice: null, ritual: [], isMember: false });"
)

GOBOOKINGNAV_RESET_SRC = (
    "{ booking: { cityId: null, storeId: null, step: 1 }, "
    "selectedChairIds: [], selectedTime: null, bookingConfirmed: false }"
)
GOBOOKINGNAV_RESET_DST = (
    "{ booking: { cityId: null, storeId: null, step: 1 }, bookingMaxStep: 1, "
    "selectedChairIds: [], selectedTime: null, bookingConfirmed: false, "
    "bookingError: false, bookingSubmitting: false, "
    "bookingServiceId: null, bookingServiceIds: [], bookingServiceName: null, "
    "bookingServicePrice: null, bookingActiveServiceCat: null, "
    "bookingPackageId: null, bookingPackageName: null, bookingPackagePrice: null, "
    "rewardServiceId: null, rewardServiceName: null, bookingStylist: null, "
    "bookingLookLength: null, bookingLookShadeIndex: null, bookingLookFinish: null, "
    "bookingLookPrice: null, ritual: [], isMember: false }"
)

# --- Confirmed ticket -- "YOUR STYLIST" showed a random, unrelated name ----
# Was: `const st = STYLISTS[s.spotlightIdx % STYLISTS.length]` -- spotlightIdx
# is the homepage/Stylists-page spotlight carousel's own position (defaults
# to 0, changed only by browsing that carousel), completely unrelated to
# which artist -- if any -- this booking was actually made with. Every normal
# booking (the wizard has no artist-picker step at all outside "Book with
# this stylist", see STYLIST_BOOK_DST) showed whichever stylist the carousel
# happened to be on, not "no stylist chosen" and not the real one on the
# rare booking that did pick one -- reproduced live: STYLIST_PHOTOS was even
# indexed by the same wrong spotlightIdx instead of matching whichever
# stylist st.name showed. Now: the ticket only ever shows a stylist when
# bookingStylist (set by STYLIST_BOOK_DST) says one was actually picked, and
# says so honestly otherwise instead of implying a specific, wrong artist.
TICKET_STYLIST_SRC = "const st = STYLISTS[s.spotlightIdx % STYLISTS.length];"
TICKET_STYLIST_DST = (
    "const stIdx = (typeof s.bookingStylist === 'number') ? s.bookingStylist : null; "
    "const st = (stIdx !== null && STYLISTS[stIdx]) ? STYLISTS[stIdx] : null;"
)

TICKET_STYLIST_NAME_SRC = "ticketStylistName: st.name,"
TICKET_STYLIST_NAME_DST = "ticketStylistName: st ? st.name : 'Any Available Stylist',"

TICKET_STYLIST_PHOTO_SRC = "ticketStylistPhoto: STYLIST_PHOTOS[s.spotlightIdx % STYLIST_PHOTOS.length],"
TICKET_STYLIST_PHOTO_DST = (
    "ticketStylistPhoto: st ? STYLIST_PHOTOS[stIdx % STYLIST_PHOTOS.length] : STYLIST_PHOTOS[0],"
)


# Applied in order. Each is (label, anchor, replacement).
PATCHES = (
    # deep-linkable pages -- refresh/back/shared-link lands on the right page
    ('nav initial page from url', NAV_INITIAL_SRC, NAV_INITIAL_DST),
    ('nav url on navigate', NAV_URL_SRC, NAV_URL_DST),
    # navbar hides on scroll down, reappears on scroll up
    ('nav transform compute', NAV_TRANSFORM_COMPUTE_SRC, NAV_TRANSFORM_COMPUTE_DST),
    ('nav transform expose', NAV_TRANSFORM_EXPOSE_SRC, NAV_TRANSFORM_EXPOSE_DST),
    ('nav tag transform', NAV_TAG_SRC, NAV_TAG_DST),
    ('confirm handler', CONFIRM_SRC, CONFIRM_DST),
    ('booking error/submitting default state', BOOKING_ERROR_STATE_SRC, BOOKING_ERROR_STATE_DST),
    ('membership CTA', TIER_CTA_SRC, TIER_CTA_DST),
    # membership page -- gate re-purchase while a tier is already active
    ('membership current-plan computation', TIER_CURRENT_SRC, TIER_CURRENT_DST),
    ('membership current-plan fields', TIER_CURRENT_FIELDS_SRC, TIER_CURRENT_FIELDS_DST),
    ('membership current-plan gate', TIER_GATE_SRC, TIER_GATE_DST),
    ('membership current-plan ribbon', TIER_MARKUP_SRC, TIER_MARKUP_DST),
    ('membership current-plan button', TIER_BUTTON_SRC, TIER_BUTTON_DST),
    ('contact form', CONTACT_SRC, CONTACT_DST),
    # look configurator -- name captions and price maths onto the live catalogue
    ('look finish name (caption)', FINISH_NAME_SRC, FINISH_NAME_DST),
    ('look finish name (summary)', FINISH_NAME_SRC, FINISH_NAME_DST),
    ('look finish surcharge', FINISH_SURCHARGE_SRC, FINISH_SURCHARGE_DST),
    ('look length name', LENGTH_NAME_SRC, LENGTH_NAME_DST),
    ('look length surcharge', LENGTH_SURCHARGE_SRC, LENGTH_SURCHARGE_DST),
    ('look shade surcharge', SHADE_SURCHARGE_SRC, SHADE_SURCHARGE_DST),
    ('look base price', PRICE_BASE_SRC, PRICE_BASE_DST),
    ('look illustration length key fallback', LENKEY_SRC, LENKEY_DST),
    ('booking confirm price for a booked look', BASEPRICE_SRC, BASEPRICE_DST),
    # chair-side ritual builder -- key on the stable add-on key, not the id
    ('ritual add-on picked filter', RITUAL_PICKED_SRC, RITUAL_PICKED_DST),
    ('ritual add-on toggle/active', RITUAL_TOGGLE_SRC, RITUAL_TOGGLE_DST),
    # consultation simulator -- rule-driven recommendations
    ('consultation recommendations', CONSULT_SRC, CONSULT_DST),
    # membership discount -- gated on a real active subscription
    ('membership status fetch', MOUNT_SRC, MOUNT_DST),
    ('membership status default state', MEMBER_STATE_SRC, MEMBER_STATE_DST),
    ('membership discount price', MEMBER_PRICE_SRC, MEMBER_PRICE_DST),
    ('membership discount checkbox', MEMBER_CHECKBOX_SRC, MEMBER_CHECKBOX_DST),
    # gift card purchase -- cart/checkout, same pattern as membership CTA
    ('gift card buy method', GIFT_METHOD_SRC, GIFT_METHOD_DST),
    ('gift card buy state', GIFT_STATE_SRC, GIFT_STATE_DST),
    ('gift card status banner', GIFT_STATUS_SRC, GIFT_STATUS_DST),
    ('gift card buy button', GIFT_BUTTON_SRC, GIFT_BUTTON_DST),
    # loyalty reward redemption -- real spend, service carried into booking
    # loyalty wallet -- real balance instead of the design's fixed 1240 pts
    ('wallet points real balance', WALLET_POINTS_SRC, WALLET_POINTS_DST),
    ('wallet dash real balance', WALLET_DASH_SRC, WALLET_DASH_DST),
    ('wallet to-next real balance', WALLET_TONEXT_SRC, WALLET_TONEXT_DST),
    ('wallet tier pct real balance', WALLET_TIERPCT_SRC, WALLET_TIERPCT_DST),
    ('wallet reward afford check real balance', WALLET_CAN_SRC, WALLET_CAN_DST),
    ('loyalty redeem onclick', REDEEM_SRC, REDEEM_DST),
    ('loyalty redeem method', REDEEM_METHOD_SRC, REDEEM_METHOD_DST),
    # services page -- redeem a plain service directly against loyalty points
    ('service points redeem method', SERVICE_POINTS_METHOD_SRC, SERVICE_POINTS_METHOD_DST),
    ('service points list computation', SERVICE_POINTS_LIST_SRC, SERVICE_POINTS_LIST_DST),
    # Services page -- Packages listing
    ('packages list computation', PACKAGES_LIST_SRC, PACKAGES_LIST_DST),
    ('packages section markup', PACKAGES_SECTION_SRC, PACKAGES_SECTION_DST),
    ('service points markup', SERVICE_POINTS_MARKUP_SRC, SERVICE_POINTS_MARKUP_DST),
    # branch-specific chairs -- real roster fetched once a branch is picked
    ('chairs fetch method', CHAIRS_FETCH_SRC, CHAIRS_FETCH_DST),
    ('chairs on store select', CHAIRS_STORE_SRC, CHAIRS_STORE_DST),
    ('booking city step max-step tracking', CITY_MAXSTEP_SRC, CITY_MAXSTEP_DST),
    ('chairs on book-from-branch', CHAIRS_BOOKFROM_SRC, CHAIRS_BOOKFROM_DST),
    # "Book this look" -- auto-fetch the customer's own city, branch still a real choice
    ('book-from-look method', LOOK_METHOD_SRC, LOOK_METHOD_DST),
    ('book-from-look nav expose', LOOK_NAV_EXPOSE_SRC, LOOK_NAV_EXPOSE_DST),
    ('book-from-look button', LOOK_BUTTON_SRC, LOOK_BUTTON_DST),
    # "Book with this stylist" -- auto-fill their own branch
    ('book with stylist', STYLIST_BOOK_SRC, STYLIST_BOOK_DST),
    # booking step indicator -- clickable to jump back to a completed step
    ('booking steps compute', STEPS_COMPUTE_SRC, STEPS_COMPUTE_DST),
    ('booking steps markup', STEPS_MARKUP_SRC, STEPS_MARKUP_DST),
    # Contact page city tiles -- select in place, no more redirect to Stores
    ('contact city list', CONTACT_CITY_LIST_SRC, CONTACT_CITY_LIST_DST),
    ('contact city tile markup', CONTACT_TILE_MARKUP_SRC, CONTACT_TILE_MARKUP_DST),
    # Remove Salon 360 tour section entirely -- markup, state, methods, CSS
    ('salon tour section removed', TOUR_SECTION_SRC, TOUR_SECTION_DST),
    ('salon tour render vals removed', TOUR_RENDER_SRC, TOUR_RENDER_DST),
    ('salon tour state removed', TOUR_STATE_SRC, TOUR_STATE_DST),
    ('salon tour method removed', TOUR_METHOD_SRC, TOUR_METHOD_DST),
    ('salon tour css removed', TOUR_CSS_SRC, TOUR_CSS_DST),
    # transformations gallery -- keep the top of the photo (the face) in frame
    ('gallery before image top-anchored crop', GALLERY_BEFORE_IMG_SRC, GALLERY_BEFORE_IMG_DST),
    ('gallery after image top-anchored crop', GALLERY_AFTER_IMG_SRC, GALLERY_AFTER_IMG_DST),
    # booking wizard Service step -- new step between Store and Chair
    ('booking step defs (add Service)', STEP_DEFS_SRC, STEP_DEFS_DST),
    ('booking step gate 6 (Confirm)', STEP_IS6_SRC, STEP_IS6_DST),
    ('booking service categories/list expose', STEP_EXPOSE_SRC, STEP_EXPOSE_DST),
    ('booking service categories/list compute', STEP_COMPUTE_SRC, STEP_COMPUTE_DST),
    ('booking select service handler', STEP_SERVICE_METHOD_SRC, STEP_SERVICE_METHOD_DST),
    ('booking chairNext step 4->5', STEP_CHAIRNEXT_SRC, STEP_CHAIRNEXT_DST),
    ('booking selectTimeAndNext step 5->6', STEP_SELECTTIME_SRC, STEP_SELECTTIME_DST),
    ('booking timeNext step 5->6', STEP_TIMENEXT_SRC, STEP_TIMENEXT_DST),
    # renumber later steps' own gate highest-first so each anchor stays unique
    ('booking Confirm step gate 5->6', STEP_CONFIRM_TAG_SRC, STEP_CONFIRM_TAG_DST),
    ('booking Time step gate 4->5', STEP_TIME_TAG_SRC, STEP_TIME_TAG_DST),
    ('booking Service step markup + Chair gate 3->4', STEP_CHAIR_TAG_SRC, STEP_CHAIR_TAG_DST),
    ('booking summary service compute', STEP_SUMMARY_COMPUTE_SRC, STEP_SUMMARY_COMPUTE_DST),
    # pre-existing bug: bookingSubmitting/bookingError never exposed to template
    ('booking submit/error state expose', BOOKING_SUBMIT_EXPOSE_SRC, BOOKING_SUBMIT_EXPOSE_DST),
    # Booking Summary card redesign -- receipt-style rows + fixed Confirm button
    ('booking summary card grid redesign', SUMMARY_GRID_SRC, SUMMARY_GRID_DST),
    ('booking summary card total+button redesign', SUMMARY_TOTAL_SRC, SUMMARY_TOTAL_DST),
    # a fresh booking must not inherit the previous one's selections
    ('reset booking -- book another', RESET_BOOKING_SRC, RESET_BOOKING_DST),
    ('reset booking -- book now nav', GOBOOKINGNAV_RESET_SRC, GOBOOKINGNAV_RESET_DST),
    # Active Membership Plan banner (Membership page)
    ('membership perk rows expose', MEMBERSHIP_PERKS_EXPOSE_SRC, MEMBERSHIP_PERKS_EXPOSE_DST),
    ('membership active plan banner', MEMBERSHIP_BANNER_SRC, MEMBERSHIP_BANNER_DST),
    # confirmed ticket -- show the real booked stylist, not the homepage carousel's
    ('ticket stylist real selection', TICKET_STYLIST_SRC, TICKET_STYLIST_DST),
    ('ticket stylist name fallback', TICKET_STYLIST_NAME_SRC, TICKET_STYLIST_NAME_DST),
    ('ticket stylist photo real selection', TICKET_STYLIST_PHOTO_SRC, TICKET_STYLIST_PHOTO_DST),
)
