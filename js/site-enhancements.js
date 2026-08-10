/* The Butler Realty — site-wide enhancements
   1. Scroll-reveal animations on cards/sections
   2. Exit-intent / scroll-depth lead popup (free market report)
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

  /* ==================== EXIT-INTENT / SCROLL-DEPTH LEAD POPUP ==================== */
  var POPUP_SESSION_KEY = 'tbrLeadPopupShown';
  // Don't interrupt people already mid-conversion or on utility pages
  var SKIP_PATH_FRAGMENTS = ['contact', 'home-value', '404'];

  function shouldSkipPopup() {
    var path = location.pathname.toLowerCase();
    for (var i = 0; i < SKIP_PATH_FRAGMENTS.length; i++) {
      if (path.indexOf(SKIP_PATH_FRAGMENTS[i]) !== -1) return true;
    }
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
    '      <a href="/downloads/East_Valley_Market_Report.pdf" id="leadPopupDownloadLink" class="btn btn-accent" target="_blank" rel="noopener">Download Now &rarr;</a>' +
    '    </div>' +
    '  </div>' +
    '</div>';

  function injectPopup() {
    if (document.getElementById('leadPopupOverlay')) return;
    var wrap = document.createElement('div');
    wrap.innerHTML = POPUP_HTML;
    document.body.appendChild(wrap.firstElementChild);
    wireUpPopup();
  }

  function wireUpPopup() {
    var overlay = document.getElementById('leadPopupOverlay');
    var closeBtn = document.getElementById('leadPopupClose');
    var form = document.getElementById('leadPopupFormEl');
    var formWrap = document.getElementById('leadPopupForm');
    var success = document.getElementById('leadPopupSuccess');

    function close() { overlay.classList.remove('active'); }
    closeBtn.addEventListener('click', close);
    overlay.addEventListener('click', function (e) { if (e.target === overlay) close(); });
    document.addEventListener('keydown', function (e) { if (e.key === 'Escape') close(); });

    form.addEventListener('submit', async function (e) {
      e.preventDefault();
      var btn = form.querySelector('.submit-btn');
      btn.textContent = 'Sending...';
      btn.disabled = true;
      try {
        var formData = new FormData(form);
        var response = await fetch('/', {
          method: 'POST',
          headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
          body: new URLSearchParams(formData).toString()
        });
        if (response.ok) {
          formWrap.classList.add('hidden');
          success.classList.remove('hidden');
          var a = document.createElement('a');
          a.href = document.getElementById('leadPopupDownloadLink').href;
          a.download = '';
          document.body.appendChild(a);
          a.click();
          a.remove();
        } else {
          throw new Error('Form submission failed');
        }
      } catch (error) {
        btn.textContent = 'Send Me the Report →';
        btn.disabled = false;
      }
    });
  }

  function showPopup() {
    if (shouldSkipPopup()) return;
    markPopupShown();
    injectPopup();
    var overlay = document.getElementById('leadPopupOverlay');
    if (!overlay) return;
    // Force a style flush before adding .active so the opacity/visibility
    // transition actually plays (rAF alone can stall on a backgrounded tab).
    overlay.getBoundingClientRect();
    overlay.classList.add('active');
  }

  function initPopup() {
    if (shouldSkipPopup()) return;
    var fired = false;
    function fireOnce(trigger) {
      return function () {
        if (fired) return;
        fired = true;
        showPopup();
      };
    }

    // Desktop: exit intent (mouse leaves toward the browser chrome)
    document.addEventListener('mouseout', function (e) {
      if (!e.relatedTarget && e.clientY < 8) fireOnce('exit-intent')();
    });

    // All devices: scroll depth past ~55%
    window.addEventListener(
      'scroll',
      function () {
        var docHeight = document.body.scrollHeight - window.innerHeight;
        if (docHeight <= 0) return;
        var pct = (window.scrollY / docHeight) * 100;
        if (pct > 55) fireOnce('scroll-depth')();
      },
      { passive: true }
    );

    // Fallback: time on page
    setTimeout(fireOnce('time-on-page'), 45000);
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
      overlay.classList.add('active');
    };

    function close() { overlay.classList.remove('active'); }
    document.getElementById('resourceModalClose').addEventListener('click', close);
    overlay.addEventListener('click', function (e) { if (e.target === overlay) close(); });
    document.addEventListener('keydown', function (e) { if (e.key === 'Escape') close(); });

    form.addEventListener('submit', async function (e) {
      e.preventDefault();
      var btn = form.querySelector('.submit-btn');
      btn.textContent = 'Sending...';
      btn.disabled = true;
      try {
        var formData = new FormData(form);
        var response = await fetch('/', {
          method: 'POST',
          headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
          body: new URLSearchParams(formData).toString()
        });
        if (response.ok) {
          formWrap.classList.add('hidden');
          success.classList.remove('hidden');
          var a = document.createElement('a');
          a.href = pendingPath;
          a.download = '';
          document.body.appendChild(a);
          a.click();
          a.remove();
        } else {
          throw new Error('Form submission failed');
        }
      } catch (error) {
        btn.textContent = 'Send Me the Guide →';
        btn.disabled = false;
      }
    });
  }

  document.addEventListener('DOMContentLoaded', function () {
    initReveal();
    initPopup();
    initDownloadModal();
  });
})();
