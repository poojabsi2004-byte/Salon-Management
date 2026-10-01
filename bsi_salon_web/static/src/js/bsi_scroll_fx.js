/*
 * PHASE 7 DEV — scroll-triggered reveal + progress bar.
 *
 * Adds three motion patterns familiar from the awwwards scrolling gallery
 * without touching any of the design's own markup or copy:
 *   - a slim top-of-viewport progress bar tracking how far down the page
 *     the visitor has scrolled;
 *   - section-level fade-up as each <section> crosses the viewport;
 *   - per-word heading stagger for h1/h2/h3 inside sections;
 *   - a back-to-top button once the visitor is well down the page.
 *
 * All reveals are opt-in — this script adds the CSS classes (and, for
 * headings, wraps each word in a span) at runtime. If this script never
 * runs, the site renders normally, since no reveal style ever activates.
 *
 * The SPA rerenders its DOM as the visitor navigates between virtual
 * pages, so a MutationObserver keeps decorating whatever gets added.
 */
(function () {
  'use strict';

  if (typeof document === 'undefined' || typeof window === 'undefined') return;
  if (!('IntersectionObserver' in window) || !('MutationObserver' in window)) return;

  var progressEl = null;
  var progressBar = null;
  var progressRaf = null;
  var lastPct = -1;

  function ensureProgress() {
    if (progressEl) return;
    progressEl = document.createElement('div');
    progressEl.className = 'bsi-fx-progress';
    progressEl.setAttribute('aria-hidden', 'true');
    progressBar = document.createElement('span');
    progressEl.appendChild(progressBar);
    document.body.appendChild(progressEl);
  }

  var topBtn = null;

  function ensureTopButton() {
    if (topBtn) return;
    topBtn = document.createElement('button');
    topBtn.type = 'button';
    topBtn.className = 'bsi-top';
    topBtn.setAttribute('aria-label', 'Back to top');
    topBtn.innerHTML = '<svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">'
      + '<path fill="currentColor" d="M11 20V7.8l-5.6 5.6L4 12l8-8 8 8-1.4 1.4L13 7.8V20h-2Z"/></svg>';
    topBtn.addEventListener('click', function () {
      window.scrollTo({ top: 0, behavior: 'smooth' });
      if (document.body.scrollTop > 0) document.body.scrollTo({ top: 0, behavior: 'smooth' });
    });
    document.body.appendChild(topBtn);
  }

  function onScroll() {
    if (progressRaf) return;
    progressRaf = window.requestAnimationFrame(function () {
      progressRaf = null;
      // The site's mobile CSS makes <body> the scroller (html/body are
      // height:100% with overflow), so read whichever one is scrolling.
      var doc = document.documentElement;
      var body = document.body;
      var bodyScrolls = body.scrollTop > 0 || body.scrollHeight > body.clientHeight + 1
        && getComputedStyle(body).overflowY !== 'visible';
      var y = bodyScrolls ? body.scrollTop : (window.scrollY || doc.scrollTop || 0);
      var height = bodyScrolls
        ? body.scrollHeight - body.clientHeight
        : Math.max(doc.scrollHeight, body.scrollHeight) - window.innerHeight;
      var pct = height > 0
        ? Math.min(100, Math.max(0, (y / height) * 100))
        : 0;
      // Round to one decimal so the transition step is visible without
      // repainting on every sub-pixel scroll delta.
      var rounded = Math.round(pct * 10) / 10;
      if (rounded === lastPct) return;
      lastPct = rounded;
      if (progressBar) progressBar.style.width = rounded + '%';
      if (topBtn) topBtn.classList.toggle('is-on', y > 700);
    });
  }

  var io = new IntersectionObserver(function (entries) {
    for (var i = 0; i < entries.length; i++) {
      var e = entries[i];
      if (e.isIntersecting) {
        e.target.classList.add('is-in');
        io.unobserve(e.target);
      }
    }
  }, {
    threshold: 0.14,
    rootMargin: '0px 0px -60px 0px',
  });

  // Guard against a first-frame flash: anything already visible in the
  // viewport when we decorate it gets `is-in` synchronously, so the reveal
  // class never actually hides above-the-fold content between class-add and
  // the observer's first async callback.
  function observeOrShow(el) {
    var rect;
    try { rect = el.getBoundingClientRect(); }
    catch (err) { io.observe(el); return; }
    if (rect.height > 0 && rect.top < (window.innerHeight * 0.9)) {
      el.classList.add('is-in');
    } else {
      io.observe(el);
    }
  }

  // Split a heading's text into per-word <span> so each word can transition
  // with its own delay. Runs once per heading; further re-decoration is a
  // no-op via a data flag.
  function splitHeading(el) {
    if (el.__bsiFxSplit) return;
    el.__bsiFxSplit = true;
    // Guard: only pure text-node children. If the design has already put
    // markup inside a heading (an <em>, <br>, an <sc-if>) skip the split
    // entirely — it'll still fade up as a whole via the outer reveal.
    var hasComplex = false;
    for (var k = 0; k < el.childNodes.length; k++) {
      var n = el.childNodes[k];
      if (n.nodeType !== 3 /* text */) { hasComplex = true; break; }
    }
    if (hasComplex) {
      // Fall back to a whole-heading fade rather than a per-word one --
      // the outer section reveal already covers this heading, so leaving
      // it undecorated here is the safe, no-op choice.
      return;
    }
    var text = el.textContent || '';
    if (!text.trim()) return;
    // Preserve spaces AS TEXT NODES between word spans so line-breaking
    // still works exactly as if the text were unwrapped.
    el.textContent = '';
    var words = text.split(/(\s+)/);
    var idx = 0;
    for (var j = 0; j < words.length; j++) {
      var w = words[j];
      if (!w) continue;
      if (/^\s+$/.test(w)) {
        el.appendChild(document.createTextNode(w));
      } else {
        var span = document.createElement('span');
        span.className = 'bsi-fx-word';
        span.style.setProperty('--i', idx);
        span.textContent = w;
        el.appendChild(span);
        idx++;
      }
    }
    el.classList.add('bsi-fx-heading');
  }

  // Decorate a root — apply reveal classes to sections, headings, images
  // and cards inside it that haven't been decorated yet.
  function decorate(root) {
    if (!root || root.nodeType !== 1) return;
    // Sections
    var sections = (root.tagName === 'SECTION' ? [root] : []).concat(
      Array.prototype.slice.call(root.querySelectorAll ? root.querySelectorAll('section') : [])
    );
    for (var i = 0; i < sections.length; i++) {
      var s = sections[i];
      if (s.__bsiFxSec) continue;
      s.__bsiFxSec = true;
      // Skip decorating the SPA's own root or elements deep inside a
      // custom cursor / grain overlay — those are utility layers, not
      // content sections. A section that is 0px tall (design uses
      // section as a semantic marker) is also skipped.
      if (s.getAttribute('data-screen-label') === '' && !s.textContent.trim()) continue;
      // Skip sections that already carry their own live design-authored
      // motion of their own (LIVE-ticker band with its pulseBars/sheenRun
      // animations, service-marquee band with marqueeL, etc.). Fading
      // the whole section in on scroll fights those animations and reads
      // as a jarring double-move -- the client's own screenshot flagged
      // exactly the LIVE ticker under the hero. The signature check
      // matches the ticker's distinctive inline background gradient
      // (see enrich_site.html); anything with `bsi-fx-skip` set on it
      // is also skipped, giving a manual escape hatch for later.
      if (isDesignAuthoredMotionSection(s)) continue;
      // Skip sections that contain a position:fixed lightbox — will-change:transform
      // would make the section a containing block, pinning fixed descendants to it
      // instead of the viewport (see bsi_scroll_fx.css .bsi-fx-section rule).
      if (s.getAttribute('data-screen-label') === 'Stylists') continue;
      s.classList.add('bsi-fx-section');
      observeOrShow(s);
    }
    // Headings inside sections (skip the same live-motion sections)
    var heads = root.querySelectorAll ? root.querySelectorAll('section h1, section h2, section h3') : [];
    for (var j = 0; j < heads.length; j++) {
      var h = heads[j];
      if (h.closest && h.closest('.bsi-fx-skip, [data-bsi-fx-skip]')) continue;
      var parentSec = h.closest ? h.closest('section') : null;
      if (parentSec && isDesignAuthoredMotionSection(parentSec)) continue;
      splitHeading(h);
      if (h.classList.contains('bsi-fx-heading')) observeOrShow(h);
    }
  }

  // Matches sections that the design already animates on its own so we do
  // not layer a scroll-reveal fade-up on top and cause a double-move. Keep
  // the list narrow -- one signature per real case, not a general "any
  // animation" broom that would silently skip legitimate content sections.
  //
  // Uses getComputedStyle for the background match (not the raw `style`
  // attribute) because browsers normalise inline styles differently
  // -- Chrome rewrites hex colours to rgb(...) form and re-spaces
  // gradient stops, so a substring on the source `#0f0c0d,#241b1e` misses
  // in the live DOM. Every browser reports the same normalised form via
  // getComputedStyle.
  function isDesignAuthoredMotionSection(section) {
    if (!section) return false;
    // Explicit opt-out from any caller.
    if (section.classList && section.classList.contains('bsi-fx-skip')) return true;
    if (section.hasAttribute && section.hasAttribute('data-bsi-fx-skip')) return true;
    // The LIVE-ticker band under the hero (see enrich_site.html). Its own
    // sheenRun sweep + pulseBars run continuously, so a section fade-up
    // reads as it "jumping into place" after each scroll. Signature:
    // linear-gradient at 100deg with two ink stops #0f0c0d and #241b1e
    // (rgb 15,12,13 and 36,27,30) -- unique to this band.
    var bg = '';
    try { bg = window.getComputedStyle(section).backgroundImage || ''; }
    catch (e) { bg = ''; }
    if (bg.indexOf('linear-gradient') !== -1
        && bg.indexOf('rgb(15, 12, 13)') !== -1
        && bg.indexOf('rgb(36, 27, 30)') !== -1) {
      return true;
    }
    return false;
  }

  function start() {
    ensureProgress();
    ensureTopButton();
    onScroll();
    // Mark html ready — reveal styles only activate once the JS is
    // committed to decorating, so the first paint is always visible.
    document.documentElement.classList.add('bsi-fx-ready');
    decorate(document.body);
    var mo = new MutationObserver(function (mutations) {
      for (var i = 0; i < mutations.length; i++) {
        var added = mutations[i].addedNodes;
        for (var j = 0; j < added.length; j++) {
          var n = added[j];
          if (n && n.nodeType === 1) decorate(n);
        }
      }
    });
    mo.observe(document.body, { childList: true, subtree: true });
    // Capture on document: scroll events from <body> (the mobile scroller)
    // don't reach a window listener.
    document.addEventListener('scroll', onScroll, { passive: true, capture: true });
    window.addEventListener('resize', onScroll, { passive: true });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', start, { once: true });
  } else {
    start();
  }
})();
