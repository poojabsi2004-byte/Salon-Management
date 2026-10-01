# -*- coding: utf-8 -*-
"""Visual redesign layer for the served Enrich page.

Presentation only: every data binding ({{ ... }}), sc-for / sc-if block and
click handler the design already had is carried over unchanged, so the backend
behaviour behind each section is untouched.

Three kinds of patch, applied by BsiSalonWeb._build_site:
  * PATCHES        exact-string swaps inside the app template;
  * BLOCK_PATCHES  replace a whole element (located by an anchor inside it);
  * OUTER_PATCHES  exact-string swaps on the outer bundler shell, i.e. the
                   first-paint HTML that exists before the app has unpacked.
"""

LOGO_FONT_URL = '/bsi_salon_web/static/src/fonts/playfair-display-latin.woff2'

# --- Single loader ------------------------------------------------------------
# Was three loaders in a row: the bundler shell splash, a JS preloader, and the
# app's own 3.4s curtain intro (showIntro). Now one: the brand wordmark comes in
# first, then the spinner. The same markup is painted twice -- as the bundler
# shell (first paint) and again inside the app template, because the bundler
# swaps the whole <html> element once it has unpacked. The second copy reads
# the shell's start time (window survives the swap) and offsets its animations
# by the elapsed time, so the two copies read as one continuous animation. The
# logo is set in the site's own Playfair Display file, preloaded on the shell,
# so the wordmark is pixel-identical on both copies. (!important where the
# bundler's own #__bundler_thumbnail id rules would otherwise win on the shell.)

_HEART_SVG = (
    '<svg class="bsi-ld__heart" viewBox="0 0 24 22" aria-hidden="true">'
    '<path fill="#e8283f" d="M12 21.5 10.3 20C4.2 14.5.5 11.2.5 7 .5 3.7 3.1 1 6.5 1c1.9 0 '
    '3.8.9 5 2.4C12.7 1.9 14.6 1 16.5 1c3.4 0 6 2.7 6 6 0 4.2-3.7 7.5-9.8 13L12 21.5z"/></svg>'
)

_LOADER_CSS = (
    "@font-face{font-family:'BsiLogo';src:url('" + LOGO_FONT_URL + "') format('woff2');"
    "font-weight:500;font-style:normal;font-display:block;}"
    ".bsi-ld{position:fixed;inset:0;z-index:2147483000;display:flex;align-items:center;"
    "justify-content:center;background:#ffffff!important;z-index:2147483000!important;--bsi-el:0s;"
    "transition:opacity .55s ease,visibility .55s ease;}"
    ".bsi-ld.is-out{opacity:0;visibility:hidden;pointer-events:none;}"
    ".bsi-ld__stack{display:flex;flex-direction:column;align-items:center;}"
    ".bsi-ld__mark{position:relative;font-family:'BsiLogo','Playfair Display',Georgia,serif;"
    "font-weight:500;font-size:60px;line-height:1;color:#161213;letter-spacing:.5px;"
    "animation:bsiLdIn .9s cubic-bezier(.2,.8,.2,1) calc(.05s - var(--bsi-el)) both;}"
    ".bsi-ld__i{position:relative;display:inline-block;}"
    ".bsi-ld__heart{position:absolute;left:50%;top:-.36em;width:.3em!important;height:.27em!important;"
    "margin-left:-.13em;animation:bsiLdHeart .7s cubic-bezier(.34,1.56,.64,1) "
    "calc(.6s - var(--bsi-el)) both;}"
    ".bsi-ld__tag{margin-top:8px;font:italic 400 14px/1.2 -apple-system,BlinkMacSystemFont,"
    "'Segoe UI',Roboto,Arial,sans-serif;color:#767676;letter-spacing:.3px;"
    "animation:bsiLdFade .6s ease calc(.9s - var(--bsi-el)) both;}"
    ".bsi-ld__spin{margin-top:34px;width:28px;height:28px;border-radius:50%;"
    "border:2px solid rgba(20,17,17,.08);border-top-color:#e8283f;"
    "animation:bsiLdFade .5s ease calc(1.15s - var(--bsi-el)) both,"
    "bsiLdSpin .8s linear calc(0s - var(--bsi-el)) infinite;}"
    "@keyframes bsiLdIn{from{opacity:0;transform:translateY(14px) scale(.96);"
    "letter-spacing:8px;filter:blur(6px)}to{opacity:1;transform:none;letter-spacing:.5px;"
    "filter:blur(0)}}"
    "@keyframes bsiLdHeart{0%{opacity:0;transform:translateY(-.4em) scale(.4)}"
    "60%{opacity:1;transform:translateY(0) scale(1.25)}100%{opacity:1;transform:none}}"
    "@keyframes bsiLdFade{from{opacity:0}to{opacity:1}}"
    "@keyframes bsiLdSpin{to{transform:rotate(360deg)}}"
    "@media (prefers-reduced-motion:reduce){.bsi-ld *{animation-duration:.01ms!important;"
    "animation-delay:0s!important;}}"
    "@media (max-width:520px){.bsi-ld__mark{font-size:46px}}"
)


def _loader(element_id):
    return (
        '<div id="%s" class="bsi-ld" role="status" aria-label="Loading Enrich">'
        '<style>%s</style>'
        '<div class="bsi-ld__stack">'
        '<div class="bsi-ld__mark">enr<span class="bsi-ld__i">i%s</span>ch</div>'
        '<div class="bsi-ld__tag">love begins with you</div>'
        '<div class="bsi-ld__spin"></div>'
        '</div></div>'
    ) % (element_id, _LOADER_CSS, _HEART_SVG)


# Runs as the first script of the app document (the bundler re-creates the
# template's scripts in order right after swapping it in, before first paint).
# Keeps the loader up until the app has hydrated (#dc-root replaces the raw
# x-dc template -- the raw template itself must never be seen, it still shows
# placeholder content) and the redesign stylesheet is in, with a floor so the wordmark-then-spinner sequence always
# completes, and a ceiling so it can never get stuck.
_LOADER_SCRIPT = (
    '<script>(function(){'
    'var el=document.getElementById("bsi-loader");if(!el)return;'
    'var t0=window.__bsiLoaderT0||Date.now();'
    'el.style.setProperty("--bsi-el",((Date.now()-t0)/1000)+"s");'
    'var root=document.documentElement;root.style.overflow="hidden";'
    'var MIN=1.8,MAX=25,done=false;'
    'function ready(){var app=document.getElementById("dc-root");'
    'if(!app||!app.querySelector(".bsi-navi"))return false;'
    'var l=document.querySelector(\'link[href*="bsi_site_redesign"]\');'
    'return !l||!!l.sheet;}'
    'function out(){if(done)return;done=true;el.classList.add("is-out");'
    'root.style.overflow="";'
    'setTimeout(function(){if(el.parentNode)el.parentNode.removeChild(el);},650);}'
    '(function poll(){var s=(Date.now()-t0)/1000;'
    'if((s>=MIN&&ready())||s>=MAX){out();return;}setTimeout(poll,80);})();'
    '})();</script>'
)

# --- Outer bundler shell ------------------------------------------------------
BUNDLER_HEAD_SRC = '<title>Bundled Page</title>'
BUNDLER_HEAD_DST = (
    '<title>Enrich Beauty</title>\n'
    '  <link rel="preload" href="' + LOGO_FONT_URL + '" as="font" type="font/woff2" crossorigin>'
)

BUNDLER_THUMB_SRC = (
    '<div id="__bundler_thumbnail"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200">'
    '<rect width="200" height="200" fill="#161213"></rect><g fill="none">'
    '<path d="M93.8 113.6 L93 2.4 C101 38.4 107 78 110.6 115.8 Z" fill="#fdf3ea"></path>'
    '<path d="M106.2 113.6 L107 2.4 C99 38.4 93 78 89.4 115.8 Z" fill="#c9c2c3"></path>'
    '<path d="M107 115 C120.2 124.6 129 137 130.8 144.8" stroke="#fdf3ea" stroke-width="9" stroke-linecap="round"></path>'
    '<path d="M93 115 C79.8 124.6 71 137 69.2 144.8" stroke="#c9c2c3" stroke-width="9" stroke-linecap="round"></path>'
    '<circle cx="132.6" cy="158" r="13.6" stroke="#e8283f" stroke-width="8.4"></circle>'
    '<circle cx="67.4" cy="158" r="13.6" stroke="#e8283f" stroke-width="8.4"></circle>'
    '<circle cx="100" cy="100" r="9.6" fill="#e8283f"></circle></g></svg></div>'
)
# The bundler removes #__bundler_thumbnail along with the rest of the old
# document, so the id is kept for it to find.
BUNDLER_THUMB_DST = (
    _loader('__bundler_thumbnail')
    + '<script>window.__bsiLoaderT0=Date.now();</script>'
)

BUNDLER_LOADING_SRC = '<div id="__bundler_loading">Unpacking...</div>'
BUNDLER_LOADING_DST = '<div id="__bundler_loading" style="display:none"></div>'

OUTER_PATCHES = (
    ('loader: shell title + logo font preload', BUNDLER_HEAD_SRC, BUNDLER_HEAD_DST),
    ('loader: bundler splash -> brand loader', BUNDLER_THUMB_SRC, BUNDLER_THUMB_DST),
    ('loader: bundler "Unpacking..." pill hidden', BUNDLER_LOADING_SRC, BUNDLER_LOADING_DST),
)

# --- App template patches -----------------------------------------------------
APP_HEAD_SRC = '<html><head>\n<meta charset="utf-8">'
APP_HEAD_DST = '<html><head>\n' + _LOADER_SCRIPT + '\n<meta charset="utf-8">'

APP_BODY_SRC = '<body>\n<x-dc>'
APP_BODY_DST = '<body>\n' + _loader('bsi-loader') + '\n<x-dc>'

# The app's own curtain/scissors intro was the third loader in the sequence.
INTRO_OFF_SRC = 'showIntro: true,'
INTRO_OFF_DST = (
    'showIntro: false, bookingDate: null, bsiDateNudge: 0, '
    'bsiCalMonth: null, bsiCalYear: null,'
)

# --- Booking wizard: pick a date before a time ----------------------------------
# Was: step 5 only asked for a time, so every website lead reached the salon with
# no date at all. Now the step opens on a full month calendar (prev/next month
# navigation, past days disabled); the chosen day is sent with the booking as
# bsi_preferred_date. Every time slot always reads as open -- the site no longer
# calls out to check or display existing bookings for a day/chair/stylist (see
# bsiSlotOff below); main.py's own booking endpoint likewise no longer lets
# the backend's slot-capacity check reject a website booking that collides
# with an existing one on the same chair/slot/day (bsi_skip_slot_capacity_check).

_DATE_METHODS = (
    "bsiIsoDay = (offset) => { const d = new Date(); d.setHours(0, 0, 0, 0); "
    "d.setDate(d.getDate() + offset); const p = (n) => (n < 10 ? '0' : '') + n; "
    "return d.getFullYear() + '-' + p(d.getMonth() + 1) + '-' + p(d.getDate()); };\n"
    # Fixed names: toLocaleDateString's short month varies by browser ("Sept").
    "  bsiDow = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];\n"
    "  bsiMon = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];\n"
    "  bsiDateLabel = (iso) => { if (!iso) return ''; const d = new Date(iso + 'T00:00:00'); "
    "return this.bsiDow[d.getDay()] + ' ' + d.getDate() + ' ' + this.bsiMon[d.getMonth()]; };\n"
    "  bsiMonFull = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', "
    "'September', 'October', 'November', 'December'];\n"
    # Every slot on every open day is always bookable from the website: no
    # "time already passed today" guard and no conflict/availability check
    # against other bookings (the user asked for no booked/validation state on
    # the site). bsiSlotPassed stays as a no-op so its callers (slot cards,
    # dial, exact-time picker, date change) keep working unchanged; the only
    # thing that still holds a slot back is "no date picked yet".
    "  bsiSlotPassed = (iso, t) => false;\n"
    "  bsiSlotOff = (t) => !this.state.bookingDate;\n"
    "  bsiSelectDate = (iso) => {\n"
    "    this.setState((s) => {\n"
    "      const out = { bookingDate: iso };\n"
    "      if (s.selectedTime && this.bsiSlotPassed(iso, s.selectedTime)) { out.selectedTime = null; }\n"
    "      return out;\n"
    "    });\n"
    "  };\n"
    "  bsiCalPrev = () => {\n"
    "    const s = this.state;\n"
    "    const mi = (s.bsiCalMonth == null ? new Date().getMonth() : s.bsiCalMonth);\n"
    "    const yr = (s.bsiCalYear == null ? new Date().getFullYear() : s.bsiCalYear);\n"
    "    let m = mi - 1, y = yr;\n"
    "    if (m < 0) { m = 11; y -= 1; }\n"
    "    this.setState({ bsiCalMonth: m, bsiCalYear: y });\n"
    "  };\n"
    "  bsiCalNext = () => {\n"
    "    const s = this.state;\n"
    "    const mi = (s.bsiCalMonth == null ? new Date().getMonth() : s.bsiCalMonth);\n"
    "    const yr = (s.bsiCalYear == null ? new Date().getFullYear() : s.bsiCalYear);\n"
    "    let m = mi + 1, y = yr;\n"
    "    if (m > 11) { m = 0; y += 1; }\n"
    "    this.setState({ bsiCalMonth: m, bsiCalYear: y });\n"
    "  };\n"
    # Custom time: native <input type=time> yields "HH:MM" (24h); convert to
    # "H:MM AM/PM" display label so it matches the slot card format seen
    # elsewhere in the wizard and on the Confirm screen.
    "  bsiCustomTimeChange = (e) => {\n"
    "    const v = e && e.target ? e.target.value : '';\n"
    "    if (!v) {\n"
    "      if (this._bsiCustomSelected) { this.setState({ selectedTime: null }); "
    "this._bsiCustomSelected = false; }\n"
    "      return;\n"
    "    }\n"
    "    const parts = v.split(':');\n"
    "    if (parts.length < 2) return;\n"
    "    let h = parseInt(parts[0], 10), min = parseInt(parts[1], 10);\n"
    "    if (isNaN(h) || isNaN(min)) return;\n"
    "    const ampm = h >= 12 ? 'PM' : 'AM';\n"
    "    const h12 = h % 12 || 12;\n"
    "    const label = h12 + ':' + (min < 10 ? '0' : '') + min + ' ' + ampm;\n"
    "    this._bsiCustomSelected = true;\n"
    "    this.selectTime(label);\n"
    "  };\n"
    # PHASE 8 DEV -- exact-time picker (hour + minute chips), see bsiXt below.
    "  bsiXtPick = (h, m) => {\n"
    "    const label = ((h % 12) || 12) + ':' + (m < 10 ? '0' : '') + m + ' ' + (h >= 12 ? 'PM' : 'AM');\n"
    "    this._bsiCustomSelected = true;\n"
    "    this.setState({ bsiXtHour: h, bsiXtOpen: true, bsiXtLabel: label });\n"
    "    this.selectTime(label);\n"
    "  };\n"
    "  bsiXtClear = () => {\n"
    "    const t = this.state.selectedTime;\n"
    "    const custom = !!t && (TIME_SLOTS.indexOf(t) === -1 || t === this.state.bsiXtLabel);\n"
    "    this._bsiCustomSelected = false;\n"
    "    this.setState(custom ? { selectedTime: null, bsiXtHour: null, bsiXtOpen: false, bsiXtLabel: null } : { bsiXtHour: null, bsiXtOpen: false, bsiXtLabel: null });\n"
    "  };\n  "
)

# Methods ride in front of timeNext (already renumbered by enrich_patches).
TIMENEXT_SRC = (
    "timeNext = () => { if (this.state.selectedTime) { this.setState((s) => "
    "({ booking: { ...s.booking, step: 6 }, bookingMaxStep: Math.max(s.bookingMaxStep || 1, 6) })); "
    "this.bsiFetchQuote(); } };"
)
# A time is optional (the salon confirms one with the customer); only the day
# itself is still needed to continue.
TIMENEXT_DST = _DATE_METHODS + (
    "timeNext = () => { if (this.state.bookingDate) { this.setState((s) => "
    "({ booking: { ...s.booking, step: 6 }, bookingMaxStep: Math.max(s.bookingMaxStep || 1, 6) })); "
    "this.bsiFetchQuote(); } };"
)

SELECTTIME_SRC = "  selectTime = (t) => {\n"
SELECTTIME_DST = (
    "  selectTime = (t) => {\n"
    "    if (!this.state.bookingDate) { this.setState({ bsiDateNudge: Date.now() }); return; }\n"
    "    if (this.bsiSlotOff(t)) return;\n"
)

SELECTTIME_NEXT_SRC = "selectTimeAndNext = (t) => { this.setState((s) => "
SELECTTIME_NEXT_DST = (
    "selectTimeAndNext = (t) => { if (this.bsiSlotOff(t)) { this.selectTime(t); return; } "
    "this.setState((s) => "
)

BOOKING_PARAMS_SRC = "      location_id: store ? store.id : null, slot_label: s.selectedTime || null,\n"
BOOKING_PARAMS_DST = (
    "      location_id: store ? store.id : null, slot_label: s.selectedTime || null,\n"
    "      preferred_date: s.bookingDate || null,\n"
)

