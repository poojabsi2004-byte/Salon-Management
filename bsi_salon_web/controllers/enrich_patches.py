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
    # PHASE 6 DEV: the request body is bsiBookingParams() (see
    # STEP_SERVICE_METHOD_DST), the exact same description of the booking the
    # Confirm screen's own quote was priced from -- including the loyalty points
    # and gift card code the payment panel applied. The server re-resolves and
    # re-validates all of it before writing anything, so what is recorded is
    # always what was quoted.
    'confirmBooking = () => { '
    'this.setState({ bookingError: false, bookingSubmitting: true }); '
    'this.bsiRpc("/salon/api/booking", this.bsiBookingParams()).then((res) => { '
    'if (res.ok) { this.setState({ bookingConfirmed: true, bookingError: false, '
    'bookingSubmitting: false }); } '
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
    # PHASE 6 DEV -- jumping straight back to Confirm re-prices too, or the
    # panel would still show whatever was quoted before the selection changed.
    "      onClick: b.n <= bookingReachedStep ? (() => { this.setState((s2) => "
    "({ booking: { ...s2.booking, step: b.n } })); "
    "if (b.n === 6) { this.bsiFetchQuote(); } }) : null,\n"
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
# PHASE 6 DEV -- the navbar's account controls ride along on the same exposure.
# Every one of these is per-visitor, so none of it can be baked into the served
# page (which is one cached document shared by everyone -- see main.py's
# _PAGE_CACHE): componentDidMount asks /salon/api/user_status once and these
# read whatever came back, defaulting to the signed-out navbar until it does.
NAV_TRANSFORM_EXPOSE_DST = (
    "navTransform, userIsAdmin: s.userIsAdmin, userLoggedIn: s.userLoggedIn, "
    "userLoggedOut: !s.userLoggedIn, "
    "userAccountLabel: (s.userName && s.userName.length > 12) "
    "? (s.userName.slice(0, 11) + '\\u2026') : (s.userName || 'My Account'), "
    "navItems, goHome: this.goHome,"
)

NAV_TAG_SRC = (
    '<nav style="position:sticky;top:0;z-index:100;display:flex;align-items:center;'
    'justify-content:space-between;padding:16px 48px;background:rgba(255,255,255,.94);'
    'backdrop-filter:blur(10px);border-bottom:1px solid rgba(20,17,17,.08);'
    'box-shadow:0 2px 16px rgba(20,17,17,.05);">'
)
NAV_TAG_DST = (
    '<nav class="bsi-nav-shell" style="position:sticky;top:0;z-index:100;display:flex;align-items:center;'
    'justify-content:space-between;padding:16px 48px;background:rgba(255,255,255,.94);'
    'backdrop-filter:blur(10px);border-bottom:1px solid rgba(20,17,17,.08);'
    'box-shadow:0 2px 16px rgba(20,17,17,.05);transform:{{ navTransform }};'
    'transition:transform .3s ease;">'
)

# --- PHASE 6 DEV (nav overhaul): hover-dropdown submenus + Account dropdown ---
# Was: the navbar was a flat row of one-word buttons and a Shop link, plus
# (Phase 6) three separate account controls -- Dashboard, "My Account", Log
# out -- squeezed in between Shop and the Book Now CTA. Two problems for a
# customer who actually uses the site:
#
#   * The three big destinations behind Services / Stores / Membership had
#     nowhere in the nav to hint at what they held. A visitor had to click
#     through to find out that Services was five categories, or that
#     Membership was three tiers, and every category jump then re-loaded the
#     whole Services page.
#   * The account cluster spread across three sibling links, so a signed-in
#     customer had one door for "my history" but no door at all for booking
#     vs order history separately, and Log out was next to it in the same
#     row -- easy to hit by mistake, and none of it collapsed on a narrow
#     window.
#
# Now:
#   * Each nav item optionally carries a children[] and renders a small pane
#     that shows on hover / focus-within (pure CSS, no state involved).
#     Services -> the five real categories, jumping straight to the Services
#     page with that category active. Stores -> the cities the site actually
#     covers, each pre-selecting its own branches. Membership -> the three
#     tiers.
#   * Everything about the signed-in visitor -- Dashboard (admins only),
#     Booking History, Order History and Log out -- lives inside one Account
#     dropdown to the right of the link row, replacing the three separate
#     controls the Phase 6 initial pass added.
#
# The one red thing in the nav is still Book Now: submenus are on the site's
# neutral cream/ink palette so a customer's eye still lands on the CTA. Pure
# CSS hover, so nothing here is state-driven and no click is ever needed to
# open a submenu.

# ── 1. CSS injected inside the design's own <helmet> block ──────────────────
NAV_STYLE_SRC = '</helmet>'
# PHASE 6 DEV -- a single <link>, not an inline <style>: the CSS itself now
# lives in bsi_nav_dropdown.css, shared with every other frontend page (see
# that file's own header comment for why one file beats two copies). A cache-
# busting query string isn't needed here the way bsi_salon_dashboard.js's own
# route needs one (see dashboard.py's _bsi_dashboard_js_version) -- this page
# is itself rebuilt and cached fresh on every module change during
# development, and in production a static asset changing only ships with a
# new module version, at which point every visitor's cache is stale anyway.
NAV_STYLE_DST = (
    '<link rel="stylesheet" '
    'href="/bsi_salon_web/static/src/css/bsi_nav_dropdown.css?v=6"/>\n'
    '<link rel="stylesheet" '
    'href="/bsi_salon_web/static/src/css/bsi_booking_confirm.css?v=4"/>\n'
    # PHASE 7 DEV -- scoped visual overhaul for the "Design your look" section
    # on the salon home page (rotating ring around the canvas, aurora orbs,
    # glass control pills, neon price). Everything targets the design's own
    # [data-screen-label="Design your look"] wrapper, so no markup patch is
    # needed for it -- see the file's own header comment.
    '<link rel="stylesheet" '
    'href="/bsi_salon_web/static/src/css/bsi_design_your_look.css?v=1"/>\n'
    # PHASE 7 DEV -- scroll choreography (top progress bar, section fade-up,
    # heading word stagger, back-to-top) and the testimonials /
    # transformations / footer redesign (see enrich_redesign.py). The loader
    # is not linked here: it is painted by the bundler shell and the app
    # template themselves (enrich_redesign), so it never waits on a stylesheet.
    '<link rel="stylesheet" '
    'href="/bsi_salon_web/static/src/css/bsi_scroll_fx.css?v=2"/>\n'
    '<link rel="stylesheet" '
    'href="/bsi_salon_web/static/src/css/bsi_site_redesign.css?v=21"/>\n'
    '<script defer '
    'src="/bsi_salon_web/static/src/js/bsi_scroll_fx.js?v=5"></script>\n'
    '<script defer '
    'src="/bsi_salon_web/static/src/js/bsi_carousel.js?v=1"></script>\n'
    '</helmet>'
)

# ── 2. NAV_DEFS + navItems compute: attach a children[] per top-level item ──
# Home / Book Now / Stylists / About / Contact stay plain buttons (nothing to
# expand). Services / Stores / Membership each get a dropdown built off the
# same live data the page already renders elsewhere -- SERVICES_DATA, CITIES,
# TIERS_DATA -- so a category or a city that is not currently populated
# never appears in the dropdown either. bookingApplyPackage / selectCity /
# setPage all already exist.
NAV_ITEMS_COMPUTE_SRC = (
    "const NAV_DEFS = [\n"
    "      { key: 'home', label: 'Home' }, { key: 'stores', label: 'Stores' }, { key: 'booking', label: 'Book Now' },\n"
    "      { key: 'membership', label: 'Membership' }, { key: 'services', label: 'Services' }, { key: 'stylists', label: 'Artists' },\n"
    "      { key: 'about', label: 'About' }, { key: 'contact', label: 'Contact' },\n"
    "    ];\n"
    "    const navItems = NAV_DEFS.map((n) => ({\n"
    "      ...n,\n"
    "      onClick: () => this.setPage(n.key),\n"
    "      color: s.page === n.key ? wine : '#2c2c2c',\n"
    "      weight: s.page === n.key ? 800 : 600,\n"
    "    }));"
)
NAV_ITEMS_COMPUTE_DST = (
    "const NAV_DEFS = [\n"
    "      { key: 'home', label: 'Home' }, { key: 'stores', label: 'Stores' }, { key: 'booking', label: 'Book Now' },\n"
    "      { key: 'membership', label: 'Membership' }, { key: 'services', label: 'Services' }, { key: 'stylists', label: 'Artists' },\n"
    "      { key: 'about', label: 'About' }, { key: 'contact', label: 'Contact' },\n"
    "    ];\n"
    # Category labels for the Services dropdown -- the same five the Services
    # page's own filter pills carry (see serviceCategories a few blocks down),
    # kept in step so a customer picks the same names in the nav they will see
    # highlighted on the page they land on.
    "    const bsiNavServiceCats = [\n"
    "      { id: 'hair', label: 'Hair' }, { id: 'skin', label: 'Skin' }, { id: 'makeup', label: 'Makeup' },\n"
    "      { id: 'waxing', label: 'Waxing & Threading' }, { id: 'handsfeet', label: 'Hands & Feet' },\n"
    "    ].filter((c) => (SERVICES_DATA[c.id] || []).length);\n"
    "    const bsiNavChildrenFor = (key) => {\n"
    "      if (key === 'services') {\n"
    # Each category row now also carries a "time" meta -- the duration range
    # across that category's own services (e.g. "30-90 min"), read straight
    # off the same SERVICES_DATA the Services page and booking wizard render,
    # so it can never drift from what a customer sees once they click through.
    "        const rows = bsiNavServiceCats.map((c) => {\n"
    "          const items = SERVICES_DATA[c.id] || [];\n"
    "          const mins = items.map((sv) => parseInt(sv.duration, 10)).filter((n) => !isNaN(n));\n"
    "          const time = mins.length ? (Math.min(...mins) + '\\u2013' + Math.max(...mins) + ' min') : '';\n"
    "          return {\n"
    "            label: c.label, meta: String(items.length), time,\n"
    "            onClick: () => this.setPage('services', { activeServiceCat: c.id }),\n"
    "          };\n"
    "        });\n"
    # The last row jumps into the wizard's own Service step, so a customer
    # who wants to book after browsing the categories does not have to walk
    # City / Store first from the Services listing page.
    "        rows.push({ divider: true });\n"
    "        rows.push({ label: 'Browse all services \\u2192', onClick: () => this.setPage('services') });\n"
    "        return rows;\n"
    "      }\n"
    "      if (key === 'stores') {\n"
    # "time" here is that city's own branch opening hours (Mon-Fri), taken
    # from whichever branch has one set -- branches in the same city almost
    # always share timings, so one representative value is enough for a nav
    # row rather than listing every branch's hours.
    "        const rows = CITIES.map((c) => {\n"
    "          const withHours = (c.branches || []).find((b) => b.hours);\n"
    "          return {\n"
    "            label: c.name, meta: String((c.branches || []).length),\n"
    "            time: withHours ? withHours.hours : '',\n"
    "            onClick: () => { this.selectCity(c.id); this.setPage('stores'); },\n"
    "          };\n"
    "        });\n"
    "        rows.push({ divider: true });\n"
    "        rows.push({ label: 'See every branch \\u2192', onClick: () => this.setPage('stores') });\n"
    "        return rows;\n"
    "      }\n"
    "      if (key === 'membership') {\n"
    # Tier labels/prices ride off the same TIERS_DATA the Membership page
    # itself renders (see tiersDisplay), so a tier hidden from that grid is
    # already hidden here for the same reason.
    "        return TIERS_DATA.map((t) => ({\n"
    "          label: t.name, meta: '\\u20b9' + (t.yearly || t.monthly) + '/yr',\n"
    "          onClick: () => this.setPage('membership'),\n"
    "        }));\n"
    "      }\n"
    "      return null;\n"
    "    };\n"
    "    const navItems = NAV_DEFS.map((n) => {\n"
    "      const children = bsiNavChildrenFor(n.key);\n"
    # Services / Stores dropdowns lay their rows out horizontally (category +
    # time side by side); Membership keeps the original vertical price list.
    "      const rowMenu = (n.key === 'services' || n.key === 'stores');\n"
    "      return {\n"
    "        ...n,\n"
    "        onClick: () => this.setPage(n.key),\n"
    "        color: s.page === n.key ? wine : '#2c2c2c',\n"
    "        weight: s.page === n.key ? 800 : 600,\n"
    "        naviClass: 'bsi-navi' + (s.page === n.key ? ' is-active' : ''),\n"
    "        hasChildren: !!(children && children.length),\n"
    "        children: children || [],\n"
    "        submClass: 'bsi-subm' + (rowMenu ? ' bsi-subm--row' : ''),\n"
    "      };\n"
    "    });"
)

# The link row wrapper carries overflow-x:auto (a narrow-screen fallback so the
# eight nav items could scroll horizontally); with dropdown submenus that also
# clips them vertically, so any submenu opens invisible even though the CSS
# behind it fires. Turning that container off means the nav items no longer
# scroll on a very narrow screen -- they wrap onto a second row instead, same
# treatment the account pages' own navbar already uses (see enr-navlinks in
# bsi_salon_account_templates.xml's @media rule).
NAV_ROW_OVERFLOW_SRC = (
    '<div style="display:flex;align-items:center;gap:22px;overflow-x:auto;'
    'scrollbar-width:none;min-width:0;">'
)
NAV_ROW_OVERFLOW_DST = (
    '<div style="display:flex;align-items:center;gap:18px;flex-wrap:wrap;min-width:0;">'
)

# ── 3. Rewrite the navItems markup to render a submenu when children exist ──
# Each item now sits inside a .bsi-navi wrapper; the button is the trigger
# and the .bsi-subm pane holds children rendered from item.children (each
# child either a link with label + meta, or a plain {divider:true} row). The
# trigger for an item with children carries a small caret; it stays a button
# either way so keyboard focus opens the same panel that hover does.
NAV_LIST_MARKUP_SRC = (
    '<sc-for list="{{ navItems }}" as="item" hint-placeholder-count="8">\n'
    '          <button sc-camel-on-click="{{ item.onClick }}" style="background:none;border:none;'
    "cursor:pointer;font-family:'Manrope',sans-serif;font-size:14px;color:{{ item.color }};"
    'font-weight:{{ item.weight }};padding:4px 0;white-space:nowrap;flex-shrink:0;">{{ item.label }}</button>\n'
    '        </sc-for>'
)
NAV_LIST_MARKUP_DST = (
    '<sc-for list="{{ navItems }}" as="item" hint-placeholder-count="8">\n'
    '          <div class="{{ item.naviClass }}">\n'
    '            <button sc-camel-on-click="{{ item.onClick }}" class="bsi-nav-trigger" '
    'style="color:{{ item.color }};font-weight:{{ item.weight }};">{{ item.label }}'
    '<sc-if value="{{ item.hasChildren }}" hint-placeholder-val="{{ false }}">'
    '<span class="bsi-caret">▾</span></sc-if></button>\n'
    '            <sc-if value="{{ item.hasChildren }}" hint-placeholder-val="{{ false }}">\n'
    '              <div class="{{ item.submClass }}">\n'
    '                <div class="bsi-sub-group">{{ item.label }}</div>\n'
    '                <sc-for list="{{ item.children }}" as="ch" hint-placeholder-count="5">\n'
    '                  <sc-if value="{{ ch.divider }}" hint-placeholder-val="{{ false }}">'
    '<div class="bsi-sub-divider"></div></sc-if>\n'
    '                  <sc-if value="{{ ch.label }}" hint-placeholder-val="{{ true }}">'
    '<button sc-camel-on-click="{{ ch.onClick }}" class="bsi-sublink">'
    '<span class="bsi-sub-cat">{{ ch.label }}</span>'
    '<span class="bsi-sub-meta">'
    '<sc-if value="{{ ch.time }}" hint-placeholder-val="{{ false }}">'
    '<em class="bsi-sub-time">{{ ch.time }}</em></sc-if>'
    '<sc-if value="{{ ch.meta }}" hint-placeholder-val="{{ false }}">'
    '<small>{{ ch.meta }}</small></sc-if>'
    '</span></button></sc-if>\n'
    '                </sc-for>\n'
    '              </div>\n'
    '            </sc-if>\n'
    '          </div>\n'
    '        </sc-for>'
)

