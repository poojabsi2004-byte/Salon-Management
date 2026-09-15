(function () {
    "use strict";

    // Odoo's frontend JS often loads in a deferred "lazy" bundle fetched
    // after the initial page load, so DOMContentLoaded may have already
    // fired by the time this file executes — a plain listener would then
    // never run. Init immediately if the document is already ready.
    function bsiOnReady(fn) {
        if (document.readyState === "loading") {
            document.addEventListener("DOMContentLoaded", fn);
        } else {
            fn();
        }
    }

    bsiOnReady(function () {
        var root = document.getElementById("bsi-salon-root");
        if (!root) {
            return;
        }

        bsiInitThemeToggle();
        bsiInitNavbar();
        bsiInitScrollReveal(root);
        bsiInitTestimonialCarousel();
        bsiInitOffersFilter();
        bsiInitBillingToggle();
        bsiInitMembershipCta();
        bsiInitStoresSelector();
        bsiInitStoresMap();
        bsiInitShopSort();
        bsiInitShopCart();
        bsiInitBookingWizard();
        bsiInitScrollProgress();
        bsiInitSplitWords(root);
        bsiInitCounters(root);
        bsiInitMotionExtras(root);
        bsiInitHeroScrollCue();
        bsiInitFooterToTop();
    });

    /* ── Hero scroll cue: smooth-scrolls to the "Why Enrich" section ── */
    function bsiInitHeroScrollCue() {
        var cue = document.querySelector(".bsi-hero__scroll-cue");
        if (!cue) {
            return;
        }
        cue.addEventListener("click", function (e) {
            var target = document.querySelector(cue.getAttribute("href"));
            if (!target) {
                return;
            }
            e.preventDefault();
            target.scrollIntoView({ behavior: bsiPrefersReducedMotion() ? "auto" : "smooth", block: "start" });
        });
    }

    /* ── Footer "back to top" ── */
    function bsiInitFooterToTop() {
        var btn = document.getElementById("bsiFooterToTop");
        if (!btn) {
            return;
        }
        btn.addEventListener("click", function () {
            window.scrollTo({ top: 0, behavior: bsiPrefersReducedMotion() ? "auto" : "smooth" });
        });
    }

    /* Shared guard: skip decorative, non-essential motion for users who asked
       for reduced motion, and skip pointer-follow effects on touch devices. */
    function bsiPrefersReducedMotion() {
        return window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    }
    function bsiHasFinePointer() {
        return window.matchMedia && window.matchMedia("(pointer: fine)").matches;
    }

    /* ── Slim reading-progress bar under the navbar ── */
    function bsiInitScrollProgress() {
        var bar = document.getElementById("bsiProgressBar");
        if (!bar) {
            return;
        }
        var ticking = false;
        function update() {
            var doc = document.documentElement;
            var max = doc.scrollHeight - doc.clientHeight;
            var ratio = max > 0 ? Math.min(1, Math.max(0, doc.scrollTop / max)) : 0;
            bar.style.transform = "scaleX(" + ratio + ")";
            ticking = false;
        }
        window.addEventListener("scroll", function () {
            if (!ticking) {
                window.requestAnimationFrame(update);
                ticking = true;
            }
        }, { passive: true });
        update();
    }

    /* ── Break hero-style headings into per-word spans for a staggered
       reveal, without needing hand-authored markup in every template. ── */
    function bsiInitSplitWords(root) {
        var targets = root.querySelectorAll("[data-split-words]");
        targets.forEach(function (el) {
            if (el.getAttribute("data-split-done")) {
                return;
            }
            var words = el.textContent.trim().split(/\s+/);
            el.textContent = "";
            words.forEach(function (word, i) {
                var wrap = document.createElement("span");
                wrap.className = "bsi-split-word";
                var inner = document.createElement("span");
                inner.style.setProperty("--bsi-word-i", i);
                inner.textContent = word;
                wrap.appendChild(inner);
                el.appendChild(wrap);
                el.appendChild(document.createTextNode(" "));
            });
            el.setAttribute("data-split-done", "1");
        });
    }

    /* ── Count-up numbers once their stat card scrolls into view ── */
    function bsiInitCounters(root) {
        var counters = root.querySelectorAll(".bsi-counter[data-count]");
        if (!counters.length) {
            return;
        }
        var reduced = bsiPrefersReducedMotion();
        function run(el) {
            var raw = el.getAttribute("data-count");
            var target = parseFloat(raw);
            var suffix = el.getAttribute("data-suffix") || "";
            // Preserve decimal precision for targets like "4.8" — rounding
            // to a whole number would count up to the wrong final figure.
            var decimals = (raw.split(".")[1] || "").length;
            if (reduced || !("IntersectionObserver" in window) || isNaN(target)) {
                el.textContent = target.toFixed(decimals) + suffix;
                return;
            }
            var duration = 1400;
            var start = null;
            function step(ts) {
                if (start === null) { start = ts; }
                var progress = Math.min(1, (ts - start) / duration);
                var eased = 1 - Math.pow(1 - progress, 3);
                var value = decimals ? (target * eased).toFixed(decimals) : Math.round(target * eased);
                el.textContent = value + suffix;
                if (progress < 1) {
                    window.requestAnimationFrame(step);
                }
            }
            window.requestAnimationFrame(step);
        }
        if (!("IntersectionObserver" in window)) {
            counters.forEach(run);
            return;
        }
        var observer = new IntersectionObserver(function (entries) {
            entries.forEach(function (entry) {
                if (entry.isIntersecting) {
                    run(entry.target);
                    observer.unobserve(entry.target);
                }
            });
        }, { threshold: 0.5 });
        counters.forEach(function (el) { observer.observe(el); });
    }

    /* ── Cursor spotlight, magnetic buttons, pointer-tilt cards and a light
       hero parallax. All are motion-safe, opt out on touch devices /
       reduced-motion, and are purely decorative — the page works fully
       without them. ── */
    function bsiInitMotionExtras(root) {
        if (bsiPrefersReducedMotion()) {
            return;
        }

        // Spotlight glow that tracks the pointer within `.bsi-spotlight` blocks.
        if (bsiHasFinePointer()) {
            root.querySelectorAll(".bsi-spotlight").forEach(function (el) {
                el.addEventListener("pointermove", function (e) {
                    var rect = el.getBoundingClientRect();
                    el.style.setProperty("--bsi-spot-x", (e.clientX - rect.left) + "px");
                    el.style.setProperty("--bsi-spot-y", (e.clientY - rect.top) + "px");
                });
            });

            // Magnetic pull toward the pointer, clamped to a small radius.
            root.querySelectorAll(".bsi-magnetic").forEach(function (el) {
                var strength = 14;
                el.addEventListener("pointermove", function (e) {
                    var rect = el.getBoundingClientRect();
                    var relX = (e.clientX - rect.left) / rect.width - 0.5;
                    var relY = (e.clientY - rect.top) / rect.height - 0.5;
                    el.style.transform = "translate(" + (relX * strength).toFixed(1) + "px, " + (relY * strength).toFixed(1) + "px)";
                });
                el.addEventListener("pointerleave", function () {
                    el.style.transform = "";
                });
            });

            // Pointer-tilt on the "Why Enrich" glass cards: a small perspective
            // rotation that follows the cursor, on top of the existing lift.
            root.querySelectorAll(".bsi-why-glass-card").forEach(function (card) {
                var strength = 8; // max degrees of rotation
                card.addEventListener("pointerenter", function () {
                    card.classList.add("bsi-why-glass-card--tilting");
                });
                card.addEventListener("pointermove", function (e) {
                    var rect = card.getBoundingClientRect();
                    var relX = (e.clientX - rect.left) / rect.width - 0.5;
                    var relY = (e.clientY - rect.top) / rect.height - 0.5;
                    card.style.transform = "perspective(900px) rotateX(" + (-relY * strength).toFixed(2)
                        + "deg) rotateY(" + (relX * strength).toFixed(2) + "deg) translateY(-6px)";
                });
                card.addEventListener("pointerleave", function () {
                    card.classList.remove("bsi-why-glass-card--tilting");
                    card.style.transform = "";
                });
            });

            // Same pointer-tilt pattern, applied to the booking wizard's chair
            // image so it reads as a real 3D object following the cursor
            // instead of the plain CSS-only hover tilt it had before.
            root.querySelectorAll(".bsi-chair").forEach(function (chair) {
                var img = chair.querySelector(".bsi-chair__img");
                if (!img) {
                    return;
                }
                var strength = 16; // max degrees of rotation
                chair.addEventListener("pointerenter", function () {
                    chair.classList.add("bsi-chair--tilting");
                });
                chair.addEventListener("pointermove", function (e) {
                    var rect = chair.getBoundingClientRect();
                    var relX = (e.clientX - rect.left) / rect.width - 0.5;
                    var relY = (e.clientY - rect.top) / rect.height - 0.5;
                    img.style.transform = "perspective(700px) rotateX(" + (-relY * strength).toFixed(2)
                        + "deg) rotateY(" + (relX * strength).toFixed(2) + "deg) scale(1.06)";
                });
                chair.addEventListener("pointerleave", function () {
                    chair.classList.remove("bsi-chair--tilting");
                    img.style.transform = "";
                });
            });
        }

        // Subtle hero background parallax, driven by rAF-throttled scroll.
        // Skipped when GSAP + ScrollTrigger are present: bsi_salon_theme_motion.js
        // drives the same element with a scrubbed GSAP tween instead, and the two
        // must not both write to its transform on every scroll frame.
        var heroBg = root.querySelector(".bsi-hero__bg");
        if (heroBg && !(window.gsap && window.ScrollTrigger)) {
            var ticking = false;
            var update = function () {
                var offset = Math.min(window.scrollY * 0.15, 120);
                heroBg.style.transform = "translate3d(0," + offset + "px,0)";
                ticking = false;
            };
            window.addEventListener("scroll", function () {
                if (!ticking) {
                    window.requestAnimationFrame(update);
                    ticking = true;
                }
            }, { passive: true });
        }
    }

    /* ── Stores: mini-map pin → rail scroll sync ── */
    function bsiInitStoresMap() {
        var map = document.querySelector(".bsi-mini-map");
        if (!map) {
            return;
        }
        map.querySelectorAll("[data-loc-id]").forEach(function (pin) {
            pin.addEventListener("click", function (e) {
                var target = document.getElementById("loc-" + pin.getAttribute("data-loc-id"));
                if (target) {
                    e.preventDefault();
                    target.scrollIntoView({ behavior: "smooth", block: "nearest" });
                    target.style.outline = "2px solid var(--bsi-accent)";
                    setTimeout(function () { target.style.outline = ""; }, 1200);
                }
            });
        });
    }

    /* ── Booking wizard: city → store → services → chairs → date/time → confirm ── */
    function bsiInitBookingWizard() {
        var form = document.getElementById("bsiBookingWizard");
        if (!form) {
            return;
        }
        var steps = form.querySelectorAll(".bsi-booking-step");
        var panels = form.querySelectorAll(".bsi-booking-panel");
        var backBtn = document.getElementById("bsiBookingBack");
        var state = {
            city: null, locationId: null, locationName: null,
            services: [], chairs: [],
            artistId: null, artistName: "No preference", artistCharge: 0,
            date: null, useSlot: false, slotId: null, slotLabel: null, customTime: null
        };
        var current = 1;
        var maxReached = 1;

        var stepProgressFill = document.getElementById("bsiStepProgressFill");
        var stepCurrentEl = document.getElementById("bsiStepCurrent");
        var stepNameEl = document.getElementById("bsiStepName");

        function goTo(n) {
            current = n;
            maxReached = Math.max(maxReached, n);
            var activeStep = null;
            steps.forEach(function (s) {
                var sn = parseInt(s.getAttribute("data-step"), 10);
                s.classList.toggle("bsi-booking-step--active", sn === n);
                s.classList.toggle("bsi-booking-step--done", sn < n);
                s.classList.toggle("bsi-booking-step--reachable", sn <= maxReached);
                if (sn === n) {
                    activeStep = s;
                }
            });
            panels.forEach(function (p) {
                p.classList.toggle("bsi-booking-panel--active", parseInt(p.getAttribute("data-panel"), 10) === n);
            });
            backBtn.style.display = n > 1 ? "" : "none";
            if (stepProgressFill) {
                stepProgressFill.style.width = (n / steps.length * 100) + "%";
            }
            if (stepCurrentEl) {
                stepCurrentEl.textContent = n;
            }
            if (stepNameEl && activeStep) {
                var numberSpan = activeStep.querySelector("span");
                stepNameEl.textContent = activeStep.textContent.replace(numberSpan ? numberSpan.textContent : "", "").trim();
            }
        }

        // Step circles: jump straight to any step already reached (back, or
        // forward again to one visited earlier) — steps beyond that stay
        // inert since each step's own "Continue" gate still has to be cleared.
        steps.forEach(function (s) {
            s.addEventListener("click", function () {
                var sn = parseInt(s.getAttribute("data-step"), 10);
                if (sn <= maxReached && sn !== current) {
                    goTo(sn);
                }
            });
        });

        backBtn.addEventListener("click", function () { if (current > 1) { goTo(current - 1); } });
        goTo(1); // normalizes classes (incl. the new --reachable marker) to match the template's static initial state

        function formatCurrency(amount) {
            return "₹" + Math.round(amount).toLocaleString("en-IN");
        }

        function serviceTotal() {
            return state.services.reduce(function (sum, s) { return sum + s.price; }, 0) + (state.artistCharge || 0);
        }

        // Step 1: city
        form.querySelectorAll('[data-panel="1"] .bsi-city-card').forEach(function (btn) {
            btn.addEventListener("click", function () {
                form.querySelectorAll('[data-panel="1"] .bsi-city-card').forEach(function (b) {
                    b.classList.remove("bsi-city-card--selected");
                });
                btn.classList.add("bsi-city-card--selected");
                state.city = btn.getAttribute("data-city");
                form.querySelectorAll(".bsi-booking-store").forEach(function (store) {
                    store.style.display = store.getAttribute("data-city") === state.city ? "" : "none";
                });
                goTo(2);
            });
        });

        // Step 2: store
        form.querySelectorAll(".bsi-booking-store").forEach(function (btn) {
            btn.addEventListener("click", function () {
                form.querySelectorAll(".bsi-booking-store").forEach(function (b) {
                    b.classList.remove("bsi-booking-store--selected");
                });
                btn.classList.add("bsi-booking-store--selected");
                state.locationId = btn.getAttribute("data-loc-id");
                state.locationName = btn.querySelector(".bsi-booking-store__name").textContent;
                document.getElementById("bsiBookingLocationId").value = state.locationId;
                filterChairs();
                filterArtists();
                goTo(3);
            });
        });

        // Step 3: services (multi-select, with a category filter, a text search and
        // a running total). The list itself lives in a dropdown that only opens once
        // the user actually starts browsing/searching, rather than always being fully
        // expanded — picks collapse into removable chips above the total instead.
        var servicePicker = document.getElementById("bsiBookingServicePicker");
        var serviceFilterBar = document.getElementById("bsiBookingServiceFilter");
        var serviceSearchInput = document.getElementById("bsiBookingServiceSearch");
        var serviceDropdown = document.getElementById("bsiBookingServiceDropdown");
        var serviceGrid = document.getElementById("bsiBookingServiceGrid");
        var serviceNext = document.getElementById("bsiServiceNext");
        var serviceTotalEl = document.getElementById("bsiServiceTotal");
        var selectedServiceChipsEl = document.getElementById("bsiSelectedServiceChips");
        var serviceCards = serviceGrid ? serviceGrid.querySelectorAll(".bsi-svc-check") : [];
        var activeServiceCategory = "all";

        function updateServiceTotal() {
            var total = serviceTotal();
            if (serviceTotalEl) {
                serviceTotalEl.textContent = formatCurrency(total);
            }
            var summaryTotal = document.getElementById("bsiSummaryTotal");
            if (summaryTotal) {
                summaryTotal.textContent = formatCurrency(total);
            }
        }

        function applyServiceFilters() {
            var query = serviceSearchInput ? serviceSearchInput.value.trim().toLowerCase() : "";
            serviceCards.forEach(function (card) {
                var matchesCategory = activeServiceCategory === "all" || card.getAttribute("data-cat") === activeServiceCategory;
                var matchesQuery = !query || (card.getAttribute("data-name") || "").indexOf(query) !== -1;
                card.style.display = (matchesCategory && matchesQuery) ? "" : "none";
            });
        }

        function openServiceDropdown() {
            if (serviceDropdown) {
                serviceDropdown.classList.add("bsi-svc-dropdown--open");
            }
        }
        function closeServiceDropdown() {
            if (serviceDropdown) {
                serviceDropdown.classList.remove("bsi-svc-dropdown--open");
            }
        }

        function renderServiceChips() {
            if (!selectedServiceChipsEl) {
                return;
            }
            selectedServiceChipsEl.textContent = "";
            state.services.forEach(function (s) {
                var chip = document.createElement("span");
                chip.className = "bsi-svc-chip";
                var label = document.createElement("span");
                label.textContent = s.name;
                var remove = document.createElement("span");
                remove.className = "bsi-svc-chip__remove";
                remove.textContent = "✕";
                remove.setAttribute("role", "button");
                remove.setAttribute("aria-label", "Remove " + s.name);
                remove.addEventListener("click", function () {
                    var card = serviceGrid && serviceGrid.querySelector('.bsi-svc-check[data-service-id="' + s.id + '"]');
                    if (card) {
                        card.click();
                    }
                });
                chip.appendChild(label);
                chip.appendChild(remove);
                selectedServiceChipsEl.appendChild(chip);
            });
        }

        if (serviceFilterBar) {
            serviceFilterBar.querySelectorAll(".bsi-filter-btn").forEach(function (btn) {
                btn.addEventListener("click", function () {
                    serviceFilterBar.querySelectorAll(".bsi-filter-btn").forEach(function (b) {
                        b.classList.remove("bsi-filter-btn--active");
                    });
                    btn.classList.add("bsi-filter-btn--active");
                    activeServiceCategory = btn.getAttribute("data-cat");
                    applyServiceFilters();
                    openServiceDropdown();
                });
            });
        }
        if (serviceSearchInput) {
            serviceSearchInput.addEventListener("focus", openServiceDropdown);
            serviceSearchInput.addEventListener("input", function () {
                applyServiceFilters();
                openServiceDropdown();
            });
            serviceSearchInput.addEventListener("keydown", function (e) {
                if (e.key === "Escape") {
                    closeServiceDropdown();
                    serviceSearchInput.blur();
                }
            });
        }
        document.addEventListener("click", function (e) {
            if (servicePicker && !servicePicker.contains(e.target)) {
                closeServiceDropdown();
            }
        });
        serviceCards.forEach(function (card) {
            card.addEventListener("click", function () {
                var id = card.getAttribute("data-service-id");
                var selected = card.classList.toggle("bsi-svc-check--selected");
                if (selected) {
                    state.services.push({
                        id: id,
                        name: card.querySelector(".bsi-svc-check__name").textContent,
                        price: parseFloat(card.getAttribute("data-price")) || 0
                    });
                } else {
                    state.services = state.services.filter(function (s) { return s.id !== id; });
                }
                document.getElementById("bsiBookingServiceIds").value = state.services.map(function (s) { return s.id; }).join(",");
                if (serviceNext) {
                    serviceNext.toggleAttribute("disabled", state.services.length === 0);
                }
                updateServiceTotal();
                renderServiceChips();
                filterChairs();
            });
        });
        if (serviceNext) {
            serviceNext.addEventListener("click", function () { goTo(4); });
        }

        // Step 4: chairs (multi-select — one per service type booked at once — filtered
        // by the selected branch and the categories of the selected services)
        var chairNext = document.getElementById("bsiChairNext");
        var chairCards = form.querySelectorAll(".bsi-chair");

        function filterChairs() {
            var categories = {};
            serviceCards.forEach(function (card) {
                if (card.classList.contains("bsi-svc-check--selected")) {
                    categories[card.getAttribute("data-cat")] = true;
                }
            });
            var hasCategories = Object.keys(categories).length > 0;
            chairCards.forEach(function (chair) {
                var matchesLocation = !state.locationId || chair.getAttribute("data-location") === state.locationId;
                var matchesCategory = !hasCategories || categories[chair.getAttribute("data-category")];
                var visible = matchesLocation && matchesCategory;
                chair.style.display = visible ? "" : "none";
                if (!visible && chair.classList.contains("bsi-chair--selected")) {
                    chair.classList.remove("bsi-chair--selected");
                    onChairToggle(chair, false);
                }
            });
        }

        function onChairToggle(chair, selected) {
            var id = chair.getAttribute("data-chair-id");
            if (selected) {
                state.chairs.push({ id: id, label: chair.querySelector(".bsi-chair__label").textContent });
            } else {
                state.chairs = state.chairs.filter(function (c) { return c.id !== id; });
            }
            document.getElementById("bsiBookingChairIds").value = state.chairs.map(function (c) { return c.id; }).join(",");
            if (chairNext) {
                chairNext.toggleAttribute("disabled", state.chairs.length === 0);
            }
            // Chair availability is now part of the slot-availability preview (see
            // refreshSlotAvailability below) — re-check in case the user already
            // picked a date and is coming back to change chairs via the step nav.
            refreshSlotAvailability();
        }

        chairCards.forEach(function (chair) {
            chair.addEventListener("click", function () {
                if (chair.classList.contains("bsi-chair--booked")) {
                    return; // already booked for the chosen date/slot — see refreshResourceAvailability
                }
                var selected = chair.classList.toggle("bsi-chair--selected");
                onChairToggle(chair, selected);
            });
        });
        if (chairNext) {
            chairNext.addEventListener("click", function () { goTo(5); });
        }

        // Step 5: stylist (single-select, optional — "No preference" is valid and
        // pre-selected; picking a stylist may add their flat ₹ surcharge to the total)
        var artistGrid = document.getElementById("bsiBookingArtistGrid");
        var artistCards = artistGrid ? artistGrid.querySelectorAll(".bsi-artist-check") : [];
        var artistNext = document.getElementById("bsiArtistNext");
        var artistSearchInput = document.getElementById("bsiBookingArtistSearch");
        var artistSearchQuery = "";

        function selectArtist(card) {
            artistCards.forEach(function (c) { c.classList.remove("bsi-artist-check--selected"); });
            card.classList.add("bsi-artist-check--selected");
            state.artistId = card.getAttribute("data-artist-id") || null;
            state.artistName = card.querySelector(".bsi-artist-check__name").textContent;
            state.artistCharge = parseFloat(card.getAttribute("data-charge")) || 0;
            document.getElementById("bsiBookingArtistId").value = state.artistId || "";
            updateServiceTotal();
            // A specific artist only conflicts with themself (see refreshSlotAvailability
            // below), so switching artists can change which slots are actually available —
            // re-check in case a date was already picked (e.g. coming back via the step nav).
            refreshSlotAvailability();
        }

        // Location visibility and the search box both filter the same list —
        // combined here so neither one clobbers the other's hidden cards.
        function filterArtists() {
            artistCards.forEach(function (card) {
                if (card.getAttribute("data-artist-id") === "") {
                    return; // "No preference" is always available
                }
                var loc = card.getAttribute("data-location");
                var matchesLocation = !loc || !state.locationId || loc === state.locationId;
                var matchesQuery = !artistSearchQuery || (card.getAttribute("data-name") || "").indexOf(artistSearchQuery) !== -1;
                var visible = matchesLocation && matchesQuery;
                card.style.display = visible ? "" : "none";
                if (!visible && card.classList.contains("bsi-artist-check--selected") && artistCards.length) {
                    selectArtist(artistCards[0]);
                }
            });
        }

        if (artistSearchInput) {
            artistSearchInput.addEventListener("input", function () {
                artistSearchQuery = artistSearchInput.value.trim().toLowerCase();
                filterArtists();
            });
        }
        artistCards.forEach(function (card) {
            card.addEventListener("click", function () {
                if (card.classList.contains("bsi-artist-check--booked")) {
                    return; // already booked for the chosen date/slot — see refreshResourceAvailability
                }
                selectArtist(card);
            });
        });
        if (artistNext) {
            artistNext.addEventListener("click", function () { goTo(6); });
        }

        // Step 6: date & a fixed slot OR a custom time
        var dateInput = document.getElementById("bsiBookingDate");
        var useSlotToggle = document.getElementById("bsiUseSlotToggle");
        var useSlotHidden = document.getElementById("bsiBookingUseSlot");
        var slotPanel = document.getElementById("bsiSlotPanel");
        var customTimePanel = document.getElementById("bsiCustomTimePanel");
        var customTimeInput = document.getElementById("bsiBookingCustomTime");
        var dateTimeNext = document.getElementById("bsiDateTimeNext");
        var slotButtons = form.querySelectorAll(".bsi-time-slot");
        var slotAvailabilityHint = document.getElementById("bsiSlotAvailabilityHint");
        state.useSlot = !!(useSlotToggle && useSlotToggle.checked);

        function checkDateTimeReady() {
            var ready = !!state.date && (state.useSlot ? !!state.slotId : !!state.customTime);
            if (dateTimeNext) {
                dateTimeNext.toggleAttribute("disabled", !ready);
            }
        }

        // Best-effort preview of which fixed slots are already full for this branch/date/
        // artist/chairs — the model's own capacity constraint is still the real guard on
        // submit. requestToken guards against a slow/late response landing after a newer
        // one (date, artist or chairs all re-trigger this) — without it, a stale response
        // could reapply disabled/"full" using inputs the user has already moved on from.
        var slotAvailabilityToken = 0;
        function refreshSlotAvailability() {
            if (!state.locationId || !state.date || !slotButtons.length) {
                return;
            }
            // Clear whatever full/disabled state is left over from the previous
            // inputs immediately — otherwise a slow or failed fetch leaves every
            // slot exactly as it was, which can mean stuck-disabled buttons the
            // user can't click out of (native `disabled` blocks the click entirely).
            slotButtons.forEach(function (slot) {
                slot.classList.remove("bsi-time-slot--full");
                slot.disabled = false;
            });
            var token = ++slotAvailabilityToken;
            fetch("/salon/booking/slot_availability", {
                method: "POST",
                credentials: "same-origin",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    id: Date.now(),
                    jsonrpc: "2.0",
                    method: "call",
                    params: {
                        location_id: state.locationId,
                        preferred_date: state.date,
                        artist_id: state.artistId,
                        chair_ids: state.chairs.map(function (c) { return c.id; }).join(",")
                    }
                })
            })
                .then(function (response) { return response.json(); })
                .then(function (payload) {
                    if (token !== slotAvailabilityToken || payload.error || !payload.result) {
                        return;
                    }
                    var availability = payload.result;
                    if (slotAvailabilityHint) {
                        slotAvailabilityHint.hidden = true;
                    }
                    slotButtons.forEach(function (slot) {
                        var remaining = availability[slot.getAttribute("data-slot-id")];
                        var full = remaining !== undefined && remaining <= 0;
                        slot.classList.toggle("bsi-time-slot--full", full);
                        slot.disabled = full;
                        if (full && slot.classList.contains("bsi-time-slot--selected")) {
                            slot.classList.remove("bsi-time-slot--selected");
                            state.slotId = null;
                            state.slotLabel = null;
                            document.getElementById("bsiBookingSlotId").value = "";
                            checkDateTimeReady();
                        }
                    });
                })
                .catch(function () { /* preview only — submit is still validated server-side */ });
        }

        // Chair/artist steps come BEFORE date+slot in this wizard, so there's usually no
        // date/slot yet the first time through — this only produces a real signal once both
        // are already chosen, i.e. when the customer navigates back via the step nav to
        // change their chair/artist. Same requestToken guard as refreshSlotAvailability, for
        // the same reason (a slow response landing after a newer one shouldn't win).
        var resourceAvailabilityToken = 0;
        function refreshResourceAvailability() {
            if (!state.locationId || !state.date || !state.useSlot || !state.slotId) {
                return;
            }
            var token = ++resourceAvailabilityToken;
            fetch("/salon/booking/resource_availability", {
                method: "POST",
                credentials: "same-origin",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    id: Date.now(),
                    jsonrpc: "2.0",
                    method: "call",
                    params: { location_id: state.locationId, preferred_date: state.date, slot_id: state.slotId }
                })
            })
                .then(function (response) { return response.json(); })
                .then(function (payload) {
                    if (token !== resourceAvailabilityToken || payload.error || !payload.result) {
                        return;
                    }
                    var availability = payload.result;
                    chairCards.forEach(function (chair) {
                        var available = availability.chairs[chair.getAttribute("data-chair-id")];
                        var busy = available === false;
                        chair.classList.toggle("bsi-chair--booked", busy);
                        if (busy && chair.classList.contains("bsi-chair--selected")) {
                            chair.classList.remove("bsi-chair--selected");
                            onChairToggle(chair, false);
                        }
                    });
                    artistCards.forEach(function (card) {
                        var artistId = card.getAttribute("data-artist-id");
                        if (!artistId) { return; } // "No preference" is always available
                        var available = availability.artists[artistId];
                        var busy = available === false;
                        card.classList.toggle("bsi-artist-check--booked", busy);
                        if (busy && card.classList.contains("bsi-artist-check--selected") && artistCards.length) {
                            selectArtist(artistCards[0]); // fall back to "No preference"
                        }
                    });
                })
                .catch(function () { /* preview only — submit is still validated server-side */ });
        }

        if (dateInput) {
            dateInput.addEventListener("change", function () {
                state.date = dateInput.value;
                checkDateTimeReady();
                refreshSlotAvailability();
                refreshResourceAvailability();
            });
        }
        if (useSlotToggle) {
            useSlotToggle.addEventListener("change", function () {
                state.useSlot = useSlotToggle.checked;
                if (useSlotHidden) {
                    useSlotHidden.value = state.useSlot ? "1" : "0";
                }
                if (slotPanel) {
                    slotPanel.hidden = !state.useSlot;
                }
                if (customTimePanel) {
                    customTimePanel.hidden = state.useSlot;
                }
                checkDateTimeReady();
            });
        }
        slotButtons.forEach(function (slot) {
            slot.addEventListener("click", function () {
                // Toggle: clicking the already-selected slot again deselects it
                // (same pattern as the Chairs/Services steps), so a pick can
                // actually be "unticked" instead of being permanently sticky.
                var wasSelected = slot.classList.contains("bsi-time-slot--selected");
                slotButtons.forEach(function (s) { s.classList.remove("bsi-time-slot--selected"); });
                if (wasSelected) {
                    state.slotId = null;
                    state.slotLabel = null;
                } else {
                    slot.classList.add("bsi-time-slot--selected");
                    state.slotId = slot.getAttribute("data-slot-id");
                    state.slotLabel = slot.textContent;
                }
                document.getElementById("bsiBookingSlotId").value = state.slotId || "";
                checkDateTimeReady();
                refreshResourceAvailability();
            });
        });
        if (customTimeInput) {
            // Listen on "input" too, not just "change" (which native time
            // inputs only fire on blur in several browsers) — otherwise
            // picking a time and immediately clicking Continue can hit it
            // while it's still disabled because state.customTime hasn't
            // updated yet.
            ["input", "change"].forEach(function (evt) {
                customTimeInput.addEventListener(evt, function () {
                    state.customTime = customTimeInput.value;
                    checkDateTimeReady();
                });
            });
        }
        if (dateTimeNext) {
            dateTimeNext.addEventListener("click", function () {
                document.getElementById("bsiSummaryCity").textContent = state.city || "—";
                document.getElementById("bsiSummaryStore").textContent = state.locationName || "—";
                document.getElementById("bsiSummaryArtist").textContent = state.artistCharge
                    ? (state.artistName + " (+₹" + state.artistCharge + ")") : state.artistName;
                document.getElementById("bsiSummaryDate").textContent = state.date || "—";
                document.getElementById("bsiSummaryTime").textContent = state.useSlot
                    ? (state.slotLabel || "—") : (state.customTime || "—");
                document.getElementById("bsiSummaryServices").textContent = state.services.length
                    ? state.services.map(function (s) { return s.name; }).join(", ") : "—";
                document.getElementById("bsiSummaryChairs").textContent = state.chairs.length
                    ? state.chairs.map(function (c) { return c.label; }).join(", ") : "—";
                updateServiceTotal();
                goTo(7);
            });
        }

        // Best-effort preview: once the customer's contact info is filled in, check whether it
        // already has an active membership and show the real tier/discount instead of a
        // generic label (pre-checking the box for them) — purely a UI nicety, the server-side
        // compute on the appointment is what actually decides/verifies the discount at submit
        // time either way. Email is checked first if given, phone otherwise, matching the
        // server's own fallback order.
        var memberEmailInput = document.getElementById("bsiBookingEmail");
        var memberPhoneInput = document.getElementById("bsiBookingPhone");
        var memberToggle = document.getElementById("bsiUseMemberToggle");
        var memberToggleLabel = document.getElementById("bsiMemberToggleLabel");
        if (memberToggle && memberToggleLabel) {
            var checkMembershipStatus = function () {
                var email = memberEmailInput ? memberEmailInput.value.trim() : "";
                var phone = memberPhoneInput ? memberPhoneInput.value.trim() : "";
                if (!email && !phone) {
                    return;
                }
                fetch("/salon/booking/membership_status", {
                    method: "POST",
                    credentials: "same-origin",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        id: Date.now(), jsonrpc: "2.0", method: "call",
                        params: { email: email, phone: email ? "" : phone }
                    })
                })
                    .then(function (response) { return response.json(); })
                    .then(function (payload) {
                        var result = payload.result;
                        if (payload.error || !result || !result.is_member) {
                            return;
                        }
                        memberToggleLabel.textContent = "Apply " + result.name + " discount — "
                            + result.discount_percent + "% off this booking";
                        memberToggle.checked = true;
                    })
                    .catch(function () { /* preview only — submit is still validated server-side */ });
            };
            if (memberEmailInput) {
                memberEmailInput.addEventListener("blur", checkMembershipStatus);
            }
            if (memberPhoneInput) {
                memberPhoneInput.addEventListener("blur", checkMembershipStatus);
            }
        }

        // At least one of email/phone is required (neither is individually required anymore) —
        // catch it client-side before a round-trip to the server, which enforces the same rule.
        var contactHint = document.getElementById("bsiContactHint");
        if (contactHint) {
            form.addEventListener("submit", function (e) {
                var email = memberEmailInput ? memberEmailInput.value.trim() : "";
                var phone = memberPhoneInput ? memberPhoneInput.value.trim() : "";
                if (!email && !phone) {
                    e.preventDefault();
                    contactHint.classList.add("bsi-form__hint--error");
                    (memberEmailInput || memberPhoneInput).focus();
                }
            });
            [memberEmailInput, memberPhoneInput].forEach(function (input) {
                if (input) {
                    input.addEventListener("input", function () {
                        contactHint.classList.remove("bsi-form__hint--error");
                    });
                }
            });
        }

        // Preselect a location if arriving from the Stores page (?location_id=)
        var preselect = document.getElementById("bsiBookingLocationId").value;
        if (preselect) {
            var storeBtn = form.querySelector('.bsi-booking-store[data-loc-id="' + preselect + '"]');
            if (storeBtn) {
                var cityBtn = form.querySelector('.bsi-city-card[data-city="' + storeBtn.getAttribute("data-city") + '"]');
                if (cityBtn) {
                    cityBtn.click();
                }
                storeBtn.click();
            }
        }
    }

    /* ── Dark / light mode ── */
    function bsiInitThemeToggle() {
        var btn = document.getElementById("bsiThemeToggle");
        var thumb = document.getElementById("bsiThemeThumb");
        if (!btn) {
            return;
        }
        var isDark = document.documentElement.getAttribute("data-theme") === "dark";
        if (thumb) {
            thumb.textContent = isDark ? "☽" : "☀";
        }
        btn.addEventListener("click", function () {
            isDark = !isDark;
            if (isDark) {
                document.documentElement.setAttribute("data-theme", "dark");
            } else {
                document.documentElement.removeAttribute("data-theme");
            }
            if (thumb) {
                thumb.textContent = isDark ? "☽" : "☀";
            }
            try {
                localStorage.setItem("bsi_salon_theme", isDark ? "dark" : "light");
            } catch (e) { /* ignore storage errors */ }
        });
    }

    /* ── Navbar scroll state + mobile menu ── */
    function bsiInitNavbar() {
        var nav = document.getElementById("bsiNav");
        var burger = document.getElementById("bsiBurger");
        var mobileMenu = document.getElementById("bsiMobileMenu");
        if (!nav) {
            return;
        }

        var onScroll = function () {
            nav.classList.toggle("bsi-nav--scrolled", window.scrollY > 24);
        };
        window.addEventListener("scroll", onScroll, { passive: true });
        onScroll();

        if (burger && mobileMenu) {
            burger.addEventListener("click", function () {
                var open = mobileMenu.classList.toggle("bsi-nav__mobile--open");
                burger.classList.toggle("bsi-nav__burger--open", open);
                nav.classList.toggle("bsi-nav--menu-open", open);
            });
            mobileMenu.querySelectorAll("a").forEach(function (link) {
                link.addEventListener("click", function () {
                    mobileMenu.classList.remove("bsi-nav__mobile--open");
                    burger.classList.remove("bsi-nav__burger--open");
                    nav.classList.remove("bsi-nav--menu-open");
                });
            });
        }
    }

    /* ── Fade-up on scroll ──
       Fallback path only: when GSAP + ScrollTrigger are present,
       bsi_salon_theme_motion.js's bsiInitGsapReveal() drives these same
       ".bsi-reveal" elements with a staggered GSAP timeline instead, so
       this plain IntersectionObserver version steps aside rather than
       both toggling/animating the same elements. ── */
    function bsiInitScrollReveal(root) {
        if (window.gsap && window.ScrollTrigger) {
            return;
        }
        var items = root.querySelectorAll(".bsi-reveal");
        if (!items.length) {
            return;
        }
        if (!("IntersectionObserver" in window)) {
            items.forEach(function (el) { el.classList.add("bsi-in-view"); });
            return;
        }
        var observer = new IntersectionObserver(function (entries) {
            entries.forEach(function (entry) {
                if (entry.isIntersecting) {
                    entry.target.classList.add("bsi-in-view");
                    observer.unobserve(entry.target);
                }
            });
        }, { threshold: 0.12 });
        items.forEach(function (el) { observer.observe(el); });
    }

    /* ── Home: testimonial carousel ── */
    function bsiInitTestimonialCarousel() {
        var wrap = document.getElementById("bsiTestimonials");
        var dotsWrap = document.getElementById("bsiTestimonialDots");
        if (!wrap) {
            return;
        }
        var slides = wrap.querySelectorAll(".bsi-testimonial");
        var dots = dotsWrap ? dotsWrap.querySelectorAll(".bsi-dot") : [];
        if (slides.length < 2) {
            return;
        }
        var active = 0;
        var timer = null;

        function show(index) {
            active = (index + slides.length) % slides.length;
            slides.forEach(function (slide, i) {
                slide.classList.toggle("bsi-testimonial--active", i === active);
            });
            dots.forEach(function (dot, i) {
                dot.classList.toggle("bsi-dot--active", i === active);
            });
        }

        function restart() {
            if (timer) {
                clearInterval(timer);
            }
            timer = setInterval(function () { show(active + 1); }, 5000);
        }

        dots.forEach(function (dot, i) {
            dot.addEventListener("click", function () {
                show(i);
                restart();
            });
        });

        restart();
    }

    /* ── Offers: category filter ── */
    function bsiInitOffersFilter() {
        var bar = document.getElementById("bsiFilterBar");
        var grid = document.getElementById("bsiServiceGrid");
        var count = document.getElementById("bsiFilterCount");
        if (!bar || !grid) {
            return;
        }
        var buttons = bar.querySelectorAll(".bsi-filter-btn");
        var cards = grid.querySelectorAll("[data-cat]");

        buttons.forEach(function (btn) {
            btn.addEventListener("click", function () {
                buttons.forEach(function (b) { b.classList.remove("bsi-filter-btn--active"); });
                btn.classList.add("bsi-filter-btn--active");
                var cat = btn.getAttribute("data-cat");
                var visible = 0;
                cards.forEach(function (card) {
                    var show = cat === "all" || card.getAttribute("data-cat") === cat;
                    card.style.display = show ? "" : "none";
                    if (show) {
                        visible += 1;
                    }
                });
                if (count) {
                    count.textContent = visible + " services";
                }
            });
        });
    }

    /* ── Packages: monthly / yearly billing toggle ── */
    function bsiInitBillingToggle() {
        var toggle = document.getElementById("bsiBillingToggle");
        if (!toggle) {
            return;
        }
        var buttons = toggle.querySelectorAll(".bsi-billing-toggle__btn");
        var priceEls = document.querySelectorAll(".bsi-membership-card__price-value");
        var unitEls = document.querySelectorAll(".bsi-membership-card__price-unit");

        buttons.forEach(function (btn) {
            btn.addEventListener("click", function () {
                buttons.forEach(function (b) { b.classList.remove("bsi-billing-toggle__btn--active"); });
                btn.classList.add("bsi-billing-toggle__btn--active");
                var billing = btn.getAttribute("data-billing");
                priceEls.forEach(function (el) {
                    var value = billing === "yearly" ? el.getAttribute("data-yearly") : el.getAttribute("data-monthly");
                    if (value) {
                        el.textContent = value;
                    }
                });
                // bsi_price_yearly is itself a per-month rate ("billed annually") — only
                // the unit label needs to change to make that clear, the number already did.
                unitEls.forEach(function (el) {
                    var unit = billing === "yearly" ? el.getAttribute("data-yearly-unit") : el.getAttribute("data-monthly-unit");
                    if (unit) {
                        el.textContent = unit;
                    }
                });
            });
        });
    }

    /* ── Packages: "Choose <tier>" -> resolve the right product for the currently-selected
       billing period -> add to cart via the same stock /shop/cart/add endpoint the shop grid
       uses -> hand off to stock checkout/payment. No custom cart/payment code at all. ── */
    function bsiInitMembershipCta() {
        var buttons = document.querySelectorAll(".bsi-membership-cta");
        if (!buttons.length) {
            return;
        }
        var toggle = document.getElementById("bsiBillingToggle");

        function currentBilling() {
            var active = toggle && toggle.querySelector(".bsi-billing-toggle__btn--active");
            return (active && active.getAttribute("data-billing")) || "monthly";
        }

        function jsonrpc(url, params) {
            return fetch(url, {
                method: "POST",
                credentials: "same-origin",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ id: Date.now(), jsonrpc: "2.0", method: "call", params: params })
            }).then(function (response) { return response.json(); });
        }

        buttons.forEach(function (btn) {
            btn.addEventListener("click", function () {
                if (btn.disabled) {
                    return;
                }
                var membershipId = parseInt(btn.getAttribute("data-membership-id"), 10);
                if (!membershipId) {
                    return;
                }
                btn.disabled = true;
                jsonrpc("/salon/membership/product", {
                    membership_id: membershipId,
                    billing_period: currentBilling()
                }).then(function (payload) {
                    var result = payload.result;
                    if (payload.error || !result || result.error) {
                        throw new Error("membership product resolution failed");
                    }
                    return jsonrpc("/shop/cart/add", {
                        product_id: result.product_id,
                        product_template_id: result.product_template_id,
                        quantity: 1
                    });
                }).then(function () {
                    window.location.href = "/shop/checkout";
                }).catch(function () {
                    // Never a dead click — fall back to the booking wizard if the cart/product
                    // resolution failed for any reason.
                    window.location.href = "/salon/booking";
                    btn.disabled = false;
                });
            });
        });
    }

    /* ── Stores: location selector ── */
    function bsiInitStoresSelector() {
        var list = document.getElementById("bsiStoresList");
        if (!list) {
            return;
        }
        var listItems = list.querySelectorAll("[data-loc-id]");
        var panels = document.querySelectorAll("[data-loc-panel]");
        var chips = document.querySelectorAll("[data-loc-jump]");

        function select(id, scrollIntoView) {
            listItems.forEach(function (item) {
                item.classList.toggle("bsi-stores-list__item--active", item.getAttribute("data-loc-id") === id);
            });
            panels.forEach(function (panel) {
                panel.classList.toggle("bsi-stores-detail--active", panel.getAttribute("data-loc-panel") === id);
            });
            if (scrollIntoView) {
                var target = list.closest("section");
                if (target) {
                    target.scrollIntoView({ behavior: "smooth", block: "start" });
                }
            }
        }

        listItems.forEach(function (item) {
            item.addEventListener("click", function () {
                select(item.getAttribute("data-loc-id"), false);
            });
        });
        chips.forEach(function (chip) {
            chip.addEventListener("click", function () {
                select(chip.getAttribute("data-loc-jump"), true);
            });
        });
    }

    /* ── Shop: sort dropdown auto-submits the toolbar's filter form ── */
    function bsiInitShopSort() {
        var select = document.getElementById("bsiShopSort");
        if (!select) {
            return;
        }
        select.addEventListener("change", function () {
            select.form.submit();
        });
    }

    /* ── Shop: quick "add to cart" from the product grid, via the same
       /shop/cart/add endpoint the standard eCommerce product page uses. */
    function bsiInitShopCart() {
        var buttons = document.querySelectorAll(".bsi-shop-card__quick-add");
        if (!buttons.length) {
            return;
        }
        var toast = document.getElementById("bsiShopToast");
        var toastTimer = null;

        function showToast(message, href) {
            if (!toast) {
                return;
            }
            toast.textContent = "";
            var text = document.createElement("span");
            text.textContent = message;
            toast.appendChild(text);
            if (href) {
                var link = document.createElement("a");
                link.href = href;
                link.className = "bsi-shop-toast__link";
                link.textContent = "View cart →";
                toast.appendChild(link);
            }
            toast.classList.add("bsi-shop-toast--visible");
            window.clearTimeout(toastTimer);
            toastTimer = window.setTimeout(function () {
                toast.classList.remove("bsi-shop-toast--visible");
            }, 4000);
        }

        function updateCartBadge(quantity) {
            var badge = document.getElementById("bsiNavCartCount");
            if (!badge) {
                return;
            }
            badge.textContent = quantity;
            badge.hidden = !quantity;
        }

        buttons.forEach(function (btn) {
            btn.addEventListener("click", function () {
                if (btn.disabled) {
                    return;
                }
                var productId = parseInt(btn.getAttribute("data-product-id"), 10);
                var templateId = parseInt(btn.getAttribute("data-template-id"), 10);
                if (!productId || !templateId) {
                    return;
                }
                btn.disabled = true;
                fetch("/shop/cart/add", {
                    method: "POST",
                    credentials: "same-origin",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        id: Date.now(),
                        jsonrpc: "2.0",
                        method: "call",
                        params: {
                            product_id: productId,
                            product_template_id: templateId,
                            quantity: 1
                        }
                    })
                })
                    .then(function (response) { return response.json(); })
                    .then(function (payload) {
                        if (payload.error) {
                            showToast("Sorry, that product couldn't be added.");
                            return;
                        }
                        updateCartBadge(payload.result && payload.result.cart_quantity);
                        btn.classList.add("bsi-shop-card__quick-add--done");
                        showToast("Added to cart.", "/shop/cart");
                        window.setTimeout(function () {
                            btn.classList.remove("bsi-shop-card__quick-add--done");
                        }, 1500);
                    })
                    .catch(function () {
                        showToast("Sorry, that product couldn't be added.");
                    })
                    .finally(function () {
                        btn.disabled = false;
                    });
            });
        });
    }
})();