# Slot cards always read as open -- no conflict/availability check is made
# against other bookings and no "time passed" state; only "no date yet"
# marks a card unselectable.
SLOT_AVAIL_SRC = "      const avail = slotSeats[t] || 'Available';\n"
SLOT_AVAIL_DST = (
    "      const off = this.bsiSlotOff(t);\n"
    "      const avail = !s.bookingDate ? 'Pick a date first' : 'Available';\n"
)
SLOT_TONE_SRC = (
    "const seatTone = (a) => a === 'Wide open' ? '#1f8a4c' : (/Filling|Last/.test(a) ? '#e8283f' : '#a8760f');"
)
SLOT_TONE_DST = (
    "const seatTone = (a) => (a === 'Wide open' || a === 'Available') ? '#1f8a4c' "
    ": (/passed|Pick a date/.test(a) ? '#b3a8ab' "
    ": (/Filling|Last/.test(a) ? '#e8283f' : '#a8760f'));"
)
SLOT_CARD_SRC = (
    "        cardShadow: sel ? '0 16px 32px -16px rgba(232,40,63,.9)' : '0 4px 14px -12px rgba(20,17,17,.6)',\n"
    "      };\n"
    "    });\n"
    "    const periodSlots"
)
SLOT_CARD_DST = (
    "        cardShadow: sel ? '0 16px 32px -16px rgba(232,40,63,.9)' : '0 4px 14px -12px rgba(20,17,17,.6)',\n"
    "        ...(off && !sel ? { cardBg: '#f7f3f1', cardBorder: 'rgba(20,17,17,.06)', cardText: '#b3a8ab', "
    "cardShadow: 'none', chipOpacity: 0.3 } : {}),\n"
    "      };\n"
    "    });\n"
    "    const periodSlots"
)

TIME_RENDER_SRC = (
    "      timeSummaryTitle: s.selectedTime ? ('Chair held at ' + s.selectedTime) : 'No slot selected yet',\n"
    "      timeSummarySub: s.selectedTime\n"
    "        ? 'We hold your chair for 10 minutes past this time.'\n"
    "        : 'Tap a marker on the dial or a card below.',\n"
    "      timeNext: this.timeNext,\n"
    "      timeNextDisabled: !s.selectedTime,\n"
    "      timeNextBg: s.selectedTime ? wine : '#d9c3c9',"
)
TIME_RENDER_DST = (
    "      timeSummaryTitle: (s.selectedTime && s.bookingDate)\n"
    "        ? ('Chair held on ' + this.bsiDateLabel(s.bookingDate) + ' at ' + s.selectedTime)\n"
    "        : (s.bookingDate ? ('No time picked for ' + this.bsiDateLabel(s.bookingDate) + ' yet') : 'Pick a date to see open times'),\n"
    "      timeSummarySub: (s.selectedTime && s.bookingDate)\n"
    "        ? 'We hold your chair for 10 minutes past this time.'\n"
    "        : (s.bookingDate ? 'Tap a marker on the dial or a card below, or continue and the salon will confirm a time.' : 'Choose a day above first, then a time.'),\n"
    "      timeNext: this.timeNext,\n"
    "      bsiCustomTimeChange: this.bsiCustomTimeChange,\n"
    "      timeNextDisabled: !s.bookingDate,\n"
    "      timeNextBg: s.bookingDate ? wine : '#d9c3c9',\n"
    "      bsiXt: (() => {\n"
    "        // Exact-time picker: any quarter hour the salon is open, from the branch's own\n"
    "        // opening hours (last start 30 min before closing), every one of them always pickable.\n"
    "        const pad = (n) => (n < 10 ? '0' : '') + n;\n"
    "        const lbl = (h, m) => ((h % 12) || 12) + ':' + pad(m) + ' ' + (h >= 12 ? 'PM' : 'AM');\n"
    "        const toMin = (t) => { const x = String(t || '').match(/(\\d{1,2}):(\\d{2})\\s*(AM|PM)?/i); if (!x) return null;\n"
    "          let h = parseInt(x[1], 10); if (x[3]) { h = h % 12 + (/pm/i.test(x[3]) ? 12 : 0); } return h * 60 + parseInt(x[2], 10); };\n"
    "        const hrs = String((bookingStore && bookingStore.hours) || '10:00 - 20:00').match(/\\d{1,2}:\\d{2}\\s*(?:AM|PM)?/gi) || [];\n"
    "        let openM = toMin(hrs[0]); let closeM = toMin(hrs[1]);\n"
    "        if (openM == null) openM = 600;\n"
    "        if (closeM == null || closeM <= openM) closeM = 1200;\n"
    "        const lastM = closeM - 30;\n"
    "        // Custom = picked here (even if it happens to match a fixed slot) or not a slot at all.\n"
    "        const custom = !!s.selectedTime && (TIME_SLOTS.indexOf(s.selectedTime) === -1 || s.selectedTime === s.bsiXtLabel);\n"
    "        const cur = custom ? toMin(s.selectedTime) : null;\n"
    "        const selH = cur != null ? Math.floor(cur / 60) : ((s.bsiXtOpen && s.bsiXtHour != null) ? s.bsiXtHour : null);\n"
    "        const selM = cur != null ? cur % 60 : null;\n"
    "        const QUARTERS = [0, 15, 30, 45];\n"
    "        const ok = (h, m) => { const t = h * 60 + m; return !!s.bookingDate && t >= openM && t <= lastM && !this.bsiSlotPassed(s.bookingDate, lbl(h, m)); };\n"
    "        const hours = [];\n"
    "        for (let h = Math.floor(openM / 60); h * 60 <= lastM; h++) {\n"
    "          const first = QUARTERS.find((m) => ok(h, m));\n"
    "          hours.push({ key: 'h' + h, label: ((h % 12) || 12) + (h >= 12 ? ' PM' : ' AM'),\n"
    "            disabled: first === undefined, cls: 'bsi-xt__chip' + (selH === h ? ' is-on' : ''),\n"
    "            onClick: first === undefined ? (() => {}) : (() => this.bsiXtPick(h, (selM != null && ok(h, selM)) ? selM : first)) });\n"
    "        }\n"
    "        const mins = QUARTERS.map((m) => {\n"
    "          const can = selH != null && ok(selH, m);\n"
    "          return { key: 'm' + m, label: ':' + pad(m), disabled: !can,\n"
    "            cls: 'bsi-xt__chip bsi-xt__chip--min' + (custom && selM === m ? ' is-on' : ''),\n"
    "            onClick: can ? (() => this.bsiXtPick(selH, m)) : (() => {}) };\n"
    "        });\n"
    "        const open = !!s.bsiXtOpen || custom;\n"
    "        return {\n"
    "          open, custom,\n"
    "          cls: 'bsi-xt' + (open ? ' is-open' : '') + (custom ? ' has-time' : ''),\n"
    "          toggle: () => { if (!custom) this.setState({ bsiXtOpen: !open }); },\n"
    "          sub: custom ? ('Booked for exactly ' + s.selectedTime)\n"
    "            : ('Any quarter hour from ' + lbl(Math.floor(openM / 60), openM % 60) + ' to ' + lbl(Math.floor(lastM / 60), lastM % 60)),\n"
    "          hours, mins,\n"
    "          value: custom ? s.selectedTime : '--:--',\n"
    "          hint: !s.bookingDate ? 'Choose a date above first.' : (custom ? 'Your chair is held for this exact time.' : 'Pick an hour, then fine-tune the minutes.'),\n"
    "          clear: this.bsiXtClear,\n"
    "        };\n"
    "      })(),\n"
    "      bsiCal: (() => {\n"
    "        // Bookings open up to 90 days ahead -- the same horizon the booking API\n"
    "        // enforces (see BsiSalonWeb._BSI_BOOKING_HORIZON_DAYS) -- so a day the\n"
    "        // server would refuse is never offered here in the first place.\n"
    "        const HORIZON = 90;\n"
    "        const mi = (s.bsiCalMonth == null ? new Date().getMonth() : s.bsiCalMonth);\n"
    "        const yr = (s.bsiCalYear == null ? new Date().getFullYear() : s.bsiCalYear);\n"
    "        const today = new Date(); today.setHours(0, 0, 0, 0);\n"
    "        const todayIso = this.bsiIsoDay(0);\n"
    "        const lastIso = this.bsiIsoDay(HORIZON);\n"
    "        const last = new Date(lastIso + 'T00:00:00');\n"
    "        const canPrev = new Date(yr, mi, 1) > new Date(today.getFullYear(), today.getMonth(), 1);\n"
    "        const canNext = new Date(yr, mi + 1, 1) <= last;\n"
    "        const startOffset = new Date(yr, mi, 1).getDay();\n"
    "        const daysInMonth = new Date(yr, mi + 1, 0).getDate();\n"
    "        const total = Math.ceil((startOffset + daysInMonth) / 7) * 7;\n"
    "        const p = (n) => (n < 10 ? '0' : '') + n;\n"
    "        const longFmt = { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' };\n"
    "        const cells = Array.from({ length: total }, (_, i) => {\n"
    "          const dayNum = i - startOffset + 1;\n"
    "          if (dayNum < 1 || dayNum > daysInMonth) return { blank: true, key: 'b' + mi + '_' + i };\n"
    "          const iso = yr + '-' + p(mi + 1) + '-' + p(dayNum);\n"
    "          const isPast = iso < todayIso;\n"
    "          const isOut = iso > lastIso;\n"
    "          const isToday = iso === todayIso;\n"
    "          const isSel = s.bookingDate === iso;\n"
    "          const dow = i % 7;\n"
    "          const isWeekend = dow === 0 || dow === 6;\n"
    "          const off = isPast || isOut;\n"
    "          const label = new Date(iso + 'T00:00:00').toLocaleDateString('en-GB', longFmt);\n"
    "          return {\n"
    "            key: iso, day: String(dayNum), off: off,\n"
    "            cls: 'bsi-cal__cell' + (isToday ? ' is-today' : '') + (isSel ? ' is-sel' : '') "
    "+ (isPast ? ' is-past' : '') + (isOut ? ' is-out' : '') + ((isWeekend && !off && !isSel) ? ' is-weekend' : ''),\n"
    "            onClick: off ? (() => {}) : (() => this.bsiSelectDate(iso)),\n"
    "            aria: label + (isToday ? ', today' : '') + (isPast ? ', unavailable' : '') "
    "+ (isOut ? ', not open for booking yet' : '') + (isSel ? ', selected' : ''),\n"
    "            animStyle: '--bsi-cd:' + (i * 0.022).toFixed(3) + 's',\n"
    "          };\n"
    "        });\n"
    "        // Quick picks: today, tomorrow, the coming Saturday and next Monday.\n"
    "        const offsetOf = (d) => Math.round((d - today) / 86400000);\n"
    "        const nextDow = (dow, minGap) => { const d = new Date(today); d.setDate(d.getDate() + minGap); "
    "while (d.getDay() !== dow) d.setDate(d.getDate() + 1); return d; };\n"
    "        const picks = [\n"
    "          { label: 'Today', offset: 0 },\n"
    "          { label: 'Tomorrow', offset: 1 },\n"
    "          { label: 'This weekend', offset: offsetOf(nextDow(6, 2)) },\n"
    "          { label: 'Next week', offset: offsetOf(nextDow(1, 2)) },\n"
    "        ];\n"
    "        const quick = picks.map((q) => {\n"
    "          const iso = this.bsiIsoDay(q.offset);\n"
    "          const d = new Date(iso + 'T00:00:00');\n"
    "          const disabled = q.offset > HORIZON;\n"
    "          return {\n"
    "            key: q.label, label: q.label,\n"
    "            sub: this.bsiDow[d.getDay()] + ' ' + d.getDate() + ' ' + this.bsiMon[d.getMonth()],\n"
    "            disabled: disabled,\n"
    "            cls: 'bsi-cal__pick' + (s.bookingDate === iso ? ' is-on' : ''),\n"
    "            onClick: disabled ? (() => {}) : (() => { this.bsiSelectDate(iso); "
    "this.setState({ bsiCalMonth: d.getMonth(), bsiCalYear: d.getFullYear() }); }),\n"
    "          };\n"
    "        });\n"
    "        const onThisMonth = yr === today.getFullYear() && mi === today.getMonth();\n"
    "        return {\n"
    "          title: this.bsiMonFull[mi] + ' ' + yr,\n"
    "          monthKey: 'm' + yr + '_' + mi,\n"
    "          prevCls: 'bsi-cal__arrow' + (canPrev ? '' : ' is-disabled'),\n"
    "          prevClick: canPrev ? this.bsiCalPrev : (() => {}),\n"
    "          nextCls: 'bsi-cal__arrow' + (canNext ? '' : ' is-disabled'),\n"
    "          nextClick: canNext ? this.bsiCalNext : (() => {}),\n"
    "          showToday: !onThisMonth,\n"
    "          todayClick: () => this.setState({ bsiCalMonth: null, bsiCalYear: null }),\n"
    "          horizonLabel: 'Open until ' + last.getDate() + ' ' + this.bsiMon[last.getMonth()],\n"
    "          quick,\n"
    "          cells,\n"
    "        };\n"
    "      })(),\n"
    "      bsiDateTitle: s.bookingDate ? new Date(s.bookingDate + 'T00:00:00').toLocaleDateString('en-GB', "
    "{ weekday: 'long', day: 'numeric', month: 'long' }) : 'When would you like to come in?',\n"
    "      bsiDateHint: s.bookingDate ? ((() => { const t = new Date(); t.setHours(0, 0, 0, 0); "
    "const n = Math.round((new Date(s.bookingDate + 'T00:00:00') - t) / 86400000); "
    "return (n === 0 ? 'Today' : n === 1 ? 'Tomorrow' : 'In ' + n + ' days') + ' · now pick a time below'; })()) "
    ": 'Choose a day to see open times',\n"
    "      bsiDateCls: 'bsi-date' + (s.bookingDate ? ' has-date' : '') "
    "+ ((s.bsiDateNudge && Date.now() - s.bsiDateNudge < 1200) ? ' is-nudge' : ''),\n"
    "      bsiSlotPickerCls: 'bsi-slots' + (s.bookingDate ? '' : ' is-locked'),"
)

SUMMARY_TIME_SRC = "summaryTime: s.selectedTime || '',\n"
SUMMARY_TIME_DST = (
    "summaryTime: s.selectedTime ? ((s.bookingDate ? this.bsiDateLabel(s.bookingDate) + ' \\u00b7 ' : '') "
    "+ s.selectedTime) : '',\n"
)