# ── 4. Account controls: one right-anchored dropdown ────────────────────────
# Was NAV_ACCOUNT_DST (see the Phase 6 initial pass): a Dashboard button,
# a "● name" pill and a Log out link, three siblings between the Shop
# link and the Book Now CTA. Now: one .bsi-account-trigger pill with the
# green live dot and the account name, opening a right-anchored dropdown
# that lists Dashboard (admins only), Booking History, Order History and
# Log out. A signed-out visitor sees a single Log in pill instead. Shop
# also gains the .bsi-navi wrapper so it sits at the same height as the
# other trigger pills and can grow a dropdown later without a further
# refactor.
NAV_ACCOUNT_SRC = (
    '<a href="/shop" style="font-family:\'Manrope\',sans-serif;font-size:14px;color:#454545;'
    'font-weight:500;padding:4px 0;white-space:nowrap;flex-shrink:0;text-decoration:none;'
    'transition:color .2s;" style-hover="color:#e8283f;">Shop</a>\n'
    '      </div>\n'
    '      <button sc-camel-on-click="{{ goBookingNav }}"'
)
NAV_ACCOUNT_DST = (
    '<div class="bsi-navi">\n'
    '          <a href="/shop" class="bsi-nav-trigger" '
    "style=\"color:#454545;font-weight:600;text-decoration:none;\">Shop</a>\n"
    '        </div>\n'
    '      </div>\n'
    '      <sc-if value="{{ userLoggedIn }}" hint-placeholder-val="{{ false }}">\n'
    '        <div class="bsi-navi bsi-navi-right">\n'
    '          <button class="bsi-account-trigger" type="button">'
    '<span class="bsi-account-dot"></span>'
    '<span>{{ userAccountLabel }}</span>'
    '<span class="bsi-caret">▾</span>'
    '</button>\n'
    '          <div class="bsi-subm">\n'
    '            <div class="bsi-sub-group">Signed in</div>\n'
    '            <sc-if value="{{ userIsAdmin }}" hint-placeholder-val="{{ false }}">\n'
    '              <a href="/salon/dashboard" class="bsi-sublink">'
    '<span>Salon Dashboard</span><small>Admin</small></a>\n'
    '              <div class="bsi-sub-divider"></div>\n'
    '            </sc-if>\n'
    '            <a href="/salon/my/appointments" class="bsi-sublink">'
    '<span>Booking History</span></a>\n'
    '            <a href="/salon/my/orders" class="bsi-sublink">'
    '<span>Order History</span></a>\n'
    '            <div class="bsi-sub-divider"></div>\n'
    '            <a href="/web/session/logout?redirect=/salon" class="bsi-sublink is-danger">'
    '<span>Log out</span></a>\n'
    '          </div>\n'
    '        </div>\n'
    '      </sc-if>\n'
    '      <sc-if value="{{ userLoggedOut }}" hint-placeholder-val="{{ true }}">\n'
    '        <a href="/web/login?redirect=/salon" class="bsi-nav-login">Log in</a>\n'
    '      </sc-if>\n'
    '      <button sc-camel-on-click="{{ goBookingNav }}"'
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
    # Full reset — same field list as RESET_BOOKING_DST / GOBOOKINGNAV_RESET_DST
    # so that stale service/reward/look/loyalty state from a previous booking
    # attempt never leaks into this stylist-seeded booking.
    "      booking: { cityId, storeId, step: storeId ? 3 : 1 }, bookingMaxStep: storeId ? 3 : 1,\n"
    "      selectedChairIds: [], selectedTime: null, bookingConfirmed: false,\n"
    "      bookingError: false, bookingSubmitting: false,\n"
    "      bookingServiceId: null, bookingServiceIds: [], bookingServiceName: null,\n"
    "      bookingServicePrice: null, bookingActiveServiceCat: null,\n"
    "      bookingPackageId: null, bookingPackageName: null, bookingPackagePrice: null,\n"
    "      rewardServiceId: null, rewardServiceName: null,\n"
    "      bookingRewardId: null, bookingRewardAddedSvc: null, bookingUseServicePoints: true,\n"
    "      bookingLookLength: null, bookingLookShadeIndex: null, bookingLookFinish: null,\n"
    "      bookingLookPrice: null, ritual: [], isMember: false,\n"
    "      bookingLoyaltyPoints: 0, bookingGiftCode: '', bookingQuote: null,\n"
    "      bookingLoyaltyAuto: true, bookingGiftAuto: true,\n"
    "      bookingQuoteError: '', bookingQuoteLoading: false,\n"
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
    "          onClick: () => this.setState({ contactSelectedCityId: on ? null : c.id }),\n"
    "          on: on,\n"
    "          branches: (c.branches || []).map((b) => ({ name: b.name || b.city || '', "
    "address: b.area || '' })),\n"
    "          stopProp: (e) => { if (e && e.stopPropagation) e.stopPropagation(); },\n"
    "          bg: on ? '#161213' : '#ffffff', color: on ? '#fdf3ea' : '#161213',\n"
    "          border: on ? '1px solid #161213' : '1px solid rgba(20,17,17,.08)',\n"
    "          flexDir: on ? 'column' : 'row',\n"
    "          alignItems: on ? 'flex-start' : 'center' };\n"
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
    '<div sc-camel-on-click="{{ c.onClick }}" style="display:flex;flex-direction:{{ c.flexDir }};'
    'justify-content:space-between;align-items:{{ c.alignItems }};'
    'padding:14px 18px;background:{{ c.bg }};border:{{ c.border }};'
    'border-radius:14px;font-size:14px;color:{{ c.color }};cursor:pointer;box-shadow:0 3px 12px -10px '
    'rgba(20,17,17,.6);transition:all .25s;'
    'animation:fadeUp .5s ease-out {{ c.delay }}s both;" '
    'style-hover="transform:translateX(4px);box-shadow:0 14px 30px -20px rgba(20,17,17,.6);">'
)

# Inject branch list inside the tile when a city is selected. The tile's
# opening div is patched by CONTACT_TILE_MARKUP_DST to flex-column; the
# name/count row becomes a plain row div, and a branch list appears below.
CONTACT_TILE_INNER_SRC = (
    '<span style="font-weight:700;">{{ c.name }}</span>\n'
    '                <span style="font-size:12px;color:#767676;">{{ c.count }} branches →</span>\n'
    '              </div>'
)
CONTACT_TILE_INNER_DST = (
    '<div style="display:flex;justify-content:space-between;align-items:center;width:100%;">\n'
    '                  <span style="font-weight:700;">{{ c.name }}</span>\n'
    '                  <span style="font-size:12px;opacity:.7;">{{ c.count }} branches →</span>\n'
    '                </div>\n'
    # Branch list shown only when city is selected
    '                <sc-if value="{{ c.on }}" hint-placeholder-val="{{ false }}">\n'
    '                  <div style="margin-top:10px;padding-top:10px;border-top:1px solid rgba(253,243,234,.2);'
    'width:100%;display:flex;flex-direction:column;gap:5px;" sc-camel-on-click="{{ c.stopProp }}">\n'
    '                    <sc-for list="{{ c.branches }}" as="br" hint-placeholder-count="2">\n'
    '                      <div style="font-size:12px;font-weight:600;color:rgba(253,243,234,.9);'
    'padding:4px 0;border-bottom:1px solid rgba(253,243,234,.08);">{{ br.name }}</div>\n'
    '                    </sc-for>\n'
    '                  </div>\n'
    '                </sc-if>\n'
    '              </div>'
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
    "  toggleGiftCardsPopup = () => this.setState((s) => ({ showGiftCardsPopup: !s.showGiftCardsPopup }));\n"
    "  buyGiftCard = () => { "
    # Block purchase when that denomination is already active (balance > 0)
    'const activeAmounts = (this.state.myGiftCards || []).filter((c) => c.active).map((c) => c.amount); '
    'if (activeAmounts.includes(this.state.giftAmount)) { return; } '
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
    "      myGiftCardMissing: !s.myGiftCardCode,\n"
    "      toggleGiftCardsPopup: this.toggleGiftCardsPopup, showGiftCardsPopup: !!s.showGiftCardsPopup,\n"
    # Disable buy button when that denomination already has an active card
    "      giftBuyDisabled: !!(s.myGiftCards || []).find((c) => c.active && c.amount === s.giftAmount),\n"
    "      giftBuyBtnBg: (s.myGiftCards || []).find((c) => c.active && c.amount === s.giftAmount) "
    "? '#9b9b9b' : '#e8283f',\n"
    "      giftBuyBtnLabel: (s.myGiftCards || []).find((c) => c.active && c.amount === s.giftAmount) "
    "? 'Already active – use your card' : ('Buy ₹' + Number(s.giftAmount || 0).toLocaleString('en-IN') + ' Gift Card'),\n"
    "      giftCardsPopupList: (s.myGiftCards || []).map((c) => ({\n"
    "        code: c.code, amount: '₹' + c.amount,\n"
    "        balance: c.active ? ('₹' + Math.round(c.balance) + ' left') : (c.state === 'used' ? 'Used up' : c.state),\n"
    "        statusColor: c.active ? '#1f8a4c' : '#9b9b9b',\n"
    "        statusLabel: c.active ? 'Active' : (c.state === 'used' ? 'Used' : c.state),\n"
    "        rowBg: c.active ? 'rgba(31,138,76,.06)' : 'rgba(20,17,17,.03)',\n"
    "        rowBorder: c.active ? '1px solid rgba(31,138,76,.25)' : '1px solid rgba(20,17,17,.08)',\n"
    "      })),\n"
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
    '            <div style="background:linear-gradient(135deg,#2c2226,#161213 55%,#0d0a0c);border-radius:16px;'
    'padding:18px 20px;box-shadow:0 18px 40px -18px rgba(20,17,17,.8);">\n'
    '              <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px;">\n'
    '                <span style="font-family:\'Playfair Display\',serif;font-size:19px;color:#fdf3ea;">enrich</span>\n'
    '                <span style="font-size:9px;font-weight:800;letter-spacing:1.6px;color:#3ddc84;">ACTIVE</span>\n'
    '              </div>\n'
    '              <div style="font-size:9.5px;letter-spacing:1.6px;color:#a79a9d;margin-bottom:4px;">CARD CODE</div>\n'
    '              <div style="font-family:monospace;font-size:15px;font-weight:700;color:#fdf3ea;'
    'letter-spacing:1px;margin-bottom:14px;">{{ myGiftCardCode }}</div>\n'
    '              <div style="font-size:9.5px;letter-spacing:1.6px;color:#a79a9d;margin-bottom:4px;">BALANCE</div>\n'
    '              <div style="font-family:\'Playfair Display\',serif;font-size:28px;color:#c9a15a;'
    'line-height:1;">₹{{ myGiftCardBalance }}</div>\n'
    '            </div>\n'
    '            <div style="font-size:12px;color:#767676;margin-top:12px;">Apply it on the booking '
    'confirmation step.</div>\n'
    '          </sc-if>\n'
    '          <sc-if value="{{ myGiftCardMissing }}" hint-placeholder-val="{{ true }}">\n'
    '            <div style="background:#ffffff;border:1px dashed rgba(20,17,17,.2);border-radius:16px;'
    'padding:22px;text-align:center;">\n'
    '              <div style="font-size:14px;font-weight:700;color:#161213;margin-bottom:4px;">No active gift card</div>\n'
    '              <div style="font-size:12px;color:#767676;">A gift card on your account will show here with its balance.</div>\n'
    '            </div>\n'
    '          </sc-if>'
)

# Everything under the Gift Cards header -- the flipping sample card, the amount
# and message pickers and the Buy button -- is removed: the panel is status only.
GIFT_BODY_SRC = (
    '\n\n          <div style="perspective:1100px;margin-bottom:16px;">\n'
    '            <div style="position:relative;width:100%;aspect-ratio:1.6;transform-style:preserve-3d;'
    'animation:cardFlip 9s ease-in-out infinite;">\n'
    '              <div style="position:absolute;inset:0;backface-visibility:hidden;border-radius:16px;'
    'overflow:hidden;background:linear-gradient(135deg,#2c2226,#161213 55%,#0d0a0c);'
    'box-shadow:0 18px 40px -18px rgba(20,17,17,.8);padding:18px;display:flex;flex-direction:column;'
    'justify-content:space-between;">\n'
    '                <div style="display:flex;justify-content:space-between;align-items:flex-start;">\n'
    '                  <span style="font-family:\'Playfair Display\',serif;font-size:19px;color:#fdf3ea;">enrich</span>\n'
    '                  <span style="font-size:8.5px;font-weight:800;letter-spacing:1.6px;color:#c9a15a;">GIFT CARD</span>\n'
    '                </div>\n'
    '                <div style="width:38px;height:27px;border-radius:5px;background:linear-gradient(140deg,'
    '#e0c68f,#a8813f);box-shadow:inset 0 1px 2px rgba(255,255,255,.5);"></div>\n'
    '                <div style="display:flex;justify-content:space-between;align-items:flex-end;">\n'
    '                  <span style="font-family:\'Playfair Display\',serif;font-size:26px;color:#fdf3ea;'
    'line-height:1;">₹{{ giftAmount }}</span>\n'
    '                  <span style="font-size:9px;color:#a79a9d;letter-spacing:1.2px;">VALID 12 MONTHS</span>\n'
    '                </div>\n'
    '                <div style="position:absolute;inset:0;overflow:hidden;pointer-events:none;"><span '
    'style="position:absolute;top:-40%;bottom:-40%;width:32%;background:linear-gradient(90deg,transparent,'
    'rgba(255,255,255,.42),transparent);animation:cardShine 9s ease-in-out infinite;"></span></div>\n'
    '              </div>\n'
    '              <div style="position:absolute;inset:0;backface-visibility:hidden;transform:rotateY(180deg);'
    'border-radius:16px;overflow:hidden;background:linear-gradient(135deg,#8a2332,#e8283f 60%,#c9505f);'
    'box-shadow:0 18px 40px -18px rgba(232,40,63,.7);padding:18px;display:flex;flex-direction:column;'
    'justify-content:center;">\n'
    '                <div style="font-size:9px;font-weight:800;letter-spacing:1.8px;color:rgba(255,255,255,.7);'
    'margin-bottom:8px;">YOUR MESSAGE</div>\n'
    '                <div style="font-family:\'Playfair Display\',serif;font-size:17px;color:#fff;line-height:1.35;'
    'font-style:italic;">“{{ giftMessage }}”</div>\n'
    '                <div style="font-size:10.5px;color:rgba(255,255,255,.8);margin-top:10px;">Redeemable at any '
    'of 100+ Enrich salons</div>\n'
    '              </div>\n'
    '            </div>\n'
    '          </div>\n'
    '\n'
    '          <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:14px;">\n'
    '            <sc-for list="{{ giftAmounts }}" as="g" hint-placeholder-count="4">\n'
    '              <button sc-camel-on-click="{{ g.onClick }}" style="flex:1;min-width:64px;border:1.5px solid '
    '{{ g.border }};background:{{ g.bg }};color:{{ g.color }};padding:10px 12px;border-radius:12px;'
    'font-weight:800;cursor:pointer;font-size:13px;transition:all .2s;">₹{{ g.amount }}</button>\n'
    '            </sc-for>\n'
    '          </div>\n'
    '          <div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:16px;">\n'
    '            <sc-for list="{{ giftMessages }}" as="m" hint-placeholder-count="3">\n'
    '              <button sc-camel-on-click="{{ m.onClick }}" style="background:{{ m.bg }};color:{{ m.color }};'
    'border:1px solid {{ m.border }};padding:6px 11px;border-radius:999px;font-size:10.5px;font-weight:700;'
    'cursor:pointer;transition:all .2s;">{{ m.label }}</button>\n'
    '            </sc-for>\n'
    '          </div>\n'
    '          <button style="width:100%;background:#e8283f;color:#ffffff;border:none;padding:14px;'
    'border-radius:12px;font-weight:700;cursor:pointer;font-size:13.5px;'
    'box-shadow:0 12px 28px -14px rgba(232,40,63,.9);">Buy ₹{{ giftAmount }} Gift Card</button>'
)
GIFT_BODY_DST = ''

