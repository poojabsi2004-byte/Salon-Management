(function () {
    "use strict";

    // GSAP + ScrollTrigger are loaded as vendor assets right before this
    // file (see __manifest__.py); this file only ever runs the GSAP-driven
    // effects it adds when both are actually present, and does nothing
    // otherwise — the page is fully usable without it either way.

    function bsiOnReady(fn) {
        if (document.readyState === "loading") {
            document.addEventListener("DOMContentLoaded", fn);
        } else {
            fn();
        }
    }

    function bsiPrefersReducedMotion() {
        return window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    }
    function bsiHasFinePointer() {
        return window.matchMedia && window.matchMedia("(pointer: fine)").matches;
    }

    bsiOnReady(function () {
        var root = document.getElementById("bsi-salon-root");
        if (!root || !window.gsap) {
            return;
        }
        if (window.ScrollTrigger) {
            gsap.registerPlugin(ScrollTrigger);
        }

        bsiInitGsapParallax(root);
        bsiInitGsapReveal(root);
    });

    /* ── Scroll reveal, GSAP-driven: supersedes bsi_salon_theme.js's plain
       IntersectionObserver version (see the guard there) for every
       ".bsi-reveal" element on every page — home, about, offers, packages,
       stores, stylists, booking, contact, shop all already carry this
       class in their templates, so nothing there needs to change.
       ScrollTrigger.batch groups elements that cross the trigger together
       and staggers them into one soft, cascading reveal instead of each
       popping in independently; the from-state is read off which
       ".bsi-reveal--*" variant class is present so it always matches
       whatever the stylesheet currently authors for that variant. ── */
    function bsiInitGsapReveal(root) {
        if (bsiPrefersReducedMotion() || !window.ScrollTrigger) {
            return;
        }
        var items = Array.prototype.slice.call(root.querySelectorAll(".bsi-reveal"));
        if (!items.length) {
            return;
        }

        items.forEach(function (el) {
            el.classList.add("bsi-gsap-reveal");
            if (el.classList.contains("bsi-reveal--left")) {
                gsap.set(el, { opacity: 0, x: -32 });
            } else if (el.classList.contains("bsi-reveal--right")) {
                gsap.set(el, { opacity: 0, x: 32 });
            } else if (el.classList.contains("bsi-reveal--scale")) {
                gsap.set(el, { opacity: 0, scale: 0.92 });
            } else {
                gsap.set(el, { opacity: 0, y: 28 });
            }
        });

        ScrollTrigger.batch(items, {
            start: "top 88%",
            onEnter: function (batch) {
                gsap.to(batch, {
                    opacity: 1, x: 0, y: 0, scale: 1,
                    duration: 0.9, ease: "power3.out", stagger: 0.08,
                    overwrite: "auto"
                });
            }
        });
    }

    /* ── GSAP ScrollTrigger-scrubbed image parallax: hero + the "Why
       Enrich" immersive panel. This supersedes the plain rAF hero
       parallax in bsi_salon_theme.js, which skips setting itself up once
       it detects GSAP is present (see the guard there) so the two never
       fight over the same transform. ── */
    function bsiInitGsapParallax(root) {
        if (bsiPrefersReducedMotion() || !window.ScrollTrigger) {
            return;
        }

        var heroBg = root.querySelector(".bsi-hero__bg");
        if (heroBg) {
            gsap.to(heroBg, {
                yPercent: 8,
                ease: "none",
                scrollTrigger: {
                    trigger: ".bsi-hero",
                    start: "top top",
                    end: "bottom top",
                    scrub: 0.6
                }
            });
        }

        var whyBg = root.querySelector(".bsi-why-immersive__bg img");
        if (whyBg) {
            // Scaled up first so a vertical drift never uncovers an edge —
            // .bsi-why-immersive__bg has no overscan margin of its own
            // (unlike .bsi-hero__bg's `inset: -6% 0`), and the section's
            // own `overflow: hidden` is the last line of defense either way.
            gsap.set(whyBg, { scale: 1.12, transformOrigin: "center center" });
            gsap.fromTo(whyBg, { yPercent: -6 }, {
                yPercent: 6,
                ease: "none",
                scrollTrigger: {
                    trigger: ".bsi-why-immersive",
                    start: "top bottom",
                    end: "bottom top",
                    scrub: 0.6
                }
            });
        }
    }
})();