STEP5_MARKUP_SRC = (
    '<sc-if value="{{ bookingStepIs5 }}" hint-placeholder-val="{{ false }}">\n'
    '        <div style="display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:34px;align-items:center;">\n'
)
STEP5_MARKUP_DST = (
    '<sc-if value="{{ bookingStepIs5 }}" hint-placeholder-val="{{ false }}">\n'
    '        <div class="{{ bsiDateCls }}">\n'
    '          <div class="bsi-date__head">\n'
    '            <div>\n'
    '              <div class="bsi-date__step"><span>1</span>Choose a date</div>\n'
    '              <div class="bsi-date__title">{{ bsiDateTitle }}</div>\n'
    '            </div>\n'
    '            <div class="bsi-date__hint">{{ bsiDateHint }}</div>\n'
    '          </div>\n'
    '          <div class="bsi-date__body">\n'
    '          <div class="bsi-cal">\n'
    '            <div class="bsi-cal__quick">\n'
    '              <sc-for list="{{ bsiCal.quick }}" as="q" hint-placeholder-count="4">\n'
    '                <button type="button" class="{{ q.cls }}" disabled="{{ q.disabled }}" '
    'sc-camel-on-click="{{ q.onClick }}"><span>{{ q.label }}</span><small>{{ q.sub }}</small></button>\n'
    '              </sc-for>\n'
    '            </div>\n'
    '            <div class="bsi-cal__nav">\n'
    '              <button type="button" class="{{ bsiCal.prevCls }}" '
    'sc-camel-on-click="{{ bsiCal.prevClick }}" aria-label="Previous month">&#10094;</button>\n'
    '              <div class="bsi-cal__month">\n'
    '                <span>{{ bsiCal.title }}</span>\n'
    '                <sc-if value="{{ bsiCal.showToday }}" hint-placeholder-val="{{ false }}">'
    '<button type="button" class="bsi-cal__today" sc-camel-on-click="{{ bsiCal.todayClick }}">Back to today</button></sc-if>\n'
    '              </div>\n'
    '              <button type="button" class="{{ bsiCal.nextCls }}" '
    'sc-camel-on-click="{{ bsiCal.nextClick }}" aria-label="Next month">&#10095;</button>\n'
    '            </div>\n'
    '            <div class="bsi-cal__dow"><span>Sun</span><span>Mon</span><span>Tue</span>'
    '<span>Wed</span><span>Thu</span><span>Fri</span><span>Sat</span></div>\n'
    '            <div class="bsi-cal__grid">\n'
    '              <sc-for list="{{ bsiCal.cells }}" as="cc" hint-placeholder-count="35">\n'
    '                <sc-if value="{{ cc.blank }}" hint-placeholder-val="{{ false }}">'
    '<div class="bsi-cal__cell is-blank"></div></sc-if>\n'
    '                <sc-if value="{{ cc.day }}" hint-placeholder-val="{{ true }}">'
    '<button type="button" class="{{ cc.cls }}" style="{{ cc.animStyle }}" disabled="{{ cc.off }}" '
    'aria-label="{{ cc.aria }}" title="{{ cc.aria }}" sc-camel-on-click="{{ cc.onClick }}">'
    '{{ cc.day }}</button></sc-if>\n'
    '              </sc-for>\n'
    '            </div>\n'
    '            <div class="bsi-cal__legend">\n'
    '              <span><i class="is-today"></i>Today</span>\n'
    '              <span><i class="is-sel"></i>Selected</span>\n'
    '              <span><i class="is-weekend"></i>Weekend</span>\n'
    '              <span><i class="is-off"></i>Unavailable</span>\n'
    '              <span class="bsi-cal__horizon">{{ bsiCal.horizonLabel }}</span>\n'
    '            </div>\n'
    '          </div>\n'
    '          <div class="bsi-date__illus">\n'
    '            <svg class="bsi-salon-svg" viewBox="0 0 220 240" xmlns="http://www.w3.org/2000/svg">\n'
    '              <defs>\n'
    '                <linearGradient id="sdG1" x1="0" y1="0" x2="1" y2="1">'
    '<stop offset="0%" stop-color="#c9a15a"/><stop offset="100%" stop-color="#7a5c20"/></linearGradient>\n'
    '                <linearGradient id="sdG2" x1="0" y1="0" x2="1" y2="1">'
    '<stop offset="0%" stop-color="#e8283f"/><stop offset="100%" stop-color="#8a2332"/></linearGradient>\n'
    '                <radialGradient id="sdBg" cx="50%" cy="50%" r="50%">'
    '<stop offset="0%" stop-color="#1e1014"/><stop offset="100%" stop-color="#0d0a0b"/></radialGradient>\n'
    '                <radialGradient id="sdA" cx="50%" cy="50%" r="50%">'
    '<stop offset="0%" stop-color="rgba(232,40,63,.28)"/><stop offset="100%" stop-color="transparent"/></radialGradient>\n'
    '                <radialGradient id="sdB" cx="50%" cy="50%" r="50%">'
    '<stop offset="0%" stop-color="rgba(201,161,90,.18)"/><stop offset="100%" stop-color="transparent"/></radialGradient>\n'
    '              </defs>\n'
    '              <circle cx="110" cy="115" r="106" fill="rgba(20,17,17,.55)"/>\n'
    '              <circle cx="110" cy="115" r="100" fill="url(#sdBg)"/>\n'
    '              <circle cx="110" cy="115" r="100" fill="url(#sdA)" opacity=".6"/>\n'
    '              <circle cx="110" cy="115" r="100" fill="url(#sdB)" opacity=".5"/>\n'
    '              <circle cx="110" cy="115" r="100" fill="none" stroke="url(#sdG1)" stroke-width="1.5" opacity=".45"/>\n'
    '              <circle cx="110" cy="115" r="95" fill="none" stroke="rgba(201,161,90,.12)" stroke-width="1"/>\n'
    '              <rect x="105" y="180" width="10" height="20" rx="5" fill="#231519"/>\n'
    '              <ellipse cx="110" cy="202" rx="30" ry="7" fill="#1a1015"/>\n'
    '              <ellipse cx="110" cy="200" rx="26" ry="5" fill="url(#sdG1)" opacity=".28"/>\n'
    '              <rect x="63" y="128" width="18" height="22" rx="4" fill="#231519"/>\n'
    '              <rect x="139" y="128" width="18" height="22" rx="4" fill="#231519"/>\n'
    '              <rect x="61" y="148" width="22" height="7" rx="3.5" fill="url(#sdG1)" opacity=".5"/>\n'
    '              <rect x="137" y="148" width="22" height="7" rx="3.5" fill="url(#sdG1)" opacity=".5"/>\n'
    '              <rect x="78" y="112" width="64" height="55" rx="11" fill="#1e1014"/>\n'
    '              <rect x="78" y="112" width="64" height="55" rx="11" fill="none" stroke="url(#sdG1)" stroke-width="1.2" opacity=".28"/>\n'
    '              <rect x="72" y="165" width="76" height="14" rx="7" fill="url(#sdG2)" opacity=".55"/>\n'
    '              <path d="M82,167 Q88,140 110,136 Q132,140 138,167 Z" fill="#0e0b0c" opacity=".92"/>\n'
    '              <rect x="105" y="114" width="10" height="20" rx="5" fill="#c9a15a" opacity=".65"/>\n'
    '              <circle cx="110" cy="102" r="22" fill="#c9a15a" opacity=".82"/>\n'
    '              <ellipse cx="106" cy="97" rx="8" ry="6" fill="rgba(253,243,234,.1)"/>\n'
    '              <path d="M91,99 Q87,85 91,75 Q96,63 106,65 Q108,66 110,65 Q112,66 114,65 Q124,63 129,75 Q133,85 129,99" fill="#161213"/>\n'
    '              <path d="M97,96 Q93,84 97,76" stroke="rgba(201,161,90,.2)" stroke-width="1.8" fill="none" stroke-linecap="round"/>\n'
    '              <path d="M123,96 Q127,84 123,76" stroke="rgba(201,161,90,.18)" stroke-width="1.8" fill="none" stroke-linecap="round"/>\n'
    '              <g transform="translate(154,58) rotate(-20)">\n'
    '                <circle cx="0" cy="0" r="5.5" fill="url(#sdG1)"/>\n'
    '                <circle cx="0" cy="0" r="2.8" fill="#161213"/>\n'
    '                <circle cx="0" cy="0" r="1.3" fill="url(#sdG1)"/>\n'
    '                <g>\n'
    '                  <path d="M0,0 L38,9 Q44,11 43,16.5 Q42,22 35,20.5 L0,0" fill="url(#sdG1)" opacity=".9"/>\n'
    '                  <circle cx="-12" cy="-14" r="9" fill="none" stroke="url(#sdG1)" stroke-width="3" opacity=".85"/>\n'
    '                  <circle cx="-12" cy="-14" r="4" fill="url(#sdG1)" opacity=".22"/>\n'
    '                  <animateTransform attributeName="transform" type="rotate"'
    ' values="-24 0 0;24 0 0;-24 0 0" keyTimes="0;0.5;1"'
    ' calcMode="spline" keySplines="0.45 0.05 0.55 0.95;0.45 0.05 0.55 0.95"'
    ' dur="2.8s" repeatCount="indefinite"/>\n'
    '                </g>\n'
    '                <g>\n'
    '                  <path d="M0,0 L38,-9 Q44,-11 43,-16.5 Q42,-22 35,-20.5 L0,0" fill="url(#sdG1)" opacity=".9"/>\n'
    '                  <circle cx="-12" cy="14" r="9" fill="none" stroke="url(#sdG1)" stroke-width="3" opacity=".85"/>\n'
    '                  <circle cx="-12" cy="14" r="4" fill="url(#sdG1)" opacity=".22"/>\n'
    '                  <animateTransform attributeName="transform" type="rotate"'
    ' values="24 0 0;-24 0 0;24 0 0" keyTimes="0;0.5;1"'
    ' calcMode="spline" keySplines="0.45 0.05 0.55 0.95;0.45 0.05 0.55 0.95"'
    ' dur="2.8s" repeatCount="indefinite"/>\n'
    '                </g>\n'
    '              </g>\n'
    '              <g transform="translate(60,150) rotate(-18)" opacity=".45">\n'
    '                <rect x="0" y="0" width="28" height="5.5" rx="2.8" fill="url(#sdG1)"/>\n'
    '                <rect x="3" y="5.5" width="2.5" height="10" rx="1.2" fill="url(#sdG1)"/>\n'
    '                <rect x="8" y="5.5" width="2.5" height="10" rx="1.2" fill="url(#sdG1)"/>\n'
    '                <rect x="13" y="5.5" width="2.5" height="10" rx="1.2" fill="url(#sdG1)"/>\n'
    '                <rect x="18" y="5.5" width="2.5" height="10" rx="1.2" fill="url(#sdG1)"/>\n'
    '                <rect x="23" y="5.5" width="2.5" height="10" rx="1.2" fill="url(#sdG1)"/>\n'
    '              </g>\n'
    '              <circle class="sd-sp sd-sp1" cx="160" cy="79" r="2.8" fill="#c9a15a"/>\n'
    '              <circle class="sd-sp sd-sp2" cx="170" cy="54" r="2" fill="#e8283f"/>\n'
    '              <circle class="sd-sp sd-sp3" cx="148" cy="43" r="2.4" fill="#c9a15a"/>\n'
    '              <circle class="sd-sp sd-sp4" cx="178" cy="41" r="1.6" fill="rgba(253,243,234,.85)"/>\n'
    '              <circle class="sd-sp sd-sp5" cx="133" cy="51" r="2.2" fill="#c9a15a"/>\n'
    '              <circle class="sd-sp sd-sp6" cx="73" cy="67" r="1.8" fill="#e8283f"/>\n'
    '              <g class="sd-sp sd-sp7" transform="translate(163,33)">'
    '<line x1="-4" y1="0" x2="4" y2="0" stroke="#c9a15a" stroke-width="1.8" stroke-linecap="round"/>'
    '<line x1="0" y1="-4" x2="0" y2="4" stroke="#c9a15a" stroke-width="1.8" stroke-linecap="round"/>'
    '<line x1="-2.8" y1="-2.8" x2="2.8" y2="2.8" stroke="#c9a15a" stroke-width="1.1" stroke-linecap="round" opacity=".6"/>'
    '<line x1="2.8" y1="-2.8" x2="-2.8" y2="2.8" stroke="#c9a15a" stroke-width="1.1" stroke-linecap="round" opacity=".6"/>'
    '</g>\n'
    '              <g class="sd-sp sd-sp8" transform="translate(71,57)">'
    '<line x1="-3" y1="0" x2="3" y2="0" stroke="#e8283f" stroke-width="1.5" stroke-linecap="round"/>'
    '<line x1="0" y1="-3" x2="0" y2="3" stroke="#e8283f" stroke-width="1.5" stroke-linecap="round"/>'
    '</g>\n'
    '              <text x="110" y="228" text-anchor="middle" font-family="Georgia,serif" font-size="8" letter-spacing="3.5" fill="rgba(201,161,90,.42)">ENRICH</text>\n'
    '            </svg>\n'
    '          </div>\n'
    '          </div>\n'
    '          <div class="bsi-date__step bsi-date__step--time"><span>2</span>Choose a time</div>\n'
    '        </div>\n'
    '        <div style="display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:34px;align-items:center;">\n'
)
SLOT_PICKER_SRC = '          <!-- slot picker -->\n          <div>\n'
SLOT_PICKER_DST = (
    '          <!-- slot picker -->\n          <div class="{{ bsiSlotPickerCls }}">\n'
    '            <div class="bsi-slots__lock">Choose a date above to see open times</div>\n'
)

TICKET_TIME_SRC = 'letter-spacing:1.6px;color:#a79a9d;margin-bottom:4px;">TIME</div>'
TICKET_TIME_DST = 'letter-spacing:1.6px;color:#a79a9d;margin-bottom:4px;">DATE &amp; TIME</div>'

CONFIRM_EDIT_SRC = 'sc-camel-on-click="{{ cfEditTime }}">Change time</button>'
CONFIRM_EDIT_DST = 'sc-camel-on-click="{{ cfEditTime }}">Change date &amp; time</button>'

# A fresh booking (Book Another / Book Now) starts with no date picked, like
# every other selection the reset clears. Both resets end in this same text,
# so the patch is applied twice, once per reset.
RESET_DATE_SRC = "bookingQuoteError: '', bookingQuoteLoading: false });"
RESET_DATE_DST = (
    "bookingQuoteError: '', bookingQuoteLoading: false, "
    "bookingDate: null, bsiCalMonth: null, bsiCalYear: null });"
)

# --- Custom time input -------------------------------------------------------
# The slot cards only show predefined time bands; a customer who needs an
# exact minute (e.g. 10:45 AM) has no way to express that. The input appears
# below the slot cards and above the Continue button. Typing a valid HH:MM
# time (or HH:MM AM/PM) calls selectTime() with a normalised label so it
# appears in the summary and is sent to the server as slot_label the same way
# a card tap does. Clearing the field deselects the custom time if that was
# the currently selected slot.
CUSTOM_TIME_SRC = (
    '<button sc-camel-on-click="{{ timeNext }}" disabled="{{ timeNextDisabled }}" '
    'style="width:100%;background:{{ timeNextBg }};color:#fff;border:none;padding:15px;'
    'border-radius:12px;font-size:14.5px;font-weight:700;cursor:pointer;transition:transform .2s;" '
    'style-hover="transform:translateY(-2px);">Continue to Confirm →</button>'
)
CUSTOM_TIME_DST = (
    # PHASE 8 DEV -- exact-time picker replacing the bare <input type=time>: hour and
    # quarter-hour chips limited to the branch's opening hours, a live readout, Clear.
    '<div class="{{ bsiXt.cls }}">\n'
    '          <button type="button" class="bsi-xt__toggle" sc-camel-on-click="{{ bsiXt.toggle }}">\n'
    '            <span class="bsi-xt__ico" aria-hidden="true"><svg viewBox="0 0 24 24" width="20" height="20" fill="none" '
    'stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg></span>\n'
    '            <span class="bsi-xt__txt"><b>Need an exact time?</b><small>{{ bsiXt.sub }}</small></span>\n'
    '            <span class="bsi-xt__chev" aria-hidden="true"></span>\n'
    '          </button>\n'
    '          <sc-if value="{{ bsiXt.open }}" hint-placeholder-val="{{ false }}">\n'
    '            <div class="bsi-xt__panel">\n'
    '              <div class="bsi-xt__label">Hour</div>\n'
    '              <div class="bsi-xt__grid">\n'
    '                <sc-for list="{{ bsiXt.hours }}" as="h" hint-placeholder-count="10">\n'
    '                  <button type="button" class="{{ h.cls }}" disabled="{{ h.disabled }}" sc-camel-on-click="{{ h.onClick }}">{{ h.label }}</button>\n'
    '                </sc-for>\n'
    '              </div>\n'
    '              <div class="bsi-xt__label">Minutes</div>\n'
    '              <div class="bsi-xt__grid bsi-xt__grid--min">\n'
    '                <sc-for list="{{ bsiXt.mins }}" as="m" hint-placeholder-count="4">\n'
    '                  <button type="button" class="{{ m.cls }}" disabled="{{ m.disabled }}" sc-camel-on-click="{{ m.onClick }}">{{ m.label }}</button>\n'
    '                </sc-for>\n'
    '              </div>\n'
    '              <div class="bsi-xt__foot">\n'
    '                <div class="bsi-xt__readout"><span>Your time</span><b>{{ bsiXt.value }}</b></div>\n'
    '                <span class="bsi-xt__hint">{{ bsiXt.hint }}</span>\n'
    '                <sc-if value="{{ bsiXt.custom }}" hint-placeholder-val="{{ false }}">'
    '<button type="button" class="bsi-xt__clear" sc-camel-on-click="{{ bsiXt.clear }}">Clear</button></sc-if>\n'
    '              </div>\n'
    '            </div>\n'
    '          </sc-if>\n'
    '        </div>\n'
    '<button sc-camel-on-click="{{ timeNext }}" disabled="{{ timeNextDisabled }}" '
    'style="width:100%;background:{{ timeNextBg }};color:#fff;border:none;padding:15px;'
    'border-radius:12px;font-size:14.5px;font-weight:700;cursor:pointer;transition:transform .2s;" '
    'style-hover="transform:translateY(-2px);">Continue to Confirm →</button>'
)

# The Chair step's Continue button is never locked: picking a chair is optional
# (the salon seats the customer in any free chair -- see
# enrich_patches.STEP_CHAIRNEXT_DST for the handler).
CHAIR_RENDER_SRC = (
    "      chairNextDisabled: !s.selectedChairIds.length,\n"
    "      chairNextBg: s.selectedChairIds.length ? wine : '#d9c3c9',\n"
)
CHAIR_RENDER_DST = (
    "      chairNextDisabled: false,\n"
    "      chairNextBg: wine,\n"
)

DATE_PATCHES = (
    ('chair: Continue never locked', CHAIR_RENDER_SRC, CHAIR_RENDER_DST),
    ('date: cleared by Book Another', RESET_DATE_SRC, RESET_DATE_DST),
    ('date: cleared by Book Now', RESET_DATE_SRC, RESET_DATE_DST),
    ('date: methods + timeNext needs a date', TIMENEXT_SRC, TIMENEXT_DST),
    ('date: selectTime gated on date', SELECTTIME_SRC, SELECTTIME_DST),
    ('date: selectTimeAndNext gated on date', SELECTTIME_NEXT_SRC, SELECTTIME_NEXT_DST),
    ('date: sent with booking/quote', BOOKING_PARAMS_SRC, BOOKING_PARAMS_DST),
    ('date: slot availability labels', SLOT_AVAIL_SRC, SLOT_AVAIL_DST),
    ('date: slot availability tones', SLOT_TONE_SRC, SLOT_TONE_DST),
    ('date: locked slot cards', SLOT_CARD_SRC, SLOT_CARD_DST),
    ('date: time step render values', TIME_RENDER_SRC, TIME_RENDER_DST),
    ('date: summary shows date + time', SUMMARY_TIME_SRC, SUMMARY_TIME_DST),
    ('date: step 5 date strip markup', STEP5_MARKUP_SRC, STEP5_MARKUP_DST),
    ('date: slot picker lock', SLOT_PICKER_SRC, SLOT_PICKER_DST),
    ('date: ticket label', TICKET_TIME_SRC, TICKET_TIME_DST),
    ('date: confirm edit label', CONFIRM_EDIT_SRC, CONFIRM_EDIT_DST),
    ('date: custom time input before Continue', CUSTOM_TIME_SRC, CUSTOM_TIME_DST),
)