# Loyalty wallet: the points ring stays; the tier bar and reward cards beside it
# are replaced by a single "worth / where to use it" line.
WALLET_BODY_SRC = (
    '              <div style="font-size:12.5px;color:#a79a9d;margin-bottom:18px;">Earn 1 point per ₹10 spent. '
    'Redeem against any service.</div>\n'
    '\n'
    '              <div style="display:flex;justify-content:space-between;font-size:10.5px;font-weight:700;'
    'color:#c9b9bd;margin-bottom:6px;">\n'
    '                <span>{{ walletTier }} member</span><span>{{ walletToNext }} pts to {{ walletNextTier }}</span>\n'
    '              </div>\n'
    '              <div style="height:8px;border-radius:99px;background:rgba(253,243,234,.12);overflow:hidden;'
    'margin-bottom:18px;">\n'
    '                <div style="height:100%;width:{{ walletTierPct }}%;border-radius:99px;background:'
    'linear-gradient(90deg,#8a2332,#e8283f,#c9a15a);animation:tierGrow 1.6s cubic-bezier(.3,.9,.3,1) both;"></div>\n'
    '              </div>\n'
    '\n'
    '              <div style="display:flex;gap:8px;flex-wrap:wrap;">\n'
    '                <sc-for list="{{ walletRewards }}" as="rw" hint-placeholder-count="3">\n'
    '                  <button sc-camel-on-click="{{ rw.onClick }}" style="flex:1;min-width:120px;text-align:left;'
    'background:{{ rw.bg }};border:1px solid {{ rw.border }};color:{{ rw.color }};padding:11px 13px;'
    'border-radius:13px;cursor:{{ rw.cursor }};transition:all .22s;" style-hover="transform:translateY(-2px);">\n'
    '                    <div style="font-size:12px;font-weight:800;line-height:1.2;">{{ rw.name }}</div>\n'
    '                    <div style="font-size:10px;margin-top:3px;opacity:.75;">{{ rw.cost }} pts · {{ rw.state }}</div>\n'
    '                  </button>\n'
    '                </sc-for>\n'
    '              </div>\n'
)
WALLET_BODY_DST = (
    '              <div style="font-size:12.5px;color:#a79a9d;line-height:1.6;">You have '
    '<b style="color:#fdf3ea;">{{ walletPoints }} points</b>. Apply them on the booking '
    'confirmation step.</div>\n'
)

