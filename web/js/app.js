/**
 * Family Board — UI logic.
 *
 * Renders the dashboard data provided by the API adapter (`api.js`)
 * and wires up the capture form. No network, no secrets, no AI calls
 * happen here — everything goes through `api`.
 */

import { api, KIND_META } from './api.js';

/* ------------------------------------------------------------------ */
/*  Element lookups                                                    */
/* ------------------------------------------------------------------ */
const $ = (sel) => document.querySelector(sel);

const els = {
  todayLabel: $('#todayLabel'),
  dataBadge: $('#dataBadge'),
  refreshBtn: $('#refreshBtn'),
  todayList: $('#todayList'),
  eventsList: $('#eventsList'),
  tasksList: $('#tasksList'),
  notesList: $('#notesList'),
  shoppingList: $('#shoppingList'),
  captureForm: $('#captureForm'),
  captureInput: $('#captureInput'),
  captureKind: $('#captureKind'),
  captureBtn: $('#captureBtn'),
  captureHint: $('#captureHint'),
};

/* ------------------------------------------------------------------ */
/*  Rendering helpers                                                  */
/* ------------------------------------------------------------------ */
function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text != null) node.textContent = text;
  return node;
}

/** Render one list section. item: {text, at?, done?, draft?, kind?} */
function renderList(listEl, items, options = {}) {
  listEl.textContent = '';
  if (!items || items.length === 0) {
    listEl.appendChild(el('li', 'empty-hint', options.emptyText || 'ยังไม่มีข้อมูล'));
    return;
  }
  for (const item of items) {
    const li = el('li');
    if (item.draft) li.className = 'draft';

    if (item.draft && item.kind && KIND_META[item.kind]) {
      const tag = el('span', 'kind-tag', KIND_META[item.kind].label);
      li.appendChild(tag);
    }

    li.appendChild(el('span', null, item.text));

    if (item.at) li.appendChild(el('span', 'time', item.at));

    if (item.done !== undefined) {
      li.appendChild(el('span', 'time', item.done ? 'เสร็จแล้ว ✓' : 'ยังไม่เสร็จ'));
    }
    if (item.draft) {
      li.appendChild(el('span', 'time', '· ดราฟต์ (ในเครื่อง)'));
    }

    listEl.appendChild(li);
  }
}

/* ------------------------------------------------------------------ */
/*  Dashboard load                                                     */
/* ------------------------------------------------------------------ */
async function loadDashboard() {
  els.refreshBtn.classList.add('spinning');
  try {
    const data = await api.getDashboard();
    els.todayLabel.textContent = data.todayLabel || '—';
    els.dataBadge.textContent = data.source === 'mock-local' ? 'mock' : data.source;

    renderList(els.todayList, data.today, { emptyText: 'ไม่มีเหตุการณ์วันนี้' });
    renderList(els.eventsList, data.events, { emptyText: 'ไม่มีอีเวนต์ที่ถึงกำหนด' });
    renderList(els.tasksList, data.tasks, { emptyText: 'ไม่มีงานค้าง' });
    renderList(els.notesList, data.notes, { emptyText: 'ยังไม่มีบันทึก' });
    renderList(els.shoppingList, data.shopping, { emptyText: 'รายการซื้อว่าง' });
  } finally {
    els.refreshBtn.classList.remove('spinning');
  }
}

/* ------------------------------------------------------------------ */
/*  Capture flow: preview → confirm → commit (adapter.local)           */
/* ------------------------------------------------------------------ */
async function handleCapture(e) {
  e.preventDefault();
  const text = els.captureInput.value;
  const kind = els.captureKind.value;
  els.captureBtn.disabled = true;
  try {
    // Step 1: preview via the adapter (simulated "AI" structured draft).
    const result = await api.capture(text, kind);

    if (!result.ok) {
      els.captureHint.textContent = result.error || 'เกิดข้อผิดพลาด';
      return;
    }

    // Step 2: confirm with the user by showing the parsed draft.
    const kindName = KIND_META[result.draft.kind]?.label || result.draft.kind;
    const confirmed = window.confirm(
      `AI จับได้ว่าเป็น “${kindName}”.\n\n“${result.draft.text}”\n\nบันทึกลงกระดานหรือไม่?`,
    );

    if (!confirmed) {
      els.captureHint.textContent = 'ยกเลิก — ไม่ได้บันทึก';
      return;
    }

    // Step 3: commit through the selected adapter (server or local demo).
    await api.recordCapture(result.draft);
    els.captureInput.value = '';
    els.captureHint.textContent = api.constructor.name === 'RealApiAdapter'
      ? 'บันทึกลงกระดานส่วนกลางแล้ว ✓'
      : 'บันทึกลงกระดานแล้ว ✓ (เก็บไว้ในเครื่องนี้เท่านั้น)';
    await loadDashboard();
  } catch (err) {
    els.captureHint.textContent = 'เกิดข้อผิดพลาด: ' + (err.message || err);
  } finally {
    els.captureBtn.disabled = false;
  }
}

/* ------------------------------------------------------------------ */
/*  Init                                                               */
/* ------------------------------------------------------------------ */
els.refreshBtn.addEventListener('click', loadDashboard);
els.captureForm.addEventListener('submit', handleCapture);

// Register service worker for offline/PWA (best-effort).
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('./sw.js').catch(() => {
      /* offline support is optional; ignore failures */
    });
  });
}

loadDashboard();

// Expose for manual debugging in console.
window.__familyBoard = { api, reload: loadDashboard };