# --- Design Your Look -> booking (PHASE 8 DEV) ------------------------------
# A booking started from "Book this look" carries the look as its service: choosing
# the salon skips straight to the Chair step, the Service step (if revisited) shows
# the look instead of the service list, and Confirm lists it as a line of its own.
LOOK_BOOKING_PATCHES = (
    ('look: store skips service step', 'bookingSelectStoreAndNext = (id) => { if (this.state.booking.storeId !== id) { this._bsiLoadChairs(id); } this.setState((s) => ({ booking: { ...s.booking, storeId: id, step: 3 }, bookingMaxStep: Math.max(s.bookingMaxStep || 1, 3) })); };', 'bookingSelectStoreAndNext = (id) => { if (this.state.booking.storeId !== id) { this._bsiLoadChairs(id); } this.setState((s) => { const st = s.bookingLookLength ? 4 : 3; return { booking: { ...s.booking, storeId: id, step: st }, bookingMaxStep: Math.max(s.bookingMaxStep || 1, st) }; }); };'),
    ('look: step label', "{ n: 3, label: 'Service' }", "{ n: 3, label: s.bookingLookLength ? 'Your look' : 'Service' }"),
    ('look: service step card (open)', '<p style="font-size:14.5px;color:#767676;margin:0 0 22px;">Choose the service you would like to book.</p>\n          <div style="display:grid;grid-template-columns:1fr 280px;gap:26px;align-items:start;">', '<sc-if value="{{ bookingHasLook }}" hint-placeholder-val="{{ false }}">\n          <div class="bsi-lk">\n            <div class="bsi-lk__swatch" style="background:{{ bookingLook.hair }};"><span style="background:{{ bookingLook.light }};"></span></div>\n            <div class="bsi-lk__body">\n              <div class="bsi-lk__kicker">Your custom look &middot; designed on the site</div>\n              <div class="bsi-lk__name">{{ bookingLook.summary }}</div>\n              <div class="bsi-lk__chips">\n                <span><small>Length</small>{{ bookingLook.length }}</span>\n                <span><small>Shade</small>{{ bookingLook.shade }}</span>\n                <span><small>Finish</small>{{ bookingLook.finish }}</span>\n              </div>\n              <p class="bsi-lk__note">This look is your service &mdash; your artist gets exactly this brief. No need to pick a service again.</p>\n            </div>\n            <div class="bsi-lk__side">\n              <div class="bsi-lk__price">{{ bookingLook.price }}<small>estimated</small></div>\n              <button type="button" class="bsi-lk__go" sc-camel-on-click="{{ bookingLookNext }}">Continue to Chair &rarr;</button>\n              <button type="button" class="bsi-lk__alt" sc-camel-on-click="{{ bookingLookEdit }}">Change look</button>\n              <button type="button" class="bsi-lk__alt" sc-camel-on-click="{{ bookingLookClear }}">Book regular services instead</button>\n            </div>\n          </div>\n          </sc-if>\n          <sc-if value="{{ bookingNoLook }}" hint-placeholder-val="{{ true }}">\n<p style="font-size:14.5px;color:#767676;margin:0 0 22px;">Choose the service you would like to book.</p>\n          <div style="display:grid;grid-template-columns:1fr 280px;gap:26px;align-items:start;">'),
    ('look: service step card (close)', '>\n              </sc-for>\n            </div>\n            </sc-if>\n          </div>\n        </div>\n      </sc-if>\n\n      <sc-if value="{{ bookingStepIs4 }}"', '>\n              </sc-for>\n            </div>\n            </sc-if>\n          </div>\n          </sc-if>\n        </div>\n      </sc-if>\n\n      <sc-if value="{{ bookingStepIs4 }}"'),
    ('look: render values', '      bsiXt: (() => {\n', '      ...(() => {\n        // PHASE 8 DEV -- a booking started from Design Your Look: the look IS the\n        // service, so the Service step shows it (and store selection skips past it).\n        const L = BSI_LOOK_LENGTHS.find((x) => x.id === s.bookingLookLength) || {};\n        const SH = LOOK_SHADES[s.bookingLookShadeIndex || 0] || {};\n        const F = BSI_LOOK_FINISHES.find((x) => x.id === s.bookingLookFinish) || {};\n        const has = !!s.bookingLookLength;\n        return {\n          bookingHasLook: has, bookingNoLook: !has,\n          bookingLook: { length: L.label || \'\', shade: SH.name || \'\', finish: F.label || \'\', hair: SH.hair || \'#2a1d18\', light: SH.light || \'#453027\',\n            summary: [L.label, SH.name, F.label].filter(Boolean).join(\' \\u00b7 \'),\n            price: \'\\u20b9\' + Number(s.bookingLookPrice || 0).toLocaleString(\'en-IN\') },\n          bookingLookNext: () => this.setState((st) => ({ booking: { ...st.booking, step: 4 }, bookingMaxStep: Math.max(st.bookingMaxStep || 1, 4) })),\n          bookingLookClear: () => this.setState({ bookingLookLength: null, bookingLookShadeIndex: null, bookingLookFinish: null, bookingLookPrice: null }),\n          bookingLookEdit: () => { this.setPage(\'home\'); setTimeout(() => { const el = document.querySelector(\'[data-screen-label="Design your look"]\'); if (el) el.scrollIntoView({ behavior: \'smooth\', block: \'start\' }); }, 700); },\n        };\n      })(),\n      bsiXt: (() => {\n'),
    ('look: confirm line', "if (!svcLines.length) { svcLines.push({ name: s.rewardServiceName || 'Signature look', meta: '', price: money(basePrice) }); }", "if (s.bookingLookLength && !s.bookingPackageId) { const lkL = (BSI_LOOK_LENGTHS.find((x) => x.id === s.bookingLookLength) || {}).label; const lkS = (LOOK_SHADES[s.bookingLookShadeIndex || 0] || {}).name; const lkF = (BSI_LOOK_FINISHES.find((x) => x.id === s.bookingLookFinish) || {}).label; svcLines.unshift({ name: 'Custom look', meta: [lkL, lkS, lkF].filter(Boolean).join(' \\u00b7 '), price: money(s.bookingLookPrice || 0) }); } if (!svcLines.length) { svcLines.push({ name: s.rewardServiceName || 'Signature look', meta: '', price: money(basePrice) }); }"),
)

# --- About page from the backend (PHASE 8 DEV) --------------------------------
# The hero copy, badge and brand values come from bsi.salon.about & co. through the
# injected BSI_ABOUT const (see bsi.enrich.data._bsi_about_page, which falls back to
# the design's own copy); the stats/timeline/awards lists are swapped in main.py.
ABOUT_VALUES_DST = (
    '      <sc-if value="{{ aboutHero.hasValues }}" hint-placeholder-val="{{ true }}">\n'
    '      <div class="bsi-ab-values">\n'
    '        <div class="bsi-ab-values__kicker">WHAT WE STAND FOR</div>\n'
    '        <h2 class="bsi-ab-values__title">The Enrich way.</h2>\n'
    '        <div class="bsi-ab-values__grid">\n'
    '          <sc-for list="{{ aboutHero.values }}" as="v" hint-placeholder-count="6">\n'
    '            <div class="bsi-ab-value" style="animation-delay:{{ v.delay }}s;">\n'
    '              <span class="bsi-ab-value__ico">{{ v.icon }}</span>\n'
    '              <div class="bsi-ab-value__t">{{ v.title }}</div>\n'
    '              <div class="bsi-ab-value__b">{{ v.body }}</div>\n'
    '            </div>\n'
    '          </sc-for>\n'
    '        </div>\n'
    '      </div>\n'
    '      </sc-if>\n'
    '\n'
)
_ABOUT_RECOGNITION = (
    '      <div style="max-width:1180px;margin:0 auto;padding:70px 48px 100px;">\n'
    '        <div style="font-size:11.5px;font-weight:700;letter-spacing:2.2px;color:#c81f36;margin-bottom:8px;">RECOGNITION</div>'
)
ABOUT_PATCHES = (
    ('about: eyebrow',
     'animation:fadeUp .8s ease-out both;">OUR STORY</div>',
     'animation:fadeUp .8s ease-out both;">{{ aboutHero.eyebrow }}</div>'),
    ('about: title',
     'Born from a love<br><em style="color:#e8283f;">of the craft.</em></h1>',
     '{{ aboutHero.title1 }}<br><em style="color:#e8283f;">{{ aboutHero.title2 }}</em></h1>'),
    ('about: story 1',
     "animation:fadeUp .9s ease-out .2s both;\">Founded in 1997 as a venture among friends with no background in the beauty industry, Enrich has grown into one of India's largest company-owned salon chains — built on trust between our artists and the guests they serve.</p>",
     'animation:fadeUp .9s ease-out .2s both;">{{ aboutHero.story1 }}</p>'),
    ('about: story 2',
     "<p style=\"font-size:16.5px;line-height:1.8;color:#454545;margin:0;animation:fadeUp .9s ease-out .3s both;\">Today we partner with global names like L'Oréal Professionnel to bring international technique to every chair, in every city we operate in.</p>",
     '<sc-if value="{{ aboutHero.hasStory2 }}" hint-placeholder-val="{{ true }}"><p style="font-size:16.5px;line-height:1.8;color:#454545;margin:0;animation:fadeUp .9s ease-out .3s both;">{{ aboutHero.story2 }}</p></sc-if>'),
    ('about: badge number',
     'color:#e8283f;">25+</div>',
     'color:#e8283f;">{{ aboutHero.badgeN }}</div>'),
    ('about: badge label',
     'margin-top:4px;">YEARS OF EXCELLENCE</div>',
     'margin-top:4px;">{{ aboutHero.badgeL }}</div>'),
    ('about: values section', _ABOUT_RECOGNITION, ABOUT_VALUES_DST + _ABOUT_RECOGNITION),
    ('home stats: prefix + text values',
     '<div data-count="{{ s.num }}" data-suffix="{{ s.suffix }}" data-dec="{{ s.dec }}"',
     '<div data-count="{{ s.num }}" data-prefix="{{ s.prefix }}" data-suffix="{{ s.suffix }}" data-dec="{{ s.dec }}"'),
    ('home stats: count-up prefix',
     "    const dec = parseInt(el.getAttribute('data-dec') || '0', 10);\n",
     "    const dec = parseInt(el.getAttribute('data-dec') || '0', 10);\n"
     "    const rawPrefix = el.getAttribute('data-prefix');\n"
     "    const prefix = (rawPrefix && rawPrefix !== 'undefined') ? rawPrefix : '';\n"
     "    if (!isFinite(target)) { el.textContent = prefix + suffix; return; }\n"),
    ('home stats: count-up text',
     "      el.textContent = (target * e).toFixed(dec) + suffix;\n",
     "      el.textContent = prefix + (target * e).toFixed(dec) + suffix;\n"),
    ('about/contact: render values', '      aboutStats: ',
     '      aboutHero: BSI_ABOUT,\n      bsiContact: BSI_CONTACT,\n      aboutStats: '),
)

# --- Loyalty wallet rewards (PHASE 9 DEV) --------------------------------------
# Each reward card says what it gives ("1 free Hair Spa") and opens a booking with
# the reward already picked -- the points are spent when that booking is confirmed.
LOYALTY_PATCHES = (
    ('loyalty: wallet reward state',
     "return { ...r, state: can ? 'Redeem now' : 'Locked',",
     "return { ...r, benefit: r.benefit || '', state: can ? 'Book with it →' : ((r.cost - (s.loyaltyPoints || 0)) + ' more pts'),"),
)

