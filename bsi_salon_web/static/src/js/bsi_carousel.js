/*
 * Testimonials carousel: prev/next arrows (looping), mouse drag, autoplay and
 * a progress bar on top of the native scroll-snap track (.bsi-rev__grid).
 * Touch swipe is the browser's own. Everything is delegated from document,
 * because the app re-renders the cards whenever a review filter changes.
 */
(function () {
  'use strict';

  var AUTOPLAY_MS = 5000;
  var reduceMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var lastInteraction = 0;

  function trackOf(root) { return root && root.querySelector('.bsi-rev__grid'); }

  function stepOf(track) {
    var card = track.querySelector('.bsi-rev__card');
    var gap = parseFloat(getComputedStyle(track).columnGap) || 20;
    return card ? card.getBoundingClientRect().width + gap : track.clientWidth;
  }

  function update(root) {
    var track = trackOf(root);
    if (!track) return;
    var max = track.scrollWidth - track.clientWidth;
    root.classList.toggle('is-static', max <= 4);
    var bar = root.querySelector('.bsi-rev__progress span');
    if (!bar || track.scrollWidth <= 0) return;
    bar.style.width = Math.min(100, (track.clientWidth / track.scrollWidth) * 100) + '%';
    bar.style.left = Math.max(0, (track.scrollLeft / track.scrollWidth) * 100) + '%';
  }

  function go(root, dir) {
    var track = trackOf(root);
    if (!track) return;
    var max = track.scrollWidth - track.clientWidth;
    if (max <= 4) return;
    var x;
    if (dir > 0 && track.scrollLeft >= max - 4) x = 0;
    else if (dir < 0 && track.scrollLeft <= 4) x = max;
    else x = track.scrollLeft + dir * stepOf(track);
    track.scrollTo({ left: x, behavior: reduceMotion ? 'auto' : 'smooth' });
  }

  function updateAll() {
    var roots = document.querySelectorAll('.bsi-rev');
    for (var i = 0; i < roots.length; i++) update(roots[i]);
  }

  document.addEventListener('click', function (e) {
    var arrow = e.target.closest && e.target.closest('.bsi-rev__arrow');
    if (arrow) {
      lastInteraction = Date.now();
      go(arrow.closest('.bsi-rev'), arrow.classList.contains('bsi-rev__arrow--prev') ? -1 : 1);
      return;
    }
    var chip = e.target.closest && e.target.closest('.bsi-rev__chip');
    if (chip) {
      // A new filter re-renders the cards; start the track from the beginning.
      var root = chip.closest('.bsi-rev');
      lastInteraction = Date.now();
      setTimeout(function () {
        var track = trackOf(root);
        if (track) track.scrollLeft = 0;
        update(root);
      }, 60);
    }
  });

  // Scroll events don't bubble; capture them from any track.
  document.addEventListener('scroll', function (e) {
    var t = e.target;
    if (t && t.classList && t.classList.contains('bsi-rev__grid')) update(t.closest('.bsi-rev'));
  }, { passive: true, capture: true });

  window.addEventListener('resize', updateAll, { passive: true });

  // Mouse drag (touch and pen already scroll natively).
  var drag = null;
  document.addEventListener('pointerdown', function (e) {
    if (e.pointerType !== 'mouse' || e.button !== 0) return;
    var track = e.target.closest && e.target.closest('.bsi-rev__grid');
    if (!track) return;
    drag = { track: track, x: e.clientX, left: track.scrollLeft, moved: false };
  });
  document.addEventListener('pointermove', function (e) {
    if (!drag) return;
    var dx = e.clientX - drag.x;
    if (!drag.moved && Math.abs(dx) > 5) {
      drag.moved = true;
      drag.track.classList.add('is-drag');
    }
    if (drag.moved) drag.track.scrollLeft = drag.left - dx;
  });
  function endDrag() {
    if (!drag) return;
    var d = drag;
    drag = null;
    if (!d.moved) return;
    lastInteraction = Date.now();
    d.track.classList.remove('is-drag');
    // Settle on the nearest card once snapping is back on.
    var step = stepOf(d.track);
    d.track.scrollTo({ left: Math.round(d.track.scrollLeft / step) * step, behavior: 'smooth' });
  }
  document.addEventListener('pointerup', endDrag);
  document.addEventListener('pointercancel', endDrag);

  // Autoplay only while the carousel is on screen, the tab is visible and the
  // visitor isn't hovering, focused in it, or interacting with it.
  if (!reduceMotion) {
    setInterval(function () {
      if (document.hidden || drag || Date.now() - lastInteraction < AUTOPLAY_MS * 1.6) return;
      var roots = document.querySelectorAll('.bsi-rev');
      for (var i = 0; i < roots.length; i++) {
        var root = roots[i];
        var r = root.getBoundingClientRect();
        if (r.bottom < 0 || r.top > window.innerHeight) continue;
        var kbFocus = false;
        try { kbFocus = !!root.querySelector(':focus-visible'); } catch (err) { kbFocus = false; }
        if (root.matches(':hover') || kbFocus) continue;
        go(root, 1);
      }
    }, AUTOPLAY_MS);
  }

  // Cards arrive after the app hydrates; keep the progress bar honest.
  var pending = null;
  new MutationObserver(function () {
    if (pending) return;
    pending = setTimeout(function () { pending = null; updateAll(); }, 150);
  }).observe(document.documentElement, { childList: true, subtree: true });
  updateAll();
})();
