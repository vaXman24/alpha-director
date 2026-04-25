/**
 * Trading Catalysts Calendar — Alpha Director Layer 2
 * Reads events.json published by event_worker.py
 * Injects a collapsible card + playbook modal into the dashboard.
 */

(function () {
  'use strict';

  // ── Category colours (match dashboard CSS vars) ───────────────────────────
  const CAT_COLOR = {
    seasonal:    '#ffd740',
    corporate:   '#448aff',
    industry:    '#00e676',
    macro:       '#ff3d71',
    bonus:       '#ce93d8',
  };

  const CAT_LABEL = {
    seasonal:    'Seasonal',
    corporate:   'Corporate',
    industry:    'Industry',
    macro:       'Macro',
    bonus:       'High-Alpha',
  };

  const STATUS_STYLE = {
    live:     { bg: 'rgba(255,61,113,.18)',  color: '#ff3d71', label: 'LIVE'     },
    imminent: { bg: 'rgba(255,215,64,.18)',  color: '#ffd740', label: 'IMMINENT' },
    upcoming: { bg: 'rgba(0,230,118,.13)',   color: '#00e676', label: 'UPCOMING' },
    monitor:  { bg: 'rgba(68,138,255,.13)',  color: '#448aff', label: 'MONITOR'  },
    future:   { bg: 'rgba(100,116,139,.12)', color: '#64748b', label: 'FUTURE'   },
  };

  // ── Inject CSS once ────────────────────────────────────────────────────────
  const STYLE = `
  /* ── Trading Catalysts card ── */
  #cat-body .cat-event-row {
    display:grid;
    grid-template-columns:110px 1fr auto;
    gap:8px 12px;
    align-items:center;
    padding:9px 0;
    border-bottom:1px solid rgba(255,255,255,.05);
    cursor:pointer;
    transition:background .15s;
    border-radius:6px;
  }
  #cat-body .cat-event-row:hover { background:rgba(255,255,255,.03); }
  #cat-body .cat-event-row:last-child { border-bottom:none; }

  .cat-date-col { font-size:11px; color:var(--t2); line-height:1.3; }
  .cat-date-col .cat-countdown { font-size:10px; color:var(--t3); margin-top:1px; }

  .cat-name-col { font-size:13px; font-weight:600; }
  .cat-name-col .cat-instruments {
    font-size:10px; font-weight:500; color:var(--t2);
    margin-top:2px; display:flex; flex-wrap:wrap; gap:4px;
  }
  .cat-instruments .cat-tick {
    background:rgba(255,255,255,.06);
    border:1px solid rgba(255,255,255,.1);
    border-radius:4px;
    padding:1px 5px;
    font-size:9px;
    letter-spacing:.4px;
  }

  .cat-right-col { display:flex; flex-direction:column; align-items:flex-end; gap:4px; }
  .cat-status-badge {
    font-size:9px; font-weight:800; letter-spacing:1.2px;
    padding:2px 7px; border-radius:12px; white-space:nowrap;
  }
  .cat-conf-bar-wrap {
    width:52px; height:4px; background:rgba(255,255,255,.08);
    border-radius:2px; overflow:hidden;
  }
  .cat-conf-bar { height:100%; border-radius:2px; transition:width .4s; }

  /* Category group header */
  .cat-group-hdr {
    font-size:9px; font-weight:700; letter-spacing:1.8px;
    text-transform:uppercase; padding:12px 0 6px;
    display:flex; align-items:center; gap:6px;
  }
  .cat-group-hdr::before { content:''; width:8px; height:8px; border-radius:50%; }

  /* 7-day strip in header */
  .cat-strip {
    display:flex; gap:6px; align-items:center; flex-wrap:wrap;
  }
  .cat-strip-pill {
    font-size:10px; font-weight:700; padding:2px 8px;
    border-radius:10px; border:1px solid rgba(255,255,255,.12);
    white-space:nowrap; cursor:pointer;
  }

  /* ── Modal overlay ── */
  #cat-modal-overlay {
    display:none; position:fixed; inset:0;
    background:rgba(0,0,0,.72); z-index:1000;
    align-items:center; justify-content:center; padding:20px;
  }
  #cat-modal-overlay.open { display:flex; }

  #cat-modal {
    background:#0d1117;
    border:1px solid rgba(255,255,255,.12);
    border-radius:14px;
    max-width:560px; width:100%;
    max-height:86vh; overflow-y:auto;
    padding:28px 24px;
    position:relative;
    box-shadow:0 24px 80px rgba(0,0,0,.7);
  }
  .cat-modal-close {
    position:absolute; top:16px; right:18px;
    font-size:20px; cursor:pointer; color:var(--t2);
    background:none; border:none; line-height:1;
  }
  .cat-modal-close:hover { color:var(--t); }

  .cat-modal-cat {
    font-size:9px; font-weight:800; letter-spacing:1.5px;
    text-transform:uppercase; margin-bottom:6px;
  }
  .cat-modal-title { font-size:20px; font-weight:800; margin-bottom:4px; }
  .cat-modal-date  { font-size:12px; color:var(--t2); margin-bottom:16px; }

  .cat-modal-section {
    margin-bottom:16px;
  }
  .cat-modal-section-label {
    font-size:9px; font-weight:700; letter-spacing:1.5px;
    text-transform:uppercase; color:var(--t3);
    margin-bottom:6px;
  }
  .cat-modal-section-body {
    font-size:13px; color:var(--t); line-height:1.6;
  }

  .cat-modal-chips { display:flex; flex-wrap:wrap; gap:6px; }
  .cat-modal-chip {
    background:rgba(255,255,255,.07);
    border:1px solid rgba(255,255,255,.12);
    border-radius:6px; padding:3px 10px;
    font-size:11px; font-weight:600; letter-spacing:.3px;
  }

  .cat-conf-display {
    display:flex; align-items:center; gap:10px;
    font-size:13px; font-weight:700;
  }
  .cat-conf-track {
    flex:1; height:6px; background:rgba(255,255,255,.08);
    border-radius:3px; overflow:hidden;
  }
  .cat-conf-fill { height:100%; border-radius:3px; }

  .cat-modal-divider {
    height:1px; background:rgba(255,255,255,.07); margin:16px 0;
  }
  `;

  const styleEl = document.createElement('style');
  styleEl.textContent = STYLE;
  document.head.appendChild(styleEl);

  // ── Helpers ────────────────────────────────────────────────────────────────
  function fmtDate(iso) {
    if (!iso) return '—';
    const d = new Date(iso + 'T00:00:00');
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  }

  function countdownLabel(days) {
    if (days === 0)  return 'TODAY';
    if (days < 0)    return `${Math.abs(days)}d ago`;
    if (days === 1)  return 'Tomorrow';
    return `in ${days}d`;
  }

  function confColor(score) {
    if (score >= 8) return '#00e676';
    if (score >= 6) return '#ffd740';
    return '#ff3d71';
  }

  function groupBy(arr, key) {
    return arr.reduce((acc, item) => {
      (acc[item[key]] = acc[item[key]] || []).push(item);
      return acc;
    }, {});
  }

  // ── Build & inject card HTML ───────────────────────────────────────────────
  function buildCard() {
    const card = document.createElement('div');
    card.className = 'coll-card';
    card.id = 'cat-coll-card';
    card.innerHTML = `
      <div class="coll-header" onclick="toggleCard('cat')">
        <div class="coll-left">
          <span class="coll-icon">🎯</span>
          <span class="coll-name">Trading Catalysts</span>
          <span class="coll-summary" id="cat-summary">loading…</span>
        </div>
        <div style="display:flex;align-items:center;gap:8px">
          <div class="cat-strip" id="cat-strip"></div>
          <button id="cat-view-toggle" onclick="event.stopPropagation();toggleCatView()"
            style="font-size:9px;font-weight:700;letter-spacing:.8px;padding:3px 9px;border-radius:8px;
                   border:1px solid rgba(255,255,255,.15);background:rgba(255,255,255,.06);
                   color:var(--t2);cursor:pointer">LIST</button>
          <span class="coll-chevron" id="cat-chevron">▼</span>
        </div>
      </div>
      <div class="coll-body collapsed" id="cat-body">
        <div id="cat-list" style="padding-top:8px">
          <div style="color:var(--t3);font-size:12px;padding:16px 0">Loading events…</div>
        </div>
        <div id="cat-month-grid" style="display:none;padding-top:8px"></div>
      </div>
    `;

    // Insert before Layer 3
    const layer3 = document.querySelector('.layer-band .l3')?.closest('.layer-band');
    if (layer3) {
      layer3.parentNode.insertBefore(card, layer3);
    } else {
      // Fallback: append to .main
      document.querySelector('.main')?.appendChild(card);
    }
  }

  // ── Modal ──────────────────────────────────────────────────────────────────
  function buildModal() {
    const overlay = document.createElement('div');
    overlay.id = 'cat-modal-overlay';
    overlay.innerHTML = `
      <div id="cat-modal">
        <button class="cat-modal-close" onclick="closeCatModal()">✕</button>
        <div id="cat-modal-content"></div>
      </div>
    `;
    document.body.appendChild(overlay);

    overlay.addEventListener('click', e => {
      if (e.target === overlay) closeCatModal();
    });
  }

  window.closeCatModal = function () {
    const ov = document.getElementById('cat-modal-overlay');
    if (ov) ov.classList.remove('open');
  };

  window.openCatModal = function (ev) {
    const ov = document.getElementById('cat-modal-overlay');
    const content = document.getElementById('cat-modal-content');
    if (!ov || !content) return;

    const cat = ev.category || 'macro';
    const color = CAT_COLOR[cat] || '#64748b';
    const st = STATUS_STYLE[ev.status] || STATUS_STYLE.future;
    const days = ev.days_until;
    const tickers = (ev.instruments || []).join(', ');

    // Build alert message now (safe from quote/HTML escaping issues in onclick)
    window._catPendingAlert = '🎯 <b>' + (ev.name||'') + '</b>\n📅 ' + fmtDate(ev.date) + ' · ' + countdownLabel(days)
      + (ev.action    ? '\n\n<b>Action Plan:</b>\n' + (ev.action||'').substring(0,350)                  : '')
      + (ev.exit_trigger ? '\n\n<b>Exit:</b> ' + ev.exit_trigger.substring(0,120)                       : '')
      + ((ev.instruments||[]).length ? '\n\n<b>Instruments:</b> ' + ev.instruments.join(', ')            : '');
    window._sendCatAlert = async function(btn) {
      const ok = await sendTgAlert(window._catPendingAlert, true);
      if (ok) { btn.textContent='✅ Alert Sent to Telegram'; btn.style.background='rgba(0,230,118,.15)'; btn.style.color='#00e676'; }
      else    { btn.textContent='❌ Configure Telegram first — click 📱 in header'; }
    };

    content.innerHTML = `
      <div class="cat-modal-cat" style="color:${color}">${CAT_LABEL[cat] || cat}</div>
      <div class="cat-modal-title">${ev.name}</div>
      <div class="cat-modal-date">
        ${fmtDate(ev.date)}
        &nbsp;·&nbsp;
        <span style="background:${st.bg};color:${st.color};font-size:10px;font-weight:700;
              padding:2px 8px;border-radius:10px;letter-spacing:1px">${st.label}</span>
        &nbsp;·&nbsp;
        <span style="color:var(--t2);font-size:12px">${countdownLabel(days)}</span>
      </div>

      <div class="cat-modal-divider"></div>

      <div class="cat-modal-section">
        <div class="cat-modal-section-label">Why it moves markets</div>
        <div class="cat-modal-section-body">${ev.why || '—'}</div>
      </div>

      <div class="cat-modal-section">
        <div class="cat-modal-section-label">Action plan</div>
        <div class="cat-modal-section-body">${ev.action || '—'}</div>
      </div>

      ${ev.trade_type ? `
      <div class="cat-modal-section">
        <div class="cat-modal-section-label">Trade type</div>
        <div class="cat-modal-section-body" style="color:var(--a)">${ev.trade_type}</div>
      </div>` : ''}

      <div class="cat-modal-section">
        <div class="cat-modal-section-label">Confidence</div>
        <div class="cat-conf-display">
          <span style="color:${confColor(ev.confidence)}">${ev.confidence}/10</span>
          <div class="cat-conf-track">
            <div class="cat-conf-fill" style="width:${ev.confidence * 10}%;background:${confColor(ev.confidence)}"></div>
          </div>
        </div>
      </div>

      ${(ev.instruments || []).length ? `
      <div class="cat-modal-section">
        <div class="cat-modal-section-label">Watch</div>
        <div class="cat-modal-chips">
          ${ev.instruments.map(t => `<span class="cat-modal-chip">${t}</span>`).join('')}
        </div>
      </div>` : ''}

      ${ev.exit_trigger ? `
      <div class="cat-modal-section">
        <div class="cat-modal-section-label">Exit trigger</div>
        <div class="cat-modal-section-body" style="color:var(--t2)">${ev.exit_trigger}</div>
      </div>` : ''}

      <div class="cat-modal-divider"></div>
      <div style="background:rgba(0,136,204,.1);border:1px solid rgba(0,136,204,.25);border-radius:8px;padding:10px 14px">
        <div style="font-size:9px;font-weight:800;letter-spacing:1px;color:#29b6f6;text-transform:uppercase;margin-bottom:5px">📱 Telegram Action Alert</div>
        <div style="font-size:10px;color:#64748b;margin-bottom:8px;line-height:1.5">
          Get a Telegram reminder with the action plan for this event.
          ${ev.action ? 'Action: ' + ev.action.substring(0, 80) + (ev.action.length > 80 ? '…' : '') : ''}
        </div>
        <button onclick="window._sendCatAlert(this)"
        style="width:100%;padding:8px 12px;border-radius:7px;background:rgba(0,136,204,.15);color:#29b6f6;border:1px solid rgba(0,136,204,.3);font-size:11px;font-weight:800;cursor:pointer;letter-spacing:.3px;transition:all .2s">
          📱 Send Action Alert to Telegram
        </button>
      </div>
      <button onclick="closeCatModal()" style="margin-top:12px;width:100%;padding:7px;border-radius:7px;background:rgba(255,255,255,.05);color:var(--t2);border:1px solid rgba(255,255,255,.1);font-size:11px;cursor:pointer">← Back / Close</button>
    `;

    ov.classList.add('open');
  };

  // ── Monthly calendar view ─────────────────────────────────────────────────
  let _catViewMode = 'list'; // 'list' | 'month'

  window.toggleCatView = function () {
    _catViewMode = _catViewMode === 'list' ? 'month' : 'list';
    const btn  = document.getElementById('cat-view-toggle');
    const list = document.getElementById('cat-list');
    const grid = document.getElementById('cat-month-grid');
    if (btn)  btn.textContent = _catViewMode === 'list' ? 'LIST' : 'MONTH';
    if (list) list.style.display = _catViewMode === 'list' ? '' : 'none';
    if (grid) grid.style.display = _catViewMode === 'month' ? '' : 'none';
    if (_catViewMode === 'month' && window.__catEvents__) renderMonthGrid(window.__catEvents__);
  };

  function renderMonthGrid(events) {
    const grid = document.getElementById('cat-month-grid');
    if (!grid) return;

    // Show the current month + next 2 months
    const today = new Date();
    let html = '';

    for (let mo = 0; mo < 3; mo++) {
      const y = today.getFullYear() + Math.floor((today.getMonth() + mo) / 12);
      const m = (today.getMonth() + mo) % 12;
      const label = new Date(y, m, 1).toLocaleDateString('en-US', { month: 'long', year: 'numeric' });
      const daysInMonth = new Date(y, m + 1, 0).getDate();
      const firstDay    = new Date(y, m, 1).getDay(); // 0=Sun

      // Events in this month
      const monthEvs = events.filter(ev => {
        if (!ev.date) return false;
        const d = new Date(ev.date + 'T00:00:00');
        return d.getFullYear() === y && d.getMonth() === m;
      });

      // Map day → [events]
      const dayMap = {};
      monthEvs.forEach(ev => {
        const d = new Date(ev.date + 'T00:00:00').getDate();
        (dayMap[d] = dayMap[d] || []).push(ev);
      });

      html += `<div style="margin-bottom:20px">
        <div style="font-size:11px;font-weight:800;letter-spacing:1px;text-transform:uppercase;color:var(--t2);margin-bottom:8px">${label}</div>
        <div style="display:grid;grid-template-columns:repeat(7,1fr);gap:2px;text-align:center">
          ${['Su','Mo','Tu','We','Th','Fr','Sa'].map(d => `<div style="font-size:9px;color:var(--t3);padding:2px 0;font-weight:600">${d}</div>`).join('')}
          ${Array.from({length: firstDay}, () => '<div></div>').join('')}
          ${Array.from({length: daysInMonth}, (_, i) => {
            const day = i + 1;
            const isToday = (y === today.getFullYear() && m === today.getMonth() && day === today.getDate());
            const evs = dayMap[day] || [];
            const dots = evs.slice(0, 3).map(ev => {
              const color = CAT_COLOR[ev.category] || '#64748b';
              return `<span style="display:inline-block;width:5px;height:5px;border-radius:50%;background:${color};margin:0 1px;cursor:pointer"
                            onclick="openCatModal(window.__catEvents__.find(e=>e.id==='${ev.id}'))"></span>`;
            }).join('');
            const moreDot = evs.length > 3 ? `<span style="font-size:7px;color:var(--t3)">+${evs.length-3}</span>` : '';
            const bg   = isToday ? 'rgba(0,230,118,.15)' : evs.length ? 'rgba(255,255,255,.04)' : 'transparent';
            const bdr  = isToday ? '1px solid rgba(0,230,118,.4)' : evs.length ? '1px solid rgba(255,255,255,.08)' : '1px solid transparent';
            const dayColor = isToday ? 'var(--g)' : evs.length ? 'var(--t)' : 'var(--t2)';
            const clickFn = evs.length === 1
              ? `openCatModal(window.__catEvents__.find(e=>e.id==='${evs[0].id}'))`
              : evs.length > 1 ? `openCatDayModal(${JSON.stringify(evs.map(e=>e.id))})` : '';
            return `<div style="background:${bg};border:${bdr};border-radius:4px;padding:2px 1px;min-height:34px;cursor:${evs.length?'pointer':'default'}"
                         onclick="${clickFn}">
                      <div style="font-size:10px;font-weight:${isToday?800:400};color:${dayColor};line-height:1.6">${day}</div>
                      <div style="display:flex;justify-content:center;flex-wrap:wrap;gap:1px;min-height:7px">${dots}${moreDot}</div>
                    </div>`;
          }).join('')}
        </div>
      </div>`;
    }
    grid.innerHTML = html;
  }

  // Multi-event day modal: list events for that day
  window.openCatDayModal = function (ids) {
    const events = (window.__catEvents__ || []).filter(e => ids.includes(e.id));
    if (!events.length) return;
    if (events.length === 1) { openCatModal(events[0]); return; }
    const ov      = document.getElementById('cat-modal-overlay');
    const content = document.getElementById('cat-modal-content');
    if (!ov || !content) return;
    const d = new Date(events[0].date + 'T00:00:00');
    const dayLabel = d.toLocaleDateString('en-US', { weekday:'long', month:'long', day:'numeric' });
    content.innerHTML = `
      <div class="cat-modal-title" style="font-size:16px;margin-bottom:12px">${dayLabel} — ${events.length} Events</div>
      <div style="display:flex;flex-direction:column;gap:8px">
        ${events.map(ev => {
          const color = CAT_COLOR[ev.category] || '#64748b';
          return `<div onclick="openCatModal(window.__catEvents__.find(e=>e.id==='${ev.id}'))"
                       style="padding:10px 12px;border-radius:8px;border:1px solid ${color}44;
                              background:${color}0d;cursor:pointer;transition:background .15s"
                       onmouseover="this.style.background='${color}1a'" onmouseout="this.style.background='${color}0d'">
                    <div style="font-size:9px;font-weight:700;color:${color};letter-spacing:1px;text-transform:uppercase;margin-bottom:3px">${CAT_LABEL[ev.category] || ev.category}</div>
                    <div style="font-size:13px;font-weight:700">${ev.name}</div>
                    <div style="font-size:10px;color:var(--t2);margin-top:2px">Confidence ${ev.confidence}/10 · Click to view playbook</div>
                  </div>`;
        }).join('')}
      </div>`;
    ov.classList.add('open');
  };

  // ── Render events list ─────────────────────────────────────────────────────
  function renderEvents(events) {
    const list = document.getElementById('cat-list');
    const summary = document.getElementById('cat-summary');
    const strip = document.getElementById('cat-strip');
    if (!list) return;

    if (!events || events.length === 0) {
      list.innerHTML = '<div style="color:var(--t3);font-size:12px;padding:16px 0">No events loaded.</div>';
      if (summary) summary.textContent = 'No events';
      return;
    }

    // 7-day events for header strip
    const soon = events.filter(e => e.days_until >= 0 && e.days_until <= 7);

    if (summary) {
      summary.textContent = soon.length
        ? `${soon.length} event${soon.length > 1 ? 's' : ''} in 7 days`
        : 'No events this week';
    }

    if (strip) {
      if (soon.length === 0) {
        strip.innerHTML = '';
      } else {
        strip.innerHTML = soon.slice(0, 4).map(ev => {
          const color = CAT_COLOR[ev.category] || '#64748b';
          return `<span class="cat-strip-pill"
                    style="background:${color}1a;color:${color};border-color:${color}33;"
                    onclick="event.stopPropagation();openCatModal(window.__catEvents__.find(e=>e.id==='${ev.id}'))"
                  >${ev.name.split(' ')[0]} · ${countdownLabel(ev.days_until)}</span>`;
        }).join('');
      }
    }

    // Group by category — display order
    const ORDER = ['macro', 'corporate', 'industry', 'seasonal', 'bonus'];
    const groups = groupBy(events, 'category');

    let html = '';
    for (const cat of ORDER) {
      const group = groups[cat];
      if (!group || group.length === 0) continue;

      const color = CAT_COLOR[cat] || '#64748b';
      html += `<div class="cat-group-hdr" style="color:${color}">
                 <span style="width:8px;height:8px;border-radius:50%;background:${color};display:inline-block;flex-shrink:0"></span>
                 ${CAT_LABEL[cat] || cat}
               </div>`;

      for (const ev of group) {
        const st = STATUS_STYLE[ev.status] || STATUS_STYLE.future;
        const confW = `${(ev.confidence || 5) * 10}%`;
        const tickers = (ev.instruments || []).slice(0, 4);

        html += `<div class="cat-event-row" onclick="openCatModal(window.__catEvents__.find(e=>e.id==='${ev.id}'))">
          <div class="cat-date-col">
            <div>${fmtDate(ev.date)}</div>
            <div class="cat-countdown">${countdownLabel(ev.days_until)}</div>
          </div>
          <div class="cat-name-col">
            <div>${ev.name}</div>
            ${tickers.length ? `<div class="cat-instruments">
              ${tickers.map(t => `<span class="cat-tick">${t}</span>`).join('')}
              ${(ev.instruments || []).length > 4 ? `<span class="cat-tick">+${ev.instruments.length - 4}</span>` : ''}
            </div>` : ''}
          </div>
          <div class="cat-right-col">
            <span class="cat-status-badge" style="background:${st.bg};color:${st.color}">${st.label}</span>
            <div class="cat-conf-bar-wrap" title="Confidence ${ev.confidence}/10">
              <div class="cat-conf-bar" style="width:${confW};background:${confColor(ev.confidence)}"></div>
            </div>
          </div>
        </div>`;
      }
    }

    list.innerHTML = html;
  }

  // ── Fetch and initialise ───────────────────────────────────────────────────
  async function init() {
    buildCard();
    buildModal();

    try {
      const res = await fetch('events.json?_=' + Date.now());
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();

      // Support both array and wrapped {events:[...]} format
      const events = Array.isArray(data) ? data : (data.events || []);

      // Expose globally so onclick handlers can look up objects
      window.__catEvents__ = events;

      renderEvents(events);
    } catch (err) {
      console.warn('[calendar.js] Could not load events.json:', err.message);
      const list = document.getElementById('cat-list');
      const summary = document.getElementById('cat-summary');
      if (list) list.innerHTML = '<div style="color:var(--t3);font-size:12px;padding:16px 0">Events unavailable — run event_worker.py to publish events.json</div>';
      if (summary) summary.textContent = 'Unavailable';
    }
  }

  // Run after DOM ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