# --- Colour Lab -> booking a colour consultation --------------------------------
# "Book a colour consultation" books a consultation for exactly the plan configured
# in the Colour Lab, the same way "Book this look" books its look (see
# LOOK_BOOKING_PATCHES): goBookingFromColourLab snapshots the visitor's raw picks
# (from/to level, tone and hair-condition keys) plus labPlan()'s estimate into
# state.bookingColourLab; the booking carries NO catalogue service (it used to
# preselect the salon's "Global Hair Colour", so the lead came through with that
# ₹2,999 service instead of the consultation). Choosing the salon opens step 3
# ("Consultation"), which shows the consultation card instead of the service list
# and continues to the Chair step; Confirm lists it as its own line priced by the quote. Server-side, main.py's
# _bsi_resolve_colour_lab re-prices the four raw picks from the backend records and
# creates the per-booking consultation service (bsi_is_custom_look, category colour).
# labPlan() itself now reads its price/time table from BSI_LAB_PRICING (the Colour
# Lab config), the same figures the server prices from.
_COLOUR_LAB_BTN = (
    ' style="width:100%;background:#e8283f;color:#fff;border:none;padding:14px;border-radius:12px;'
    'font-size:13.5px;font-weight:800;cursor:pointer;box-shadow:0 14px 30px -14px rgba(232,40,63,.9);'
    'transition:transform .2s;" style-hover="transform:translateY(-2px);">Book a colour consultation</button>'
)
_SERVICE_STEP_INTRO = (
    '<sc-if value="{{ bookingNoLook }}" hint-placeholder-val="{{ true }}">\n'
    '<p style="font-size:14.5px;color:#767676;margin:0 0 22px;">Choose the service you would like to book.</p>'
)
_LAB_PRICING_SRC = (
    "    const base = goingDarker ? 2400 : 2900;\n"
    "    const price = base + Math.max(0, lift) * 420 + (sessions - 1) * 1600 + tone.toner;\n"
    "    const minutes = (goingDarker ? 90 : 110) + Math.max(0, lift) * 12 + (tone.toner ? 30 : 0);\n"
)
_LAB_PRICING_DST = (
    "    const LP = (typeof BSI_LAB_PRICING !== 'undefined' && BSI_LAB_PRICING) || {};\n"
    "    const base = goingDarker ? (LP.baseDarker || 2400) : (LP.baseLighter || 2900);\n"
    "    const price = base + Math.max(0, lift) * (LP.perLevel || 420) + (sessions - 1) * (LP.perExtraSession || 1600) + tone.toner;\n"
    "    const minutes = (goingDarker ? (LP.minutesDarker || 90) : (LP.minutesLighter || 110)) + Math.max(0, lift) * (LP.minutesPerLevel || 12) + (tone.toner ? (LP.minutesToner || 30) : 0);\n"
)
_COLOUR_LAB_CARD = (
    '<sc-if value="{{ bookingHasColourLab }}" hint-placeholder-val="{{ false }}">\n'
    '          <div class="bsi-lk">\n'
    '            <div class="bsi-lk__swatch" style="background:linear-gradient(135deg,{{ bookingColourLab.fromTone }} 0%,'
    '{{ bookingColourLab.fromTone }} 46%,{{ bookingColourLab.toTone }} 54%,{{ bookingColourLab.toTone }} 100%);">'
    '<span style="background:{{ bookingColourLab.toTone }};"></span></div>\n'
    '            <div class="bsi-lk__body">\n'
    '              <div class="bsi-lk__kicker">Colour consultation &middot; from the Colour Lab</div>\n'
    '              <div class="bsi-lk__name" style="font-size:21px;">{{ bookingColourLab.from }} &rarr; {{ bookingColourLab.to }}</div>\n'
    '              <div class="bsi-lk__chips">\n'
    '                <span><small>Tone</small>{{ bookingColourLab.tone }}</span>\n'
    '                <span><small>Hair</small>{{ bookingColourLab.condition }}</span>\n'
    '                <span><small>Sessions</small>{{ bookingColourLab.sessions }}</span>\n'
    '                <span><small>Chair time</small>{{ bookingColourLab.chairTime }}</span>\n'
    '              </div>\n'
    '              <p class="bsi-lk__note">This consultation is your service &mdash; your colourist gets exactly this plan. '
    'No need to pick a service again.</p>\n'
    '            </div>\n'
    '            <div class="bsi-lk__side">\n'
    '              <div class="bsi-lk__price">{{ bookingColourLab.price }}<small>estimated</small></div>\n'
    '              <button type="button" class="bsi-lk__go" sc-camel-on-click="{{ bookingColourLabNext }}">Continue to Chair &rarr;</button>\n'
    '              <button type="button" class="bsi-lk__alt" sc-camel-on-click="{{ bookingColourLabEdit }}">Change shades</button>\n'
    '              <button type="button" class="bsi-lk__alt" sc-camel-on-click="{{ bookingColourLabClear }}">Book regular services instead</button>\n'
    '            </div>\n'
    '          </div>\n'
    '          </sc-if>\n'
    '          '
)
# The same one-line description the card, the Confirm line and the sidebar use.
_LAB_NAME_JS = "'Colour consultation \\u00b7 ' + lab.from + ' \\u2192 ' + lab.to + ' \\u00b7 ' + lab.tone"
COLOUR_LAB_PATCHES = (
    ('colour lab: stale brief cleared on a fresh booking',
     "  setPage = (p, extra) => {\n    if (p === this.state.page && !extra) return;\n",
     "  setPage = (p, extra) => {\n    if (p === this.state.page && !extra) return;\n"
     # Every "start a booking" entry -- and "Book Another" (resetBooking, which goes
     # to Stores) -- passes its own reset carrying bookingConfirmed; only the Colour
     # Lab's own sets a brief, so any other one drops a brief left from before.
     "    if (extra && ('bookingConfirmed' in extra) && !('bookingColourLab' in extra)) { extra = { ...extra, bookingColourLab: null }; }\n"),
    ('colour lab: plan priced from the backend table', _LAB_PRICING_SRC, _LAB_PRICING_DST),
    ('colour lab: book method',
     '  labPlan() {\n',
     "  goBookingFromColourLab = () => {\n"
     "    const s0 = this.state;\n"
     "    const p = this.labPlan();\n"
     "    const lab = {\n"
     # The raw picks are what the server prices from; the rest is display only.
     "      labFrom: s0.labFrom, labTo: s0.labTo, labTone: p.tone.id, labCondition: p.cond.id,\n"
     "      from: 'Level ' + p.from.level + ' ' + p.from.name, to: 'Level ' + p.to.level + ' ' + p.to.name,\n"
     "      fromTone: p.from.tone, toTone: p.to.tone, tone: p.tone.name, condition: p.cond.name,\n"
     "      sessions: p.sessions, price: p.price, minutes: p.minutes,\n"
     "    };\n"
     "    lab.name = " + _LAB_NAME_JS + ";\n"
     "    const start = (cityId) => this.setPage('booking', {\n"
     "      booking: { cityId: cityId || null, storeId: null, step: cityId ? 2 : 1 }, bookingMaxStep: cityId ? 2 : 1,\n"
     "      selectedChairIds: [], selectedTime: null, bookingConfirmed: false,\n"
     "      bookingError: false, bookingSubmitting: false,\n"
     "      bookingServiceId: null, bookingServiceIds: [], bookingServiceName: null,\n"
     "      bookingServicePrice: null, bookingActiveServiceCat: null,\n"
     "      bookingPackageId: null, bookingPackageName: null, bookingPackagePrice: null,\n"
     "      rewardServiceId: null, rewardServiceName: null,\n"
     "      bookingRewardId: null, bookingRewardAddedSvc: null, bookingUseServicePoints: true, bookingStylist: null,\n"
     "      bookingLookLength: null, bookingLookShadeIndex: null, bookingLookFinish: null,\n"
     "      bookingLookPrice: null, ritual: [], isMember: false,\n"
     "      bookingLoyaltyPoints: 0, bookingGiftCode: '', bookingQuote: null,\n"
     "      bookingLoyaltyAuto: true, bookingGiftAuto: true,\n"
     "      bookingQuoteError: '', bookingQuoteLoading: false,\n"
     "      bookingDate: null, bsiCalMonth: null, bsiCalYear: null,\n"
     "      bookingColourLab: lab,\n"
     "    });\n"
     "    fetch('/salon/api/customer_city', { method: 'POST', credentials: 'same-origin',\n"
     "      headers: { 'Content-Type': 'application/json' },\n"
     "      body: JSON.stringify({ id: 1, jsonrpc: '2.0', method: 'call', params: {} }) })\n"
     "      .then((r) => r.json())\n"
     "      .then((payload) => start(((payload && payload.result) || {}).city_id))\n"
     "      .catch(() => start(null));\n"
     "  };\n"
     "  labPlan() {\n"),
    ('colour lab: expose book method',
     'goBookingFromLook: this.goBookingFromLook,',
     'goBookingFromLook: this.goBookingFromLook, goBookingFromColourLab: this.goBookingFromColourLab,'),
    ('colour lab: button',
     '<button sc-camel-on-click="{{ goBookingNav }}"' + _COLOUR_LAB_BTN,
     '<button sc-camel-on-click="{{ goBookingFromColourLab }}"' + _COLOUR_LAB_BTN),
    # The consultation IS the service, but unlike a look the customer is shown it:
    # choosing the salon lands on step 3 ("Consultation"), whose card replaces the
    # service list and continues to the Chair step (bookingColourLabNext). So no
    # store-step override here -- LOOK_BOOKING_PATCHES' look-only skip is untouched.
    ('colour lab: step label',
     "{ n: 3, label: s.bookingLookLength ? 'Your look' : 'Service' }",
     "{ n: 3, label: s.bookingLookLength ? 'Your look' : (s.bookingColourLab ? 'Consultation' : 'Service') }"),
    ('colour lab: service list hidden behind the card',
     'bookingHasLook: has, bookingNoLook: !has,',
     'bookingHasLook: has, bookingNoLook: !has && !s.bookingColourLab,'),
    ('colour lab: service step card', _SERVICE_STEP_INTRO, _COLOUR_LAB_CARD + _SERVICE_STEP_INTRO),
    ('colour lab: render values',
     '      bsiXt: (() => {\n',
     "      ...(() => {\n"
     "        const lab = (s.bookingColourLab && !s.bookingLookLength) ? s.bookingColourLab : null;\n"
     "        const q = s.bookingQuote || null;\n"
     "        const qLab = (q && q.colour_lab) || null;\n"
     "        const minutes = qLab ? qLab.minutes : (lab ? (lab.minutes || 0) : 0);\n"
     "        const hrs = Math.floor(minutes / 60), mins = minutes % 60;\n"
     "        const sessions = qLab ? qLab.sessions : (lab ? lab.sessions : 0);\n"
     "        return {\n"
     "          bookingHasColourLab: !!lab,\n"
     "          bookingColourLab: lab ? {\n"
     "            from: lab.from, to: lab.to, fromTone: lab.fromTone || '#2a1d18', toTone: lab.toTone || '#c9a15a',\n"
     "            tone: lab.tone || '', condition: lab.condition || '',\n"
     "            sessions: sessions + (sessions === 1 ? ' session' : ' sessions'),\n"
     "            chairTime: (hrs ? hrs + 'h' : '') + (mins ? (hrs ? ' ' : '') + mins + 'm' : (hrs ? '' : '0m')),\n"
     "            price: '\\u20b9' + Number(qLab ? qLab.price : (lab.price || 0)).toLocaleString('en-IN'),\n"
     "          } : { from: '', to: '', fromTone: '', toTone: '', tone: '', condition: '', sessions: '', chairTime: '', price: '' },\n"
     "          bookingColourLabNext: () => this.setState((st) => ({ booking: { ...st.booking, step: 4 }, bookingMaxStep: Math.max(st.bookingMaxStep || 1, 4) })),\n"
     "          bookingColourLabClear: () => this.setState({ bookingColourLab: null, bookingQuote: null }),\n"
     "          bookingColourLabEdit: () => { this.setPage('services'); setTimeout(() => { const el = document.querySelector('[data-screen-label=\"Colour Lab\"]'); if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' }); }, 700); },\n"
     "        };\n"
     "      })(),\n"
     "      bsiXt: (() => {\n"),
    ('colour lab: confirm line',
     "if (!svcLines.length) { svcLines.push(",
     "if (s.bookingColourLab && !s.bookingLookLength && !s.bookingPackageId) { const lab = s.bookingColourLab; const qLab = (q && q.colour_lab) || null; "
     "svcLines.unshift({ name: 'Colour consultation', meta: [lab.from + ' \\u2192 ' + lab.to, lab.tone, lab.condition].filter(Boolean).join(' \\u00b7 '), "
     "price: money(qLab ? qLab.price : (lab.price || 0)) }); } "
     "if (!svcLines.length) { svcLines.push("),
    ('colour lab: pre-quote estimate',
     "const basePrice = ((s.bookingLookPrice != null) ? s.bookingLookPrice : (bsiSvcTotal || 999)) + ritualAddonCost",
     "const basePrice = ((s.bookingLookPrice != null) ? s.bookingLookPrice : ((s.bookingColourLab && !s.bookingPackageId) ? ((s.bookingColourLab.price || 0) + bsiSvcTotal) : (bsiSvcTotal || 999))) + ritualAddonCost"),
    ('colour lab: sidebar service name',
     "        if (!ids.length) { return s.rewardServiceName || ''; }",
     "        const bsiLabName = (s.bookingColourLab && !s.bookingLookLength) ? (s.bookingColourLab.name || 'Colour consultation') : '';\n"
     "        if (!ids.length) { return bsiLabName || s.rewardServiceName || ''; }"),
    ('colour lab: sidebar service name with others',
     "        return names.length ? names.join(', ') : (s.rewardServiceName || '');",
     "        if (bsiLabName) { names.unshift(bsiLabName); }\n"
     "        return names.length ? names.join(', ') : (s.rewardServiceName || '');"),
    # Only the raw picks: the server re-prices them (main.py _bsi_resolve_colour_lab)
    # and ignores anything else, so the page's own estimate is never charged.
    ('colour lab: plan sent with the booking',
     "      use_service_points: s.bookingUseServicePoints !== false,\n",
     "      use_service_points: s.bookingUseServicePoints !== false,\n"
     "      colour_lab: (s.bookingColourLab && !s.bookingLookLength && !s.bookingPackageId) ? {\n"
     "        lab_from: s.bookingColourLab.labFrom, lab_to: s.bookingColourLab.labTo,\n"
     "        lab_tone: s.bookingColourLab.labTone, lab_condition: s.bookingColourLab.labCondition,\n"
     "      } : null,\n"),
)

# --- Confirm step: one code box for gift cards AND discount codes -------------
# The box used to send whatever was typed as gift_card_code, and the server only
# knew the customer's own "Salon Gift Card" cards -- a received gift card, a card
# from Odoo's standard Gift Cards program, a promo code or a coupon all came back
# "not found / not linked to your account". It now sends entered_code and the
# server (main.py _bsi_booking_quote) tells a gift card from a discount / promo /
# coupon code; the discount code then rides along as promo_code like the gift card
# does, shows as its own perk and receipt line, and is priced by the backend.
_CODE_ICON_TAG = (
    '<svg sc-camel-view-box="0 0 24 24" style="fill:none;stroke:currentColor;'
    'stroke-width:1.8;stroke-linecap:round;stroke-linejoin:round;"><path d="'
    'M20.6 13.4l-7.2 7.2a2 2 0 0 1-2.8 0L3 13V3h10l7.6 7.6a2 2 0 0 1 0 2.8zM7.5 7.5h.01'
    '"></path></svg>'
)
CODE_FIELD_SRC = (
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
)
CODE_FIELD_DST = (
    # The gift card perks stay under the gift card toggle; the code box (and the
    # discount code it applied) only needs a signed-in customer.
    '                  </sc-if>\n'
    '                  <sc-if value="{{ cfShowCode }}" hint-placeholder-val="{{ false }}">\n'
    '                    <sc-if value="{{ cfPromoOn }}" hint-placeholder-val="{{ false }}">\n'
    '                      <div class="cf-perk is-on">\n'
    '                        <span class="cf-perk-ico">' + _CODE_ICON_TAG + '</span>\n'
    '                        <div><div class="cf-perk-title">{{ cfPromoTitle }}'
    '<span class="cf-tag cf-tag--on">Applied</span></div>'
    '<div class="cf-perk-sub">{{ cfPromoSub }}</div>'
    '<div class="cf-perk-actions"><button class="cf-btn cf-btn--link" '
    'sc-camel-on-click="{{ bsiClearPromo }}">Remove code</button></div></div>\n'
    '                        <div class="cf-perk-amt">{{ cfPromoAmount }}</div>\n'
    '                      </div>\n'
    '                    </sc-if>\n'
    '                    <sc-if value="{{ cfGiftNotApplied }}" hint-placeholder-val="{{ false }}">\n'
    '                      <div class="cf-field-label">{{ cfCodeLabel }}</div>\n'
    '                      <div class="cf-field cf-field-code" style="margin-top:8px;">'
    '<input id="bsiGiftCardCode" type="text" placeholder="Gift card or discount code" autocomplete="off">'
    '<button class="cf-btn cf-btn--ghost" sc-camel-on-click="{{ bsiApplyGiftCard }}">Apply</button></div>\n'
    '                    </sc-if>\n'
    '                    <sc-if value="{{ bsiGiftError }}" hint-placeholder-val="{{ false }}">\n'
    '                      <div class="cf-alert">{{ bsiGiftError }}</div>\n'
    '                    </sc-if>\n'
    '                  </sc-if>\n'
)
CODE_ENTRY_PATCHES = (
    # A new booking (every entry goes through setPage with bookingConfirmed) forgets
    # the previous one's discount code. Inserted above the colour-lab line, which
    # enrich_loyalty anchors on.
    ('codes: reset the discount code on a new booking',
     "    if (p === this.state.page && !extra) return;\n",
     "    if (p === this.state.page && !extra) return;\n"
     "    if (extra && ('bookingConfirmed' in extra) && !('bookingPromoCode' in extra)) "
     "{ extra = { ...extra, bookingPromoCode: '' }; }\n"),
    ('codes: discount code sent with the quote and the booking',
     "      gift_card_code: s.bookingGiftCode || '',\n",
     "      gift_card_code: s.bookingGiftCode || '',\n"
     "      promo_code: s.bookingPromoCode || '',\n"),
    # Whatever the quote applied becomes the booking's own code; a typed gift card
    # switches the automatic own-card pick off, and an applied code empties the box.
    ('codes: keep what the quote applied',
     "bookingLoyaltyPoints: L.points || 0, bookingGiftCode: G.code || '' });\n",
     "bookingLoyaltyPoints: L.points || 0, bookingGiftCode: G.code || '', "
     "bookingPromoCode: (res.promo && res.promo.code) || '', "
     "...((res.code_entry && res.code_entry.kind === 'gift_card') ? { bookingGiftAuto: false } : {}) });\n"
     "        if (res.code_entry && res.code_entry.kind) { const bsiCodeEl = document.getElementById('bsiGiftCardCode'); "
     "if (bsiCodeEl) { bsiCodeEl.value = ''; } }\n"),
    ('codes: Apply takes a gift card or a discount code',
     "  bsiApplyGiftCard = () => {\n"
     "    const el = document.getElementById('bsiGiftCardCode');\n"
     "    const code = (el && el.value ? el.value : '').trim();\n"
     "    this.setState({ bookingGiftCode: code, bookingGiftAuto: false });\n"
     "    this.bsiFetchQuote({ gift_card_code: code, auto_gift_card: false });\n"
     "  };\n",
     "  bsiApplyGiftCard = () => {\n"
     "    const el = document.getElementById('bsiGiftCardCode');\n"
     "    const code = (el && el.value ? el.value : '').trim();\n"
     "    if (!code) { if (window.bsiToast) { window.bsiToast('Enter a gift card or discount code.', 'info'); } return; }\n"
     "    this.bsiFetchQuote({ entered_code: code });\n"
     "  };\n"),
    ('codes: remove the discount code',
     "  bsiClearGiftCard = () => {\n",
     "  bsiClearPromo = () => {\n"
     "    this.setState({ bookingPromoCode: '' });\n"
     "    this.bsiFetchQuote({ promo_code: '' });\n"
     "  };\n"
     "  bsiClearGiftCard = () => {\n"),
    ('codes: discount code amount',
     "        const giftAmt = G.code ? (G.applied || 0) : 0;\n",
     "        const giftAmt = G.code ? (G.applied || 0) : 0;\n"
     "        const PR = (q && q.promo) || {};\n"
     "        const promoAmt = PR.code ? (PR.amount || 0) : 0;\n"),
    ('codes: membership share leaves the discount code out',
     "- loyaltyAmt - giftAmt - payable) : 0;\n",
     "- loyaltyAmt - giftAmt - promoAmt - payable) : 0;\n"),
    ('codes: savings include the discount code',
     "const savings = memberAmt + rewardAmt + rwAmt + spAmt + loyaltyAmt + giftAmt;\n",
     "const savings = memberAmt + rewardAmt + rwAmt + spAmt + loyaltyAmt + giftAmt + promoAmt;\n"),
    ('codes: discount code receipt line',
     "        if (giftAmt) { lines.push({ label: 'Gift card · ' + G.code",
     "        if (promoAmt) { lines.push({ label: 'Discount code · ' + PR.code, value: '−' + money(promoAmt), cls: 'is-save' }); }\n"
     "        if (giftAmt) { lines.push({ label: 'Gift card · ' + G.code"),
    ('codes: code box and discount code perk values',
     "          cfGiftNotApplied: !giftApplied,\n",
     "          cfGiftNotApplied: !giftApplied || !PR.code,\n"
     "          cfShowCode: loggedIn,\n"
     "          cfPromoOn: !!PR.code,\n"
     "          cfPromoTitle: 'Discount code ' + (PR.code || ''),\n"
     "          cfPromoSub: PR.name || 'Applied to this booking',\n"
     "          cfPromoAmount: '−' + money(promoAmt),\n"
     "          cfCodeLabel: (F.gift_card && !giftApplied) ? 'Have a gift card or discount code?' : 'Have a discount code?',\n"),
    ('codes: code box error and remove handler',
     "          bsiGiftError: G.error || '',\n",
     "          bsiGiftError: G.error || PR.error || '',\n"
     "          bsiClearPromo: this.bsiClearPromo,\n"),
    ('codes: code box markup', CODE_FIELD_SRC, CODE_FIELD_DST),
)

