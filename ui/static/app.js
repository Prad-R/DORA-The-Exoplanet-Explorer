const $ = s => document.querySelector(s);
const $$ = s => [...document.querySelectorAll(s)];
let current = null, timer = null, baseObs = null, shownEntries = 0;

const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));

async function api(url, opt) {
  const r = await fetch(url, opt);
  const j = await r.json();
  if (!r.ok) throw Error(j.error || r.statusText);
  return j;
}

// Minimal markdown: headings, bullet lists, tables, bold, italic, code. Input is escaped first.
function inline(s) {
  return s.replace(/`([^`]+)`/g, '<code>$1</code>')
          .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
          .replace(/(^|[^*])\*([^*\s][^*]*)\*/g, '$1<em>$2</em>');
}
function md(text) {
  const lines = esc(text || '').split('\n');
  const out = [];
  for (let i = 0; i < lines.length;) {
    const line = lines[i];
    if (/^\s*\|/.test(line)) {
      const rows = [];
      while (i < lines.length && /^\s*\|/.test(lines[i])) rows.push(lines[i++]);
      const cells = r => r.trim().replace(/^\||\|$/g, '').split('|').map(c => inline(c.trim()));
      const body = rows.filter(r => !/^\s*\|[\s|:-]+\|\s*$/.test(r));
      out.push('<table><thead><tr>' + cells(body[0]).map(c => `<th>${c}</th>`).join('') + '</tr></thead><tbody>' +
               body.slice(1).map(r => '<tr>' + cells(r).map(c => `<td>${c}</td>`).join('') + '</tr>').join('') + '</tbody></table>');
    } else if (/^\s*[-*] /.test(line)) {
      const items = [];
      while (i < lines.length && /^\s*[-*] /.test(lines[i])) items.push(lines[i++].replace(/^\s*[-*] /, ''));
      out.push('<ul>' + items.map(t => `<li>${inline(t)}</li>`).join('') + '</ul>');
    } else if (/^#{1,4} /.test(line)) {
      out.push(`<h4>${inline(line.replace(/^#+ /, ''))}</h4>`); i++;
    } else if (!line.trim()) {
      i++;
    } else {
      const para = [];
      while (i < lines.length && lines[i].trim() && !/^\s*(\||[-*] |#{1,4} )/.test(lines[i])) para.push(lines[i++]);
      out.push(`<p>${inline(para.join(' '))}</p>`);
    }
  }
  return out.join('');
}

async function init() {
  const tasks = await api('/api/tasks');
  $('#task').innerHTML = tasks.map(t => `<option value="${t.id}">${t.id} · ${t.bank} · difficulty ${t.difficulty}</option>`).join('');
  $('#task').value = tasks.find(t => t.id === 'seed96_diff3')?.id || tasks[0]?.id;
  $('#task').onchange = loadTask;
  $('#start').onclick = start;
  await loadTask();
}

async function loadTask() {
  const d = await api('/api/tasks/' + encodeURIComponent($('#task').value));
  baseObs = d.observations;
  $('#targetTitle').textContent = d.id;
  const ts = d.observations.times_days;
  $('#sampleCount').textContent = `${ts.length} measurements`;
  $('#facts').innerHTML =
    `<div>Difficulty <b>${d.difficulty}</b></div>` +
    `<div>Time span <b>${(Math.max(...ts) - Math.min(...ts)).toFixed(1)} days</b></div>` +
    `<div>Star mass <b>${(d.star_mass_sun ?? 0).toFixed(2)} M☉</b></div>` +
    `<div>Instruments <b>${new Set(d.observations.instruments).size}</b></div>`;
  draw([]);
}

function draw(extra) {
  const t = [...baseObs.times_days, ...extra.map(x => x.time_days)];
  const y = [...baseObs.rvs_ms, ...extra.map(x => x.rv_ms)];
  if (!t.length) return;
  const W = 900, H = 320, p = 35;
  const x0 = Math.min(...t), x1 = Math.max(...t), y0 = Math.min(...y), y1 = Math.max(...y);
  const sx = x => p + (x - x0) / (x1 - x0 || 1) * (W - 2 * p);
  const sy = v => H - p - (v - y0) / (y1 - y0 || 1) * (H - 2 * p);
  let out = '';
  for (let i = 0; i < 5; i++) {
    const yy = p + i * (H - 2 * p) / 4;
    out += `<line class="grid" x1="${p}" y1="${yy}" x2="${W - p}" y2="${yy}"/><text class="axis-label" x="2" y="${yy + 3}">${(y1 - i * (y1 - y0) / 4).toFixed(0)}</text>`;
  }
  const n0 = baseObs.times_days.length;
  out += `<polyline class="rv-line" points="${t.slice(0, n0).map((v, i) => `${sx(v)},${sy(y[i])}`).join(' ')}"/>`;
  out += t.map((v, i) => `<circle class="point ${i >= n0 ? 'follow' : ''}" cx="${sx(v)}" cy="${sy(y[i])}" r="3"/>`).join('');
  $('#chart').innerHTML = out;
}

async function start() {
  clearInterval(timer);
  $('#start').disabled = true;
  shownEntries = 0;
  try {
    const d = await api('/api/runs', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        task_id: $('#task').value, prompt: $('#prompt').value,
        max_observations: +$('#maxObs').value, obs_per_campaign: +$('#perCampaign').value,
        max_compute_rounds: +$('#maxRounds').value,
      }),
    });
    current = d.run_id;
    setStatus('running', 'Running');
    poll();
    timer = setInterval(poll, 1500);
  } catch (e) {
    setStatus('error', e.message);
    $('#start').disabled = false;
  }
}

