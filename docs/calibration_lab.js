/* Calibration Lab — Phase G-T MVP widget (v1).
 *
 * Renders the data.json `calibration_status` block as a collapsed pill at the
 * top of the dashboard, expanding to a per-source health panel on click.
 *
 * Defensive: never throws — wraps everything in try/catch consistent with the
 * dashboard's safe(fn) discipline. If `data.calibration_status` is missing,
 * the widget hides itself silently.
 *
 * Skipped in v1 (defer to v2 post-shadow):
 *   - sparklines / per-source charts
 *   - drill-down detail pages
 *   - action buttons ([view log] [retry] [mute 24h])
 *   - last-signal / last-error per source
 */

(function () {
  'use strict';

  function _esc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function _fmtAge(iso) {
    if (!iso) return '—';
    try {
      var ts = new Date(iso).getTime();
      if (!isFinite(ts)) return '—';
      var diff = Date.now() - ts;
      if (diff < 0) return 'just now';
      var mins = Math.floor(diff / 60000);
      if (mins < 1) return 'just now';
      if (mins < 60) return mins + 'm ago';
      var hrs = Math.floor(mins / 60);
      if (hrs < 24) return hrs + 'h ago';
      var days = Math.floor(hrs / 24);
      return days + 'd ago';
    } catch (e) { return '—'; }
  }

  function _statusColorClass(status) {
    return ({
      GREEN:  'cl-green',
      YELLOW: 'cl-yellow',
      RED:    'cl-red',
      DEAD:   'cl-dead',
      PAUSED: 'cl-paused',
    })[status] || 'cl-paused';
  }

  function _aggregateColor(status) {
    if (status.n_red > 0)                 return 'cl-pill-red';
    if (status.n_healthy < status.n_total) return 'cl-pill-amber';
    return 'cl-pill-green';
  }

  function _ensureContainer() {
    var existing = document.getElementById('calibration-lab');
    if (existing) return existing;
    var c = document.createElement('div');
    c.id = 'calibration-lab';
    c.className = 'cl-container';
    // Insert at top of body, ahead of tape if present
    var tape = document.querySelector('.tape-wrap');
    if (tape && tape.parentNode) {
      tape.parentNode.insertBefore(c, tape);
    } else {
      document.body.insertBefore(c, document.body.firstChild);
    }
    return c;
  }

  function _renderCollapsed(status) {
    var phase = _esc(status.phase || '?');
    var costMonth = (status.costs && status.costs.month_spent_usd != null)
      ? '$' + status.costs.month_spent_usd
      : '—';
    var costBudget = (status.costs && status.costs.month_budget_usd != null)
      ? '$' + status.costs.month_budget_usd
      : '—';
    var n_healthy = status.n_healthy || 0;
    var n_total = status.n_total || 0;
    var n_red = status.n_red || 0;
    var redSegment = n_red > 0 ? ' · <span class="cl-red">' + n_red + ' 🔴</span>' : '';
    return (
      '<button type="button" class="cl-pill ' + _aggregateColor(status) + '" data-cl-toggle="1" aria-label="Calibration Lab status">' +
        '<span class="cl-icon">🔬</span>' +
        '<span class="cl-label">Calibration Lab</span>' +
        '<span class="cl-sep">·</span>' +
        '<span class="cl-phase">' + phase + ' ' + (status.phase_progress_pct || 0) + '%</span>' +
        '<span class="cl-sep">·</span>' +
        '<span class="cl-cost">' + costMonth + '/' + costBudget + '</span>' +
        '<span class="cl-sep">·</span>' +
        '<span class="cl-health">' + n_healthy + '/' + n_total + ' 🟢' + redSegment + '</span>' +
        '<span class="cl-caret">▼</span>' +
      '</button>'
    );
  }

  function _renderExpanded(status) {
    var rows = (status.sources || []).map(function (s) {
      var statusClass = _statusColorClass(s.status);
      var icon = s.status_icon || '?';
      var weightStr = s.weight_empirical != null
        ? s.weight_empirical.toFixed(2) + ' (emp.)'
        : (s.weight_prior != null ? s.weight_prior.toFixed(2) + ' (prior)' : '—');
      var baseline = s.baseline_volume_per_week
        ? ' / ~' + s.baseline_volume_per_week + '/wk'
        : '';
      var typeIcon = s.type === 'discrete-event' ? '⚡' : '📊';
      return (
        '<tr class="' + statusClass + '">' +
          '<td class="cl-row-status">' + icon + '</td>' +
          '<td class="cl-row-label" title="' + _esc(s.type) + '">' + typeIcon + ' ' + _esc(s.label) + '</td>' +
          '<td class="cl-row-weight">' + _esc(weightStr) + '</td>' +
          '<td class="cl-row-vol">' + (s.volume_7d || 0) + '/wk' + baseline + '</td>' +
          '<td class="cl-row-poll">' + _fmtAge(s.last_successful_poll) + '</td>' +
          '<td class="cl-row-method">' + _esc(s.phase_method || '') + '</td>' +
        '</tr>'
      );
    }).join('');
    var theses = status.theses || {};
    var warming = status.warming_up
      ? '<div class="cl-warming">Warming up — corpus needs n ≥ 30 graded outcomes for reliable weights (currently ' +
        (theses.outcomes_with_brier || 0) + ').</div>'
      : '';
    var nextMs = status.next_milestone
      ? '<div class="cl-milestone">Next milestone: ' + _esc(status.next_milestone) +
        (status.next_milestone_target ? ' (target ' + _esc(status.next_milestone_target) + ')' : '') +
        '</div>'
      : '';
    return (
      '<div class="cl-panel">' +
        '<div class="cl-panel-header">' +
          '<strong>Phase ' + _esc(status.phase) + ' — ' + _esc(status.phase_label || '') + '</strong>' +
          '<span class="cl-progress">' + (status.phase_progress_pct || 0) + '% · started ' + _esc(status.started_at) + '</span>' +
        '</div>' +
        warming +
        '<table class="cl-table">' +
          '<thead><tr>' +
            '<th></th><th>Source</th><th>Weight</th><th>Volume (7d)</th><th>Last poll</th><th>Method</th>' +
          '</tr></thead>' +
          '<tbody>' + rows + '</tbody>' +
        '</table>' +
        '<div class="cl-footer">' +
          '<span>Theses: ' + (theses.open_theses || 0) + ' open · ' +
          (theses.outcomes_total || 0) + ' outcomes · ' +
          (theses.outcomes_with_brier || 0) + ' graded</span>' +
          (status.generated_at ? '<span class="cl-gen">updated ' + _fmtAge(status.generated_at) + '</span>' : '') +
        '</div>' +
        nextMs +
      '</div>'
    );
  }

  function _wireToggle(container) {
    container.addEventListener('click', function (e) {
      var btn = e.target.closest('[data-cl-toggle]');
      if (!btn) return;
      container.classList.toggle('cl-expanded');
    });
  }

  function buildCalibrationLab(data) {
    try {
      // Accept dashboard's D directly (top-level `let D` not on window).
      // Fallback chain: arg → window.D → window.data
      var src = data || (typeof window !== 'undefined' ? (window.D || window.data) : null);
      var status = (src && src.calibration_status) || null;
      var container = _ensureContainer();
      if (!status) {
        // Hide silently if missing — dashboard pre-deploy or writer crashed
        container.style.display = 'none';
        return;
      }
      container.style.display = '';
      container.innerHTML = _renderCollapsed(status) + _renderExpanded(status);
      // Wire toggle once per render (re-bind safe — container.innerHTML resets state)
      _wireToggle(container);
    } catch (err) {
      try { console.error('[calibration_lab]', err); } catch (e) {}
    }
  }

  // Expose so the dashboard's safe() boot can call it
  if (typeof window !== 'undefined') {
    window.buildCalibrationLab = buildCalibrationLab;
  }
})();