PATCHES = (
    ('loader: app-side script', APP_HEAD_SRC, APP_HEAD_DST),
    ('loader: app-side overlay', APP_BODY_SRC, APP_BODY_DST),
    ('loader: app intro disabled', INTRO_OFF_SRC, INTRO_OFF_DST),
) + DATE_PATCHES + LOOK_BOOKING_PATCHES + ABOUT_PATCHES + LOYALTY_PATCHES + COLOUR_LAB_PATCHES \
    + CODE_ENTRY_PATCHES

# --- Testimonials -------------------------------------------------------------
# A swipeable carousel (bsi_carousel.js drives the arrows, autoplay, drag and
# progress bar); the filter chips, cards and their bindings are the design's.
_ARROW_PREV = (
    '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" '
    'd="M14.7 5.3 16 6.6 10.6 12l5.4 5.4-1.3 1.3L8 12l6.7-6.7Z"/></svg>'
)
_ARROW_NEXT = (
    '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" '
    'd="M9.3 5.3 8 6.6l5.4 5.4L8 17.4l1.3 1.3L16 12 9.3 5.3Z"/></svg>'
)
_STAR_ROW = (
    '<sc-for list="{{ t.stars }}" as="filled" hint-placeholder-count="5">'
    '<span style="color:{{ filled.color }};">★</span></sc-for>'
)

TESTIMONIALS_DST = (
    '<section class="bsi-rev">\n'
    '      <div class="bsi-rev__head">\n'
    '        <div class="bsi-rev__intro">\n'
    '          <div class="bsi-eyebrow">TESTIMONIALS</div>\n'
    '          <h2 class="bsi-rev__title">Loved across <em>India</em></h2>\n'
    '          <p class="bsi-rev__sub">Real words from verified visits. Filter by the service you are curious about.</p>\n'
    '        </div>\n'
    '        <div class="bsi-rev__score">\n'
    '          <div class="bsi-rev__avg">{{ reviewAvg }}</div>\n'
    '          <div>\n'
    '            <div class="bsi-rev__stars">★★★★★</div>\n'
    '            <div class="bsi-rev__count">from {{ reviewCount }} verified visits</div>\n'
    '          </div>\n'
    '        </div>\n'
    '      </div>\n'
    '      <div class="bsi-rev__bar">\n'
    '        <div class="bsi-rev__filters">\n'
    '          <sc-for list="{{ reviewFilters }}" as="rf" hint-placeholder-count="5">\n'
    '            <button sc-camel-on-click="{{ rf.onClick }}" class="bsi-rev__chip" '
    'style="background:{{ rf.bg }};color:{{ rf.color }};border-color:{{ rf.border }};">{{ rf.label }}</button>\n'
    '          </sc-for>\n'
    '        </div>\n'
    '        <div class="bsi-rev__nav">\n'
    '          <button type="button" class="bsi-rev__arrow bsi-rev__arrow--prev" aria-label="Previous reviews">' + _ARROW_PREV + '</button>\n'
    '          <button type="button" class="bsi-rev__arrow bsi-rev__arrow--next" aria-label="Next reviews">' + _ARROW_NEXT + '</button>\n'
    '        </div>\n'
    '      </div>\n'
    '      <div class="bsi-rev__grid">\n'
    '        <sc-for list="{{ reviewsDisplay }}" as="t" hint-placeholder-count="3">\n'
    '          <article class="bsi-rev__card" style="animation-delay:{{ t.delay }}s;">\n'
    '            <svg class="bsi-rev__quote" viewBox="0 0 48 36" aria-hidden="true"><path d="M0 36V21.6C0 9.4 6.6 2.2 19.8 0l1.8 4.6C14.5 6.5 10.9 10.4 10.4 16.2H20V36H0Zm28 0V21.6C28 9.4 34.6 2.2 47.8 0l1.8 4.6c-7.1 1.9-10.7 5.8-11.2 11.6H48V36H28Z"/></svg>\n'
    '            <div class="bsi-rev__top">\n'
    '              <div class="bsi-rev__rating">' + _STAR_ROW + '</div>\n'
    '              <span class="bsi-rev__service">{{ t.service }}</span>\n'
    '            </div>\n'
    '            <sc-if value="{{ t.hasPhoto }}" hint-placeholder-val="{{ false }}">\n'
    '              <div class="bsi-rev__photo">\n'
    '                <img src="{{ t.photoSafe }}" alt="Result photo from {{ t.name }}">\n'
    '                <span>GUEST PHOTO</span>\n'
    '              </div>\n'
    '            </sc-if>\n'
    '            <blockquote class="bsi-rev__text">{{ t.text }}</blockquote>\n'
    '            <div class="bsi-rev__author">\n'
    '              <span class="bsi-rev__avatar"><img src="{{ t.avatarSrc }}" alt="{{ t.name }}"></span>\n'
    '              <div class="bsi-rev__who">\n'
    '                <div class="bsi-rev__name">{{ t.name }}</div>\n'
    '                <div class="bsi-rev__meta">{{ t.city }} · with {{ t.stylist }}</div>\n'
    '              </div>\n'
    '              <span class="bsi-rev__verified">✓ Verified</span>\n'
    '            </div>\n'
    '          </article>\n'
    '        </sc-for>\n'
    '      </div>\n'
    '      <div class="bsi-rev__progress" aria-hidden="true"><span></span></div>\n'
    '      <sc-if value="{{ reviewsEmpty }}" hint-placeholder-val="{{ false }}">\n'
    '        <div class="bsi-rev__empty">No reviews for that filter yet. Try another service.</div>\n'
    '      </sc-if>\n'
    '    </section>'
)

# --- Transformations ----------------------------------------------------------
# Was: a fixed 260px-tall, wide card for photos that are portrait (3:4), so most
# of every photo was cropped away, and four items in a 3-column grid left one
# orphaned on its own row. Now each stage is 3:4 so a portrait shows whole, and
# the grid auto-fits so any count lays out evenly. The drag-to-compare wiring
# (ref / onDown / pct) is the design's own, unchanged.
TRANSFORMATIONS_DST = (
    '<section class="bsi-tf">\n'
    '      <div class="bsi-tf__inner">\n'
    '        <div class="bsi-tf__head">\n'
    '          <div>\n'
    '            <div class="bsi-eyebrow">REAL RESULTS</div>\n'
    '            <h2 class="bsi-tf__title">Transformations</h2>\n'
    '          </div>\n'
    '          <p class="bsi-tf__sub">Drag the handle across any photo to compare before and after.</p>\n'
    '        </div>\n'
    '        <div class="bsi-tf__grid">\n'
    '          <sc-for list="{{ galleryItems }}" as="g" hint-placeholder-count="3">\n'
    '            <figure class="bsi-tf__card">\n'
    '              <div ref="{{ g.ref }}" sc-camel-on-mouse-down="{{ g.onDown }}" '
    'sc-camel-on-touch-start="{{ g.onDown }}" class="bsi-tf__stage">\n'
    '                <img class="bsi-tf__img" src="{{ g.beforeSrc }}" alt="{{ g.beforeLabel }}">\n'
    '                <div class="bsi-tf__after" style="clip-path:inset(0 0 0 {{ g.pct }}%);">\n'
    '                  <img class="bsi-tf__img" src="{{ g.afterSrc }}" alt="{{ g.afterLabel }}">\n'
    '                </div>\n'
    '                <div class="bsi-tf__line" style="left:{{ g.pct }}%;"></div>\n'
    '                <div class="bsi-tf__handle" style="left:{{ g.pct }}%;">'
    '<span>‹</span><span>›</span></div>\n'
    '                <span class="bsi-tf__tag bsi-tf__tag--before">BEFORE</span>\n'
    '                <span class="bsi-tf__tag bsi-tf__tag--after">AFTER</span>\n'
    '                <span class="bsi-tf__hint">DRAG TO COMPARE</span>\n'
    '              </div>\n'
    '              <figcaption class="bsi-tf__cap">\n'
    '                <span class="bsi-tf__caption">{{ g.caption }}</span>\n'
    '                <span class="bsi-tf__service">{{ g.service }}</span>\n'
    '              </figcaption>\n'
    '            </figure>\n'
    '          </sc-for>\n'
    '        </div>\n'
    '      </div>\n'
    '    </section>'
)

# --- Footer -------------------------------------------------------------------
_ICON_PIN = (
    '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M12 2a7 7 0 0 0-7 '
    '7c0 5.2 7 13 7 13s7-7.8 7-13a7 7 0 0 0-7-7Zm0 9.5A2.5 2.5 0 1 1 12 6.5a2.5 2.5 0 0 1 0 5Z"/></svg>'
)
_ICON_PHONE = (
    '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M6.6 10.8a15.1 15.1 '
    '0 0 0 6.6 6.6l2.2-2.2a1 1 0 0 1 1-.25 11.4 11.4 0 0 0 3.6.57 1 1 0 0 1 1 1V20a1 1 0 0 1-1 1A17 '
    '17 0 0 1 3 4a1 1 0 0 1 1-1h3.5a1 1 0 0 1 1 1c0 1.25.2 2.45.57 3.57a1 1 0 0 1-.25 1l-2.2 2.23Z"/></svg>'
)
_ICON_MAIL = (
    '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M4 4h16a2 2 0 0 1 2 '
    '2v12a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2Zm8 7.2L20 6H4l8 5.2ZM4 8.3V18h16V8.3l-8 '
    '5.2-8-5.2Z"/></svg>'
)
_ICON_IG = (
    '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M12 7.3A4.7 4.7 0 1 0 '
    '16.7 12 4.7 4.7 0 0 0 12 7.3Zm0 7.7a3 3 0 1 1 3-3 3 3 0 0 1-3 3Zm6-7.9a1.1 1.1 0 1 1-1.1-1.1A1.1 '
    '1.1 0 0 1 18 7.1ZM21.9 8c-.1-1.6-.4-3-1.6-4.2S17.6 2.2 16 2.1C14.4 2 9.6 2 8 2.1 6.4 2.2 5 2.5 3.8 '
    '3.7S2.2 6.4 2.1 8C2 9.6 2 14.4 2.1 16c.1 1.6.4 3 1.6 4.2s2.6 1.5 4.2 1.6c1.6.1 6.4.1 8 0 1.6-.1 '
    '3-.4 4.2-1.6s1.5-2.6 1.6-4.2c.1-1.6.1-6.4 0-8Zm-2.1 9.7a3.3 3.3 0 0 1-1.8 1.8c-1.3.5-4.3.4-5.7.4s-'
    '4.4.1-5.7-.4a3.3 3.3 0 0 1-1.8-1.8c-.5-1.3-.4-4.3-.4-5.7s-.1-4.4.4-5.7a3.3 3.3 0 0 1 1.8-1.8c1.3-.5 '
    '4.3-.4 5.7-.4s4.4-.1 5.7.4a3.3 3.3 0 0 1 1.8 1.8c.5 1.3.4 4.3.4 5.7s.1 4.4-.4 5.7Z"/></svg>'
)
_ICON_FB = (
    '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M14 8.5V6.8c0-.8.2-1.3 '
    '1.4-1.3H17V2.3A22 22 0 0 0 14.6 2C12.2 2 10.6 3.5 10.6 6.2v2.3H8V12h2.6v10H14V12h2.7l.4-3.5H14Z"/></svg>'
)
_CHEVRON = (
    '<svg class="bsi-foot__chev" viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" '
    'd="M9.3 5.3 8 6.6l5.4 5.4L8 17.4l1.3 1.3 6.7-6.7-6.7-6.7Z"/></svg>'
)
_FOOT_HEART = (
    '<svg class="bsi-foot__heart" viewBox="0 0 24 22" aria-hidden="true"><path fill="#e8283f" '
    'd="M12 21.5 10.3 20C4.2 14.5.5 11.2.5 7 .5 3.7 3.1 1 6.5 1c1.9 0 3.8.9 5 2.4C12.7 1.9 14.6 1 16.5 '
    '1c3.4 0 6 2.7 6 6 0 4.2-3.7 7.5-9.8 13L12 21.5z"/></svg>'
)


def footer_markup(links_html, cities_html, network_html):
    """Shared footer shell; the /shop template builds the same structure in QWeb."""
    return (
        '<footer class="bsi-foot">\n'
        '    <div class="bsi-foot__glow" aria-hidden="true"></div>\n'
        '    <div class="bsi-foot__main">\n'
        '      <div class="bsi-foot__brand">\n'
        '        <div class="bsi-foot__logo">enr<span class="bsi-foot__i">i' + _FOOT_HEART + '</span>ch</div>\n'
        '        <div class="bsi-foot__tagline">love begins with you</div>\n'
        '        <p class="bsi-foot__about">India\'s leading salon chain since 1997 — hair, skin, makeup '
        'and wellness across 100+ locations.</p>\n'
        '        <ul class="bsi-foot__contact">\n'
        '          <li>' + _ICON_PIN + '<span>{{ bsiContact.branchesLabel }} {{ bsiContact.citiesLabel }}</span></li>\n'
        '          <li>' + _ICON_PHONE + '<a class="bsi-foot__tel" href="{{ bsiContact.phoneHref }}">{{ bsiContact.phone }}</a></li>\n'
        '          <li>' + _ICON_MAIL + '<a class="bsi-foot__tel" href="{{ bsiContact.emailHref }}">{{ bsiContact.email }}</a></li>\n'
        '        </ul>\n'
        '        <div class="bsi-foot__social">\n'
        '          <sc-if value="{{ bsiContact.instagram }}" hint-placeholder-val="{{ false }}"><a class="bsi-foot__soc" title="Instagram" href="{{ bsiContact.instagram }}" target="_blank" rel="noopener">' + _ICON_IG + '</a></sc-if>\n'
        '          <sc-if value="{{ bsiContact.no_instagram }}" hint-placeholder-val="{{ true }}"><span class="bsi-foot__soc" title="Instagram">' + _ICON_IG + '</span></sc-if>\n'
        '          <sc-if value="{{ bsiContact.facebook }}" hint-placeholder-val="{{ false }}"><a class="bsi-foot__soc" title="Facebook" href="{{ bsiContact.facebook }}" target="_blank" rel="noopener">' + _ICON_FB + '</a></sc-if>\n'
        '          <sc-if value="{{ bsiContact.no_facebook }}" hint-placeholder-val="{{ true }}"><span class="bsi-foot__soc" title="Facebook">' + _ICON_FB + '</span></sc-if>\n'
        '        </div>\n'
        '      </div>\n'
        '      <div class="bsi-foot__nav">\n'
        '        <div class="bsi-foot__col">\n'
        '          <h4 class="bsi-foot__h">Quick Links</h4>\n'
        + links_html +
        '        </div>\n'
        '        <div class="bsi-foot__col">\n'
        '          <h4 class="bsi-foot__h">Our Cities</h4>\n'
        + cities_html +
        '        </div>\n'
        '        <div class="bsi-foot__network">\n'
        '          <h4 class="bsi-foot__h">Our Network</h4>\n'
        + network_html +
        '        </div>\n'
        '      </div>\n'
        '    </div>\n'
        '    <div class="bsi-foot__bar">\n'
        '      <span>© 2026 Enrich Hair and Skin Solutions Pvt. Ltd. All rights reserved.</span>\n'
        '      <span class="bsi-foot__bar-right">Hair · Skin · Makeup · Wellness</span>\n'
        '    </div>\n'
        '  </footer>'
    )


_FOOT_LINKS = (
    '          <sc-for list="{{ footerLinks }}" as="l" hint-placeholder-count="6">\n'
    '            <a class="bsi-foot__link" sc-camel-on-click="{{ l.onClick }}">' + _CHEVRON + '<span>{{ l.label }}</span></a>\n'
    '          </sc-for>\n'
)
_FOOT_CITIES = (
    '          <sc-for list="{{ footerCities }}" as="fc" hint-placeholder-count="6">\n'
    '            <a class="bsi-foot__link" sc-camel-on-click="{{ fc.onClick }}">' + _CHEVRON + '<span>{{ fc.name }}</span></a>\n'
    '          </sc-for>\n'
)
# The design's animated network map, kept with its own bindings.
_FOOT_NETWORK = (
    '          <div class="bsi-foot__map">\n'
    '            <div class="bsi-foot__map-grid"></div>\n'
    '            <svg sc-camel-view-box="0 0 100 100" sc-camel-preserve-aspect-ratio="none" class="bsi-foot__map-svg">\n'
    '              <path d="M30 12 L46 8 L58 16 L54 30 L64 38 L60 52 L70 62 L62 76 L48 88 L38 78 L30 60 L22 44 L26 26 Z" '
    'fill="rgba(253,243,234,.05)" stroke="rgba(201,161,90,.28)" stroke-width="0.6"></path>\n'
    '              <g stroke="rgba(232,40,63,.45)" stroke-width="0.6" fill="none" stroke-linecap="round" '
    'stroke-dasharray="60" stroke-dashoffset="60">\n'
    '                <sc-for list="{{ footerRoutes }}" as="rt" hint-placeholder-count="5">\n'
    '                  <path d="{{ rt.d }}" style="animation:routeDraw 2.4s ease-out {{ rt.delay }}s forwards;"></path>\n'
    '                </sc-for>\n'
    '              </g>\n'
    '            </svg>\n'
    '            <sc-for list="{{ footerCities }}" as="fc" hint-placeholder-count="6">\n'
    '              <button sc-camel-on-click="{{ fc.onClick }}" class="bsi-foot__pin" '
    'style="left:{{ fc.x }}%;top:{{ fc.y }}%;">\n'
    '                <span class="bsi-foot__pin-ring" style="animation:cityPing 3s ease-out {{ fc.delay }}s infinite;"></span>\n'
    '                <span class="bsi-foot__pin-dot" style="animation:cityGlow 2.6s ease-in-out {{ fc.delay }}s infinite;"></span>\n'
    '                <span class="bsi-foot__pin-name">{{ fc.name }}</span>\n'
    '              </button>\n'
    '            </sc-for>\n'
    '          </div>\n'
)

