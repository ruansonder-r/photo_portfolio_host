/* Ruan Sonder — portfolio behaviour.
 * No inline handlers: everything binds by delegation, so filenames can never
 * be interpolated into executable markup.
 */
(function () {
  'use strict';

  var reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  /* ------------------------------------------------------------------ *
   * Carousel
   * Scroll position is the single source of truth. The buttons and dots
   * only ever call scrollTo, so the controls can never disagree with what
   * is on screen — the failure mode of the old transform-based version.
   * ------------------------------------------------------------------ */

  function initCarousel(root) {
    var track = root.querySelector('[data-carousel-track]');
    if (!track) return;

    var slides = Array.prototype.slice.call(track.querySelectorAll('[data-carousel-slide]'));
    if (slides.length === 0) return;

    var prev = root.querySelector('[data-carousel-prev]');
    var next = root.querySelector('[data-carousel-next]');
    var dotsBox = root.querySelector('[data-carousel-dots]');
    var index = 0;
    var timer = null;
    var AUTOPLAY_MS = 6500;

    var dots = [];
    if (dotsBox && slides.length > 1) {
      slides.forEach(function (_, i) {
        var dot = document.createElement('button');
        dot.type = 'button';
        dot.className = 'carousel__dot';
        dot.setAttribute('aria-label', 'Go to photo ' + (i + 1));
        dot.addEventListener('click', function () { goTo(i); restart(); });
        dotsBox.appendChild(dot);
        dots.push(dot);
      });
    }

    function goTo(i, instant) {
      index = Math.max(0, Math.min(i, slides.length - 1));
      var slide = slides[index];
      // Slides are content-width, so centre the target rather than aligning
      // its left edge -- otherwise the active photo drifts off to one side.
      track.scrollTo({
        left: slide.offsetLeft - track.offsetLeft - (track.clientWidth - slide.offsetWidth) / 2,
        behavior: (instant || reduceMotion) ? 'auto' : 'smooth'
      });
    }

    function sync() {
      // Whichever slide's centre is nearest the track's centre is current.
      var centre = track.scrollLeft + track.clientWidth / 2;
      var best = 0;
      var bestGap = Infinity;
      slides.forEach(function (slide, i) {
        var gap = Math.abs(slide.offsetLeft - track.offsetLeft + slide.offsetWidth / 2 - centre);
        if (gap < bestGap) { bestGap = gap; best = i; }
      });
      index = best;
      slides.forEach(function (slide, i) {
        slide.classList.toggle('is-active', i === index);
      });
      dots.forEach(function (dot, i) {
        dot.setAttribute('aria-current', i === index ? 'true' : 'false');
      });
      if (prev) prev.disabled = index === 0;
      if (next) next.disabled = index === slides.length - 1;
    }

    function stop() { if (timer) { clearInterval(timer); timer = null; } }
    function start() {
      if (reduceMotion || slides.length < 2 || timer) return;
      timer = setInterval(function () {
        goTo(index >= slides.length - 1 ? 0 : index + 1);
      }, AUTOPLAY_MS);
    }
    function restart() { stop(); start(); }

    if (prev) prev.addEventListener('click', function () { goTo(index - 1); restart(); });
    if (next) next.addEventListener('click', function () { goTo(index + 1); restart(); });

    var raf;
    track.addEventListener('scroll', function () {
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(sync);
    }, { passive: true });

    root.addEventListener('mouseenter', stop);
    root.addEventListener('mouseleave', start);
    root.addEventListener('focusin', stop);
    root.addEventListener('focusout', start);
    document.addEventListener('visibilitychange', function () {
      document.hidden ? stop() : start();
    });

    // Arrow keys act on the carousel only while it holds focus, so they no
    // longer fight the lightbox for the same keystrokes.
    root.addEventListener('keydown', function (event) {
      if (event.key === 'ArrowLeft') { event.preventDefault(); goTo(index - 1); restart(); }
      if (event.key === 'ArrowRight') { event.preventDefault(); goTo(index + 1); restart(); }
    });

    window.addEventListener('resize', function () { goTo(index, true); sync(); });
    goTo(0, true);
    sync();
    start();
  }

  /* ------------------------------------------------------------------ *
   * Lightbox
   * ------------------------------------------------------------------ */

  var Lightbox = (function () {
    var root, imgEl, capEl, countEl, downloadEl;
    var items = [];
    var index = 0;
    var lastFocused = null;

    function ensure() {
      if (root) return root;
      root = document.getElementById('lightbox');
      if (!root) return null;
      imgEl = root.querySelector('[data-lightbox-image]');
      capEl = root.querySelector('[data-lightbox-caption]');
      countEl = root.querySelector('[data-lightbox-count]');
      downloadEl = root.querySelector('[data-lightbox-download]');

      root.querySelector('[data-lightbox-close]').addEventListener('click', close);
      root.querySelector('[data-lightbox-prev]').addEventListener('click', function () { step(-1); });
      root.querySelector('[data-lightbox-next]').addEventListener('click', function () { step(1); });

      // Click the backdrop (but not the photo or the controls) to dismiss.
      root.addEventListener('click', function (event) {
        if (event.target === root || event.target.hasAttribute('data-lightbox-stage')) close();
      });

      document.addEventListener('keydown', function (event) {
        if (!root.classList.contains('is-open')) return;
        if (event.key === 'Escape') { event.preventDefault(); close(); }
        else if (event.key === 'ArrowLeft') { event.preventDefault(); step(-1); }
        else if (event.key === 'ArrowRight') { event.preventDefault(); step(1); }
        else if (event.key === 'Tab') trapFocus(event);
      });

      addSwipe();
      return root;
    }

    function trapFocus(event) {
      var focusable = root.querySelectorAll('button, [href]');
      if (!focusable.length) return;
      var first = focusable[0];
      var last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault(); last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault(); first.focus();
      }
    }

    function addSwipe() {
      var startX = 0, startY = 0, tracking = false;
      var stage = root.querySelector('[data-lightbox-stage]');
      stage.addEventListener('touchstart', function (e) {
        startX = e.touches[0].clientX; startY = e.touches[0].clientY; tracking = true;
      }, { passive: true });
      stage.addEventListener('touchend', function (e) {
        if (!tracking) return;
        tracking = false;
        var dx = e.changedTouches[0].clientX - startX;
        var dy = e.changedTouches[0].clientY - startY;
        if (Math.abs(dy) > Math.abs(dx) && dy > 70) { close(); return; }
        if (Math.abs(dx) > 50) step(dx < 0 ? 1 : -1);
      }, { passive: true });
    }

    function render() {
      var item = items[index];
      if (!item) return;
      imgEl.src = item.full;
      imgEl.alt = item.alt;
      capEl.textContent = item.alt;
      countEl.textContent = (index + 1) + ' / ' + items.length;
      if (downloadEl) {
        if (item.download) {
          downloadEl.href = item.download;
          downloadEl.hidden = false;
        } else {
          downloadEl.hidden = true;
        }
      }
      // Warm the neighbours so stepping feels instant.
      [index - 1, index + 1].forEach(function (i) {
        if (items[i]) { var pre = new Image(); pre.src = items[i].full; }
      });
    }

    function step(delta) {
      if (items.length < 2) return;
      index = (index + delta + items.length) % items.length;
      render();
    }

    function open(list, start) {
      if (!ensure() || !list.length) return;
      items = list;
      index = start || 0;
      lastFocused = document.activeElement;
      render();
      root.classList.add('is-open');
      root.setAttribute('aria-hidden', 'false');
      document.body.classList.add('is-locked');
      root.querySelector('[data-lightbox-close]').focus();
    }

    function close() {
      if (!root) return;
      root.classList.remove('is-open');
      root.setAttribute('aria-hidden', 'true');
      document.body.classList.remove('is-locked');
      imgEl.removeAttribute('src');
      if (lastFocused && lastFocused.focus) lastFocused.focus();
    }

    return { open: open, close: close };
  })();

  function collect(container) {
    return Array.prototype.slice.call(container.querySelectorAll('[data-full]')).map(function (el) {
      return {
        full: el.getAttribute('data-full'),
        alt: el.getAttribute('data-alt') || '',
        download: el.getAttribute('data-download') || ''
      };
    });
  }

  /* ------------------------------------------------------------------ *
   * Clipboard
   * ------------------------------------------------------------------ */

  function copyFrom(button) {
    var target = document.querySelector(button.getAttribute('data-copy-target'));
    if (!target) return;
    var text = target.value !== undefined ? target.value : target.textContent;
    var done = function () {
      var original = button.textContent;
      button.textContent = 'Copied';
      setTimeout(function () { button.textContent = original; }, 1800);
    };
    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard.writeText(text).then(done).catch(function () {});
    } else {
      target.select && target.select();
      try { document.execCommand('copy'); done(); } catch (e) {}
    }
  }

  /* --- Line items on the document form ------------------------------- */
  /* Add and remove rows against a Django formset, and keep a running total
     as you type. The figures here are a convenience only -- the server
     recalculates every one of them on save. */

  function initDocumentForm(form) {
    var rows = form.querySelector('[data-line-rows]');
    var template = form.querySelector('[data-empty-line]');
    var addButton = form.querySelector('[data-add-line]');
    var totalForms = form.querySelector('[name$="-TOTAL_FORMS"]');
    if (!rows || !totalForms) return;

    function money(value) {
      var parts = Math.abs(value).toFixed(2).split('.');
      var whole = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, ' ');
      return (value < 0 ? '-' : '') + whole + '.' + parts[1];
    }

    function recalculate() {
      var subtotal = 0;
      rows.querySelectorAll('[data-line-row]').forEach(function (row) {
        var deleted = row.querySelector('input[type="checkbox"][name$="-DELETE"]');
        var removed = deleted && deleted.checked;
        row.classList.toggle('is-removed', !!removed);

        var quantity = parseFloat(row.querySelector('[data-line-quantity]').value) || 0;
        var price = parseFloat(row.querySelector('[data-line-price]').value) || 0;
        // Round each line before summing, the way the server does, so the
        // running figure agrees with the saved one to the cent.
        var lineTotal = Math.round(quantity * price * 100) / 100;

        row.querySelector('[data-line-total]').textContent = money(lineTotal);
        if (!removed) subtotal += lineTotal;
      });

      var adjustmentField = form.querySelector('[name="adjustment_amount"]');
      var adjustment = adjustmentField ? parseFloat(adjustmentField.value) || 0 : 0;

      var subtotalEl = form.querySelector('[data-running-subtotal]');
      var totalEl = form.querySelector('[data-running-total]');
      if (subtotalEl) subtotalEl.textContent = money(subtotal);
      if (totalEl) totalEl.textContent = money(subtotal + adjustment);
    }

    function addRow() {
      var index = parseInt(totalForms.value, 10);
      var html = template.innerHTML.replace(/__prefix__/g, index);
      var body = document.createElement('tbody');
      body.innerHTML = html.trim();
      var row = body.querySelector('[data-line-row]');
      rows.appendChild(row);
      totalForms.value = index + 1;
      var first = row.querySelector('textarea, input[type="text"]');
      if (first) first.focus();
      recalculate();
    }

    if (addButton) addButton.addEventListener('click', addRow);
    form.addEventListener('input', recalculate);
    form.addEventListener('change', recalculate);
    recalculate();
  }

  /* ------------------------------------------------------------------ */

  document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('[data-carousel]').forEach(initCarousel);

    document.querySelectorAll('[data-lightbox-group]').forEach(function (group) {
      group.addEventListener('click', function (event) {
        var trigger = event.target.closest('[data-full]');
        if (!trigger || !group.contains(trigger)) return;
        // Let the per-photo download link do its own job.
        if (event.target.closest('a[download], a[data-direct]')) return;
        event.preventDefault();
        var list = collect(group);
        Lightbox.open(list, list.findIndex(function (item) {
          return item.full === trigger.getAttribute('data-full');
        }));
      });
    });

    document.addEventListener('click', function (event) {
      var button = event.target.closest('[data-copy-target]');
      if (button) copyFrom(button);
    });

    document.querySelectorAll('[data-document-form]').forEach(initDocumentForm);
  });
})();
