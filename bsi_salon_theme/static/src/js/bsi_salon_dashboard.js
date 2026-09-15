(function () {
    "use strict";

    var SVG_NS = "http://www.w3.org/2000/svg";
    var STATE_COLORS = { completed: "#2fb35c", pending: "#8b8b93", in_progress: "#2b8c82", cancelled: "#ef233c" };
    var STATE_ORDER = ["completed", "pending", "in_progress", "cancelled"];
    var STATE_LABELS = { completed: "Completed", pending: "Pending", in_progress: "In Progress", cancelled: "Cancelled" };
    var PAYMENT_LABELS = { paid: "Paid", pending: "Pending", unbilled: "Unbilled" };
    var REDUCED_MOTION = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    var state = { revenuePeriod: "month", locationId: "", selectedDate: "", lastStats: null, pages: {} };

    function escapeHtml(value) {
        return String(value == null ? "" : value).replace(/[&<>"']/g, function (c) {
            return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
        });
    }

    function formatMoney(amount) {
        var sign = amount < 0 ? "-" : "";
        return sign + "₹" + Math.round(Math.abs(amount || 0)).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
    }

    // A plain setTimeout(fn, 40) doesn't reliably give the browser a chance to paint the
    // "width: 0%" starting state before the target width is applied — occasionally the two
    // updates land in the same paint and the CSS transition never visibly plays, leaving the
    // bar stuck at 0%. Waiting two animation frames guarantees the initial state has been
    // committed to the screen first, so the transition to the target width always runs.
    function bsi_nextFrame(fn) {
        requestAnimationFrame(function () { requestAnimationFrame(fn); });
    }

    // Generic client-side pagination: slices `items` into pages of `pageSize`, calls
    // `renderPage(slice)` to draw the current page, and wires up the Prev/Next buttons +
    // "Page X of Y" text inside #controlsId. The current page is kept in `state.pages[key]`
    // so it survives the 60s auto-refresh (a background reload doesn't yank the user back
    // to page 1) — only reset if the refreshed data now has fewer pages than that.
    function bsi_paginate(key, controlsId, items, pageSize, renderPage) {
        if (!(key in state.pages)) { state.pages[key] = 0; }
        var totalPages = Math.max(1, Math.ceil(items.length / pageSize));
        if (state.pages[key] > totalPages - 1) { state.pages[key] = totalPages - 1; }

        function show() {
            var page = state.pages[key];
            renderPage(items.slice(page * pageSize, page * pageSize + pageSize));
            var controls = document.getElementById(controlsId);
            if (!controls) { return; }
            controls.hidden = totalPages <= 1;
            var info = controls.querySelector("[data-page-info]");
            var prev = controls.querySelector("[data-page-prev]");
            var next = controls.querySelector("[data-page-next]");
            if (info) { info.textContent = "Page " + (page + 1) + " of " + totalPages; }
            if (prev) {
                prev.disabled = page === 0;
                prev.onclick = function () { state.pages[key] = Math.max(0, page - 1); show(); };
            }
            if (next) {
                next.disabled = page >= totalPages - 1;
                next.onclick = function () { state.pages[key] = Math.min(totalPages - 1, page + 1); show(); };
            }
        }
        show();
    }

    function initials(name) {
        var parts = String(name || "?").trim().split(/\s+/);
        return ((parts[0] || "")[0] || "?").toUpperCase() + ((parts[1] || "")[0] || "").toUpperCase();
    }

    function avatarHtml(url, name, cssClass) {
        var safeName = escapeHtml(name);
        if (!url) {
            return '<span class="' + cssClass + '">' + initials(name) + "</span>";
        }
        return '<img class="' + cssClass + '" src="' + encodeURI(url) + '" alt="' + safeName + '" ' +
            'onerror="this.outerHTML=\'<span class=&quot;' + cssClass + '&quot;>' + initials(name) + '</span>\'"/>';
    }

    function jsonrpc(url, params) {
        return fetch(url, {
            method: "POST",
            credentials: "same-origin",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ id: Date.now(), jsonrpc: "2.0", method: "call", params: params || {} })
        }).then(function (response) {
            if (!response.ok) { throw new Error("HTTP " + response.status); }
            return response.json();
        }).then(function (payload) {
            if (payload.error) { throw new Error(payload.error.message || "RPC error"); }
            return payload.result;
        });
    }

    /* ── Animated count-up (no library — plain requestAnimationFrame) ── */
    function animateCount(el, target, opts) {
        opts = opts || {};
        var format = opts.money ? formatMoney : function (v) {
            return Math.round(v).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
        };
        el.classList.remove("bsi-skel-text");
        if (REDUCED_MOTION) { el.textContent = format(target); return; }
        var duration = 900;
        var startTime = null;
        function step(ts) {
            if (!startTime) { startTime = ts; }
            var progress = Math.min((ts - startTime) / duration, 1);
            var eased = 1 - Math.pow(1 - progress, 3);
            el.textContent = format(target * eased);
            if (progress < 1) { requestAnimationFrame(step); }
        }
        requestAnimationFrame(step);
    }

    function renderChangeBadge(el, pct) {
        if (pct == null) { el.textContent = "·"; el.className = "bsi-kpi__change"; return; }
        var arrow = pct > 0 ? "▲" : pct < 0 ? "▼" : "•";
        el.textContent = arrow + " " + Math.abs(pct).toFixed(1) + "%";
        el.className = "bsi-kpi__change " + (pct > 0 ? "is-up" : pct < 0 ? "is-down" : "is-flat");
    }

    function renderSparkline(svg, trend) {
        svg.innerHTML = "";
        if (!trend || trend.length < 2) { return; }
        var w = 100, h = 28;
        var max = Math.max.apply(null, trend.concat([1]));
        var min = Math.min.apply(null, trend.concat([0]));
        var range = (max - min) || 1;
        var stepX = w / (trend.length - 1);
        var points = trend.map(function (v, i) { return [i * stepX, h - ((v - min) / range) * h]; });
        var d = "M" + points.map(function (p) { return p[0].toFixed(1) + "," + p[1].toFixed(1); }).join(" L");
        var path = document.createElementNS(SVG_NS, "path");
        path.setAttribute("d", d);
        path.setAttribute("stroke", "currentColor");
        svg.appendChild(path);
    }

    function renderKpis(kpis) {
        Object.keys(kpis).forEach(function (key) {
            var card = document.querySelector('.bsi-kpi[data-kpi="' + key + '"]');
            if (!card) { return; }
            var kpi = kpis[key];
            animateCount(card.querySelector(".bsi-kpi__value"), kpi.value, { money: kpi.is_money });
            var changeEl = card.querySelector('[data-change="' + key + '"]');
            if (changeEl) { renderChangeBadge(changeEl, kpi.change_pct); }
            var subEl = card.querySelector('[data-sub="' + key + '"]');
            if (subEl && key === "available_staff") { subEl.textContent = "of " + kpi.total + " total"; }
            var spark = card.querySelector('[data-spark="' + key + '"]');
            if (spark) { renderSparkline(spark, kpi.trend); }
        });
    }

    /* ── Appointment status donut ── */
    function renderDonut(svg, legendEl, counts) {
        var total = 0;
        STATE_ORDER.forEach(function (key) { total += counts[key] || 0; });
        svg.innerHTML = "";
        legendEl.innerHTML = "";
        var cx = 56, cy = 56, r = 44;
        var circumference = 2 * Math.PI * r;

        var track = document.createElementNS(SVG_NS, "circle");
        track.setAttribute("cx", cx); track.setAttribute("cy", cy); track.setAttribute("r", r);
        track.setAttribute("fill", "none"); track.setAttribute("stroke", "var(--dash-gray-100)");
        track.setAttribute("stroke-width", "11");
        svg.appendChild(track);

        if (!total) {
            var empty = document.createElement("li");
            empty.className = "bsi-dash-empty";
            empty.textContent = "No bookings yet";
            legendEl.appendChild(empty);
            return;
        }

        var offsetAccum = 0;
        STATE_ORDER.forEach(function (key) {
            var count = counts[key] || 0;
            if (!count) { return; }
            var length = (count / total) * circumference;
            var circle = document.createElementNS(SVG_NS, "circle");
            circle.setAttribute("cx", cx); circle.setAttribute("cy", cy); circle.setAttribute("r", r);
            circle.setAttribute("fill", "none");
            circle.setAttribute("stroke", STATE_COLORS[key]);
            circle.setAttribute("stroke-width", "11");
            circle.setAttribute("transform", "rotate(-90 " + cx + " " + cy + ")");
            // stroke-dasharray is fixed at its final value from the start — browsers don't
            // reliably interpolate that property (it's a list, not a single number), which
            // previously caused the ring to render with visible gaps/overlaps whenever a
            // redraw (e.g. the 60s auto-refresh) landed mid-transition. Only stroke-dashoffset
            // (a single number, safe to animate) ever changes — same technique already used
            // for the revenue chart's line draw-in below.
            circle.style.strokeDasharray = length + " " + (circumference - length);
            circle.style.strokeDashoffset = -offsetAccum;
            svg.appendChild(circle);
            offsetAccum += length;

            var li = document.createElement("li");
            var swatch = document.createElement("span");
            swatch.className = "bsi-dash-legend__swatch";
            swatch.style.background = STATE_COLORS[key];
            var label = document.createElement("span");
            label.textContent = STATE_LABELS[key];
            var countSpan = document.createElement("span");
            countSpan.className = "bsi-dash-legend__count";
            countSpan.textContent = count;
            li.appendChild(swatch); li.appendChild(label); li.appendChild(countSpan);
            legendEl.appendChild(li);
        });
    }

    /* ── Today's appointments table ── */
    function renderAppointmentsTable(items) {
        var body = document.getElementById("appointmentsTableBody");
        if (!items.length) {
            body.innerHTML = '<tr><td colspan="7" class="bsi-dash-empty">No bookings scheduled for today</td></tr>';
            document.getElementById("appointmentsPagination").hidden = true;
            return;
        }
        bsi_paginate("appointments", "appointmentsPagination", items, 5, function (page) {
            body.innerHTML = page.map(function (a) {
                return '<tr data-id="' + a.id + '">' +
                    '<td data-label="Customer"><span class="bsi-dash-table__person">' +
                        avatarHtml(a.avatar_url, a.customer, "bsi-dash-table__avatar") +
                        "<span>" + escapeHtml(a.customer) + "</span></span></td>" +
                    '<td data-label="Service">' + escapeHtml(a.service) + "</td>" +
                    '<td data-label="Staff" class="bsi-dash-table__muted">' + escapeHtml(a.staff) + "</td>" +
                    '<td data-label="Time">' + escapeHtml(a.time) + "</td>" +
                    '<td data-label="Duration" class="bsi-dash-table__muted">' + escapeHtml(a.duration) + "</td>" +
                    '<td data-label="Status"><span class="bsi-dash-badge bsi-dash-badge--' + a.status_label.toLowerCase().replace(/\s+/g, "_") + '">' + escapeHtml(a.status_label) + "</span></td>" +
                    '<td data-label="Payment"><span class="bsi-dash-badge bsi-dash-badge--' + a.payment_status + '">' + escapeHtml(PAYMENT_LABELS[a.payment_status] || a.payment_status) + "</span></td>" +
                "</tr>";
            }).join("");
        });
    }

    function formatUpcomingWhen(a) {
        var now = new Date();
        var todayIso = now.getFullYear() + "-" + String(now.getMonth() + 1).padStart(2, "0") + "-" + String(now.getDate()).padStart(2, "0");
        var when = a.date === todayIso ? "Today"
            : new Date(a.date + "T00:00:00").toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" });
        return when + " · " + a.time;
    }

    /* ── Upcoming: real future-looking appointments from data.upcoming_appointments,
       not just "later today" ── */
    function renderUpcoming(items) {
        var list = document.getElementById("upcomingFeed");
        if (!items.length) {
            list.innerHTML = '<li class="bsi-dash-empty">Nothing else scheduled</li>';
            document.getElementById("upcomingPagination").hidden = true;
            return;
        }
        bsi_paginate("upcoming", "upcomingPagination", items, 5, function (page) {
            list.innerHTML = page.map(function (a) {
                return '<li data-id="' + a.id + '"><span><span class="bsi-dash-feed__name">' + escapeHtml(formatUpcomingWhen(a)) + " · " + escapeHtml(a.customer) + "</span>" +
                    '<div class="bsi-dash-feed__meta">' + escapeHtml(a.service) + " — " + escapeHtml(a.staff) + "</div></span>" +
                    '<span class="bsi-dash-badge bsi-dash-badge--' + a.status_label.toLowerCase().replace(/\s+/g, "_") + '">' + escapeHtml(a.status_label) + "</span></li>";
            }).join("");
        });
    }

    /* ── Recent Leads: leads not yet converted to a booking — a Won one still showing up
       here got blocked by a slot/artist conflict at Won-time (see crm_lead.py) and needs a
       staff retry, so it's flagged rather than shown as if still a fresh, unactioned lead. ── */
    function renderRecentLeads(items) {
        var list = document.getElementById("recentLeadsFeed");
        var totalEl = document.getElementById("recentLeadsTotal");
        if (totalEl) { totalEl.textContent = items.length ? "(" + items.length + ")" : ""; }
        if (!items.length) {
            list.innerHTML = '<li class="bsi-dash-empty">No new leads waiting</li>';
            document.getElementById("recentLeadsPagination").hidden = true;
            return;
        }
        bsi_paginate("recentLeads", "recentLeadsPagination", items, 5, function (page) {
            list.innerHTML = page.map(function (l) {
                var badgeClass = l.is_won_pending ? "bsi-dash-badge--pending" : "bsi-dash-badge--unbilled";
                var badgeText = l.is_won_pending ? "Won · Retry needed" : l.stage;
                return '<li data-id="' + l.id + '"><span><span class="bsi-dash-feed__name">' + escapeHtml(l.customer) + "</span>" +
                    '<div class="bsi-dash-feed__meta">' + escapeHtml(l.service) + " — " + escapeHtml(l.location) + "</div></span>" +
                    '<span class="bsi-dash-badge ' + badgeClass + '">' + escapeHtml(badgeText) + "</span></li>";
            }).join("");
        });
    }

    /* ── Notifications: real, bounded operational alerts from data.notifications ── */
    function renderNotifications(items) {
        var list = document.getElementById("bsiDashNotifList");
        var dot = document.getElementById("bsiDashNotifDot");
        dot.hidden = !items.length;
        if (!items.length) {
            list.innerHTML = '<li class="bsi-dash-empty">You\'re all caught up</li>';
            return;
        }
        list.innerHTML = items.map(function (n) {
            return "<li>" + escapeHtml(n.text) + "</li>";
        }).join("");
    }

    function renderPopularServices(services) {
        var container = document.getElementById("popularServices");
        if (!services.length) {
            container.innerHTML = '<p class="bsi-dash-empty">No service bookings yet</p>';
            document.getElementById("popularServicesPagination").hidden = true;
            return;
        }
        bsi_paginate("popularServices", "popularServicesPagination", services, 5, function (page) {
            container.innerHTML = page.map(function (s) {
                return '<div class="bsi-service-row" data-id="' + s.id + '">' +
                    '<div class="bsi-service-row__top"><span class="bsi-service-row__name">' + escapeHtml(s.name) + "</span>" +
                    '<span class="bsi-service-row__meta">' + s.bookings + " bookings · " + formatMoney(s.revenue) + "</span></div>" +
                    '<div class="bsi-service-row__track"><span class="bsi-service-row__fill" data-pct="' + s.pct + '"></span></div>' +
                "</div>";
            }).join("");
            var rows = container.querySelectorAll(".bsi-service-row");
            if (window.gsap && !REDUCED_MOTION) {
                gsap.from(rows, { opacity: 0, x: -14, duration: 0.45, ease: "power2.out", stagger: 0.07 });
            }
            bsi_nextFrame(function () {
                container.querySelectorAll(".bsi-service-row__fill").forEach(function (fill) {
                    fill.style.width = fill.getAttribute("data-pct") + "%";
                });
            });
        });
    }

    function renderTopStaff(staff) {
        var container = document.getElementById("topStaff");
        if (!staff.length) {
            container.innerHTML = '<p class="bsi-dash-empty">No completed bookings yet</p>';
            document.getElementById("topStaffPagination").hidden = true;
            return;
        }
        bsi_paginate("topStaff", "topStaffPagination", staff, 4, function (page) {
            container.innerHTML = page.map(function (s) {
                return '<div class="bsi-staff-card" data-id="' + s.id + '">' +
                    avatarHtml(s.avatar_url, s.name, "bsi-staff-card__avatar") +
                    '<div class="bsi-staff-card__name">' + escapeHtml(s.name) + "</div>" +
                    '<span class="bsi-dash-badge bsi-dash-badge--' + (s.is_available ? "completed" : "cancelled") + '">' +
                        (s.is_available ? "Available" : "Booked") + "</span>" +
                    '<div class="bsi-staff-card__role">' + escapeHtml(s.role || "Stylist") + "</div>" +
                    '<div class="bsi-staff-card__stat"><strong>' + s.services_completed + "</strong> services</div>" +
                    '<div class="bsi-staff-card__stat"><strong>' + formatMoney(s.revenue) + "</strong> revenue</div>" +
                    (s.rating ? '<div class="bsi-staff-card__rating">★ ' + s.rating.toFixed(1) + "</div>" : "") +
                    '<div class="bsi-staff-card__bar"><span class="bsi-staff-card__bar-fill" data-pct="' + s.performance_pct + '"></span></div>' +
                "</div>";
            }).join("");
            var staffCards = container.querySelectorAll(".bsi-staff-card");
            if (window.gsap && !REDUCED_MOTION) {
                gsap.from(staffCards, { opacity: 0, y: 14, scale: 0.94, duration: 0.45, ease: "back.out(1.6)", stagger: 0.07 });
            }
            bsi_nextFrame(function () {
                container.querySelectorAll(".bsi-staff-card__bar-fill").forEach(function (fill) {
                    fill.style.width = fill.getAttribute("data-pct") + "%";
                });
            });
        });
    }

    function renderTransactions(transactions) {
        var body = document.getElementById("transactionsTableBody");
        if (!transactions.length) {
            body.innerHTML = '<tr><td colspan="6" class="bsi-dash-empty">No transactions yet</td></tr>';
            document.getElementById("transactionsPagination").hidden = true;
            return;
        }
        bsi_paginate("transactions", "transactionsPagination", transactions, 5, function (page) {
            body.innerHTML = page.map(function (t) {
                return "<tr>" +
                    '<td data-label="Invoice">' + escapeHtml(t.ref) + "</td>" +
                    '<td data-label="Customer">' + escapeHtml(t.customer) + "</td>" +
                    '<td data-label="Amount">' + formatMoney(t.amount) + "</td>" +
                    '<td data-label="Method" class="bsi-dash-table__muted">' + escapeHtml(t.method) + "</td>" +
                    '<td data-label="Date" class="bsi-dash-table__muted">' + escapeHtml(t.date) + "</td>" +
                    '<td data-label="Status"><span class="bsi-dash-badge bsi-dash-badge--' + t.status.toLowerCase() + '">' + escapeHtml(t.status) + "</span></td>" +
                "</tr>";
            }).join("");
        });
    }

    /* ── Loyalty / Referral — cards are entirely absent from the DOM when their Settings
       toggle is off (see the template's t-if), so every lookup here is guarded rather
       than assumed to exist. ── */
    function renderLoyalty(loyalty) {
        var totalEl = document.getElementById("loyaltyTotalPoints");
        if (!totalEl) { return; }
        animateCount(totalEl, loyalty.total_points);
        var list = document.getElementById("loyaltyTopEarners");
        if (!loyalty.top_earners.length) {
            list.innerHTML = '<p class="bsi-dash-empty">No points earned yet</p>';
            return;
        }
        list.innerHTML = loyalty.top_earners.map(function (p, i) {
            return '<div class="bsi-mini-list__row" data-id="' + p.id + '"><span class="bsi-mini-list__rank">' + (i + 1) + "</span>" +
                '<span class="bsi-mini-list__name">' + escapeHtml(p.name) + "</span>" +
                '<span class="bsi-mini-list__value">' + p.points + " pts</span></div>";
        }).join("");
    }

    function renderReferral(referral) {
        var pointsEl = document.getElementById("referralBonusPoints");
        if (!pointsEl) { return; }
        animateCount(pointsEl, referral.bonus_points);
        document.getElementById("referralBonusSub").textContent =
            referral.bonus_count + " bonus" + (referral.bonus_count === 1 ? "" : "es") + " paid out";
        var topEl = document.getElementById("referralTopReferrer");
        topEl.innerHTML = referral.top_referrer
            ? '<div class="bsi-mini-list__row" data-id="' + referral.top_referrer.id + '"><span class="bsi-mini-list__name">Top referrer: <strong>' +
              escapeHtml(referral.top_referrer.name) + "</strong></span>" +
              '<span class="bsi-mini-list__value">' + referral.top_referrer.points + " pts</span></div>"
            : '<p class="bsi-dash-empty">No referrals yet</p>';
    }

    function renderQuickActions(actions) {
        document.querySelectorAll(".bsi-quick-action[data-action]").forEach(function (link) {
            var url = actions[link.getAttribute("data-action")];
            if (url) {
                link.href = url;
            } else {
                link.removeAttribute("href");
                link.style.opacity = "0.45";
                link.style.pointerEvents = "none";
            }
        });
    }

    /* ── Revenue chart (multi-series line + area, redraws smoothly on filter change) ── */
    function renderRevenueChart(data) {
        var svg = document.getElementById("revenueChart");
        var seriesGroup = document.getElementById("revenueSeries");
        var gridGroup = document.getElementById("revenueGrid");
        var labelsEl = document.getElementById("revenueChartLabels");
        var width = 720, height = 170, padTop = 10, padBottom = 10;

        var all = [].concat(data.revenue, [0]);
        var max = Math.max.apply(null, all);
        var min = Math.min.apply(null, all);
        var range = (max - min) || 1;

        function toY(v) { return height - padBottom - ((v - min) / range) * (height - padTop - padBottom); }
        function toX(i) { return data.labels.length > 1 ? (i / (data.labels.length - 1)) * width : width / 2; }

        gridGroup.innerHTML = "";
        [0.25, 0.5, 0.75].forEach(function (frac) {
            var line = document.createElementNS(SVG_NS, "line");
            var y = height * frac;
            line.setAttribute("x1", 0); line.setAttribute("x2", width);
            line.setAttribute("y1", y); line.setAttribute("y2", y);
            line.setAttribute("class", "bsi-grid-line");
            gridGroup.appendChild(line);
        });

        // Smooth Catmull-Rom-to-Bezier curve through the points instead of straight line
        // segments — sparse daily data (mostly zero, with the odd day of real revenue)
        // used to draw as a single sharp jagged spike; a smoothed curve reads as a proper
        // trend line the way the rest of this "premium" dashboard is meant to look.
        function buildSmoothLine(values) {
            var pts = values.map(function (v, i) { return [toX(i), toY(v)]; });
            if (pts.length < 2) {
                return pts.length ? pts[0][0].toFixed(1) + "," + pts[0][1].toFixed(1) : "0,0";
            }
            var d = pts[0][0].toFixed(1) + "," + pts[0][1].toFixed(1);
            for (var i = 0; i < pts.length - 1; i++) {
                var p0 = pts[i === 0 ? 0 : i - 1];
                var p1 = pts[i];
                var p2 = pts[i + 1];
                var p3 = pts[i + 2 < pts.length ? i + 2 : i + 1];
                var c1x = p1[0] + (p2[0] - p0[0]) / 6;
                var c1y = p1[1] + (p2[1] - p0[1]) / 6;
                var c2x = p2[0] - (p3[0] - p1[0]) / 6;
                var c2y = p2[1] - (p3[1] - p1[1]) / 6;
                d += " C" + c1x.toFixed(1) + "," + c1y.toFixed(1) + " " + c2x.toFixed(1) + "," + c2y.toFixed(1) +
                    " " + p2[0].toFixed(1) + "," + p2[1].toFixed(1);
            }
            return d;
        }

        seriesGroup.innerHTML = "";
        var areaPath = document.createElementNS(SVG_NS, "path");
        var areaD = "M" + buildSmoothLine(data.revenue) +
            " L" + toX(data.revenue.length - 1).toFixed(1) + "," + (height - padBottom) +
            " L" + toX(0).toFixed(1) + "," + (height - padBottom) + " Z";
        areaPath.setAttribute("d", areaD);
        areaPath.setAttribute("fill", "url(#bsiRevGradient)");
        areaPath.setAttribute("class", "bsi-series-area");
        seriesGroup.appendChild(areaPath);

        var linePath = document.createElementNS(SVG_NS, "path");
        linePath.setAttribute("d", "M" + buildSmoothLine(data.revenue));
        linePath.setAttribute("class", "bsi-series-line bsi-series-revenue");
        linePath.setAttribute("id", "bsiRevenueLinePath");
        seriesGroup.appendChild(linePath);

        // A small train of glowing dots continuously traveling the length of the line,
        // evenly spaced and looping forever — an always-alive touch rather than a one-shot
        // entrance animation. A single negative "begin" per dot (SMIL: "as if it started
        // that many seconds ago") spaces them out evenly from the very first frame, instead
        // of all bunching up together and only spreading out after the first lap.
        if (!REDUCED_MOTION) {
            var dotCount = 3;
            var dotDuration = 6; // seconds per lap — a medium, unhurried pace
            for (var d = 0; d < dotCount; d++) {
                var dot = document.createElementNS(SVG_NS, "circle");
                dot.setAttribute("r", "4");
                dot.setAttribute("class", "bsi-chart-dot");
                var motion = document.createElementNS(SVG_NS, "animateMotion");
                motion.setAttribute("dur", dotDuration + "s");
                motion.setAttribute("repeatCount", "indefinite");
                motion.setAttribute("begin", (-(d * dotDuration / dotCount)).toFixed(2) + "s");
                var mpath = document.createElementNS(SVG_NS, "mpath");
                mpath.setAttributeNS("http://www.w3.org/1999/xlink", "href", "#bsiRevenueLinePath");
                motion.appendChild(mpath);
                dot.appendChild(motion);
                seriesGroup.appendChild(dot);
            }
        }

        labelsEl.innerHTML = "";
        var step = Math.max(1, Math.ceil(data.labels.length / 8));
        data.labels.forEach(function (label, i) {
            var span = document.createElement("span");
            span.style.flex = "1";
            span.style.textAlign = "center";
            span.textContent = (i % step === 0 || i === data.labels.length - 1) ? label : "";
            labelsEl.appendChild(span);
        });

        svg.classList.remove("bsi-in-view");
        // eslint-disable-next-line no-unused-expressions
        svg.offsetHeight; // force reflow so the stroke-dashoffset transition replays on redraw
        svg.classList.add("bsi-in-view");

        var tooltip = document.getElementById("bsiRevenueTooltip");
        svg.onmousemove = function (evt) {
            var rect = svg.getBoundingClientRect();
            var relX = (evt.clientX - rect.left) / rect.width;
            var index = Math.round(relX * (data.labels.length - 1));
            index = Math.max(0, Math.min(data.labels.length - 1, index));
            tooltip.hidden = false;
            tooltip.style.left = (relX * 100) + "%";
            tooltip.style.top = "10px";
            tooltip.innerHTML = "<strong>" + escapeHtml(data.labels[index]) + "</strong><br/>" +
                "Revenue " + formatMoney(data.revenue[index]);
        };
        svg.onmouseleave = function () { tooltip.hidden = true; };
    }

    function loadRevenue(period) {
        var params = { period: period };
        if (state.locationId) { params.location_id = state.locationId; }
        return jsonrpc("/salon/dashboard/revenue", params).then(renderRevenueChart);
    }

    /* ── Date-dependent labels: "Today's Revenue"/"Today's Bookings"/the subtitle line all
       read literally "today" by default — once a different day is picked (see bsiDashDate's
       change handler below), swap them to name that day instead, so the numbers underneath
       never look like they're claiming to be "today" when they aren't. ── */
    function renderDateLabels(selectedDate, isToday) {
        var friendly = new Date(selectedDate + "T00:00:00").toLocaleDateString(undefined, { month: "short", day: "numeric" });
        var full = new Date(selectedDate + "T00:00:00").toLocaleDateString(undefined, {
            weekday: "long", month: "short", day: "numeric", year: "numeric",
        });
        var revenueLabel = document.getElementById("bsiKpiLabelRevenue");
        var bookingsLabel = document.getElementById("bsiKpiLabelBookings");
        var tableTitle = document.getElementById("bsiBookingsTableTitle");
        var subtitle = document.getElementById("bsiDashSubtitle");
        if (revenueLabel) { revenueLabel.textContent = isToday ? "Today's Revenue" : friendly + " Revenue"; }
        if (bookingsLabel) { bookingsLabel.textContent = isToday ? "Today's Bookings" : friendly + " Bookings"; }
        if (tableTitle) { tableTitle.textContent = isToday ? "Today's Bookings" : friendly + " Bookings"; }
        if (subtitle) {
            subtitle.textContent = isToday
                ? "Here's what's happening at your salon today."
                : "Here's what happened at your salon on " + full + ".";
        }
    }

    /* ── Full stats render pass ── */
    function render(data) {
        state.lastStats = data;
        renderDateLabels(data.selected_date, data.is_today);
        renderKpis(data.kpis);

        var apptTotal = STATE_ORDER.reduce(function (sum, k) { return sum + (data.appointment_stats[k] || 0); }, 0);
        document.getElementById("statApptTotal").textContent = apptTotal + " total";
        renderDonut(document.getElementById("apptDonut"), document.getElementById("apptLegend"), data.appointment_stats);

        renderAppointmentsTable(data.appointments_today);
        renderUpcoming(data.upcoming_appointments);
        renderRecentLeads(data.recent_leads);
        renderPopularServices(data.popular_services);
        renderTopStaff(data.top_staff);
        renderTransactions(data.transactions);
        renderLoyalty(data.loyalty);
        renderReferral(data.referral);
        renderQuickActions(data.quick_actions);
        renderNotifications(data.notifications);
    }

    function showError(show) {
        document.getElementById("bsiDashError").hidden = !show;
        document.getElementById("bsiDashContent").style.display = show ? "none" : "";
    }

    function loadAll(isManual) {
        var btn = document.getElementById("bsiDashRefresh");
        if (isManual) { btn.classList.add("is-spinning"); }
        var statsParams = {};
        if (state.locationId) { statsParams.location_id = state.locationId; }
        if (state.selectedDate) { statsParams.selected_date = state.selectedDate; }
        return Promise.all([jsonrpc("/salon/dashboard/stats", statsParams), loadRevenue(state.revenuePeriod)])
            .then(function (results) {
                showError(false);
                render(results[0]);
            })
            .catch(function () {
                if (!state.lastStats) { showError(true); }
            })
            .then(function () {
                if (isManual) { setTimeout(function () { btn.classList.remove("is-spinning"); }, 700); }
            });
    }

    /* ── Sidebar: mobile drawer + notification/profile dropdowns ── */

    function initChrome() {
        var sidebar = document.getElementById("bsiDashSidebar");
        var scrim = document.getElementById("bsiDashScrim");
        var burger = document.getElementById("bsiDashBurger");

        function openDrawer() { sidebar.classList.add("is-mobile-open"); scrim.classList.add("is-visible"); }
        function closeDrawer() { sidebar.classList.remove("is-mobile-open"); scrim.classList.remove("is-visible"); }
        burger.addEventListener("click", openDrawer);
        scrim.addEventListener("click", closeDrawer);
        document.addEventListener("keydown", function (e) { if (e.key === "Escape") { closeDrawer(); } });

        function initDropdown(btnId, panelId) {
            var btn = document.getElementById(btnId), panel = document.getElementById(panelId);
            btn.addEventListener("click", function (e) {
                e.stopPropagation();
                var willOpen = !panel.classList.contains("is-open");
                document.querySelectorAll(".bsi-dash__notif-panel, .bsi-dash__profile-panel").forEach(function (p) { p.classList.remove("is-open"); });
                if (willOpen) { panel.classList.add("is-open"); }
            });
        }
        initDropdown("bsiDashNotifBtn", "bsiDashNotifPanel");
        initDropdown("bsiDashProfileBtn", "bsiDashProfilePanel");
        document.addEventListener("click", function () {
            document.querySelectorAll(".bsi-dash__notif-panel, .bsi-dash__profile-panel").forEach(function (p) { p.classList.remove("is-open"); });
        });

        document.getElementById("bsiRevenueFilter").addEventListener("click", function (e) {
            var btn = e.target.closest("button[data-period]");
            if (!btn || btn.classList.contains("is-active")) { return; }
            this.querySelectorAll("button").forEach(function (b) { b.classList.remove("is-active"); });
            btn.classList.add("is-active");
            state.revenuePeriod = btn.getAttribute("data-period");
            loadRevenue(state.revenuePeriod);
        });

        document.getElementById("bsiDashRetry").addEventListener("click", function () { loadAll(false); });
        document.getElementById("bsiDashRefresh").addEventListener("click", function () { loadAll(true); });

        var locationSelect = document.getElementById("bsiDashLocation");
        if (locationSelect) {
            locationSelect.addEventListener("change", function () {
                state.locationId = locationSelect.value;
                loadAll(false);
            });
        }

        var dateInput = document.getElementById("bsiDashDate");
        if (dateInput) {
            dateInput.addEventListener("change", function () {
                // Empty out (cleared by the user) — fall back to the server's own "today".
                state.selectedDate = dateInput.value || "";
                if (!dateInput.value) { dateInput.value = dateInput.getAttribute("data-today"); }
                loadAll(false);
            });
        }

        var greeting = document.getElementById("bsiDashGreeting");
        var hour = new Date().getHours();
        var period = hour < 12 ? "Good morning" : hour < 17 ? "Good afternoon" : "Good evening";
        greeting.innerHTML = greeting.innerHTML.replace(/^Good \w+,/, period + ",");

        document.getElementById("bsiDashSearch").addEventListener("input", function (e) {
            var term = e.target.value.trim().toLowerCase();
            document.querySelectorAll("#appointmentsTableBody tr").forEach(function (row) {
                row.style.display = (!term || row.textContent.toLowerCase().indexOf(term) !== -1) ? "" : "none";
            });
        });
    }

    /* ── Staggered card entrance — GSAP (already vendored for the public website's own
       motion) drives a spring-eased reveal when available; falls back to the plain CSS
       class toggle otherwise, and skips animation entirely under reduced-motion. ── */
    function initReveal() {
        var cards = Array.prototype.slice.call(document.querySelectorAll(".bsi-dash-card"));
        var hasGsap = typeof window.gsap !== "undefined";
        if (REDUCED_MOTION || !("IntersectionObserver" in window)) {
            cards.forEach(function (c) { c.classList.add("bsi-in-view"); });
            return;
        }
        if (hasGsap) {
            gsap.set(cards, { autoAlpha: 0, y: 22, scale: 0.97 });
        }
        var observer = new IntersectionObserver(function (entries) {
            entries.forEach(function (entry, idx) {
                if (!entry.isIntersecting) { return; }
                var el = entry.target;
                observer.unobserve(el);
                setTimeout(function () {
                    if (hasGsap) {
                        gsap.to(el, { autoAlpha: 1, y: 0, scale: 1, duration: 0.6, ease: "back.out(1.5)" });
                    } else {
                        el.classList.add("bsi-in-view");
                    }
                }, idx * 55);
            });
        }, { threshold: 0.1 });
        cards.forEach(function (c) { observer.observe(c); });

        if (hasGsap) {
            gsap.from(".bsi-kpi__icon", {
                scale: 0.3, rotate: -20, duration: 0.55, delay: 0.15, ease: "back.out(2.2)", stagger: 0.06
            });
        }
    }

    /* ── Row click-through: Artists/Appointments/Services/Loyalty/Referral rows each open
       their real backend record. The dashboard itself renders inside an iframe (see
       bsi_salon_dashboard_client_action.js), so navigation must target the top-level Odoo
       shell — window.top.location — exactly like every other outbound link here already
       does via target="_top". Listeners are delegated onto each container (attached once,
       at load) since the rows themselves are fully replaced on every re-render. ── */
    function initDashboardNavigation() {
        [
            ["appointmentsTableBody", "tr[data-id]", "bsi.salon.booking.request"],
            ["upcomingFeed", "li[data-id]", "bsi.salon.booking.request"],
            ["recentLeadsFeed", "li[data-id]", "crm.lead"],
            ["popularServices", ".bsi-service-row[data-id]", "bsi.salon.service"],
            ["topStaff", ".bsi-staff-card[data-id]", "bsi.salon.team.member"],
            ["loyaltyTopEarners", ".bsi-mini-list__row[data-id]", "res.partner"],
            ["referralTopReferrer", ".bsi-mini-list__row[data-id]", "res.partner"],
        ].forEach(function (entry) {
            var container = document.getElementById(entry[0]);
            if (!container) { return; }
            container.addEventListener("click", function (e) {
                var row = e.target.closest(entry[1]);
                var id = row && row.getAttribute("data-id");
                if (id) { window.top.location.href = "/odoo/" + entry[2] + "/" + id; }
            });
        });

        // KPI cards (Today's Revenue, Today's Bookings, New Customers, Available Staff,
        // Pending Payments, Completed Services) — each opens the exact list of records
        // behind its number (data-href is a real backend action URL, see dashboard.py's
        // kpi_action_urls and views/bsi_salon_dashboard_kpi_actions.xml).
        document.querySelectorAll(".bsi-kpi[data-href]").forEach(function (card) {
            card.addEventListener("click", function () {
                window.top.location.href = card.getAttribute("data-href");
            });
        });
    }

    /* ── Floating mascot button doubles as "back to top" ── */
    /* ── Custom animated cursor: a glowing dot + trailing ring follow the real pointer, and
       little symbols spawn and drift away as it moves fast enough — ported from the
       reference CursorTrail component's behavior (same spawn-rate/fade/rotate logic), just
       in plain JS and this dashboard's own palette instead of React state. ── */
    function initCursorTrail() {
        var dot = document.querySelector(".bsi-dash-cursor__dot");
        var ring = document.querySelector(".bsi-dash-cursor__ring");
        var particleLayer = document.getElementById("bsiDashCursorParticles");
        if (!dot || !ring || !particleLayer) { return; }

        var SYMBOLS = ["✦", "✿", "◈", "✂", "◇", "★", "·"];
        var COLORS = ["var(--dash-red)", "var(--dash-red-dark)", "var(--dash-amber)", "var(--dash-teal)", "rgba(255,255,255,0.7)"];
        var last = { x: 0, y: 0 };
        var hidingForField = false;

        function setVisible(visible) {
            var show = visible && !hidingForField;
            dot.classList.toggle("is-visible", show);
            ring.classList.toggle("is-visible", show);
        }

        function spawnParticle(x, y) {
            var el = document.createElement("span");
            el.className = "bsi-dash-cursor-particle";
            el.textContent = SYMBOLS[Math.floor(Math.random() * SYMBOLS.length)];
            var color = COLORS[Math.floor(Math.random() * COLORS.length)];
            var rotation = Math.random() * 360;
            var opacity = 0.9;
            el.style.left = (x + (Math.random() - 0.5) * 14) + "px";
            el.style.top = (y + (Math.random() - 0.5) * 14) + "px";
            el.style.fontSize = (8 + Math.random() * 12) + "px";
            el.style.color = color;
            el.style.textShadow = "0 0 8px " + color;
            particleLayer.appendChild(el);

            function fade() {
                opacity -= 0.04;
                rotation += 2;
                if (opacity <= 0) { el.remove(); return; }
                el.style.opacity = String(opacity);
                el.style.transform = "translate(-50%, -50%) rotate(" + rotation + "deg)";
                requestAnimationFrame(fade);
            }
            requestAnimationFrame(fade);
        }

        document.addEventListener("mousemove", function (e) {
            dot.style.left = ring.style.left = e.clientX + "px";
            dot.style.top = ring.style.top = e.clientY + "px";
            setVisible(true);

            var dx = e.clientX - last.x, dy = e.clientY - last.y;
            var dist = Math.sqrt(dx * dx + dy * dy);
            if (dist > 12) {
                last = { x: e.clientX, y: e.clientY };
                var count = Math.min(3, Math.floor(dist / 12));
                for (var i = 0; i < count; i++) { spawnParticle(e.clientX, e.clientY); }
            }
        });
        document.addEventListener("mouseleave", function () { setVisible(false); });
        document.addEventListener("mouseover", function (e) {
            if (e.target.closest && e.target.closest("input, textarea, select")) {
                hidingForField = true;
                setVisible(false);
            }
        });
        document.addEventListener("mouseout", function (e) {
            if (e.target.closest && e.target.closest("input, textarea, select")) {
                hidingForField = false;
                setVisible(true);
            }
        });
    }

    /* ── Sidebar collapse/expand: an explicit click (not hover) toggles .is-collapsed,
       remembered in localStorage so it stays how the user left it across reloads. Starts
       collapsed by default on small screens, same as the reference design. ── */
    function initSidebarCollapse() {
        var sidebar = document.getElementById("bsiDashSidebar");
        var btn = document.getElementById("bsiDashSidebarCollapse");
        if (!sidebar || !btn) { return; }

        var STORAGE_KEY = "bsi_dash_sidebar_collapsed";
        var stored = null;
        try { stored = localStorage.getItem(STORAGE_KEY); } catch (e) { /* private mode etc. */ }
        var collapsed = stored !== null ? stored === "1" : window.innerWidth < 768;
        applyState(collapsed);

        function applyState(isCollapsed) {
            collapsed = isCollapsed;
            sidebar.classList.toggle("is-collapsed", collapsed);
            btn.setAttribute("aria-label", collapsed ? "Expand sidebar" : "Collapse sidebar");
        }

        btn.addEventListener("click", function () {
            applyState(!collapsed);
            try { localStorage.setItem(STORAGE_KEY, collapsed ? "1" : "0"); } catch (e) { /* ignore */ }
        });
    }

    /* ── Light/Dark toggle: sets data-theme on <body> (see the [data-theme="dark"] token
       overrides in the scss — only neutral surface colors change, never the red accent),
       remembered in localStorage. ── */
    function initTheme() {
        // Matches the attribute target of the pre-first-paint inline script in the
        // template's <head> (see its comment for why <html>, not <body>).
        var root = document.documentElement;
        var btn = document.getElementById("bsiDashThemeToggle");
        var icon = document.getElementById("bsiDashThemeIcon");
        var label = document.getElementById("bsiDashThemeLabel");
        if (!btn) { return; }

        var STORAGE_KEY = "bsi_dash_theme";
        var stored = null;
        try { stored = localStorage.getItem(STORAGE_KEY); } catch (e) { /* private mode etc. */ }
        var dark = stored === "dark";
        applyTheme(dark);

        function applyTheme(isDark) {
            dark = isDark;
            if (dark) { root.setAttribute("data-theme", "dark"); } else { root.removeAttribute("data-theme"); }
            if (icon) { icon.textContent = dark ? "☀" : "☾"; }
            if (label) { label.textContent = dark ? "Light mode" : "Dark mode"; }
        }

        btn.addEventListener("click", function () {
            applyTheme(!dark);
            try { localStorage.setItem(STORAGE_KEY, dark ? "dark" : "light"); } catch (e) { /* ignore */ }
        });
    }

    function initScrollTop() {
        var btn = document.getElementById("bsiDashScrollTop");
        if (!btn) { return; }

        // Past a small threshold, the icon turns 90° left (see .is-scrolled in the scss) —
        // throttled to one check per animation frame. While the click handler below is
        // smooth-scrolling back up, this is suppressed so the icon straightens out
        // immediately on click rather than staying turned for the whole (gradual)
        // scroll-up — see returningToTop.
        var ticking = false;
        var returningToTop = false;
        function updateScrolledState() {
            if (returningToTop) {
                if (window.scrollY <= 0) { returningToTop = false; }
                ticking = false;
                return;
            }
            btn.classList.toggle("is-scrolled", window.scrollY > 80);
            ticking = false;
        }
        window.addEventListener("scroll", function () {
            if (!ticking) {
                window.requestAnimationFrame(updateScrolledState);
                ticking = true;
            }
        }, { passive: true });
        updateScrolledState();

        btn.addEventListener("click", function () {
            returningToTop = true;
            btn.classList.remove("is-scrolled");
            window.scrollTo({ top: 0, behavior: "smooth" });
            // Safety net in case scrollY never fires a "== 0" scroll event (very short
            // scrolls, some browsers rounding) — resume normal threshold checks regardless.
            setTimeout(function () { returningToTop = false; }, 1000);
        });
    }

    document.addEventListener("DOMContentLoaded", function () {
        initChrome();
        initReveal();
        initDashboardNavigation();
        initScrollTop();
        initCursorTrail();
        initSidebarCollapse();
        initTheme();
        loadAll(false);
        setInterval(function () { loadAll(false); }, 60000);
    });
})();
