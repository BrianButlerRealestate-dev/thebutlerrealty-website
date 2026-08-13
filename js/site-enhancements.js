/* Brian Butler — site-wide enhancements
   1. Scroll-reveal animations on cards/sections
   2. Exit-intent / scroll-depth lead popup (free market report)
   3. Gated resource-download modal
   Loaded on every page via <script src="/js/site-enhancements.js" defer></script>
*/
(function () {
  'use strict';

  /* ==================== SCROLL-REVEAL ANIMATIONS ==================== */
  function initReveal() {
    var els = document.querySelectorAll(
      '.card, .download-card, .area-card, .review-card, .calc-card, .form-card'
    );
    if (!els.length) return;

    if (!('IntersectionObserver' in window) || window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      return; // leave elements fully visible, no observer needed
    }

    els.forEach(function (el) { el.classList.add('reveal'); });

    var io = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) {
            entry.target.classList.add('reveal-visible');
            io.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.12, rootMargin: '0px 0px -40px 0px' }
    );

    els.forEach(function (el) { io.observe(el); });
  }

  /* ==================== SHARED MODAL HELPERS ====================
     Both the lead popup and the gated resource-download modal use this so
     they can't stack on top of each other, background scroll locks while
     either is open, and there's exactly one Netlify AJAX-submit flow to
     maintain instead of two copies that can drift apart. */
  var activeOverlay = null;

  function openModal(overlay) {
    if (activeOverlay && activeOverlay !== overlay) closeModal(activeOverlay);
    activeOverlay = overlay;
    document.body.classList.add('modal-open');
    // Force a style flush before adding .active so the opacity/visibility
    // transition actually plays (rAF alone can stall on a backgrounded tab).
    overlay.getBoundingClientRect();
    overlay.classList.add('active');
  }

  function closeModal(overlay) {
    overlay.classList.remove('active');
    if (activeOverlay === overlay) {
      activeOverlay = null;
      document.body.classList.remove('modal-open');
    }
  }

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && activeOverlay) closeModal(activeOverlay);
  });

  // Wires an overlay's close button/click-outside-to-close, and its form's
  // Netlify AJAX submit -> success/download/error flow.
  function bindModalForm(opts) {
    opts.closeBtn.addEventListener('click', function () { closeModal(opts.overlay); });
    opts.overlay.addEventListener('click', function (e) {
      if (e.target === opts.overlay) closeModal(opts.overlay);
    });

    opts.form.addEventListener('submit', async function (e) {
      e.preventDefault();
      var btn = opts.form.querySelector('.submit-btn');
      btn.textContent = 'Sending...';
      btn.disabled = true;
      try {
        var formData = new FormData(opts.form);
        var response = await fetch('/', {
          method: 'POST',
          headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
          body: new URLSearchParams(formData).toString()
        });
        if (response.ok) {
          opts.formWrap.classList.add('hidden');
          opts.success.classList.remove('hidden');
          var a = document.createElement('a');
          a.href = opts.getDownloadHref();
          a.download = '';
          document.body.appendChild(a);
          a.click();
          a.remove();
        } else {
          throw new Error('Form submission failed');
        }
      } catch (error) {
        btn.textContent = opts.sendingLabel;
        btn.disabled = false;
      }
    });
  }

  /* ==================== EXIT-INTENT / SCROLL-DEPTH LEAD POPUP ==================== */
  var POPUP_SESSION_KEY = 'tbrLeadPopupShown';

  function shouldSkipPopup() {
    // Utility pages: contact/home-value (already mid-conversion) and the 404
    // error page. Netlify serves 404.html for any unmatched route WITHOUT
    // rewriting location.pathname, so a pathname/substring check can never
    // detect the error page — 404.html instead marks itself directly via a
    // body attribute, which this checks instead of guessing from the URL.
    if (document.body.getAttribute('data-page') === 'error') return true;
    var path = location.pathname.toLowerCase();
    if (path.indexOf('contact') !== -1 || path.indexOf('home-value') !== -1) return true;
    try {
      return !!sessionStorage.getItem(POPUP_SESSION_KEY);
    } catch (e) {
      return false; // sessionStorage unavailable (privacy mode) — allow popup once
    }
  }

  function markPopupShown() {
    try { sessionStorage.setItem(POPUP_SESSION_KEY, '1'); } catch (e) { /* ignore */ }
  }

  var POPUP_HTML =
    '<div class="modal-overlay lead-popup" id="leadPopupOverlay">' +
    '  <div class="modal-box">' +
    '    <button type="button" class="modal-close" id="leadPopupClose" aria-label="Close">&times;</button>' +
    '    <div id="leadPopupForm">' +
    '      <div class="section-label">Before You Go</div>' +
    '      <h3>Get the Free East Valley Market Report</h3>' +
    '      <p>Median prices, days on market, and inventory trends for Gilbert, Mesa, Chandler, San Tan Valley, Queen Creek &amp; Florence — updated regularly.</p>' +
    '      <form name="lead-popup" method="POST" data-netlify="true" netlify-honeypot="bot-field" id="leadPopupFormEl">' +
    '        <input type="hidden" name="form-name" value="lead-popup">' +
    '        <p class="hidden"><label>Don\'t fill this out: <input name="bot-field"></label></p>' +
    '        <div class="form-group"><label>Name</label><input type="text" name="name" required></div>' +
    '        <div class="form-group"><label>Email</label><input type="email" name="email" required></div>' +
    '        <button type="submit" class="btn btn-accent submit-btn">Send Me the Report &rarr;</button>' +
    '      </form>' +
    '    </div>' +
    '    <div id="leadPopupSuccess" class="modal-success hidden">' +
    '      <div class="modal-icon">🎉</div>' +
    '      <h3>You\'re In!</h3>' +
    '      <p>Your download should start automatically. Questions in the meantime? <a href="/contact">Reach out anytime</a>.</p>' +
    '      <a href="/downloads/east_valley_market_report.pdf" id="leadPopupDownloadLink" class="btn btn-accent" target="_blank" rel="noopener">Download Now &rarr;</a>' +
    '    </div>' +
    '  </div>' +
    '</div>';

  function injectPopup() {
    if (document.getElementById('leadPopupOverlay')) return;
    var wrap = document.createElement('div');
    wrap.innerHTML = POPUP_HTML;
    document.body.appendChild(wrap.firstElementChild);

    var overlay = document.getElementById('leadPopupOverlay');
    bindModalForm({
      overlay: overlay,
      closeBtn: document.getElementById('leadPopupClose'),
      form: document.getElementById('leadPopupFormEl'),
      formWrap: document.getElementById('leadPopupForm'),
      success: document.getElementById('leadPopupSuccess'),
      sendingLabel: 'Send Me the Report →',
      getDownloadHref: function () { return document.getElementById('leadPopupDownloadLink').href; }
    });
  }

  function showPopup() {
    if (shouldSkipPopup()) return;
    markPopupShown();
    injectPopup();
    var overlay = document.getElementById('leadPopupOverlay');
    if (overlay) openModal(overlay);
  }

  function initPopup() {
    if (shouldSkipPopup()) return;
    var fired = false;
    function fireOnce() {
      if (fired) return;
      fired = true;
      showPopup();
    }

    // Desktop: exit intent (mouse leaves toward the browser chrome). Not
    // armed until someone's actually been on the page a bit -- otherwise a
    // visitor whose cursor is still resting near the address bar right after
    // the page loads (e.g. they just typed the URL and hit enter) trips this
    // instantly, which reads as the popup firing "immediately" even though
    // nothing about their behavior actually signaled they were leaving.
    var exitIntentArmed = false;
    setTimeout(function () { exitIntentArmed = true; }, 20000);
    document.addEventListener('mouseout', function (e) {
      if (exitIntentArmed && !e.relatedTarget && e.clientY < 8) fireOnce();
    });

    // All devices: scroll depth past ~75%, rAF-gated so the layout read in
    // here runs at most once per frame instead of on every raw scroll tick.
    var scrollTicking = false;
    window.addEventListener(
      'scroll',
      function () {
        if (scrollTicking || fired) return;
        scrollTicking = true;
        requestAnimationFrame(function () {
          scrollTicking = false;
          var docHeight = document.body.scrollHeight - window.innerHeight;
          if (docHeight <= 0) return;
          var pct = (window.scrollY / docHeight) * 100;
          if (pct > 75) fireOnce();
        });
      },
      { passive: true }
    );

    // Fallback: time on page
    setTimeout(fireOnce, 120000);
  }

  /* ==================== GATED RESOURCE DOWNLOADS ====================
     Any page can call openDownloadModal(name, path) from a button's onclick.
     The modal + form are injected here so the markup/logic lives in one place;
     a static hidden copy of the "resource-download" form lives in index.html
     purely so Netlify's build-time scanner registers the form name/fields. */
  var RESOURCE_MODAL_HTML =
    '<div class="modal-overlay" id="resourceModalOverlay">' +
    '  <div class="modal-box">' +
    '    <button type="button" class="modal-close" id="resourceModalClose" aria-label="Close">&times;</button>' +
    '    <div id="resourceModalForm">' +
    '      <h3 id="resourceModalTitle">Get Your Free Guide</h3>' +
    '      <p id="resourceModalCopy">Enter your name and email and I\'ll unlock the download instantly.</p>' +
    '      <form name="resource-download" method="POST" data-netlify="true" netlify-honeypot="bot-field" id="resourceModalFormEl">' +
    '        <input type="hidden" name="form-name" value="resource-download">' +
    '        <input type="hidden" name="resource" id="resourceModalField" value="">' +
    '        <p class="hidden"><label>Don\'t fill this out: <input name="bot-field"></label></p>' +
    '        <div class="form-group"><label>Name</label><input type="text" name="name" required></div>' +
    '        <div class="form-group"><label>Email</label><input type="email" name="email" required></div>' +
    '        <button type="submit" class="btn btn-accent submit-btn">Send Me the Guide &rarr;</button>' +
    '      </form>' +
    '    </div>' +
    '    <div id="resourceModalSuccess" class="modal-success hidden">' +
    '      <div class="modal-icon">🎉</div>' +
    '      <h3>You\'re In!</h3>' +
    '      <p>Your download should start automatically. If it doesn\'t, click below.</p>' +
    '      <a href="#" id="resourceModalLink" class="btn btn-accent" target="_blank" rel="noopener">Download Now &rarr;</a>' +
    '    </div>' +
    '  </div>' +
    '</div>';

  function initDownloadModal() {
    if (document.getElementById('resourceModalOverlay')) return;
    var wrap = document.createElement('div');
    wrap.innerHTML = RESOURCE_MODAL_HTML;
    document.body.appendChild(wrap.firstElementChild);

    var overlay = document.getElementById('resourceModalOverlay');
    var form = document.getElementById('resourceModalFormEl');
    var formWrap = document.getElementById('resourceModalForm');
    var success = document.getElementById('resourceModalSuccess');
    var title = document.getElementById('resourceModalTitle');
    var copy = document.getElementById('resourceModalCopy');
    var resourceField = document.getElementById('resourceModalField');
    var downloadLink = document.getElementById('resourceModalLink');
    var pendingPath = '';

    window.openDownloadModal = function (name, path) {
      pendingPath = path;
      resourceField.value = name;
      title.textContent = 'Get "' + name + '"';
      copy.textContent = "Enter your name and email and I'll unlock the download instantly — no spam, just useful info.";
      downloadLink.href = path;
      formWrap.classList.remove('hidden');
      success.classList.add('hidden');
      form.reset();
      var btn = form.querySelector('.submit-btn');
      btn.textContent = 'Send Me the Guide →';
      btn.disabled = false;
      openModal(overlay);
    };

    bindModalForm({
      overlay: overlay,
      closeBtn: document.getElementById('resourceModalClose'),
      form: form,
      formWrap: formWrap,
      success: success,
      sendingLabel: 'Send Me the Guide →',
      getDownloadHref: function () { return pendingPath; }
    });
  }

  document.addEventListener('DOMContentLoaded', function () {
    initReveal();
    initPopup();
    initDownloadModal();
  });
})();