FOOTER_DST = footer_markup(_FOOT_LINKS, _FOOT_CITIES, _FOOT_NETWORK)

# (label, anchor inside the element, opening tag prefix, closing tag, replacement)
# --- Contact page redesign (PHASE 8 DEV) -------------------------------------
# One focused page: the hero stays exactly as designed; below it a contact column
# (toll-free / email / visit a salon, a live card for the branch picked in the form,
# and what happens next) beside the form itself. The old per-city branch list and the
# "new client offer" box are gone. The form keeps every binding sendContact relies on
# -- the four text fields stay the only input/textarea elements, in the same order
# (name, email, phone, message), and City/Branch/topic are buttons only.
CONTACT_SECTION_DST = (
    '<section data-screen-label="Contact">\n'
    '      <div class="bsi-cx-hero">\n'
    '        <div class="bsi-cx-hero__deco" aria-hidden="true"><i></i><i></i><i></i></div>\n'
    '        <div class="bsi-cx-hero__inner">\n'
    '          <div class="bsi-cx-hero__copy">\n'
    '            <div class="bsi-ct-hero2__top">\n'
    '              <span class="bsi-ct-hero2__kicker">Get in touch</span>\n'
    '              <span class="{{ contactLineCls }}"><i></i>{{ contactLineLabel }}</span>\n'
    '            </div>\n'
    '            <h1 class="bsi-cx-title">Let\'s talk<br><em>transformation.</em></h1>\n'
    '            <p class="bsi-cx-sub">Questions about a service, a booking or a membership? Tell us which salon you visit and that team replies directly &mdash; usually within a working day.</p>\n'
    '            <div class="bsi-cx-actions">\n'
    '              <button type="button" class="bsi-cx-btn" sc-camel-on-click="{{ contactScrollToForm }}">Write to us <i aria-hidden="true">&darr;</i></button>\n'
    '              <a class="bsi-cx-btn bsi-cx-btn--ghost" href="{{ bsiContact.phoneHref }}">Call {{ bsiContact.phone }}</a>\n'
    '            </div>\n'
    '            <div class="bsi-ct-hero__chips">\n'
    '              <span><b>1 day</b>reply time</span>\n'
    '              <span><b>{{ bsiContact.branchesLabel }}</b>{{ bsiContact.citiesLabel }}</span>\n'
    '              <span><b>{{ bsiContact.rating }}&#9733;</b>average rating</span>\n'
    '            </div>\n'
    '          </div>\n'
    '          <div class="bsi-cx-scene">\n'
    '            <svg class="bsi-cx-svg" sc-camel-view-box="0 0 560 470" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="An Enrich artist cutting a guest\'s hair">\n'
    '              <defs>\n'
    '                <linearGradient id="bsiCxWall" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="#fdf0e9"/><stop offset="100%" stop-color="#f4d6cb"/></linearGradient>\n'
    '                <linearGradient id="bsiCxGold" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stop-color="#e6c684"/><stop offset="100%" stop-color="#a47a31"/></linearGradient>\n'
    '                <linearGradient id="bsiCxGlass" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stop-color="#fffaf6"/><stop offset="100%" stop-color="#ead8d1"/></linearGradient>\n'
    '                <clipPath id="bsiCxMirrorClip"><ellipse cx="452" cy="212" rx="46" ry="74"/></clipPath>\n'
    '              </defs>\n'
    '            \n'
    '              <!-- room -->\n'
    '              <rect x="10" y="10" width="540" height="450" rx="36" fill="url(#bsiCxWall)"/>\n'
    '              <path d="M10 378 H550 V424 Q550 460 514 460 H46 Q10 460 10 424 Z" fill="#e9c6b9"/>\n'
    '              <path d="M70 378 L40 460 M170 378 L160 460 M280 378 L280 460 M390 378 L400 460 M490 378 L520 460" stroke="#ddb3a5" stroke-width="2"/>\n'
    '              <rect x="10" y="366" width="540" height="12" fill="#e2b7a8"/>\n'
    '            \n'
    '              <!-- neon sign -->\n'
    '              <text class="bsi-cx-neon" x="452" y="84" text-anchor="middle" font-family="Playfair Display, Georgia, serif" font-size="34" fill="#e8283f">enrich</text>\n'
    '              <path class="bsi-cx-neon" d="M463 46 c-2.4 -3 -7 -1.6 -7 1.6 c0 2.4 3 4.8 7 7 c4 -2.2 7 -4.6 7 -7 c0 -3.2 -4.6 -4.6 -7 -1.6 z" fill="#e8283f"/>\n'
    '            \n'
    '              <!-- pendant lamp -->\n'
    '              <g>\n'
    '                <animateTransform attributeName="transform" type="rotate" values="-5 262 10;5 262 10;-5 262 10" dur="4.2s" repeatCount="indefinite" calcMode="spline" keySplines="0.45 0 0.55 1;0.45 0 0.55 1"/>\n'
    '                <line x1="262" y1="10" x2="262" y2="62" stroke="#161213" stroke-width="2"/>\n'
    '                <circle class="bsi-cx-glow" cx="262" cy="92" r="30" fill="#ffd98a"/>\n'
    '                <path d="M244 62 H280 L294 88 H230 Z" fill="#161213"/>\n'
    '                <rect x="244" y="86" width="36" height="4" rx="2" fill="url(#bsiCxGold)"/>\n'
    '                <circle cx="262" cy="94" r="6" fill="#ffe3a3"/>\n'
    '              </g>\n'
    '            \n'
    '              <!-- mirror -->\n'
    '              <ellipse cx="452" cy="212" rx="58" ry="86" fill="url(#bsiCxGold)"/>\n'
    '              <ellipse cx="452" cy="212" rx="46" ry="74" fill="url(#bsiCxGlass)"/>\n'
    '              <circle cx="440" cy="200" r="17" fill="#eab494" opacity=".35"/>\n'
    '              <path d="M424 196 Q424 176 441 175 Q457 176 457 190 Q448 184 440 185 Q430 187 428 202 Z" fill="#161213" opacity=".28"/>\n'
    '              <g clip-path="url(#bsiCxMirrorClip)"><rect class="bsi-cx-shine" x="380" y="120" width="26" height="200" fill="#ffffff" opacity=".7" transform="skewX(-18)"/></g>\n'
    '            \n'
    '              <!-- hair dryer on the wall -->\n'
    '              <circle cx="92" cy="186" r="4" fill="#161213"/>\n'
    '              <path d="M92 190 Q88 206 96 214" stroke="#161213" stroke-width="2" fill="none"/>\n'
    '              <rect x="90" y="228" width="11" height="26" rx="5" fill="#161213"/>\n'
    '              <circle cx="96" cy="222" r="16" fill="#e8283f"/>\n'
    '              <circle cx="96" cy="222" r="6" fill="#b3172b"/>\n'
    '              <rect x="108" y="215" width="26" height="14" rx="4" fill="#b3172b"/>\n'
    '              <path class="bsi-cx-air" d="M140 214 q10 -3 20 0 M140 222 q12 0 24 0 M140 230 q10 3 20 0" stroke="#c9a15a" stroke-width="2.4" fill="none" stroke-linecap="round"/>\n'
    '            \n'
    '              <!-- trolley with products -->\n'
    '              <rect x="42" y="268" width="14" height="32" rx="4" fill="#e8283f"/>\n'
    '              <rect x="62" y="278" width="12" height="22" rx="4" fill="url(#bsiCxGold)"/>\n'
    '              <rect x="80" y="262" width="16" height="38" rx="5" fill="#fdf3ea" stroke="#161213" stroke-width="2"/>\n'
    '              <rect x="100" y="274" width="14" height="26" rx="4" fill="#161213"/>\n'
    '              <rect x="34" y="300" width="92" height="9" rx="4.5" fill="#161213"/>\n'
    '              <rect x="34" y="344" width="92" height="7" rx="3.5" fill="#161213"/>\n'
    '              <path d="M42 309 V366 M118 309 V366" stroke="#161213" stroke-width="4"/>\n'
    '              <circle cx="42" cy="370" r="6" fill="#161213"/><circle cx="118" cy="370" r="6" fill="#161213"/>\n'
    '              <rect x="48" y="326" width="30" height="18" rx="5" fill="#f3c9bd"/>\n'
    '            \n'
    '              <!-- plant -->\n'
    '              <g>\n'
    '                <animateTransform attributeName="transform" type="rotate" values="-3 510 332;3 510 332;-3 510 332" dur="5s" repeatCount="indefinite"/>\n'
    '                <path d="M510 332 Q486 300 494 268 Q512 292 510 332 Z" fill="#3f7a5c"/>\n'
    '                <path d="M510 332 Q530 296 524 262 Q504 290 510 332 Z" fill="#4f8c6b"/>\n'
    '                <path d="M510 332 Q472 318 466 292 Q498 300 510 332 Z" fill="#35684f"/>\n'
    '              </g>\n'
    '              <path d="M490 332 H530 L524 374 H496 Z" fill="#161213"/>\n'
    '              <rect x="488" y="330" width="44" height="7" rx="3.5" fill="url(#bsiCxGold)"/>\n'
    '            \n'
    '              <!-- salon chair -->\n'
    '              <ellipse cx="370" cy="404" rx="54" ry="9" fill="#161213"/>\n'
    '              <rect x="364" y="342" width="12" height="62" fill="#3a2d31"/>\n'
    '              <rect x="404" y="358" width="42" height="8" rx="4" fill="#161213"/>\n'
    '              <rect x="312" y="210" width="30" height="118" rx="14" fill="#b3172b"/>\n'
    '              <rect x="316" y="318" width="116" height="28" rx="12" fill="#e8283f"/>\n'
    '            \n'
    '              <!-- guest -->\n'
    '              <g class="bsi-cx-guest">\n'
    '                <rect x="364" y="204" width="14" height="18" fill="#e3a888"/>\n'
    '                <path d="M336 230 Q372 212 406 230 L430 322 Q372 338 316 322 Z" fill="#fdf3ea" stroke="#efd1c6" stroke-width="2"/>\n'
    '                <path d="M348 246 L336 318 M372 238 L372 326 M396 246 L410 318" stroke="#e8283f" stroke-width="3" opacity=".35"/>\n'
    '                <circle cx="372" cy="184" r="26" fill="#eab494"/>\n'
    '                <path d="M346 186 Q344 154 372 152 Q398 153 401 174 Q386 164 372 168 Q356 171 353 198 Z" fill="#161213"/>\n'
    '                <path d="M347 182 Q338 206 352 216 L356 198 Z" fill="#161213"/>\n'
    '                <path d="M382 184 q5 -5 10 0" stroke="#161213" stroke-width="2.4" fill="none" stroke-linecap="round"/>\n'
    '                <path d="M385 198 q6 5 11 -1" stroke="#b3172b" stroke-width="2.2" fill="none" stroke-linecap="round"/>\n'
    '                <circle cx="392" cy="193" r="4.5" fill="#e8283f" opacity=".25"/>\n'
    '                <rect x="336" y="300" width="86" height="11" rx="5.5" fill="url(#bsiCxGold)"/>\n'
    '              </g>\n'
    '            \n'
    '              <!-- stylist -->\n'
    '              <rect x="212" y="300" width="16" height="90" rx="6" fill="#161213"/>\n'
    '              <rect x="236" y="300" width="16" height="90" rx="6" fill="#2a2023"/>\n'
    '              <ellipse cx="222" cy="393" rx="15" ry="6" fill="#161213"/>\n'
    '              <ellipse cx="249" cy="393" rx="15" ry="6" fill="#161213"/>\n'
    '              <path d="M206 224 Q200 256 198 282" stroke="#dba07e" stroke-width="10" fill="none" stroke-linecap="round"/>\n'
    '              <path d="M200 216 Q232 196 264 216 L270 306 Q232 316 194 306 Z" fill="#e8283f"/>\n'
    '              <path d="M208 236 H256 L262 308 Q232 316 202 308 Z" fill="#161213"/>\n'
    '              <rect x="222" y="262" width="22" height="14" rx="3" fill="url(#bsiCxGold)"/>\n'
    '              <path d="M226 262 V254 M232 262 V252 M238 262 V255" stroke="#fdf3ea" stroke-width="1.6" stroke-linecap="round"/>\n'
    '              <rect x="226" y="190" width="12" height="14" fill="#d3946f"/>\n'
    '              <circle cx="232" cy="170" r="24" fill="#dba07e"/>\n'
    '              <path d="M208 170 Q207 142 232 142 Q257 142 257 164 Q246 154 232 156 Q216 158 211 178 Z" fill="#161213"/>\n'
    '              <circle cx="226" cy="138" r="11" fill="#161213"/>\n'
    '              <path d="M214 132 L238 144" stroke="url(#bsiCxGold)" stroke-width="2.5" stroke-linecap="round"/>\n'
    '              <circle cx="243" cy="168" r="2.6" fill="#161213"/>\n'
    '              <path d="M241 180 q5 4 10 0" stroke="#b3172b" stroke-width="2" fill="none" stroke-linecap="round"/>\n'
    '              <circle cx="248" cy="176" r="4" fill="#e8283f" opacity=".22"/>\n'
    '            \n'
    "              <!-- stylist's cutting arm + scissors -->\n"
    '              <g>\n'
    '                <animateTransform attributeName="transform" type="rotate" values="-4 258 222;5 258 222;-4 258 222" dur="1.8s" repeatCount="indefinite" calcMode="spline" keySplines="0.45 0 0.55 1;0.45 0 0.55 1"/>\n'
    '                <path d="M258 222 Q290 214 314 198" stroke="#e8283f" stroke-width="13" fill="none" stroke-linecap="round"/>\n'
    '                <path d="M308 201 L330 184" stroke="#dba07e" stroke-width="9" fill="none" stroke-linecap="round"/>\n'
    '                <circle cx="333" cy="182" r="6.5" fill="#dba07e"/>\n'
    '                <g transform="translate(338 176)">\n'
    '                  <g>\n'
    '                    <animateTransform attributeName="transform" type="rotate" values="0;-18;0" dur=".6s" repeatCount="indefinite"/>\n'
    '                    <path d="M0 0 L28 -7" stroke="url(#bsiCxGold)" stroke-width="3.6" stroke-linecap="round"/>\n'
    '                    <circle cx="-6" cy="-4" r="4.5" fill="none" stroke="url(#bsiCxGold)" stroke-width="2.4"/>\n'
    '                  </g>\n'
    '                  <g>\n'
    '                    <animateTransform attributeName="transform" type="rotate" values="0;18;0" dur=".6s" repeatCount="indefinite"/>\n'
    '                    <path d="M0 0 L28 7" stroke="url(#bsiCxGold)" stroke-width="3.6" stroke-linecap="round"/>\n'
    '                    <circle cx="-6" cy="5" r="4.5" fill="none" stroke="url(#bsiCxGold)" stroke-width="2.4"/>\n'
    '                  </g>\n'
    '                  <circle cx="0" cy="0" r="2.4" fill="#161213"/>\n'
    '                </g>\n'
    '              </g>\n'
    '            \n'
    '              <!-- falling hair -->\n'
    '              <path class="bsi-cx-hair bsi-cx-hair--1" d="M356 170 q3 6 0 12" stroke="#161213" stroke-width="2.2" fill="none" stroke-linecap="round"/>\n'
    '              <path class="bsi-cx-hair bsi-cx-hair--2" d="M362 168 q-3 5 0 10" stroke="#161213" stroke-width="2" fill="none" stroke-linecap="round"/>\n'
    '              <path class="bsi-cx-hair bsi-cx-hair--3" d="M350 174 q4 5 1 11" stroke="#161213" stroke-width="2" fill="none" stroke-linecap="round"/>\n'
    '              <path class="bsi-cx-hair bsi-cx-hair--4" d="M366 172 q2 6 -1 11" stroke="#161213" stroke-width="1.8" fill="none" stroke-linecap="round"/>\n'
    '              <path class="bsi-cx-hair bsi-cx-hair--5" d="M358 176 q-3 5 1 10" stroke="#161213" stroke-width="2" fill="none" stroke-linecap="round"/>\n'
    '            \n'
    '              <!-- speech bubble -->\n'
    '              <g class="bsi-cx-bubble">\n'
    '                <rect x="62" y="70" width="166" height="54" rx="20" fill="#161213"/>\n'
    '                <path d="M196 122 L214 142 L208 120 Z" fill="#161213"/>\n'
    '                <text x="145" y="103" text-anchor="middle" font-family="Manrope, Arial, sans-serif" font-size="15" font-weight="800" fill="#fdf3ea">How can we help?</text>\n'
    '              </g>\n'
    '            \n'
    "              <!-- guest's typing dots -->\n"
    '              <g class="bsi-cx-think">\n'
    '                <rect x="352" y="104" width="58" height="28" rx="14" fill="#ffffff" stroke="#efd1c6" stroke-width="2"/>\n'
    '                <circle class="bsi-cx-dot bsi-cx-dot--1" cx="369" cy="118" r="3.6" fill="#e8283f"/>\n'
    '                <circle class="bsi-cx-dot bsi-cx-dot--2" cx="381" cy="118" r="3.6" fill="#e8283f"/>\n'
    '                <circle class="bsi-cx-dot bsi-cx-dot--3" cx="393" cy="118" r="3.6" fill="#e8283f"/>\n'
    '              </g>\n'
    '            \n'
    '              <!-- hearts + sparkles -->\n'
    '              <path class="bsi-cx-heart bsi-cx-heart--1" d="M410 160 c-3 -4 -9 -2 -9 2 c0 3 4 6 9 9 c5 -3 9 -6 9 -9 c0 -4 -6 -6 -9 -2 z" fill="#e8283f"/>\n'
    '              <path class="bsi-cx-heart bsi-cx-heart--2" d="M330 140 c-2.4 -3 -7 -1.6 -7 1.6 c0 2.4 3 4.8 7 7 c4 -2.2 7 -4.6 7 -7 c0 -3.2 -4.6 -4.6 -7 -1.6 z" fill="#c9a15a"/>\n'
    '              <path class="bsi-cx-spark bsi-cx-spark--1" d="M170 190 l3 8 l8 3 l-8 3 l-3 8 l-3 -8 l-8 -3 l8 -3 z" fill="#c9a15a"/>\n'
    '              <path class="bsi-cx-spark bsi-cx-spark--2" d="M300 128 l2.4 6 l6 2.4 l-6 2.4 l-2.4 6 l-2.4 -6 l-6 -2.4 l6 -2.4 z" fill="#e8283f"/>\n'
    '              <path class="bsi-cx-spark bsi-cx-spark--3" d="M520 120 l3 8 l8 3 l-8 3 l-3 8 l-3 -8 l-8 -3 l8 -3 z" fill="#c9a15a"/>\n'
    '              <path class="bsi-cx-spark bsi-cx-spark--4" d="M160 300 l2.4 6 l6 2.4 l-6 2.4 l-2.4 6 l-2.4 -6 l-6 -2.4 l6 -2.4 z" fill="#e8283f"/>\n'
    '            </svg>\n'
    '          </div>\n'
    '        </div>\n'
    '      </div>\n'
    '\n'
    '      <div class="bsi-cx-reach">\n'
    '        <a class="bsi-cx-reach__card" href="{{ bsiContact.phoneHref }}">\n'
    '          <span class="bsi-cx-reach__ico">&#9742;</span>\n'
    '          <span class="bsi-cx-reach__txt"><small>Call us</small><b>{{ bsiContact.phone }}</b><em>{{ bsiContact.hours }}</em></span>\n'
    '          <span class="bsi-cx-reach__go" aria-hidden="true">&rarr;</span>\n'
    '        </a>\n'
    '        <a class="bsi-cx-reach__card" href="{{ bsiContact.emailHref }}">\n'
    '          <span class="bsi-cx-reach__ico">&#9993;</span>\n'
    '          <span class="bsi-cx-reach__txt"><small>Email us</small><b>{{ bsiContact.email }}</b><em>We reply within a working day</em></span>\n'
    '          <span class="bsi-cx-reach__go" aria-hidden="true">&rarr;</span>\n'
    '        </a>\n'
    '        <button type="button" class="bsi-cx-reach__card bsi-cx-reach__card--dark" sc-camel-on-click="{{ goStores }}">\n'
    '          <span class="bsi-cx-reach__ico">&#8982;</span>\n'
    '          <span class="bsi-cx-reach__txt"><small>Visit a salon</small><b>{{ bsiContact.branchesLabel }}</b><em>{{ bsiContact.citiesLabel }} &middot; find the nearest</em></span>\n'
    '          <span class="bsi-cx-reach__go" aria-hidden="true">&rarr;</span>\n'
    '        </button>\n'
    '      </div>\n'
    '\n'
    '      <div class="bsi-ct-main">\n'
    '      <div class="bsi-ct bsi-cx-grid">\n'
    '        <div class="bsi-ct__form-card" id="bsiContactForm">\n'
    '          <sc-if value="{{ contactNotSent }}" hint-placeholder-val="{{ true }}">\n'
    '            <div>\n'
    '              <div class="bsi-ct__form-head">\n'
    '                <div>\n'
    '                  <h2 class="bsi-ct__title">Send us a message</h2>\n'
    '                  <p class="bsi-ct__lead">We reply within one working day.</p>\n'
    '                </div>\n'
    '                <div class="bsi-ct__ring" style="--p:{{ contactProgress.pct }};"><span>{{ contactProgress.pct }}%</span></div>\n'
    '              </div>\n'
    '              <div class="bsi-ct__progress">\n'
    '                <sc-for list="{{ contactProgress.steps }}" as="st" hint-placeholder-count="4">\n'
    '                  <span class="{{ st.cls }}"><i>{{ st.n }}</i>{{ st.label }}</span>\n'
    '                </sc-for>\n'
    '              </div>\n'
    '              <form sc-camel-on-submit="{{ sendContact }}" class="bsi-ct__form" novalidate>\n'
    '                <div class="bsi-ct__topics" role="group" aria-label="What is it about?">\n'
    '                  <sc-for list="{{ contactTopics }}" as="t" hint-placeholder-count="4">\n'
    '                    <button type="button" class="{{ t.cls }}" sc-camel-on-click="{{ t.onClick }}">{{ t.label }}</button>\n'
    '                  </sc-for>\n'
    '                </div>\n'
    '                <label class="{{ contactFieldCls.name }}"><span>Your name</span><input name="name" autocomplete="name" placeholder="e.g. Priya Shah" class="bsi-ct__input" maxlength="80" sc-camel-on-input="{{ contactOnName }}"><i class="bsi-ct__ok">✓</i></label>\n'
    '                <div class="bsi-ct__two">\n'
    '                  <label class="{{ contactFieldCls.email }}"><span>Email</span><input name="email" type="email" autocomplete="email" placeholder="you@example.com" class="bsi-ct__input" maxlength="120" sc-camel-on-input="{{ contactOnEmail }}"><i class="bsi-ct__ok">✓</i></label>\n'
    '                  <label class="{{ contactFieldCls.phone }}"><span>Phone <em>(optional)</em></span><input name="phone" type="tel" autocomplete="tel" placeholder="+91 98765 43210" class="bsi-ct__input" maxlength="20" sc-camel-on-input="{{ contactOnPhone }}"><i class="bsi-ct__ok">✓</i></label>\n'
    '                </div>\n'
    '                <div class="bsi-cf-row">\n'
    '                  <div class="bsi-cf-field">\n'
    '                    <span class="bsi-cf-cap">City</span>\n'
    '                    <button type="button" class="{{ contactCityBtnCls }}" sc-camel-on-click="{{ contactToggleCity }}" aria-haspopup="listbox"><span class="bsi-cf-value">{{ contactCityLabel }}</span><span class="bsi-cf-caret" aria-hidden="true"></span></button>\n'
    '                    <sc-if value="{{ contactCityOpen }}" hint-placeholder-val="{{ false }}">\n'
    '                      <div class="bsi-cf-menu" role="listbox">\n'
    '                        <sc-for list="{{ contactCityOptions }}" as="o" hint-placeholder-count="6">\n'
    '                          <button type="button" class="{{ o.cls }}" sc-camel-on-click="{{ o.onClick }}" role="option"><span>{{ o.name }}</span><small>{{ o.meta }}</small></button>\n'
    '                        </sc-for>\n'
    '                      </div>\n'
    '                    </sc-if>\n'
    '                  </div>\n'
    '                  <div class="bsi-cf-field">\n'
    '                    <span class="bsi-cf-cap">Salon</span>\n'
    '                    <button type="button" class="{{ contactBranchBtnCls }}" sc-camel-on-click="{{ contactToggleBranch }}" aria-haspopup="listbox"><span class="bsi-cf-value">{{ contactBranchLabel }}</span><span class="bsi-cf-caret" aria-hidden="true"></span></button>\n'
    '                    <sc-if value="{{ contactBranchOpen }}" hint-placeholder-val="{{ false }}">\n'
    '                      <div class="bsi-cf-menu" role="listbox">\n'
    '                        <sc-for list="{{ contactBranchOptions }}" as="o" hint-placeholder-count="4">\n'
    '                          <button type="button" class="{{ o.cls }}" sc-camel-on-click="{{ o.onClick }}" role="option"><span>{{ o.name }}</span><small>{{ o.meta }}</small></button>\n'
    '                        </sc-for>\n'
    '                      </div>\n'
    '                    </sc-if>\n'
    '                  </div>\n'
    '                </div>\n'
    '                <sc-if value="{{ contactMenuOpen }}" hint-placeholder-val="{{ false }}"><div class="bsi-cf-backdrop" sc-camel-on-click="{{ contactCloseMenus }}"></div></sc-if>\n'
    '                <label class="{{ contactFieldCls.message }}"><span>Message <em class="bsi-ct__count">{{ contactMsgCount }}/500</em></span><textarea name="message" placeholder="How can we help?" rows="5" maxlength="500" class="bsi-ct__input bsi-ct__textarea" sc-camel-on-input="{{ contactOnMsg }}"></textarea></label>\n'
    '                <sc-if value="{{ contactHasError }}" hint-placeholder-val="{{ false }}"><div class="bsi-cf-error" role="alert">{{ contactError }}</div></sc-if>\n'
    '                <button type="submit" class="{{ contactSubmitCls }}" disabled="{{ contactSending }}"><span>{{ contactSendLabel }}</span><i aria-hidden="true">→</i></button>\n'
    '                <p class="bsi-ct__fine">🔒 By sending, you agree we may contact you about this enquiry. We never share your details.</p>\n'
    '              </form>\n'
    '            </div>\n'
    '          </sc-if>\n'
    '          <sc-if value="{{ contactSent }}" hint-placeholder-val="{{ false }}">\n'
    '            <div class="bsi-ct__done">\n'
    '              <div class="bsi-ct__done-ico">✓</div>\n'
    '              <h2 class="bsi-ct__title">We\'ll be in touch.</h2>\n'
    '              <p class="bsi-ct__lead">{{ contactSentNote }}</p>\n'
    '              <div class="bsi-ct__bactions bsi-ct__bactions--center">\n'
    '                <button type="button" class="bsi-ct__btn bsi-ct__btn--ghost-dark" sc-camel-on-click="{{ contactReset }}">Send another message</button>\n'
    '                <button type="button" class="bsi-ct__btn" sc-camel-on-click="{{ goBookingNav }}">Book an appointment →</button>\n'
    '              </div>\n'
    '            </div>\n'
    '          </sc-if>\n'
    '        </div>\n'
    '        <aside class="bsi-ct__info">\n'
    '          <div class="{{ contactBranchCardCls }}">\n'
    '            <sc-if value="{{ contactHasBranch }}" hint-placeholder-val="{{ false }}">\n'
    '              <div>\n'
    '                <div class="bsi-ct__bhead">\n'
    '                  <div>\n'
    '                    <div class="bsi-ct__kicker bsi-ct__kicker--gold">Your salon</div>\n'
    '                    <div class="bsi-ct__bname">Enrich {{ contactBranch.name }}</div>\n'
    '                    <div class="bsi-ct__bcity">{{ contactBranch.city }}</div>\n'
    '                  </div>\n'
    '                  <span class="{{ contactBranchExtra.openCls }}"><i></i>{{ contactBranchExtra.openLabel }}</span>\n'
    '                </div>\n'
    '                <sc-if value="{{ contactBranchExtra.hasMap }}" hint-placeholder-val="{{ false }}">\n'
    '                  <div class="bsi-ct__map"><iframe title="Map of the salon" src="{{ contactBranchExtra.mapEmbed }}" loading="lazy"></iframe></div>\n'
    '                </sc-if>\n'
    '                <ul class="bsi-ct__facts">\n'
    '                  <sc-if value="{{ contactBranch.area }}" hint-placeholder-val="{{ true }}"><li><span>Address</span><b>{{ contactBranch.area }}</b></li></sc-if>\n'
    '                  <sc-if value="{{ contactBranch.hours }}" hint-placeholder-val="{{ true }}"><li><span>Hours</span><b>{{ contactBranch.hours }}</b></li></sc-if>\n'
    '                  <sc-if value="{{ contactBranch.phone }}" hint-placeholder-val="{{ true }}"><li><span>Phone</span><b><a href="{{ contactBranch.telHref }}">{{ contactBranch.phone }}</a></b></li></sc-if>\n'
    '                  <li><span>Rating</span><b>★ {{ contactBranch.rating }}</b></li>\n'
    '                </ul>\n'
    '                <div class="bsi-ct__bactions">\n'
    '                  <a class="bsi-ct__btn bsi-ct__btn--ghost" href="{{ contactBranch.mapHref }}" target="_blank" rel="noopener">Get directions</a>\n'
    '                  <button type="button" class="bsi-ct__btn" sc-camel-on-click="{{ contactBookBranch }}">Book here →</button>\n'
    '                </div>\n'
    '              </div>\n'
    '            </sc-if>\n'
    '            <sc-if value="{{ contactNoBranch }}" hint-placeholder-val="{{ true }}">\n'
    '              <div class="bsi-ct__empty">\n'
    '                <span class="bsi-ct__empty-ico">⌖</span>\n'
    '                <b>Pick your city and salon</b>\n'
    "                <small>Choose them in the form and your salon's map, hours and directions appear here.</small>\n"
    '              </div>\n'
    '            </sc-if>\n'
    '          </div>\n'
    '\n'
    '          <ol class="bsi-ct__steps">\n'
    '            <li><b>1</b><span>Your message goes straight to the salon you pick.</span></li>\n'
    '            <li><b>2</b><span>We reply by email or phone within one working day.</span></li>\n'
    '            <li><b>3</b><span>Ready to book? We hold your chair for you.</span></li>\n'
    '          </ol>\n'
    '        </aside>\n'
    '\n'
    '      </div>\n'
    '      </div>\n'
    '\n'
    '      <div class="bsi-ct-more">\n'
    '        <div class="bsi-ct-more__head">\n'
    '          <div class="bsi-ct__kicker bsi-ct__kicker--gold">Quick answers</div>\n'
    '          <h2 class="bsi-ct-more__title">Maybe you don\'t need to wait for a reply.</h2>\n'
    '        </div>\n'
    '        <div class="bsi-ct-more__grid">\n'
    '          <div class="bsi-ct-faq">\n'
    '            <sc-for list="{{ contactFaq }}" as="q" hint-placeholder-count="5">\n'
    '              <div class="{{ q.cls }}">\n'
    '                <button type="button" class="bsi-ct-faq__q" sc-camel-on-click="{{ q.onClick }}"><span>{{ q.q }}</span><i aria-hidden="true"></i></button>\n'
    '                <sc-if value="{{ q.open }}" hint-placeholder-val="{{ false }}"><div class="bsi-ct-faq__a">{{ q.a }}</div></sc-if>\n'
    '              </div>\n'
    '            </sc-for>\n'
    '          </div>\n'
    '          <div class="bsi-ct-tiles">\n'
    '            <button type="button" class="bsi-ct-tile" sc-camel-on-click="{{ goBookingNav }}"><span class="bsi-ct-tile__ico">✂</span><b>Book an appointment</b><small>Pick a salon, artist and time in under a minute.</small><em>Book now →</em></button>\n'
    '            <a class="bsi-ct-tile" href="/my/appointments"><span class="bsi-ct-tile__ico">▤</span><b>My appointments</b><small>See, review or follow up on your visits.</small><em>Open →</em></a>\n'
    '            <button type="button" class="bsi-ct-tile bsi-ct-tile--dark" sc-camel-on-click="{{ goMembership }}"><span class="bsi-ct-tile__ico">♛</span><b>Membership &amp; gift cards</b><small>Save on every visit, or gift a treatment.</small><em>Explore →</em></button>\n'
    '          </div>\n'
    '        </div>\n'
    '      </div>\n'
    '    </section>'
)


BLOCK_PATCHES = (
    ('testimonials redesign', 'Loved across India</h2>', '<section', '</section>', TESTIMONIALS_DST),
    ('transformations redesign', 'Transformations</h2>', '<section', '</section>', TRANSFORMATIONS_DST),
    ('footer redesign', '<footer style="background:#0d0d0d', '<footer', '</footer>', FOOTER_DST),
    ('contact page redesign', '<section data-screen-label="Contact">', '<section', '</section>', CONTACT_SECTION_DST),
)


def apply_block_patch(page, anchor, open_tag, close_tag, replacement):
    """Replace the element that encloses `anchor`; None if it can't be located."""
    at = page.find(anchor)
    if at == -1:
        return None
    start = page.rfind(open_tag, 0, at + len(open_tag))
    end = page.find(close_tag, at)
    if start == -1 or end == -1:
        return None
    return page[:start] + replacement + page[end + len(close_tag):]