function setStatus(c, t) { $('#status').className = 'status ' + c; $('#status').textContent = t; }

async function poll() {
  if (!current) return;
  try {
    const d = await api('/api/runs/' + current);
    render(d);
    if (!d.running) {
      clearInterval(timer);
      $('#start').disabled = false;
      setStatus(d.error ? 'error' : 'done', d.error ? 'Failed' : 'Complete');
    }
  } catch (e) { setStatus('error', e.message); }
}

const STATUS_WORDS = {conclude: 'Concluded', observe: 'Observing', refine: 'Refining', needs_review: 'In review',
                      unresolved: 'Unresolved', refitted: 'Refitting'};

function render(d) {
  draw(d.observations);
  const decisions = d.ledger.filter(x => x.kind === 'decision' && x.status);
  const last = decisions.at(-1);
  const m = $$('#metrics strong');
  m[0].textContent = last ? (STATUS_WORDS[last.status] || last.status) : 'Analysing';
  const campaigns = decisions.filter(x => x.status === 'observe').length;
  m[1].textContent = `${d.observations.length}` + (campaigns ? ` in ${campaigns} campaign${campaigns > 1 ? 's' : ''}` : '');
  m[2].textContent = d.result?.submissions ?? d.state?.submissions ?? 0;
  m[3].textContent = d.result ? `${Math.round(d.result.duration_s)} s` : 'running';

  $('#ledgerCount').textContent = `${d.entries.length} entries`;
  const log = $('#ledger');
  if (!d.entries.length) {
    log.className = 'ledger empty';
    log.textContent = 'Waiting for the first agent record…';
  } else if (d.entries.length !== shownEntries) {
    const atBottom = log.scrollHeight - log.scrollTop - log.clientHeight < 40;
    log.className = 'ledger';
    log.innerHTML = d.entries.map((e, i) => {
      const open = ['Decision', 'Submission'].includes(e.label) || i === d.entries.length - 1;
      return `<details class="entry tone-${e.tone}" ${open ? 'open' : ''}><summary><span class="chip">${esc(e.label)}</span>` +
             `<span class="title">${md(e.title).replace(/^<p>|<\/p>$/g, '')}</span></summary>` +
             (e.body ? `<div class="body">${md(e.body)}</div>` : '') + '</details>';
    }).join('');
    if (atBottom || !shownEntries) log.scrollTop = log.scrollHeight;
    shownEntries = d.entries.length;
  }

  const c = $('#conclusion');
  c.className = 'conclusion';
  if (d.final_report) {
    c.innerHTML = md(d.final_report);
  } else if (d.error) {
    c.innerHTML = `<pre>${esc(d.error)}</pre>`;
  } else if (last) {
    const e = d.entries[d.ledger.lastIndexOf(last)];
    c.innerHTML = `<p class="pill tone-${e.tone}">${esc(STATUS_WORDS[last.status] || last.status)}</p>` + md(e.body);
  } else {
    c.innerHTML = '<span class="empty">The lab has not reached a decision yet.</span>';
  }
}

init().catch(e => setStatus('error', e.message));
