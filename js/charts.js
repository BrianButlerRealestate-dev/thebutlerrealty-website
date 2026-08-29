/* Brian Butler — self-contained data visualization for the market-data pages.
   1. Rate-history line chart          -> mortgage-rates.html  (gated on #rateHistoryBody)
   2. Market stat-tiles + paired bars  -> market-updates/*     (gated on [data-market-viz])

   Hand-rolled inline SVG, no charting library. Every value is read from a table
   already on the page, so nothing is hardcoded and future monthly pages inherit
   the visualization for free. If JS is off, or the source table is missing/empty,
   the chart simply doesn't render and the existing table stays as the source of
   truth. prefers-reduced-motion is honored in styles.css — the draw animation
   only runs under (prefers-reduced-motion: no-preference).

   Loaded (defer) on mortgage-rates.html and every market-updates/*.html page.
*/
(function () {
  'use strict';

  var SVGNS = 'http://www.w3.org/2000/svg';

  function el(tag, attrs, text) {
    var node = document.createElementNS(SVGNS, tag);
    if (attrs) {
      for (var k in attrs) {
        if (Object.prototype.hasOwnProperty.call(attrs, k)) node.setAttribute(k, attrs[k]);
      }
    }
    if (text != null) node.textContent = text;
    return node;
  }

  // "1,334" -> 1334 ; "86 days" -> 86 ; "6.65%" -> 6.65 ; "+2.3%" -> 2.3
  function num(str) {
    if (str == null) return NaN;
    var m = String(str).replace(/,/g, '').match(/-?\d+(\.\d+)?/);
    return m ? parseFloat(m[0]) : NaN;
  }

  // leading-sign arrow for a delta string; value keeps the table's exact text
  // minus the redundant leading sign (mirrors the on-page rate-card style).
  function withArrow(str) {
    var s = String(str).trim();
    if (/^\+/.test(s)) return '▲ ' + s.replace(/^\+/, '');
    if (/^-/.test(s)) return '▼ ' + s.replace(/^-/, '');
    return s;
  }

  /* ==================== 1. RATE-HISTORY LINE CHART ==================== */
  function initRateChart() {
    var tbody = document.getElementById('rateHistoryBody');
    if (!tbody) return;
    var rows = tbody.querySelectorAll('tr');
    if (rows.length < 2) return;

    // DOM rows are newest-first; walk backwards to plot oldest -> newest.
    var pts = [];
    for (var i = rows.length - 1; i >= 0; i--) {
      var c = rows[i].querySelectorAll('td');
      if (c.length < 3) continue;
      var week = c[0].textContent.trim();
      var r30 = num(c[1].textContent);
      var r15 = num(c[2].textContent);
      if (!week || isNaN(r30) || isNaN(r15)) continue;
      pts.push({ week: week, r30: r30, r15: r15 });
    }
    if (pts.length < 2) return;

    var W = 700, H = 220;
    var padL = 46, padR = 66, padT = 18, padB = 34;
    var plotW = W - padL - padR, plotH = H - padT - padB;

    var all = [];
    pts.forEach(function (p) { all.push(p.r30, p.r15); });
    var lo = Math.min.apply(null, all), hi = Math.max.apply(null, all);
    // Rates sit in a narrow band (~5.9-6.7) — do NOT zero-base; pad tightly.
    var span = (hi - lo) * 0.35 || 0.15;
    var yLo = lo - span, yHi = hi + span;

    function x(idx) { return padL + (plotW * idx) / (pts.length - 1); }
    function y(val) { return padT + plotH * (1 - (val - yLo) / (yHi - yLo)); }

    var svg = el('svg', {
      viewBox: '0 0 ' + W + ' ' + H,
      role: 'img',
      'aria-label': 'Line chart of 30-year and 15-year fixed mortgage rates across the weeks listed in the table below.'
    });

    // 3 horizontal gridlines + y labels
    [yLo + (yHi - yLo) * 0.15, (yLo + yHi) / 2, yHi - (yHi - yLo) * 0.15].forEach(function (gv) {
      svg.appendChild(el('line', {
        x1: padL, y1: y(gv), x2: W - padR, y2: y(gv),
        stroke: 'var(--gray-100)', 'stroke-width': 1
      }));
      svg.appendChild(el('text', {
        x: padL - 8, y: y(gv) + 3, 'text-anchor': 'end',
        'font-size': 10, fill: 'var(--gray-500)'
      }, gv.toFixed(2) + '%'));
    });

    function series(key, color, label) {
      var points = pts.map(function (p, idx) { return x(idx) + ',' + y(p[key]); }).join(' ');
      svg.appendChild(el('polyline', {
        points: points, fill: 'none', stroke: color, 'stroke-width': 2.5,
        'stroke-linejoin': 'round', 'stroke-linecap': 'round', 'class': 'svg-line'
      }));
      pts.forEach(function (p, idx) {
        svg.appendChild(el('circle', { cx: x(idx), cy: y(p[key]), r: 3, fill: color }));
      });
      var last = pts[pts.length - 1];
      svg.appendChild(el('text', {
        x: x(pts.length - 1) + 8, y: y(last[key]) + 3,
        'font-size': 11, 'font-weight': 700, fill: color
      }, label));
    }
    series('r30', 'var(--primary)', '30-yr');
    series('r15', 'var(--accent)', '15-yr');

    // x labels: first + last week only
    svg.appendChild(el('text', {
      x: padL, y: H - 9, 'text-anchor': 'start', 'font-size': 10, fill: 'var(--gray-500)'
    }, pts[0].week));
    svg.appendChild(el('text', {
      x: W - padR, y: H - 9, 'text-anchor': 'end', 'font-size': 10, fill: 'var(--gray-500)'
    }, pts[pts.length - 1].week));

    var fig = document.createElement('figure');
    fig.className = 'svg-chart svg-chart--line';
    fig.appendChild(svg);
    var cap = document.createElement('figcaption');
    cap.textContent = '30-year (navy) vs 15-year (blue) fixed rate, oldest to newest. Exact figures in the table below.';
    fig.appendChild(cap);

    var table = tbody.closest('table');
    var anchor = (table && table.parentElement) || table;
    if (!anchor || !anchor.parentNode) return;
    anchor.parentNode.insertBefore(fig, anchor);

    // Now the polylines are rendered — measure them for the CSS draw animation.
    Array.prototype.forEach.call(fig.querySelectorAll('.svg-line'), function (ln) {
      try {
        var len = ln.getTotalLength();
        if (len) ln.style.setProperty('--dash', len);
      } catch (e) { /* getTotalLength unsupported — line just renders solid */ }
    });
  }

  /* ==================== 2. MARKET STAT-TILES + PAIRED BARS ==================== */
  function initMarketViz() {
    var host = document.querySelector('[data-market-viz]');
    if (!host) return;
    var table = document.querySelector('.market-table');
    if (!table) return;
    var rows = table.querySelectorAll('tbody tr');
    if (!rows.length) return;

    // short metric name -> { valueText, valueNum, changeText, changeClass, labelFull }
    var data = {};
    Array.prototype.forEach.call(rows, function (tr) {
      var cells = tr.querySelectorAll('td');
      if (cells.length < 3) return;
      var nameCell = cells[0];
      var firstNode = nameCell.childNodes[0];
      var short = (firstNode && firstNode.nodeType === 3)
        ? firstNode.textContent.trim()
        : nameCell.textContent.replace(/\s+/g, ' ').trim();
      var chg = cells[2].querySelector('.change-up, .change-down, .change-neutral');
      data[short] = {
        valueText: cells[1].textContent.trim(),
        valueNum: num(cells[1].textContent),
        changeText: chg ? chg.textContent.replace(/\s+/g, ' ').trim() : '',
        changeClass: chg ? chg.className : '',
        labelFull: nameCell.textContent.replace(/\s+/g, ' ').trim()
      };
    });

    function find(sub) {
      sub = sub.toLowerCase();
      for (var k in data) {
        if (Object.prototype.hasOwnProperty.call(data, k) && k.toLowerCase().indexOf(sub) !== -1) {
          return data[k];
        }
      }
      return null;
    }

    /* --- a. headline stat tiles --- */
    var tiles = document.createElement('div');
    tiles.className = 'stat-tiles';
    var tileMade = false;
    ['Sold Listings', 'Months of Supply', 'Days on Market', 'Sold-to-List'].forEach(function (key) {
      var d = find(key);
      if (!d) return;
      tileMade = true;
      var tile = document.createElement('div');
      tile.className = 'stat-tile';

      var val = document.createElement('div');
      val.className = 'stat-tile__value';
      val.textContent = d.valueText;
      tile.appendChild(val);

      var lab = document.createElement('span');
      lab.className = 'stat-tile__label';
      lab.textContent = d.labelFull;
      tile.appendChild(lab);

      if (d.changeText) {
        var delta = document.createElement('span');
        delta.className = (d.changeClass ? d.changeClass + ' ' : '') + 'stat-tile__delta';
        delta.textContent = withArrow(d.changeText);
        tile.appendChild(delta);
      }
      tiles.appendChild(tile);
    });
    if (tileMade) host.appendChild(tiles);

    /* --- b. paired-bar chart for the count metrics --- */
    var bars = [];
    ['Sold Listings', 'New Listings', 'Active Listings', 'Under Contract'].forEach(function (k) {
      var d = find(k);
      if (!d || isNaN(d.valueNum)) return;
      var prior = NaN;
      if (d.changeText.indexOf('%') !== -1) {
        var pct = num(d.changeText);
        if (!isNaN(pct)) prior = d.valueNum / (1 + pct / 100);
      } else if (/flat/i.test(d.changeText)) {
        prior = d.valueNum;
      }
      bars.push({ label: d.labelFull, now: d.valueNum, prior: prior });
    });
    if (!bars.length) return;

    var W = 700, H = 250;
    var padX = 12, padT = 26, padB = 44;
    var plotH = H - padT - padB;
    var baseY = padT + plotH;
    var maxV = 0;
    bars.forEach(function (b) { maxV = Math.max(maxV, b.now, isNaN(b.prior) ? 0 : b.prior); });
    maxV = maxV * 1.14 || 1;

    var clusterW = (W - padX * 2) / bars.length;
    var barW = Math.min(44, clusterW * 0.28);
    var gap = 8;

    var svg = el('svg', {
      viewBox: '0 0 ' + W + ' ' + H, role: 'img',
      'aria-label': 'Bar chart comparing this month and prior month counts for sold, new, active and under-contract listings. Figures in the table below.'
    });
    svg.appendChild(el('line', {
      x1: padX, y1: baseY, x2: W - padX, y2: baseY, stroke: 'var(--gray-300)', 'stroke-width': 1
    }));

    var g = el('g', { 'class': 'svg-bars' });
    bars.forEach(function (b, idx) {
      var cx = padX + clusterW * idx + clusterW / 2;
      var x0 = cx - (barW * 2 + gap) / 2;

      function drawBar(val, x, color) {
        if (isNaN(val)) return;
        var h = plotH * (val / maxV);
        g.appendChild(el('rect', {
          x: x, y: baseY - h, width: barW, height: h, fill: color, rx: 2, 'class': 'svg-bar'
        }));
        g.appendChild(el('text', {
          x: x + barW / 2, y: baseY - h - 6, 'text-anchor': 'middle',
          'font-size': 11, 'font-weight': 700, fill: 'var(--gray-700)'
        }, Math.round(val).toLocaleString()));
      }
      drawBar(b.prior, x0, 'var(--gray-300)');
      drawBar(b.now, x0 + barW + gap, 'var(--primary)');

      svg.appendChild(el('text', {
        x: cx, y: baseY + 18, 'text-anchor': 'middle', 'font-size': 11, fill: 'var(--gray-700)'
      }, b.label));
    });
    svg.appendChild(g);

    // legend
    var lg = el('g', {});
    lg.appendChild(el('rect', { x: padX, y: 5, width: 11, height: 11, fill: 'var(--primary)', rx: 2 }));
    lg.appendChild(el('text', { x: padX + 17, y: 14, 'font-size': 10, fill: 'var(--gray-500)' }, 'This month'));
    lg.appendChild(el('rect', { x: padX + 92, y: 5, width: 11, height: 11, fill: 'var(--gray-300)', rx: 2 }));
    lg.appendChild(el('text', { x: padX + 109, y: 14, 'font-size': 10, fill: 'var(--gray-500)' }, 'Prior month'));
    svg.appendChild(lg);

    var fig = document.createElement('figure');
    fig.className = 'svg-chart svg-chart--bars';
    fig.appendChild(svg);
    var cap = document.createElement('figcaption');
    cap.textContent = 'Listing counts, this month vs prior month. Prior-month values derived from the table’s month-over-month change.';
    fig.appendChild(cap);
    host.appendChild(fig);
  }

  document.addEventListener('DOMContentLoaded', function () {
    initRateChart();
    initMarketViz();
  });
})();