GIFT_BUTTON_SRC = (
    '<button style="width:100%;background:#e8283f;color:#ffffff;border:none;'
    'padding:14px;border-radius:12px;font-weight:700;cursor:pointer;font-size:13.5px;'
    'box-shadow:0 12px 28px -14px rgba(232,40,63,.9);">Buy ₹{{ giftAmount }} Gift Card</button>'
)
GIFT_BUTTON_DST = (
    '<button sc-camel-on-click="{{ buyGiftCard }}" disabled="{{ giftBuyDisabled }}" '
    'style="width:100%;background:{{ giftBuyBtnBg }};'
    'color:#ffffff;border:none;padding:14px;border-radius:12px;font-weight:700;'
    'cursor:{{ giftBuyDisabled ? \'not-allowed\' : \'pointer\' }};'
    'font-size:13.5px;box-shadow:{{ giftBuyDisabled ? \'none\' : \'0 12px 28px -14px rgba(232,40,63,.9)\' }};">'
    '{{ giftBuyBtnLabel }}</button>'
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
# PHASE 6 DEV -- walletValue was still the design's own "2 points = \u20b91" guess
# (Math.round(WALLET_PTS / 2)), which now openly contradicts the booking Confirm
# screen: that states the configured conversion and redeems at it (see
# res_config_settings.bsi_loyalty_point_value, 1 point = \u20b91 by default), so a
# 300-point balance read "Worth \u20b9150 today" here and bought \u20b9300 of booking
# one page over. Same /salon/api/loyalty_status call supplies both now.
WALLET_POINTS_SRC = "walletPoints: WALLET_PTS, walletValue: Math.round(WALLET_PTS / 2),"
WALLET_POINTS_DST = (
    "walletPoints: (s.loyaltyPoints || 0), "
    "walletValue: Math.round((s.loyaltyPoints || 0) * (s.loyaltyPointValue || 1)),"
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
    # PHASE 9 DEV -- no longer spends the points up front: the reward rides into the
    # booking and is used (and the points spent) only when the booking is confirmed.
    "void rpc; const rw = (WALLET_REWARDS || []).find((x) => x.id === rewardId) || {}; "
    "this.setPage('booking', { booking: { cityId: null, storeId: null, step: 1 }, "
    "selectedChairIds: [], selectedTime: null, bookingConfirmed: false, "
    "bookingRewardId: rewardId, bookingRewardAddedSvc: rw.service_id || null, "
    "bookingServiceIds: rw.service_id ? [rw.service_id] : [], bookingServiceId: null, "
    "bookingPackageId: null }); };"
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
    # PHASE 9 DEV -- booking the service is enough: its own points are used
    # automatically on the Confirm step while the balance covers them.
    "void rpc; const svAll = [].concat.apply([], Object.keys(SERVICES_DATA).map((k) => SERVICES_DATA[k])); "
    "const sv = svAll.find((x) => x.id === serviceId) || {}; "
    "this.goBookingWithService(serviceId, sv.name || ''); };"
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
    "redeemPointsLabel: sv.points ? ('Book · use ' + sv.points + ' pts') : '', "
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
    'const s = this.state; if (s.contactSending) return; '
    'const form = e && e.target ? e.target : null; '
    'const vals = form ? Array.prototype.map.call('
    'form.querySelectorAll("input, textarea"), (el) => String(el.value || "").trim()) : []; '
    'const name = vals[0] || "", email = vals[1] || "", phone = vals[2] || "", notes = vals[3] || ""; '
    'let err = ""; '
    'if (!name) err = "Please tell us your name."; '
    'else if (!email && !phone) err = "Please add an email or a phone number so we can reply."; '
    'else if (email && !/^[^\\s@]+@[^\\s@]+\\.[^\\s@]+$/.test(email)) err = "That email address does not look right."; '
    'else if (!s.contactFormCityId) err = "Please choose your city."; '
    'else if (!s.contactFormBranchId) err = "Please choose the branch you would like to hear from."; '
    'else if (notes.length < 5) err = "Please write a short message so we know how to help."; '
    'if (err) { this.setState({ contactError: err }); return; } '
    'const city = (CITIES || []).find((c) => c.id === s.contactFormCityId); '
    'const branch = city ? (city.branches || []).find((b) => b.id === s.contactFormBranchId) : null; '
    'const fail = "We could not send your message. Please try again, or call " + (((typeof BSI_CONTACT !== \'undefined\') && BSI_CONTACT.phone) || "1800-266-5300") + "."; '
    'this.setState({ contactError: "", contactSending: true, contactCityOpen: false, contactBranchOpen: false }); '
    'fetch("/salon/api/contact", { method: "POST", credentials: "same-origin", '
    'headers: { "Content-Type": "application/json" }, '
    'body: JSON.stringify({ id: 1, jsonrpc: "2.0", method: "call", params: { '
    'name: name, email: email, phone: phone, notes: (s.contactTopic ? "[" + s.contactTopic + "] " : "") + notes, '
    'location_id: s.contactFormBranchId, city: city ? city.name : "" } }) '
    '}).then((r) => r.json()).then((payload) => { const res = payload && payload.result; '
    'if (res && res.ok) { this.setState({ contactSent: true, contactSending: false, '
    'contactSentBranch: branch ? branch.name : "" }); } '
    'else { this.setState({ contactSending: false, contactError: (res && res.error) || fail }); } '
    '}).catch(() => this.setState({ contactSending: false, contactError: fail })); };'
)


# PHASE 8 DEV -- City and Branch on the contact form, so every enquiry reaches CRM
# already assigned to the branch (and so the company) it is for -- see
# bsi_salon_api_contact. Custom dropdowns rather than <select>: the page template
# engine cannot loop <option>s inside a <select> (the HTML parser drops the loop
# element), and a styled list matches the rest of the form anyway. Every control is a
# type="button", so none of them submits the form, and none is an input/textarea, so
# sendContact's positional read of the four text fields is unchanged.
CONTACT_PICKERS_SRC = '<textarea placeholder="How can we help?" rows="4"'
CONTACT_PICKERS_DST = (
    '<div class="bsi-cf-row">\n'
    '                  <div class="bsi-cf-field">\n'
    '                    <span class="bsi-cf-cap">City</span>\n'
    '                    <button type="button" class="{{ contactCityBtnCls }}" sc-camel-on-click="{{ contactToggleCity }}" aria-haspopup="listbox">'
    '<span class="bsi-cf-value">{{ contactCityLabel }}</span><span class="bsi-cf-caret" aria-hidden="true"></span></button>\n'
    '                    <sc-if value="{{ contactCityOpen }}" hint-placeholder-val="{{ false }}">\n'
    '                      <div class="bsi-cf-menu" role="listbox">\n'
    '                        <sc-for list="{{ contactCityOptions }}" as="o" hint-placeholder-count="6">\n'
    '                          <button type="button" class="{{ o.cls }}" sc-camel-on-click="{{ o.onClick }}" role="option">'
    '<span>{{ o.name }}</span><small>{{ o.meta }}</small></button>\n'
    '                        </sc-for>\n'
    '                      </div>\n'
    '                    </sc-if>\n'
    '                  </div>\n'
    '                  <div class="bsi-cf-field">\n'
    '                    <span class="bsi-cf-cap">Branch</span>\n'
    '                    <button type="button" class="{{ contactBranchBtnCls }}" sc-camel-on-click="{{ contactToggleBranch }}" aria-haspopup="listbox">'
    '<span class="bsi-cf-value">{{ contactBranchLabel }}</span><span class="bsi-cf-caret" aria-hidden="true"></span></button>\n'
    '                    <sc-if value="{{ contactBranchOpen }}" hint-placeholder-val="{{ false }}">\n'
    '                      <div class="bsi-cf-menu" role="listbox">\n'
    '                        <sc-for list="{{ contactBranchOptions }}" as="o" hint-placeholder-count="4">\n'
    '                          <button type="button" class="{{ o.cls }}" sc-camel-on-click="{{ o.onClick }}" role="option">'
    '<span>{{ o.name }}</span><small>{{ o.meta }}</small></button>\n'
    '                        </sc-for>\n'
    '                      </div>\n'
    '                    </sc-if>\n'
    '                  </div>\n'
    '                </div>\n'
    '                <sc-if value="{{ contactMenuOpen }}" hint-placeholder-val="{{ false }}">'
    '<div class="bsi-cf-backdrop" sc-camel-on-click="{{ contactCloseMenus }}"></div></sc-if>\n'
    '                <textarea placeholder="How can we help?" rows="4"'
)
CONTACT_ERROR_SRC = '                <button type="submit" style="position:relative;overflow:hidden;background:#e8283f;'
CONTACT_ERROR_DST = (
    '                <sc-if value="{{ contactHasError }}" hint-placeholder-val="{{ false }}">'
    '<div class="bsi-cf-error" role="alert">{{ contactError }}</div></sc-if>\n'
    '                <button type="submit" disabled="{{ contactSending }}" style="position:relative;overflow:hidden;background:#e8283f;'
)
CONTACT_SEND_LABEL_SRC = '\n                  Send Message\n'
CONTACT_SEND_LABEL_DST = '\n                  {{ contactSendLabel }}\n'
CONTACT_SENT_NOTE_SRC = 'Expect a reply within one working day.</p>'
CONTACT_SENT_NOTE_DST = '{{ contactSentNote }}</p>'
CONTACT_FORM_RENDER_SRC = (
    "      contactNotSent: !s.contactSent, contactSent: s.contactSent, sendContact: this.sendContact,\n"
)
CONTACT_FORM_RENDER_DST = (
    "      contactNotSent: !s.contactSent, contactSent: s.contactSent, sendContact: this.sendContact,\n"
    "      ...(() => {\n"
    "        const cityList = CITIES || [];\n"
    "        const city = cityList.find((c) => c.id === s.contactFormCityId) || null;\n"
    "        const branches = city ? (city.branches || []) : [];\n"
    "        const branch = branches.find((b) => b.id === s.contactFormBranchId) || null;\n"
    "        const close = () => this.setState({ contactCityOpen: false, contactBranchOpen: false });\n"
    "        return {\n"
    "          contactCityLabel: city ? city.name : 'Select your city',\n"
    "          contactBranchLabel: branch ? branch.name : (city ? 'Select a branch' : 'Choose a city first'),\n"
    "          contactCityBtnCls: 'bsi-cf-select' + (city ? ' has-value' : '') + (s.contactCityOpen ? ' is-open' : ''),\n"
    "          contactBranchBtnCls: 'bsi-cf-select' + (branch ? ' has-value' : '') + (s.contactBranchOpen && city ? ' is-open' : '') + (city ? '' : ' is-disabled'),\n"
    "          contactCityOpen: !!s.contactCityOpen,\n"
    "          contactBranchOpen: !!(s.contactBranchOpen && city),\n"
    "          contactMenuOpen: !!(s.contactCityOpen || (s.contactBranchOpen && city)),\n"
    "          contactCloseMenus: close,\n"
    "          contactToggleCity: () => this.setState({ contactCityOpen: !s.contactCityOpen, contactBranchOpen: false }),\n"
    "          contactToggleBranch: () => (city ? this.setState({ contactBranchOpen: !s.contactBranchOpen, contactCityOpen: false }) : this.setState({ contactCityOpen: true, contactBranchOpen: false })),\n"
    "          contactCityOptions: cityList.map((c) => ({\n"
    "            name: c.name, meta: (c.branches || []).length + ' branch' + ((c.branches || []).length === 1 ? '' : 'es'),\n"
    "            cls: 'bsi-cf-opt' + (c.id === s.contactFormCityId ? ' is-on' : ''),\n"
    "            onClick: () => this.setState({ contactFormCityId: c.id, contactFormBranchId: c.id === s.contactFormCityId ? s.contactFormBranchId : null,\n"
    "              contactCityOpen: false, contactBranchOpen: c.id !== s.contactFormCityId || !s.contactFormBranchId, contactError: '' }),\n"
    "          })),\n"
    "          contactBranchOptions: branches.map((b) => ({\n"
    "            name: b.name, meta: b.area || '',\n"
    "            cls: 'bsi-cf-opt' + (b.id === s.contactFormBranchId ? ' is-on' : ''),\n"
    "            onClick: () => this.setState({ contactFormBranchId: b.id, contactBranchOpen: false, contactError: '' }),\n"
    "          })),\n"
    "          contactError: s.contactError || '',\n"
    "          contactHasError: !!s.contactError,\n"
    "          contactSending: !!s.contactSending,\n"
    "          contactSendLabel: s.contactSending ? 'Sending\\u2026' : 'Send Message',\n"
    "          contactSentNote: s.contactSentBranch\n"
    "            ? ('Our ' + s.contactSentBranch + ' team will reply within one working day.')\n"
    "            : 'Expect a reply within one working day.',\n"
    "          // PHASE 8 DEV -- contact page redesign: topic chips, the live salon card\n"
    "          // and the post-send actions (see enrich_redesign.CONTACT_SECTION_DST).\n"
    "          contactTopics: ['Booking help', 'Services & prices', 'Membership', 'Feedback'].map((label) => ({\n"
    "            label, cls: 'bsi-ct__topic' + (s.contactTopic === label ? ' is-on' : ''),\n"
    "            onClick: () => this.setState({ contactTopic: s.contactTopic === label ? null : label }),\n"
    "          })),\n"
    "          contactHasBranch: !!branch,\n"
    "          contactNoBranch: !branch,\n"
    "          contactBranchCardCls: 'bsi-ct__branch' + (branch ? ' is-set' : ''),\n"
    "          contactBranch: branch ? {\n"
    "            name: branch.name, city: city ? city.name : '', area: branch.area || '', hours: branch.hours || '',\n"
    "            phone: branch.phone || '', telHref: 'tel:' + String(branch.phone || '').replace(/[^0-9+]/g, ''),\n"
    "            rating: branch.rating || '4.8',\n"
    "            mapHref: (branch.lat && branch.lng)\n"
    "              ? ('https://www.google.com/maps/dir/?api=1&destination=' + branch.lat + ',' + branch.lng)\n"
    "              : ('https://www.google.com/maps/search/?api=1&query=' + encodeURIComponent('Enrich ' + branch.name + ' ' + (branch.area || (city ? city.name : '')))),\n"
    "          } : { name: '', city: '', area: '', hours: '', phone: '', telHref: '', rating: '', mapHref: '' },\n"
    "          contactBookBranch: () => { if (city && branch) this.bookFromBranch(city.id, branch.id); },\n"
    "          contactScrollToForm: () => { const el = document.getElementById('bsiContactForm'); if (!el) return; "
    "const nav = document.querySelector('.bsi-nav, header, nav'); const off = (nav ? nav.getBoundingClientRect().height : 0) + 16; "
    "const docTop = el.getBoundingClientRect().top + window.scrollY - off; "
    "window.scrollTo({ top: docTop, behavior: 'smooth' }); "
    "if (document.body.scrollHeight > document.body.clientHeight && getComputedStyle(document.body).overflowY !== 'visible') { "
    "document.body.scrollTo({ top: el.getBoundingClientRect().top + document.body.scrollTop - off, behavior: 'smooth' }); } },\n"
    "          contactReset: () => this.setState({ contactSent: false, contactSentBranch: '', contactError: '', contactTopic: null,\n"
    "            contactVName: '', contactVEmail: '', contactVPhone: '', contactVMsg: '' }),\n"
    "          ...(() => {\n"
    "            // PHASE 8 DEV -- live form feedback: field ticks, 4-step progress, counter.\n"
    "            const vName = String(s.contactVName || '').trim(), vEmail = String(s.contactVEmail || '').trim();\n"
    "            const vPhone = String(s.contactVPhone || '').replace(/[^0-9]/g, ''), vMsg = String(s.contactVMsg || '').trim();\n"
    "            const nameOk = vName.length >= 2;\n"
    "            const emailOk = /^[^\\s@]+@[^\\s@]+\\.[^\\s@]+$/.test(vEmail);\n"
    "            const phoneOk = vPhone.length >= 7;\n"
    "            const msgOk = vMsg.length >= 5;\n"
    "            const fc = (touched, valid) => 'bsi-ct__field' + (valid ? ' is-valid' : (touched ? ' is-invalid' : ''));\n"
    "            const steps = [\n"
    "              { n: 1, label: 'Topic', done: !!s.contactTopic },\n"
    "              { n: 2, label: 'You', done: nameOk && (emailOk || phoneOk) },\n"
    "              { n: 3, label: 'Salon', done: !!branch },\n"
    "              { n: 4, label: 'Message', done: msgOk },\n"
    "            ];\n"
    "            const done = steps.filter((x) => x.done).length;\n"
    "            const pct = Math.round(done / steps.length * 100);\n"
    "            const minsOf = (t) => { const x = String(t || '').match(/(\\d{1,2}):(\\d{2})\\s*(AM|PM)?/i); if (!x) return null;\n"
    "              let h = parseInt(x[1], 10); if (x[3]) { h = h % 12 + (/pm/i.test(x[3]) ? 12 : 0); } return h * 60 + parseInt(x[2], 10); };\n"
    "            const now = new Date(); const nowM = now.getHours() * 60 + now.getMinutes();\n"
    "            const fmt = (m) => { const h = Math.floor(m / 60), mm = m % 60; return ((h % 12) || 12) + (mm ? ':' + (mm < 10 ? '0' : '') + mm : '') + (h >= 12 ? ' PM' : ' AM'); };\n"
    "            const CT = (typeof BSI_CONTACT !== 'undefined' && BSI_CONTACT) || {};\n"
    "            const ctOpen = CT.openMin != null ? CT.openMin : 600, ctClose = CT.closeMin != null ? CT.closeMin : 1200;\n"
    "            const lineOpen = nowM >= ctOpen && nowM < ctClose;\n"
    "            let bOpen = null, bOpenLabel = '';\n"
    "            if (branch) {\n"
    "              const hh = String(branch.hours || '').match(/\\d{1,2}:\\d{2}\\s*(?:AM|PM)?/gi) || [];\n"
    "              const o = minsOf(hh[0]), c = minsOf(hh[1]);\n"
    "              if (o != null && c != null && c > o) { bOpen = nowM >= o && nowM < c; bOpenLabel = bOpen ? ('Open now · until ' + fmt(c)) : ('Closed · opens ' + fmt(o)); }\n"
    "            }\n"
    "            const lat = branch && parseFloat(branch.lat), lng = branch && parseFloat(branch.lng);\n"
    "            const hasMap = !!(branch && lat && lng);\n"
    "            const FAQ = [\n"
    "              { q: 'Can I change or cancel my booking?', a: 'Yes. Reply to your booking email or call your salon and we will move or cancel it. We hold your chair for 10 minutes past the booked time.' },\n"
    "              { q: 'Can I choose my artist?', a: 'Yes. On the booking page pick your salon, then choose any artist working there, or leave it to us and we will match you with the right artist.' },\n"
    "              { q: 'How and when do I pay?', a: 'You pay at the salon once your services are finished. Your booking summary shows the estimated total before you arrive.' },\n"
    "              { q: 'Do members get their discount automatically?', a: 'Yes. When you book while signed in, an active membership discount is applied to your booking automatically.' },\n"
    "              { q: 'Where can I see my past and upcoming visits?', a: 'Sign in and open My appointments. You can see every visit, its status, and leave a review after it is done.' },\n"
    "            ];\n"
    "            return {\n"
    "              contactOnName: (e) => this.setState({ contactVName: e && e.target ? e.target.value : '', contactError: '' }),\n"
    "              contactOnEmail: (e) => this.setState({ contactVEmail: e && e.target ? e.target.value : '', contactError: '' }),\n"
    "              contactOnPhone: (e) => this.setState({ contactVPhone: e && e.target ? e.target.value : '', contactError: '' }),\n"
    "              contactOnMsg: (e) => this.setState({ contactVMsg: e && e.target ? e.target.value : '', contactError: '' }),\n"
    "              contactFieldCls: {\n"
    "                name: fc(vName.length > 0, nameOk),\n"
    "                email: fc(vEmail.length > 0, emailOk),\n"
    "                phone: fc(vPhone.length > 0, phoneOk),\n"
    "                message: fc(vMsg.length > 0, msgOk) + ' bsi-ct__field--msg',\n"
    "              },\n"
    "              contactMsgCount: String(s.contactVMsg || '').length,\n"
    "              contactProgress: { pct, steps: steps.map((x) => ({ n: x.done ? '✓' : x.n, label: x.label, cls: 'bsi-ct__pstep' + (x.done ? ' is-done' : '') })) },\n"
    "              contactSubmitCls: 'bsi-ct__submit' + (pct === 100 ? ' is-ready' : ''),\n"
    "              contactLineLabel: lineOpen ? ('Lines open now · until ' + (CT.closeLabel || '8 PM')) : ('Lines closed · open ' + (CT.openLabel || '10 AM') + '–' + (CT.closeLabel || '8 PM')),\n"
    "              contactLineCls: 'bsi-ct-live' + (lineOpen ? ' is-open' : ''),\n"
    "              contactFaq: FAQ.map((f, k) => ({ q: f.q, a: f.a, open: s.contactFaqOpen === k,\n"
    "                cls: 'bsi-ct-faq__item' + (s.contactFaqOpen === k ? ' is-open' : ''),\n"
    "                onClick: () => this.setState({ contactFaqOpen: s.contactFaqOpen === k ? null : k }) })),\n"
    "              contactBranchExtra: {\n"
    "                openCls: 'bsi-ct__open' + (bOpen === true ? ' is-open' : (bOpen === false ? ' is-closed' : ' is-unknown')),\n"
    "                openLabel: bOpenLabel || 'See hours below',\n"
    "                hasMap,\n"
    "                mapEmbed: hasMap ? ('https://www.openstreetmap.org/export/embed.html?bbox=' + (lng - 0.012) + ',' + (lat - 0.007) + ',' + (lng + 0.012) + ',' + (lat + 0.007) + '&layer=mapnik&marker=' + lat + ',' + lng) : '',\n"
    "              },\n"
    "            };\n"
    "          })(),\n"
    "        };\n"
    "      })(),\n"
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
    "        if (!plan.length) plan.push({ name: 'Signature cut and finish', why: 'The right starting point for healthy hair', price: '\\u20b9899' });\n"
    "        const capped = time === 't1' ? plan.slice(0, 1) : (time === 't2' ? plan.slice(0, 2) : plan.slice(0, 4));\n"
    "        const total = capped.reduce((t, p) => t + parseInt(p.price.replace(/[^0-9]/g, ''), 10), 0);\n"
    "        const mins = capped.length * 45;"
)
CONSULT_DST = (
    "const [goal, condition, history, upkeep, time] = ans;\n"
    "        // One suggestion per rule whose trigger is among the answers given, in the\n"
    "        // manager's own rule order, never the same service twice.\n"
    "        const bsiSeen = {};\n"
    "        const plan = (BSI_CONSULT_RULES || [])\n"
    "          .filter(function (r) { return ans.indexOf(String(r.trigger || '').trim().toLowerCase()) !== -1; })\n"
    "          .filter(function (r) { const k = r.service_id || r.name; if (bsiSeen[k]) return false; bsiSeen[k] = true; return true; })\n"
    "          .map(function (r) { return { name: r.name, why: r.why, price: r.price, amount: Number(r.amount) || 0, mins: Number(r.mins) || 45, service_id: r.service_id || null }; });\n"
    "        if (!plan.length) plan.push({ name: 'Signature cut and finish', why: 'The right starting point for healthy hair', price: '\\u20b9899', amount: 899, mins: 45, service_id: null });\n"
    "        // How many treatments fit: the tightest cap among the answers picked (an\n"
    "        // answer's own 'max', e.g. 1 for 'Under an hour'); 4 when none sets one.\n"
    "        const bsiCaps = Q.map(function (q, qi) { const o = (q.opts || []).find(function (x) { return x.v === ans[qi]; }); return o && o.max ? o.max : 0; }).filter(function (m) { return m > 0; });\n"
    "        const bsiCap = bsiCaps.length ? Math.min.apply(null, bsiCaps) : 4;\n"
    "        const capped = plan.slice(0, Math.max(1, bsiCap));\n"
    "        const total = capped.reduce(function (t, p) { const n = p.amount || parseInt(String(p.price || '').replace(/[^0-9]/g, ''), 10); return t + (isNaN(n) ? 0 : n); }, 0);\n"
    "        const mins = capped.reduce(function (t, p) { return t + (p.mins || 45); }, 0);\n"
    "        this._bsiConsultPlanIds = done ? capped.map(function (p) { return p.service_id; }).filter(Boolean) : [];"
)


CONSULT_BOOK_SRC = (
    '<button sc-camel-on-click="{{ goBookingNav }}" style="background:#e8283f;color:#fff;border:none;'
    'padding:13px 26px;border-radius:8px;font-size:13.5px;font-weight:700;cursor:pointer;'
    'box-shadow:0 14px 30px -14px rgba(232,40,63,.9);transition:transform .2s;" '
    'style-hover="transform:translateY(-2px);">Book this plan →</button>'
)
CONSULT_BOOK_DST = CONSULT_BOOK_SRC.replace('{{ goBookingNav }}', '{{ consultBookPlan }}')
CONSULT_BOOK_RENDER_SRC = "          consultRestart: this.restartConsult,\n"
CONSULT_BOOK_RENDER_DST = (
    "          consultRestart: this.restartConsult,\n"
    "          consultBookPlan: this.bsiBookConsultPlan,\n"
)
# The booking wizard's own reset (goBookingNav) clears the service selection when the
# page swaps in, so the plan's services are applied just after that swap.
CONSULT_BOOK_METHOD_SRC = "  restartConsult = () => {\n"
CONSULT_BOOK_METHOD_DST = (
    "  bsiBookConsultPlan = () => {\n"
    "    const ids = (this._bsiConsultPlanIds || []).slice();\n"
    "    this.goBookingNav();\n"
    "    if (!ids.length) return;\n"
    "    clearTimeout(this._bsiPlanT);\n"
    "    this._bsiPlanT = setTimeout(() => this.setState({ bookingServiceIds: ids, bookingServiceId: null, "
    "bookingPackageId: null, bookingPackageName: null, bookingPackagePrice: null }), 380);\n"
    "  };\n"
    "  restartConsult = () => {\n"
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
    # PHASE 6 DEV -- a cross-page link into the SPA (the static header used on
    # /shop and every other non-SPA page, see bsi_website_header) can only
    # ever navigate with a real browser GET, never call setPage/selectCity
    # the way an in-app click does -- so "Skin" in that header's own Services
    # dropdown links to /salon/services?cat=skin, and this reads it back on
    # mount and applies it the same way clicking the category pill in-app
    # would. Silently does nothing for an unknown/missing category or city
    # (or the wrong starting page -- NAV_INITIAL_DST already resolved that
    # off the URL path itself, before this runs), so a stale or hand-typed
    # query string just degrades to the page's own default.
    "    try {\n"
    "      var qs = new URLSearchParams(window.location.search || '');\n"
    "      var qCat = qs.get('cat');\n"
    "      if (qCat && this.state.page === 'services' && (SERVICES_DATA[qCat] || []).length) { this.setState({ activeServiceCat: qCat }); }\n"
    "      var qCity = qs.get('city');\n"
    "      if (qCity && this.state.page === 'stores' && CITIES.some(function (c) { return c.id === qCity; })) { this.selectCity(qCity); }\n"
    "    } catch (e) {}\n"
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
    "        this.setState({ loyaltyPoints: res.points || 0, "
    "loyaltyPointValue: res.point_value || 1 });\n"
    "      }).catch(function () {});\n"
    "    fetch('/salon/api/gift_card_status', { method: 'POST', credentials: 'same-origin', "
    "headers: { 'Content-Type': 'application/json' }, "
    "body: JSON.stringify({ id: 1, jsonrpc: '2.0', method: 'call', params: {} }) })\n"
    "      .then(function (r) { return r.json(); }).then((payload) => {\n"
    "        const res = (payload && payload.result) || {};\n"
    "        this.setState({ myGiftCardCode: (res.active && res.code) || '', "
    "myGiftCardBalance: (res.active && res.balance) || 0, myGiftCards: res.cards || [] });\n"
    "      }).catch(function () {});\n"
    "    fetch('/salon/api/user_status', { method: 'POST', credentials: 'same-origin', "
    "headers: { 'Content-Type': 'application/json' }, "
    "body: JSON.stringify({ id: 1, jsonrpc: '2.0', method: 'call', params: {} }) })\n"
    "      .then(function (r) { return r.json(); }).then((payload) => {\n"
    "        const res = (payload && payload.result) || {};\n"
    "        this.setState({ userLoggedIn: !!res.logged_in, userIsAdmin: !!res.is_admin, "
    "userName: res.name || '' });\n"
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
    "membershipPerks: [], loyaltyPoints: 0, loyaltyPointValue: 1, "
    "myGiftCardCode: '', myGiftCardBalance: 0, myGiftCards: [], showGiftCardsPopup: false,"
    # PHASE 6 DEV -- who is signed in (for the navbar's own account controls, see
    # NAV_ACCOUNT_MARKUP_DST) and what the Confirm screen's payment panel has been
    # asked to redeem. bookingQuote is the SERVER's own priced answer (see
    # /salon/api/booking_quote) -- the only thing the payment panel ever displays
    # figures from; nothing here is ever used to work a discount out client-side.
    "\n    userLoggedIn: false, userIsAdmin: false, userName: '',"
    "\n    bookingLoyaltyPoints: 0, bookingGiftCode: '', bookingQuote: null, "
    "bookingQuoteLoading: false, bookingQuoteError: '',"
    # Until the customer touches either redemption by hand, the quote picks them
    # itself (see main.py _bsi_booking_quote's auto_loyalty/auto_gift_card).
    "\n    bookingLoyaltyAuto: true, bookingGiftAuto: true,"
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
# "✓ <tier> Membership (−X%)" breakdown (see CONFIRM_SCREEN_DST) already
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

TOUR_RENDER_SRC = "      ...(() => {\n        const ROOMS = [\n          { num: '01', name: 'Reception', caption: 'Warm ink walls, a backlit wordmark and a seat while we bring you chai. Your artist meets you here, not at the chair.',\n            tags: ['Welcome chai', 'Consultation', 'Cloakroom'] },\n          { num: '02', name: 'Styling Floor', caption: 'Six mirror stations under bulb arcs, spaced so no two clients share an elbow. Every chair faces its own light.',\n            tags: ['6 stations', 'Ring-lit mirrors', 'Adjustable chairs'] },\n          { num: '03', name: 'Colour Bar', caption: 'The full L\\u2019Or\\u00e9al Professionnel shade library, weighed and mixed to the gram in front of you \\u2014 never pre-batched.',\n            tags: ['120+ shades', 'Weighed to gram', 'Patch tested'] },\n          { num: '04', name: 'Wash Bay', caption: 'Reclining ceramic basins with neck support and warmed towels. The head massage is included, not an upsell.',\n            tags: ['Recline basins', 'Warm towels', 'Free head massage'] },\n          { num: '05', name: 'Spa Suite', caption: 'A separate room behind a screen \\u2014 candles, low light and no mirrors. For facials, threading and anything that needs quiet.',\n            tags: ['Private room', 'Facials', 'Aromatherapy'] },\n        ];\n        const i = s.tourIdx || 0;\n        return {\n          tourTrack: `translateX(-${i * 20}%)`,\n          tourNum: ROOMS[i].num, tourName: ROOMS[i].name, tourCaption: ROOMS[i].caption,\n          tourTags: ROOMS[i].tags.map((label) => ({ label })),\n          tourPrev: () => this.setTour(i - 1),\n          tourNext: () => this.setTour(i === 4 ? 0 : i + 1),\n          tourDots: ROOMS.map((r, k) => ({\n            name: r.name, onClick: () => this.setTour(k),\n            w: k === i ? 30 : 8,\n            bg: k === i ? '#e8283f' : 'rgba(253,243,234,.32)',\n          })),\n        };\n      })(),\n"
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
    "    const bookingServiceNextLabel = s.bookingPackageId "
    "? ('Continue with ' + (s.bookingPackageName || 'this package') + ' \\u2192') "
    ": (bookingSelectedServiceIds.length > 1 "
    "? ('Continue with ' + bookingSelectedServiceIds.length + ' services \\u2192') "
    ": 'Continue to Chair \\u2192');\n"
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
    "        btnLabel: applied ? 'Applied \\u2713 \\u2014 tap to remove' : 'Apply Package',\n"
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
    # own _bsi_onchange_package_common) and prices the booking at the package's
    # flat price instead of a sum of services (see BASEPRICE_DST).
    #
    # PHASE 6 DEV: it no longer advances to Chair on its own. It used to jump
    # straight there the instant a package card was clicked, which meant a
    # customer could not see what the package had just put in their selection,
    # could not change their mind without walking back a step, and got different
    # behaviour from picking services by hand (which has had an explicit
    # Continue button since multi-select arrived). Now a package selects exactly
    # like a service card does -- the card shows as applied, the same Continue
    # button below moves on -- and clicking an applied package again removes it,
    # since with no auto-advance there is now a screen to undo it on.
    "  bookingApplyPackage = (packageId, serviceIds, priceAmount, name) => this.setState((s) => (\n"
    "    s.bookingPackageId === packageId\n"
    "      ? { bookingPackageId: null, bookingPackageName: null, bookingPackagePrice: null,\n"
    "          bookingServiceIds: [], bookingServiceId: null }\n"
    "      : { bookingPackageId: packageId, bookingPackageName: name, "
    "bookingPackagePrice: priceAmount,\n"
    "          bookingServiceIds: (serviceIds || []).slice(), bookingServiceId: null }\n"
    "  ));"
    # ── PHASE 6 DEV: the Confirm screen's payment panel ──────────────────
    # bsiBookingParams is the single description of "what is being booked",
    # shared by the quote and the real submission (see CONFIRM_DST), so the
    # two can never be priced against different selections. bsiRpc is the
    # same jsonrpc envelope every other call on this page already builds by
    # hand, written once.
    #
    # bsiFetchQuote takes `overrides` rather than relying on state having
    # settled: the Apply buttons need the points/code they just read to be in
    # THIS request, and setState is not guaranteed to have been applied by
    # the time the handler's next statement runs.
    "\n  bsiRpc = (url, params) => fetch(url, { method: 'POST', credentials: 'same-origin',\n"
    "    headers: { 'Content-Type': 'application/json' },\n"
    "    body: JSON.stringify({ id: 1, jsonrpc: '2.0', method: 'call', params: params }),\n"
    "  }).then(function (r) { return r.json(); })\n"
    "    .then(function (payload) { return (payload && payload.result) || {}; });\n"
    "  bsiBookingParams = (overrides) => {\n"
    "    const s = this.state;\n"
    "    const city = CITIES.find((c) => c.id === s.booking.cityId) || null;\n"
    "    const store = city ? (city.branches.find((b) => b.id === s.booking.storeId) || null) : null;\n"
    "    const artist = (typeof s.bookingStylist === 'number') ? STYLISTS[s.bookingStylist] : null;\n"
    "    return Object.assign({\n"
    "      location_id: store ? store.id : null, slot_label: s.selectedTime || null,\n"
    "      chair_numbers: s.selectedChairIds || [], is_member: !!s.hasActiveMembership,\n"
    "      city_name: city ? city.name : null, store_name: store ? store.name : null,\n"
    "      reward_service_id: s.rewardServiceId || null, artist_id: artist ? artist.id : null,\n"
    "      look_length: s.bookingLookLength || null, look_shade_index: s.bookingLookShadeIndex,\n"
    "      look_finish: s.bookingLookFinish || null, addon_keys: s.ritual || [],\n"
    "      selected_service_id: s.bookingServiceId || null,\n"
    "      selected_service_ids: (s.bookingServiceIds && s.bookingServiceIds.length) "
    "? s.bookingServiceIds : [],\n"
    "      package_id: s.bookingPackageId || null,\n"
    "      loyalty_points: s.bookingLoyaltyPoints || 0,\n"
    "      gift_card_code: s.bookingGiftCode || '',\n"
    "      reward_id: s.bookingRewardId || null,\n"
    "      use_service_points: s.bookingUseServicePoints !== false,\n"
    "    }, overrides || {});\n"
    "  };\n"
    "  bsiFetchQuote = (overrides) => {\n"
    "    const s0 = this.state;\n"
    "    const ov = Object.assign({ auto_loyalty: !!s0.bookingLoyaltyAuto, "
    "auto_gift_card: !!s0.bookingGiftAuto }, overrides || {});\n"
    "    const seq = (this._bsiQuoteSeq = (this._bsiQuoteSeq || 0) + 1);\n"
    "    this.setState({ bookingQuoteLoading: true });\n"
    "    return this.bsiRpc('/salon/api/booking_quote', this.bsiBookingParams(ov))\n"
    "      .then((res) => {\n"
    # A slower, older answer must never overwrite a newer one (Apply clicked
    # twice quickly, or Remove right after an automatic pick).
    "        if (seq !== this._bsiQuoteSeq) { return; }\n"
    "        if (!res || !res.ok) { this.setState({ bookingQuoteLoading: false, "
    "bookingQuoteError: 'We could not price this booking just now.' }); return; }\n"
    # The balance the wallet/Services pages show is refreshed from the same
    # answer, so a redemption made here is reflected everywhere immediately
    # rather than only after a reload. Whatever the quote actually applied --
    # an automatic pick, or a hand-entered amount/code that passed validation
    # (a refused one comes back as 0 / '' with its error) -- becomes the
    # booking's own redemption, so Confirm submits exactly what the receipt shows.
    "        const L = res.loyalty || {}; const G = res.gift_card || {};\n"
    "        this.setState({ bookingQuote: res, bookingQuoteLoading: false, "
    "bookingQuoteError: '', loyaltyPoints: L.balance || 0, "
    "bookingLoyaltyPoints: L.points || 0, bookingGiftCode: G.code || '' });\n"
    "      }).catch(() => { if (seq === this._bsiQuoteSeq) { this.setState({ bookingQuoteLoading: false, "
    "bookingQuoteError: 'We could not price this booking just now.' }); } });\n"
    "  };\n"
    # Read off the DOM on click rather than bound to state on every keystroke:
    # the whole page re-renders on any state change, and the contact form's own
    # inputs are read exactly this way for the same reason (see CONTACT_DST).
    # Any hand-made change switches that redemption's automatic pick off for
    # the rest of this booking, so a removed card or edited amount stays so.
    "  bsiApplyLoyalty = () => {\n"
    "    const el = document.getElementById('bsiLoyaltyPoints');\n"
    "    const raw = parseInt(el ? el.value : '', 10);\n"
    "    const points = (isFinite(raw) && raw > 0) ? raw : 0;\n"
    "    this.setState({ bookingLoyaltyPoints: points, bookingLoyaltyAuto: false });\n"
    "    this.bsiFetchQuote({ loyalty_points: points, auto_loyalty: false });\n"
    "  };\n"
    "  bsiUseMaxPoints = () => {\n"
    "    const q = this.state.bookingQuote || {};\n"
    "    const points = (q.loyalty && q.loyalty.max_points) || 0;\n"
    "    this.setState({ bookingLoyaltyPoints: points, bookingLoyaltyAuto: false });\n"
    "    this.bsiFetchQuote({ loyalty_points: points, auto_loyalty: false });\n"
    "  };\n"
    "  bsiClearLoyalty = () => {\n"
    "    const el = document.getElementById('bsiLoyaltyPoints');\n"
    "    if (el) { el.value = ''; }\n"
    "    this.setState({ bookingLoyaltyPoints: 0, bookingLoyaltyAuto: false });\n"
    "    this.bsiFetchQuote({ loyalty_points: 0, auto_loyalty: false });\n"
    "  };\n"
    "  bsiApplyGiftCard = () => {\n"
    "    const el = document.getElementById('bsiGiftCardCode');\n"
    "    const code = (el && el.value ? el.value : '').trim();\n"
    "    this.setState({ bookingGiftCode: code, bookingGiftAuto: false });\n"
    "    this.bsiFetchQuote({ gift_card_code: code, auto_gift_card: false });\n"
    "  };\n"
    "  bsiApplyOwnGiftCard = () => {\n"
    "    const q = this.state.bookingQuote || {};\n"
    "    const code = (q.gift_card && q.gift_card.own_code) || '';\n"
    "    this.setState({ bookingGiftCode: code, bookingGiftAuto: false });\n"
    "    this.bsiFetchQuote({ gift_card_code: code, auto_gift_card: false });\n"
    "  };\n"
    # PHASE 9 DEV -- loyalty rewards and service points on the Confirm step.
    "  bsiUseReward = (r) => {\n"
    "    const s = this.state; const patch = { bookingRewardId: r.id, bookingRewardAddedSvc: null };\n"
    "    const ov = { reward_id: r.id };\n"
    "    if (r.service_id && !s.bookingPackageId) {\n"
    "      const ids = (s.bookingServiceIds && s.bookingServiceIds.length) ? s.bookingServiceIds.slice() "
    ": (s.bookingServiceId ? [s.bookingServiceId] : []);\n"
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
    "  bsiClearGiftCard = () => {\n"
    "    const el = document.getElementById('bsiGiftCardCode');\n"
    "    if (el) { el.value = ''; }\n"
    "    this.setState({ bookingGiftCode: '', bookingGiftAuto: false });\n"
    "    this.bsiFetchQuote({ gift_card_code: '', auto_gift_card: false });\n"
    "  };\n"
    # Edit links on the Confirm screen jump straight back to one step; every
    # answer already given is kept (see STEPS_COMPUTE_DST's bookingMaxStep).
    "  bsiGoStep = (n) => { this.setState((s2) => ({ booking: { ...s2.booking, step: n } })); "
    "window.scrollTo({ top: 0, behavior: 'smooth' }); };\n"
    "  bsiGoRewards = () => this.setPage('membership');"
)

STEP_CHAIRNEXT_SRC = (
    "chairNext = () => { if (this.state.selectedChairIds.length) this.setState((s) => "
    "({ booking: { ...s.booking, step: 4 } })); };"
)
STEP_CHAIRNEXT_DST = (
    # A chair is optional: with none picked the salon seats the customer in any
    # free chair (see enrich_redesign.CHAIR_RENDER_DST for the button itself).
    "chairNext = () => { this.setState((s) => "
    "({ booking: { ...s.booking, step: 5 }, bookingMaxStep: Math.max(s.bookingMaxStep || 1, 5) })); };"
)

STEP_SELECTTIME_SRC = (
    "selectTimeAndNext = (t) => this.setState((s) => "
    "({ selectedTime: t, booking: { ...s.booking, step: 5 } }));"
)
STEP_SELECTTIME_DST = (
    # PHASE 6 DEV -- and price the booking server-side on the way in, so the
    # Confirm screen opens on the real total rather than the client estimate.
    "selectTimeAndNext = (t) => { this.setState((s) => "
    "({ selectedTime: t, booking: { ...s.booking, step: 6 }, "
    "bookingMaxStep: Math.max(s.bookingMaxStep || 1, 6) })); "
    "this.bsiFetchQuote({ slot_label: t }); };"
)

STEP_TIMENEXT_SRC = (
    "timeNext = () => { if (this.state.selectedTime) this.setState((s) => "
    "({ booking: { ...s.booking, step: 5 } })); };"
)
STEP_TIMENEXT_DST = (
    "timeNext = () => { if (this.state.selectedTime) { this.setState((s) => "
    "({ booking: { ...s.booking, step: 6 }, bookingMaxStep: Math.max(s.bookingMaxStep || 1, 6) })); "
    "this.bsiFetchQuote(); } };"
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
    # PHASE 6 DEV: the server's own quote wins over the client estimate the
    # moment there is one (see the bsiFetchQuote calls on every route into the
    # Confirm step) -- the two agree on an ordinary booking, but only the quote
    # knows what a loyalty redemption or a gift card actually did to the total.
    "      summaryHasServicesAmount: s.bookingQuote "
    "? (s.bookingQuote.services_amount > 0) : (bsiSvcTotal > 0),\n"
    "      summaryServicesAmount: '₹' + Math.round(s.bookingQuote "
    "? s.bookingQuote.services_amount : bsiSvcTotal).toLocaleString('en-IN'),\n"
    "      summaryMembershipLabel: s.hasActiveMembership "
    "? (s.membershipTierName + ' Membership (−' + s.membershipDiscountPercent + '%)') : '',\n"
    "      summaryMembershipDiscountLabel: s.hasActiveMembership "
    "? ('−₹' + Math.round(bsiSvcTotal * (s.membershipDiscountPercent || 0) / 100)) : '',\n"
    "      isMember: s.isMember, toggleMember: this.toggleMember,\n"
    # ── PHASE 6 DEV: everything the payment panel renders ────────────────
    # Every figure below is read out of s.bookingQuote, which is whatever
    # /salon/api/booking_quote last returned -- the balance, the conversion,
    # the minimum, the cap, what a redemption is worth and the payable total
    # are all the server's answers. Nothing here works out a discount: the
    # formatting is the only thing done client-side, and with no quote yet the
    # panel shows the booking's own estimate and no redemption at all.
    # ── Confirm screen (redesigned) ──────────────────────────────────────
    # Every money figure below is read out of s.bookingQuote -- whatever
    # /salon/api/booking_quote last returned -- so the balance, what a
    # redemption is worth, the membership discount and the payable total are
    # all the server's answers; formatting is the only thing done here. The
    # markup only ever reads plain identifiers (ternaries inside {{ }} render
    # blank in this runtime), so every state the screen can be in is decided
    # here as its own boolean.
    "      ...(() => {\n"
    "        const q = s.bookingQuote || null;\n"
    "        const L = (q && q.loyalty) || {};\n"
    "        const G = (q && q.gift_card) || {};\n"
    "        const F = (q && q.features) || { loyalty: true, gift_card: true, membership: true };\n"
    "        const cur = (q && q.currency) || '₹';\n"
    "        const money = (n) => cur + Math.round(n || 0).toLocaleString('en-IN');\n"
    "        const pts = (n) => Math.round(n || 0).toLocaleString('en-IN');\n"
    "        const loggedIn = q ? !!q.logged_in : !!s.userLoggedIn;\n"
    "        const memberOn = q ? !!(q.membership && q.membership.active) : !!s.hasActiveMembership;\n"
    "        const memberPct = q ? Math.round((q.membership && q.membership.percent) || 0) "
    ": (s.membershipDiscountPercent || 0);\n"
    "        const subtotal = q ? (q.subtotal || 0) : basePrice;\n"
    "        const rewardAmt = (q && q.reward_amount) || 0;\n"
    "        const loyaltyAmt = L.points ? (L.amount || 0) : 0;\n"
    "        const giftAmt = G.code ? (G.applied || 0) : 0;\n"
    "        const RW = (q && q.reward) || {};\n"
    "        const SP = (q && q.service_points) || { lines: [] };\n"
    "        const RWS = (q && q.rewards) || [];\n"
    "        const rwAmt = RW.id ? (RW.amount || 0) : 0;\n"
    "        const spAmt = SP.points ? (SP.amount || 0) : 0;\n"
    "        const rwApplied = RWS.find((r) => r.applied) || null;\n"
    "        const rwFreeSvc = rwApplied && rwApplied.type === 'service' ? rwApplied.service_id : null;\n"
    "        const ptsLeft = (L.remaining != null) ? L.remaining : (L.balance || 0);\n"
    "        const payable = q ? (q.amount_total || 0) : finalPrice;\n"
    # The membership discount is whatever the subtotal lost that no other
    # redemption accounts for -- read off the server's own figures rather
    # than re-derived from the percentage (which is applied after points).
    "        const memberAmt = memberOn ? Math.max(0, subtotal - rewardAmt - rwAmt - spAmt - loyaltyAmt - giftAmt - payable) : 0;\n"
    "        const savings = memberAmt + rewardAmt + rwAmt + spAmt + loyaltyAmt + giftAmt;\n"
    "        const svcLines = s.bookingPackageId\n"
    "          ? [{ name: s.bookingPackageName || 'Package', meta: ((s.bookingServiceIds || []).length "
    "+ ' services bundled'), price: money(s.bookingPackagePrice || 0) }]\n"
    "          : bsiSvcIds.map((id) => { const rec = bsiSvcAll.find((x) => x.id === id); "
    "return rec ? { name: rec.name, meta: (rwFreeSvc === rec.id ? ('Free with your ' + pts(rwApplied.cost) + '-pt reward') : (rec.duration || '')), price: (rwFreeSvc === rec.id ? 'FREE' : money(rec.price_amount || 0)) } : null; })"
    ".filter(Boolean);\n"
    "        if (!svcLines.length) { svcLines.push({ name: s.rewardServiceName || 'Signature look', "
    "meta: '', price: money(basePrice) }); }\n"
    "        const lines = [{ label: 'Services', value: money(q ? q.services_amount : bsiSvcTotal), cls: '' }];\n"
    "        const extras = q ? Math.max(0, (q.subtotal || 0) - (q.services_amount || 0)) : ritualAddonCost;\n"
    "        if (extras > 0.5) { lines.push({ label: 'Artist & add-ons', value: money(extras), cls: '' }); }\n"
    "        if (memberAmt > 0.5) { lines.push({ label: ((q && q.membership.tier) || s.membershipTierName || 'Member') "
    "+ ' · ' + memberPct + '% off', value: '−' + money(memberAmt), cls: 'is-save' }); }\n"
    "        if (rewardAmt) { lines.push({ label: 'Reward redeemed', value: '−' + money(rewardAmt), cls: 'is-save' }); }\n"
    "        if (rwAmt) { lines.push({ label: 'Reward · ' + (RW.benefit || RW.name), value: '−' + money(rwAmt), cls: 'is-save' }); }\n"
    "        if (spAmt) { lines.push({ label: 'Service points · ' + pts(SP.points) + ' pts', value: '−' + money(spAmt), cls: 'is-save' }); }\n"
    "        if (loyaltyAmt) { lines.push({ label: pts(L.points) + ' loyalty points', value: '−' + money(loyaltyAmt), cls: 'is-save' }); }\n"
    "        if (giftAmt) { lines.push({ label: 'Gift card · ' + G.code, value: '−' + money(giftAmt), cls: 'is-save' }); }\n"
    "        const tierFrom = (TIERS_DATA || []).map((t) => t.monthly || 0).filter((n) => n > 0);\n"
    "        const first = (s.userName || '').trim().split(/\\s+/)[0] || '';\n"
    "        const loyaltyApplied = !!L.points;\n"
    "        const giftApplied = !!G.code;\n"
    "        const busy = !!s.bookingSubmitting || !!s.bookingQuoteLoading;\n"
    "        const editTo = (n) => () => this.bsiGoStep(n);\n"
    "        return {\n"
    "          cfTitle: first ? ('Almost there, ' + first) : 'Review & confirm',\n"
    "          cfServiceLines: svcLines,\n"
    "          cfServiceCount: svcLines.length === 1 ? '1 service' : (svcLines.length + ' services'),\n"
    "          cfEditBranch: editTo(2), cfEditService: editTo(3), cfEditChair: editTo(4), cfEditTime: editTo(5),\n"
    "          cfLines: lines,\n"
    "          cfHasSavings: savings > 0.5,\n"
    "          cfSavings: 'You save ' + money(savings),\n"
    "          summaryPayable: money(payable),\n"
    "          cfLoading: !!s.bookingQuoteLoading,\n"
    "          bsiQuoteError: s.bookingQuoteError || '',\n"
    "          cfConfirmDisabled: busy,\n"
    "          cfConfirmState: busy ? 'is-busy' : '',\n"
    # ── perks: guest ──
    "          cfGuest: !loggedIn && (F.loyalty || F.gift_card),\n"
    "          cfGuestText: (F.loyalty && F.gift_card) ? 'Sign in to automatically apply your loyalty points and gift card.'\n"
    "            : (F.loyalty ? 'Sign in to automatically apply your loyalty points.' "
    ": 'Sign in to automatically apply your gift card.'),\n"
    # ── perks: membership ──
    "          cfShowMember: F.membership !== false,\n"
    "          cfMemberOn: memberOn,\n"
    "          cfMemberOff: !memberOn,\n"
    "          cfMemberTitle: memberOn ? (((q && q.membership.tier) || s.membershipTierName || 'Member') + ' membership') : 'Membership',\n"
    "          cfMemberSub: memberOn ? (memberPct + '% off applied automatically') "
    ": ('Members save on every visit' + (tierFrom.length ? (' · plans from ' + money(Math.min.apply(null, tierFrom)) + '/mo') : '')),\n"
    "          cfMemberAmount: memberAmt > 0.5 ? ('−' + money(memberAmt)) : 'Active',\n"
    # ── perks: loyalty ──
    "          cfShowLoyalty: !!F.loyalty && loggedIn,\n"
    "          cfLoyaltyOn: loyaltyApplied,\n"
    "          cfLoyaltyReady: !loyaltyApplied && !!L.redeemable,\n"
    "          cfLoyaltyLocked: !loyaltyApplied && !L.redeemable,\n"
    "          cfLoyaltyEditable: loyaltyApplied || !!L.redeemable,\n"
    "          cfLoyaltyBalance: pts(ptsLeft) + ' pts' + (ptsLeft !== (L.balance || 0) ? (' left of ' + pts(L.balance)) : '') "
    "+ ' · worth ' + money(ptsLeft * (L.point_value || 1)),\n"
    "          cfLoyaltyAppliedTitle: pts(L.points) + ' points applied',\n"
    "          cfLoyaltyAmount: '−' + money(loyaltyAmt),\n"
    "          cfLoyaltyInput: L.points ? String(L.points) : '',\n"
    "          cfLoyaltyUseMax: 'Use ' + pts(L.max_points) + ' pts · save ' + money((L.max_points || 0) * (L.point_value || 1)),\n"
    "          cfLoyaltyCanMax: !!L.redeemable && (L.points || 0) !== (L.max_points || 0),\n"
    "          cfLoyaltyRule: 'Min ' + pts(L.min_points) + ' pts · 1 pt = ' + money(L.point_value || 1) "
    "+ ' · up to ' + Math.round(L.max_percent || 0) + '% of a booking',\n"
    "          cfLoyaltyLockedTitle: (L.balance || 0) > 0 ? ('You have ' + pts(ptsLeft) + ' pts' + (ptsLeft !== (L.balance || 0) ? ' left' : '')) : 'Activate Enrich Rewards',\n"
    "          cfLoyaltyLockedSub: ((L.balance || 0) > 0 && ptsLeft <= 0) ? 'All your points are already used on this booking.'\n"
    "            : (L.balance || 0) > 0\n"
    "            ? ('Redeeming starts at ' + pts(L.min_points) + ' pts on this booking — '\n"
    "               + pts(Math.max(0, (L.min_points || 0) - (L.balance || 0))) + ' more to go.')\n"
    "            : 'Earn points on every visit and pay with them next time.',\n"
    "          bsiLoyaltyError: L.error || '',\n"
    "          cfHasRewards: !!F.loyalty && loggedIn && RWS.length > 0,\n"
    "          cfRewardCls: 'cf-perk cf-rwbox ' + (RW.id ? 'is-on' : (RWS.some((r) => r.affordable) ? 'is-ready' : 'is-suggest')),\n"
    "          cfRewardTitle: RW.id ? ('Reward · ' + (RW.benefit || RW.name)) : 'Loyalty rewards',\n"
    "          cfRewardTag: RW.id ? 'Applied' : (RWS.some((r) => r.affordable) ? 'Available' : 'Keep earning'),\n"
    "          cfRewardTagCls: 'cf-tag ' + (RW.id ? 'cf-tag--on' : (RWS.some((r) => r.affordable) ? 'cf-tag--ready' : 'cf-tag--off')),\n"
    "          cfRewardSub: RW.id ? (pts(RW.points) + ' pts used · ' + RW.name) "
    ": ('You have ' + pts(L.balance) + ' pts — use a reward on this booking'),\n"
    "          cfRewardAmount: RW.id ? ('−' + money(rwAmt)) : '',\n"
    "          cfRewards: RWS.map((r) => ({ name: r.name, benefit: r.benefit || r.name, cost: pts(r.cost) + ' pts',\n"
    "            cls: 'cf-rw' + (r.applied ? ' is-applied' : (r.affordable ? '' : ' is-locked')),\n"
    "            action: r.applied ? 'Remove' : (r.affordable ? (RW.id ? 'Switch' : 'Use') : (pts(Math.max(0, r.cost - (L.balance || 0))) + ' more pts')),\n"
    "            disabled: !r.applied && !r.affordable,\n"
    "            onClick: r.applied ? this.bsiClearReward : (r.affordable ? (() => this.bsiUseReward(r)) : null) })),\n"
    "          bsiRewardError: RW.error || '',\n"
    "          cfHasSvcPoints: !!F.loyalty && loggedIn && (SP.lines || []).length > 0,\n"
    "          cfSvcPtsCls: 'cf-perk ' + (SP.points ? 'is-on' : 'is-ready'),\n"
    "          cfSvcPtsTag: SP.points ? 'Applied' : (SP.enabled ? 'Not enough points' : 'Not used'),\n"
    "          cfSvcPtsTagCls: 'cf-tag ' + (SP.points ? 'cf-tag--on' : 'cf-tag--off'),\n"
    "          cfSvcPtsLines: (SP.lines || []).map((l) => ({ label: l.name + ' · ' + pts(l.points) + ' pts = ' + money(l.amount) + ' off'\n"
    "            + (l.applied ? '' : (SP.enabled ? ' · needs ' + pts(l.points) + ' pts' : '')) })),\n"
    "          cfSvcPtsToggle: SP.enabled ? 'Don’t use service points' : 'Use service points',\n"
    "          cfSvcPtsAmount: SP.points ? ('−' + money(spAmt)) : '',\n"
    "          bsiToggleServicePoints: this.bsiToggleServicePoints,\n"
    # ── perks: gift card ──
    "          cfShowGift: !!F.gift_card && loggedIn,\n"
    "          cfGiftOn: giftApplied,\n"
    "          cfGiftReady: !giftApplied && !!G.own_code,\n"
    "          cfGiftLocked: !giftApplied && !G.own_code,\n"
    "          cfGiftNotApplied: !giftApplied,\n"
    "          cfGiftAppliedTitle: 'Gift card ' + (G.code || ''),\n"
    "          cfGiftAmount: '−' + money(giftAmt),\n"
    "          cfGiftLeft: ((G.balance || 0) - giftAmt) > 0.5 ? (money((G.balance || 0) - giftAmt) + ' stays on your card') "
    ": 'Card fully used on this booking',\n"
    "          cfGiftReadyTitle: 'Your card ' + (G.own_code || ''),\n"
    "          cfGiftReadySub: money(G.own_balance) + ' available · apply it to this booking',\n"
    "          bsiGiftError: G.error || '',\n"
    "          bsiApplyLoyalty: this.bsiApplyLoyalty, bsiClearLoyalty: this.bsiClearLoyalty, "
    "bsiUseMaxPoints: this.bsiUseMaxPoints,\n"
    "          bsiApplyGiftCard: this.bsiApplyGiftCard, bsiClearGiftCard: this.bsiClearGiftCard, "
    "bsiApplyOwnGiftCard: this.bsiApplyOwnGiftCard, bsiGoRewards: this.bsiGoRewards,\n"
    "        };\n"
    "      })(),"
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
# for the Booking Summary and confirmed-ticket screens (see CONFIRM_SCREEN_DST
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

# The original Booking Summary card's opening half -- see CONFIRM_SCREEN_DST.
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
# ...and its closing half (total, button, the card's closing tag).
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
# --- Booking Confirm screen -- redesigned from scratch ---------------------
# Replaces the original "Booking Summary" card whole: SUMMARY_GRID_SRC is its
# opening half (card + City/Branch/Chair/Time grid) and SUMMARY_TOTAL_SRC its
# closing half (total + button + the card's closing tag); the membership
# checkbox between them is already gone (MEMBER_CHECKBOX_DST). The first
# half becomes the complete new screen and the second is simply removed, so
# the markup stays balanced.
#
# Layout: the appointment (slot, branch, chair, stylist, services -- each with
# an Edit link straight back to its step) and "Perks & payment" on the left;
# a sticky price receipt with the Confirm button on the right, stacking on
# phones. Styling lives in bsi_booking_confirm.css (linked by NAV_STYLE_DST).
#
# Perks: membership, loyalty points and gift card are each in one of three
# states -- applied (green), available but not applied (gold, one click to
# apply), or not activated (dashed, with a suggestion to activate). Loyalty
# points and the customer's own gift card are applied automatically by the
# quote (auto_loyalty / auto_gift_card) until the customer changes them;
# the Settings toggles that hide these features hide their rows too (the
# quote's `features`), and a signed-out visitor sees one sign-in prompt.
# Every flag and figure is computed in STEP_SUMMARY_COMPUTE_DST.
def _cf_icon(path, cls=''):
    return (
        '<svg sc-camel-view-box="0 0 24 24" style="fill:none;stroke:currentColor;'
        'stroke-width:1.8;stroke-linecap:round;stroke-linejoin:round;"'
        + (' class="%s"' % cls if cls else '') + '><path d="%s"></path></svg>' % path
    )


_CF_ICON_CLOCK = _cf_icon('M12 7v5l3 2M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0z')
_CF_ICON_PIN = _cf_icon('M12 21s-7-6.2-7-11.5A7 7 0 0 1 19 9.5C19 14.8 12 21 12 21zM12 12a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5z')
_CF_ICON_CHAIR = _cf_icon('M7 11V5a2 2 0 0 1 2-2h6a2 2 0 0 1 2 2v6M5 11h14v4H5zM7 15v6M17 15v6M12 15v6')
_CF_ICON_USER = _cf_icon('M20 21a8 8 0 0 0-16 0M12 13a5 5 0 1 0 0-10 5 5 0 0 0 0 10z')
_CF_ICON_CROWN = _cf_icon('M3 8l4.5 4L12 5l4.5 7L21 8l-2 11H5L3 8z')
_CF_ICON_STAR = _cf_icon('M12 3l2.8 5.7 6.2.9-4.5 4.4 1.1 6.2L12 17.3l-5.6 2.9 1.1-6.2L3 9.6l6.2-.9L12 3z')
_CF_ICON_GIFT = _cf_icon('M20 12v9H4v-9M2 7h20v5H2zM12 21V7M12 7H8a2.5 2.5 0 1 1 0-5c3 0 4 5 4 5zM12 7h4a2.5 2.5 0 1 0 0-5c-3 0-4 5-4 5z')
_CF_ICON_LOCK = _cf_icon('M6 11h12v10H6zM8.5 11V7.5a3.5 3.5 0 0 1 7 0V11')
_CF_ICON_CHECK = _cf_icon('M20 6L9 17l-5-5')

CONFIRM_SCREEN_DST = (
    '<div class="cf">\n'
    '            <div class="cf-head">\n'
    '              <div class="cf-eyebrow">Step 6 of 6 · Final check</div>\n'
    '              <h2 class="cf-title">{{ cfTitle }}</h2>\n'
    '              <p class="cf-lead">Your perks are applied automatically. Give everything a last look, '
    'then confirm — nothing is charged online.</p>\n'
    '            </div>\n'
    '            <div class="cf-grid">\n'
    '              <div class="cf-main">\n'
    # ── appointment ──
    '                <section class="cf-card cf-appt">\n'
    '                  <div class="cf-slot">\n'
    '                    <div class="cf-slot-main">\n'
    '                      <span class="cf-slot-ico">' + _CF_ICON_CLOCK + '</span>\n'
    '                      <div style="min-width:0;">\n'
    '                        <div class="cf-slot-label">YOUR SLOT</div>\n'
    '                        <div class="cf-slot-time">{{ summaryTime }}</div>\n'
    '                        <div class="cf-slot-place">{{ summaryStore }} · {{ summaryCity }}</div>\n'
    '                      </div>\n'
    '                    </div>\n'
    '                    <button class="cf-edit" sc-camel-on-click="{{ cfEditTime }}">Change time</button>\n'
    '                  </div>\n'
    '                  <div class="cf-facts">\n'
    '                    <div class="cf-fact">\n'
    '                      <span class="cf-fact-ico">' + _CF_ICON_PIN + '</span>\n'
    '                      <div style="min-width:0;"><div class="cf-fact-k">Branch</div>'
    '<div class="cf-fact-v">{{ summaryStore }}</div>'
    '<button class="cf-edit" sc-camel-on-click="{{ cfEditBranch }}">Change</button></div>\n'
    '                    </div>\n'
    '                    <div class="cf-fact">\n'
    '                      <span class="cf-fact-ico">' + _CF_ICON_CHAIR + '</span>\n'
    '                      <div style="min-width:0;"><div class="cf-fact-k">Chair</div>'
    '<div class="cf-fact-v">{{ summaryChair }}</div>'
    '<button class="cf-edit" sc-camel-on-click="{{ cfEditChair }}">Change</button></div>\n'
    '                    </div>\n'
    '                    <div class="cf-fact">\n'
    '                      <span class="cf-fact-ico">' + _CF_ICON_USER + '</span>\n'
    '                      <div style="min-width:0;"><div class="cf-fact-k">Artist</div>'
    '<div class="cf-fact-v">{{ ticketStylistName }}</div></div>\n'
    '                    </div>\n'
    '                  </div>\n'
    '                  <div class="cf-services">\n'
    '                    <div class="cf-sec-head"><span>{{ cfServiceCount }}</span>'
    '<button class="cf-edit" sc-camel-on-click="{{ cfEditService }}">Edit services</button></div>\n'
    '                    <sc-for list="{{ cfServiceLines }}" as="sv" hint-placeholder-count="2">\n'
    '                      <div class="cf-svc">\n'
    '                        <span class="cf-svc-dot"></span>\n'
    '                        <div class="cf-svc-body"><div class="cf-svc-name">{{ sv.name }}</div>'
    '<div class="cf-svc-meta">{{ sv.meta }}</div></div>\n'
    '                        <div class="cf-svc-price">{{ sv.price }}</div>\n'
    '                      </div>\n'
    '                    </sc-for>\n'
    '                  </div>\n'
    '                </section>\n'
    # ── perks & payment ──
    '                <section class="cf-card">\n'
    '                  <div class="cf-sec-head"><span>Perks &amp; payment</span>'
    '<sc-if value="{{ cfLoading }}" hint-placeholder-val="{{ false }}">'
    '<span class="cf-updating">Updating</span></sc-if></div>\n'
    '                  <div class="cf-perks-list">\n'
    # guest
    '                  <sc-if value="{{ cfGuest }}" hint-placeholder-val="{{ false }}">\n'
    '                    <div class="cf-guest">\n'
    '                      <span class="cf-guest-ico">' + _CF_ICON_LOCK + '</span>\n'
    '                      <div class="cf-guest-body"><div class="cf-guest-title">Have rewards with us?</div>'
    '<div class="cf-guest-sub">{{ cfGuestText }}</div></div>\n'
    '                      <a class="cf-btn cf-btn--gold" href="/web/login?redirect=/salon/booking">Sign in</a>\n'
    '                    </div>\n'
    '                  </sc-if>\n'
    # membership
    '                  <sc-if value="{{ cfShowMember }}" hint-placeholder-val="{{ true }}">\n'
    '                    <sc-if value="{{ cfMemberOn }}" hint-placeholder-val="{{ false }}">\n'
    '                      <div class="cf-perk is-on">\n'
    '                        <span class="cf-perk-ico">' + _CF_ICON_CROWN + '</span>\n'
    '                        <div><div class="cf-perk-title">{{ cfMemberTitle }}'
    '<span class="cf-tag cf-tag--on">Applied</span></div>'
    '<div class="cf-perk-sub">{{ cfMemberSub }}</div></div>\n'
    '                        <div class="cf-perk-amt">{{ cfMemberAmount }}</div>\n'
    '                      </div>\n'
    '                    </sc-if>\n'
    '                    <sc-if value="{{ cfMemberOff }}" hint-placeholder-val="{{ true }}">\n'
    '                      <div class="cf-perk is-suggest">\n'
    '                        <span class="cf-perk-ico">' + _CF_ICON_CROWN + '</span>\n'
    '                        <div><div class="cf-perk-title">Membership'
    '<span class="cf-tag cf-tag--off">Not active</span></div>'
    '<div class="cf-perk-sub">{{ cfMemberSub }}</div>'
    '<div class="cf-perk-actions"><button class="cf-btn cf-btn--ghost" '
    'sc-camel-on-click="{{ bsiGoRewards }}">Explore plans →</button></div></div>\n'
    '                      </div>\n'
    '                    </sc-if>\n'
    '                  </sc-if>\n'
    # loyalty
    '                  <sc-if value="{{ cfShowLoyalty }}" hint-placeholder-val="{{ false }}">\n'
    '                    <sc-if value="{{ cfHasRewards }}" hint-placeholder-val="{{ false }}">\n'
    '                      <div class="{{ cfRewardCls }}">\n'
    '                        <span class="cf-perk-ico">' + _CF_ICON_GIFT + '</span>\n'
    '                        <div style="min-width:0;flex:1;"><div class="cf-perk-title">{{ cfRewardTitle }}'
    '<span class="{{ cfRewardTagCls }}">{{ cfRewardTag }}</span></div>'
    '<div class="cf-perk-sub">{{ cfRewardSub }}</div>\n'
    '                          <div class="cf-rw-list">\n'
    '                            <sc-for list="{{ cfRewards }}" as="rw" hint-placeholder-count="3">\n'
    '                              <button type="button" class="{{ rw.cls }}" sc-camel-on-click="{{ rw.onClick }}" disabled="{{ rw.disabled }}">'
    '<span class="cf-rw-pts">{{ rw.cost }}</span>'
    '<span class="cf-rw-body"><b>{{ rw.benefit }}</b><small>{{ rw.name }}</small></span>'
    '<span class="cf-rw-act">{{ rw.action }}</span></button>\n'
    '                            </sc-for>\n'
    '                          </div>\n'
    '                        </div>\n'
    '                        <div class="cf-perk-amt">{{ cfRewardAmount }}</div>\n'
    '                      </div>\n'
    '                    </sc-if>\n'
    '                    <sc-if value="{{ bsiRewardError }}" hint-placeholder-val="{{ false }}">\n'
    '                      <div class="cf-alert">{{ bsiRewardError }}</div>\n'
    '                    </sc-if>\n'
    '                    <sc-if value="{{ cfHasSvcPoints }}" hint-placeholder-val="{{ false }}">\n'
    '                      <div class="{{ cfSvcPtsCls }}">\n'
    '                        <span class="cf-perk-ico">' + _CF_ICON_STAR + '</span>\n'
    '                        <div><div class="cf-perk-title">Service points'
    '<span class="{{ cfSvcPtsTagCls }}">{{ cfSvcPtsTag }}</span></div>'
    '<sc-for list="{{ cfSvcPtsLines }}" as="sp" hint-placeholder-count="1"><div class="cf-perk-sub">{{ sp.label }}</div></sc-for>'
    '<div class="cf-perk-actions"><button class="cf-btn cf-btn--link" '
    'sc-camel-on-click="{{ bsiToggleServicePoints }}">{{ cfSvcPtsToggle }}</button></div></div>\n'
    '                        <div class="cf-perk-amt">{{ cfSvcPtsAmount }}</div>\n'
    '                      </div>\n'
    '                    </sc-if>\n'
    '                    <sc-if value="{{ cfLoyaltyOn }}" hint-placeholder-val="{{ false }}">\n'
    '                      <div class="cf-perk is-on">\n'
    '                        <span class="cf-perk-ico">' + _CF_ICON_STAR + '</span>\n'
    '                        <div><div class="cf-perk-title">{{ cfLoyaltyAppliedTitle }}'
    '<span class="cf-tag cf-tag--on">Applied</span></div>'
    '<div class="cf-perk-sub">Balance {{ cfLoyaltyBalance }}</div>'
    '<div class="cf-perk-note">{{ cfLoyaltyRule }}</div>\n'
    '                          <div class="cf-field"><input id="bsiLoyaltyPoints" type="number" min="0" step="1" '
    'value="{{ cfLoyaltyInput }}" placeholder="Points to use">'
    '<button class="cf-btn cf-btn--ghost" sc-camel-on-click="{{ bsiApplyLoyalty }}">Update</button></div>\n'
    '                          <div class="cf-perk-actions">'
    '<sc-if value="{{ cfLoyaltyCanMax }}" hint-placeholder-val="{{ false }}">'
    '<button class="cf-btn cf-btn--gold" sc-camel-on-click="{{ bsiUseMaxPoints }}">{{ cfLoyaltyUseMax }}</button></sc-if>'
    '<button class="cf-btn cf-btn--link" sc-camel-on-click="{{ bsiClearLoyalty }}">Don’t use points</button></div>\n'
    '                        </div>\n'
    '                        <div class="cf-perk-amt">{{ cfLoyaltyAmount }}</div>\n'
    '                      </div>\n'
    '                    </sc-if>\n'
    '                    <sc-if value="{{ cfLoyaltyReady }}" hint-placeholder-val="{{ false }}">\n'
    '                      <div class="cf-perk is-ready">\n'
    '                        <span class="cf-perk-ico">' + _CF_ICON_STAR + '</span>\n'
    '                        <div><div class="cf-perk-title">Loyalty points'
    '<span class="cf-tag cf-tag--ready">Available</span></div>'
    '<div class="cf-perk-sub">{{ cfLoyaltyBalance }}</div>'
    '<div class="cf-perk-note">{{ cfLoyaltyRule }}</div>\n'
    '                          <div class="cf-perk-actions"><button class="cf-btn cf-btn--gold" '
    'sc-camel-on-click="{{ bsiUseMaxPoints }}">{{ cfLoyaltyUseMax }}</button></div>\n'
    '                          <div class="cf-field"><input id="bsiLoyaltyPoints" type="number" min="0" step="1" '
    'placeholder="Or enter points to use">'
    '<button class="cf-btn cf-btn--ghost" sc-camel-on-click="{{ bsiApplyLoyalty }}">Apply</button></div>\n'
    '                        </div>\n'
    '                      </div>\n'
    '                    </sc-if>\n'
    '                    <sc-if value="{{ cfLoyaltyLocked }}" hint-placeholder-val="{{ false }}">\n'
    '                      <div class="cf-perk is-suggest">\n'
    '                        <span class="cf-perk-ico">' + _CF_ICON_STAR + '</span>\n'
    '                        <div><div class="cf-perk-title">{{ cfLoyaltyLockedTitle }}'
    '<span class="cf-tag cf-tag--off">Not active</span></div>'
    '<div class="cf-perk-sub">{{ cfLoyaltyLockedSub }}</div>'
    '<div class="cf-perk-actions"><button class="cf-btn cf-btn--ghost" '
    'sc-camel-on-click="{{ bsiGoRewards }}">How rewards work →</button></div></div>\n'
    '                      </div>\n'
    '                    </sc-if>\n'
    '                    <sc-if value="{{ bsiLoyaltyError }}" hint-placeholder-val="{{ false }}">\n'
    '                      <div class="cf-alert">{{ bsiLoyaltyError }}</div>\n'
    '                    </sc-if>\n'
    '                  </sc-if>\n'
    # gift card
    '                  <sc-if value="{{ cfShowGift }}" hint-placeholder-val="{{ false }}">\n'
    '                    <sc-if value="{{ cfGiftOn }}" hint-placeholder-val="{{ false }}">\n'
    '                      <div class="cf-perk is-on">\n'
    '                        <span class="cf-perk-ico">' + _CF_ICON_GIFT + '</span>\n'
    '                        <div><div class="cf-perk-title">{{ cfGiftAppliedTitle }}'
    '<span class="cf-tag cf-tag--on">Applied</span></div>'
    '<div class="cf-perk-sub">{{ cfGiftLeft }}</div>'
    '<div class="cf-perk-actions"><button class="cf-btn cf-btn--link" '
    'sc-camel-on-click="{{ bsiClearGiftCard }}">Don’t use this card</button></div></div>\n'
    '                        <div class="cf-perk-amt">{{ cfGiftAmount }}</div>\n'
    '                      </div>\n'
    '                    </sc-if>\n'
    '                    <sc-if value="{{ cfGiftReady }}" hint-placeholder-val="{{ false }}">\n'
    '                      <div class="cf-perk is-ready">\n'
    '                        <span class="cf-perk-ico">' + _CF_ICON_GIFT + '</span>\n'
    '                        <div><div class="cf-perk-title">{{ cfGiftReadyTitle }}'
    '<span class="cf-tag cf-tag--ready">Available</span></div>'
    '<div class="cf-perk-sub">{{ cfGiftReadySub }}</div>'
    '<div class="cf-perk-actions"><button class="cf-btn cf-btn--gold" '
    'sc-camel-on-click="{{ bsiApplyOwnGiftCard }}">Apply my card</button></div></div>\n'
    '                      </div>\n'
    '                    </sc-if>\n'
    '                    <sc-if value="{{ cfGiftLocked }}" hint-placeholder-val="{{ false }}">\n'
    '                      <div class="cf-perk is-suggest">\n'
    '                        <span class="cf-perk-ico">' + _CF_ICON_GIFT + '</span>\n'
    '                        <div><div class="cf-perk-title">Gift card'
    '<span class="cf-tag cf-tag--off">Not active</span></div>'
    '<div class="cf-perk-sub">No gift card on your account yet. Treat yourself or someone special '
    '— it pays for bookings like this one.</div>'
    '<div class="cf-perk-actions"><button class="cf-btn cf-btn--ghost" '
    'sc-camel-on-click="{{ bsiGoRewards }}">Get a gift card →</button></div></div>\n'
    '                      </div>\n'
    '                    </sc-if>\n'
    '                    <sc-if value="{{ cfGiftNotApplied }}" hint-placeholder-val="{{ false }}">\n'
    '                      <div class="cf-field-label">Received a gift card code?</div>\n'
    '                      <div class="cf-field cf-field-code" style="margin-top:8px;">'
    '<input id="bsiGiftCardCode" type="text" placeholder="ENR-GIFT-XXXXXX">'
    '<button class="cf-btn cf-btn--ghost" sc-camel-on-click="{{ bsiApplyGiftCard }}">Apply</button></div>\n'
    '                    </sc-if>\n'
    '                    <sc-if value="{{ bsiGiftError }}" hint-placeholder-val="{{ false }}">\n'
    '                      <div class="cf-alert">{{ bsiGiftError }}</div>\n'
    '                    </sc-if>\n'
    '                  </sc-if>\n'
    '                  </div>\n'
    '                </section>\n'
    '              </div>\n'
    # ── receipt ──
    '              <aside class="cf-side">\n'
    '                <div class="cf-receipt">\n'
    '                  <div class="cf-receipt-head"><span class="cf-brand">enrich</span>'
    '<span class="cf-receipt-k">Price details</span></div>\n'
    '                  <sc-for list="{{ cfLines }}" as="ln" hint-placeholder-count="2">\n'
    '                    <div class="cf-line {{ ln.cls }}"><span>{{ ln.label }}</span><span>{{ ln.value }}</span></div>\n'
    '                  </sc-for>\n'
    '                  <div class="cf-rule"></div>\n'
    '                  <div class="cf-total">\n'
    '                    <div class="cf-total-k">To pay<small>at the salon, after your service</small></div>\n'
    '                    <div class="cf-total-v">{{ summaryPayable }}</div>\n'
    '                  </div>\n'
    '                  <sc-if value="{{ cfHasSavings }}" hint-placeholder-val="{{ false }}">\n'
    '                    <div class="cf-save">' + _CF_ICON_CHECK.replace('<svg ', '<svg width="14" height="14" ') + '{{ cfSavings }}</div>\n'
    '                  </sc-if>\n'
    '                  <sc-if value="{{ bsiQuoteError }}" hint-placeholder-val="{{ false }}">\n'
    '                    <div class="cf-alert cf-alert--warn">{{ bsiQuoteError }}</div>\n'
    '                  </sc-if>\n'
    '                  <sc-if value="{{ bookingError }}" hint-placeholder-val="{{ false }}">\n'
    '                    <div class="cf-alert">{{ bookingError }}</div>\n'
    '                  </sc-if>\n'
    '                  <button class="cf-confirm {{ cfConfirmState }}" sc-camel-on-click="{{ confirmBooking }}" '
    'disabled="{{ cfConfirmDisabled }}">{{ confirmBtnLabel }}</button>\n'
    '                  <ul class="cf-assure">\n'
    '                    <li>' + _CF_ICON_CHECK + '<span>No payment online — settle the balance at the salon</span></li>\n'
    '                    <li>' + _CF_ICON_CHECK + '<span>Free reschedule up to 4 hours before your slot</span></li>\n'
    '                    <li>' + _CF_ICON_CHECK + '<span>Points, rewards and gift card are only used once you confirm</span></li>\n'
    '                  </ul>\n'
    '                </div>\n'
    '              </aside>\n'
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
    "rewardServiceId: null, rewardServiceName: null, bookingRewardId: null, "
    "bookingRewardAddedSvc: null, bookingUseServicePoints: true, bookingStylist: null, "
    "bookingLookLength: null, bookingLookShadeIndex: null, bookingLookFinish: null, "
    "bookingLookPrice: null, ritual: [], isMember: false, "
    "bookingLoyaltyPoints: 0, bookingGiftCode: '', bookingQuote: null, "
    "bookingLoyaltyAuto: true, bookingGiftAuto: true, "
    "bookingQuoteError: '', bookingQuoteLoading: false });"
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
    "rewardServiceId: null, rewardServiceName: null, bookingRewardId: null, "
    "bookingRewardAddedSvc: null, bookingUseServicePoints: true, bookingStylist: null, "
    "bookingLookLength: null, bookingLookShadeIndex: null, bookingLookFinish: null, "
    "bookingLookPrice: null, ritual: [], isMember: false, "
    "bookingLoyaltyPoints: 0, bookingGiftCode: '', bookingQuote: null, "
    "bookingLoyaltyAuto: true, bookingGiftAuto: true, "
    "bookingQuoteError: '', bookingQuoteLoading: false }"
)

# --- Confirmed ticket -- show what was actually payable --------------------
# The appointment pass shown after a booking is confirmed carried the same
# client-side `finalPrice` estimate the Booking Summary used to, so a booking
# that redeemed loyalty points or a gift card printed a ticket for the
# un-discounted figure -- the one number the customer keeps. summaryPayable is
# the server's own quoted total (see STEP_SUMMARY_COMPUTE_DST), and falls back
# to exactly the old estimate when there is no quote, so an ordinary booking
# still prints what it always did.
TICKET_TOTAL_SRC = (
    '<div style="font-family:\'Playfair Display\',serif;font-size:22px;color:#fdf3ea;'
    'line-height:1;">\u20b9{{ finalPrice }}</div>'
)
TICKET_TOTAL_DST = (
    '<div style="font-family:\'Playfair Display\',serif;font-size:22px;color:#fdf3ea;'
    'line-height:1;">{{ summaryPayable }}</div>'
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
TICKET_STYLIST_NAME_DST = "ticketStylistName: st ? st.name : 'Any Available Artist',"

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
    # navbar account controls -- Dashboard (admins only), account, log in/out
    # PHASE 6 DEV -- navbar hover dropdowns + Account dropdown
    ('nav row overflow (allow submenus to escape)', NAV_ROW_OVERFLOW_SRC, NAV_ROW_OVERFLOW_DST),
    ('nav dropdown styles', NAV_STYLE_SRC, NAV_STYLE_DST),
    ('nav items children compute', NAV_ITEMS_COMPUTE_SRC, NAV_ITEMS_COMPUTE_DST),
    ('nav items dropdown markup', NAV_LIST_MARKUP_SRC, NAV_LIST_MARKUP_DST),
    ('nav account controls', NAV_ACCOUNT_SRC, NAV_ACCOUNT_DST),
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
    ('contact form city/branch pickers', CONTACT_PICKERS_SRC, CONTACT_PICKERS_DST),
    ('contact form error line', CONTACT_ERROR_SRC, CONTACT_ERROR_DST),
    ('contact form send label', CONTACT_SEND_LABEL_SRC, CONTACT_SEND_LABEL_DST),
    ('contact form sent note', CONTACT_SENT_NOTE_SRC, CONTACT_SENT_NOTE_DST),
    ('contact form render', CONTACT_FORM_RENDER_SRC, CONTACT_FORM_RENDER_DST),
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
    ('consultation book-this-plan button', CONSULT_BOOK_SRC, CONSULT_BOOK_DST),
    ('consultation book-this-plan render', CONSULT_BOOK_RENDER_SRC, CONSULT_BOOK_RENDER_DST),
    ('consultation book-this-plan method', CONSULT_BOOK_METHOD_SRC, CONSULT_BOOK_METHOD_DST),
    # membership discount -- gated on a real active subscription
    ('membership status fetch', MOUNT_SRC, MOUNT_DST),
    ('membership status default state', MEMBER_STATE_SRC, MEMBER_STATE_DST),
    ('membership discount price', MEMBER_PRICE_SRC, MEMBER_PRICE_DST),
    ('membership discount checkbox', MEMBER_CHECKBOX_SRC, MEMBER_CHECKBOX_DST),
    # gift card purchase -- cart/checkout, same pattern as membership CTA
    ('gift card buy method', GIFT_METHOD_SRC, GIFT_METHOD_DST),
    ('gift card buy state', GIFT_STATE_SRC, GIFT_STATE_DST),
    ('gift card body removed (status only)', GIFT_BODY_SRC, GIFT_BODY_DST),
    ('gift card status panel', GIFT_STATUS_SRC, GIFT_STATUS_DST),
    ('wallet tier bar + reward cards removed', WALLET_BODY_SRC, WALLET_BODY_DST),
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
    ('contact city tile inner content + branch list', CONTACT_TILE_INNER_SRC, CONTACT_TILE_INNER_DST),
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
    ('booking Confirm screen (redesign)', SUMMARY_GRID_SRC, CONFIRM_SCREEN_DST),
    ('booking Confirm screen -- original total/button removed', SUMMARY_TOTAL_SRC, ''),
    # a fresh booking must not inherit the previous one's selections
    ('reset booking -- book another', RESET_BOOKING_SRC, RESET_BOOKING_DST),
    ('reset booking -- book now nav', GOBOOKINGNAV_RESET_SRC, GOBOOKINGNAV_RESET_DST),
    # Active Membership Plan banner (Membership page)
    ('membership perk rows expose', MEMBERSHIP_PERKS_EXPOSE_SRC, MEMBERSHIP_PERKS_EXPOSE_DST),
    ('membership active plan banner', MEMBERSHIP_BANNER_SRC, MEMBERSHIP_BANNER_DST),
    # confirmed ticket -- show the real booked stylist, not the homepage carousel's
    ('ticket payable total', TICKET_TOTAL_SRC, TICKET_TOTAL_DST),
    ('ticket stylist real selection', TICKET_STYLIST_SRC, TICKET_STYLIST_DST),
    ('ticket stylist name fallback', TICKET_STYLIST_NAME_SRC, TICKET_STYLIST_NAME_DST),
    ('ticket stylist photo real selection', TICKET_STYLIST_PHOTO_SRC, TICKET_STYLIST_PHOTO_DST),
    # Refer Friend promo card removed -- the feature's backend discount logic is
    # preserved for any existing bookings that used a referral code, but the
    # "Give ₹500, Get ₹500" card on the Packages page is no longer shown.
    ('refer friend promo card removed',
     '\n      <div style="background:#ffffff;border:1.5px dashed rgba(20,17,17,.25);'
     'border-radius:22px;padding:26px 30px;display:flex;justify-content:space-between;'
     'align-items:center;flex-wrap:wrap;gap:16px;">\n        <div>\n'
     '          <div style="font-family:\'Manrope\',sans-serif;font-weight:700;'
     'font-size:18px;color:#161213;margin-bottom:4px;">Give ₹500, Get ₹500</div>\n'
     '          <div style="font-size:13px;color:#767676;">Share your code — '
     'you both get credit on their first visit.</div>\n        </div>\n'
     '        <button sc-camel-on-click="{{ copyReferral }}" '
     'style="background:#e8283f;color:#161213;border:none;padding:13px 22px;'
     'border-radius:4px;font-weight:700;cursor:pointer;">{{ referralBtnLabel }}</button>\n'
     '      </div>',
     ''),
)
