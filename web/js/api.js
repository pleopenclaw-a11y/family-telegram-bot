/**
 * Family Board — data layer (API adapter).
 *
 * This module is the SINGLE boundary between the UI and data.
 * It exposes a small async interface (`getDashboard`, `capture`,
 * `recordCapture`) that the rest of the app calls.
 *
 * Three guarantees:
 *   1. The browser never contacts an AI endpoint and never holds an
 *      API key — all "AI" capture here is simulated locally.
 *   2. Data is mock/offline. Display sections are seeded with fake
 *      samples so the UI is previewable; what you type into the
 *      capture box is stored ONLY in this browser's localStorage
 *      (per device), clearly rendered as "draft" items.
 *   3. To go live, implement a `RealApiAdapter` with the SAME
 *      methods and switch the export at the bottom of this file.
 *      No UI change is required.
 */

const KIND_META = {
  note: { label: 'บันทึก' },
  event: { label: 'อีเวนต์' },
  task: { label: 'งาน' },
  shopping: { label: 'ซื้อของ' },
  today: { label: 'วันนี้' },
};

const STORAGE_KEY = 'family-board.drafts.v1';

/* ------------------------------------------------------------------ */
/*  Mock seed data                                                     */
/* ------------------------------------------------------------------ */

// Relative to "today". Uses day offsets so the sample always looks live.
function seedForToday() {
  const now = new Date();
  const day = now.toLocaleDateString('th-TH', {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
  });
  const iso = (d) => d.toISOString().slice(0, 10);
  const addDays = (n) => { const d = new Date(now); d.setDate(d.getDate() + n); return d; };

  const dayOffset = (d) => Math.floor((d - new Date(now.setHours(0, 0, 0, 0))) / 86400000);
  const fmt = (d) => {
    const off = dayOffset(d);
    if (off === 0) return 'วันนี้';
    if (off === 1) return 'พรุ่งนี้';
    if (off === 2) return 'มะรืนนี้';
    if (off === -1) return 'เมื่อวาน';
    return d.toLocaleDateString('th-TH', { day: 'numeric', month: 'short' });
  };

  return {
    todayLabel: day,
    today: [
      { id: 't1', kind: 'event', text: 'นัดคุณหมอฟัน 10:00 น.', at: 'วันนี้' },
      { id: 't2', kind: 'task', text: 'โทรหาคุณยายตอนเย็น', at: 'วันนี้' },
    ],
    events: [
      { id: 'e1', text: 'งานวันเกิดคุณแม่', at: fmt(addDays(3)), date: iso(addDays(3)) },
      { id: 'e2', text: 'เที่ยวสวนสนุกเสาร์นี้', at: fmt(addDays(5)), date: iso(addDays(5)) },
      { id: 'e3', text: 'ประชุมผู้ปกครอง', at: fmt(addDays(9)), date: iso(addDays(9)) },
    ],
    tasks: [
      { id: 'k1', text: 'ล้างรถ', done: false },
      { id: 'k2', text: 'จองตั๋วเครื่องบิน', done: true },
      { id: 'k3', text: 'ซื้อของใช้ในบ้าน', done: false },
    ],
    notes: [
      { id: 'n1', text: 'รหัสห้องเก็บของ: 4472', ts: now.toISOString() },
      { id: 'n2', text: 'เบอร์ช่างแอร์: 08x-xxx-xxxx', ts: addDays(-1).toISOString() },
    ],
    shopping: [
      { id: 's1', text: 'นมสด 2 ลิตร', done: false },
      { id: 's2', text: 'ไข่ไก่ 1 แผง', done: false },
      { id: 's3', text: 'สบู่เหลว', done: true },
    ],
  };
}

/* ------------------------------------------------------------------ */
/*  Storage helpers for locally captured drafts (this device only)     */
/* ------------------------------------------------------------------ */

function loadDrafts() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]');
  } catch {
    return [];
  }
}

function saveDrafts(drafts) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(drafts));
}

/* ------------------------------------------------------------------ */
/*  MockApiAdapter — the current implementation                        */
/* ------------------------------------------------------------------ */

class MockApiAdapter {
  async getDashboard() {
    // Simulated latency so the refresh animation is visible.
    await new Promise((r) => setTimeout(r, 250));

    const data = seedForToday();
    const recalled = loadDrafts();

    // Merge captured drafts into their matching sections (marked as drafts).
    const withDrafts = (seedList, kind) =>
      seedList.concat(
        recalled
          .filter((d) => d.kind === kind)
          .map((d) => ({ id: d.id, text: d.text, kind: d.kind, draft: true })),
      );

    return {
      todayLabel: data.todayLabel,
      today: data.today
        .concat(
          recalled
            .filter((d) => d.when === 'today')
            .map((d) => ({ id: d.id, text: d.text, at: 'วันนี้', kind: d.kind, draft: true })),
        ),
      events: withDrafts(data.events, 'event'),
      tasks: withDrafts(data.tasks, 'task'),
      notes: withDrafts(data.notes, 'note'),
      shopping: withDrafts(data.shopping, 'shopping'),
      source: 'mock-local',
    };
  }

  /**
   * Simulate "AI capture". In a real deployment this would POST to a
   * server-side endpoint (Track C) that runs the 9arm model server-side
   * and returns a structured draft for preview→confirm→commit. The
   * browser never sees the key.
   */
  async capture(text, kind) {
    await new Promise((r) => setTimeout(r, 350));
    const trimmed = (text || '').trim();
    if (!trimmed) return { ok: false, error: 'กรุณาพิมพ์ข้อความก่อนส่ง' };
    return {
      ok: true,
      draft: {
        id: 'd-' + Date.now(),
        text: trimmed,
        kind,
        when: kind === 'event' ? 'ล่าสุด' : null,
        timestamp: new Date().toISOString(),
      },
      // Note for the UI: what "AI" would have classified. Demo only.
      aiKind: kind,
    };
  }

  /** Publish a confirmed capture to THIS device's local storage. */
  recordCapture(draft) {
    const drafts = loadDrafts();
    drafts.unshift({ id: draft.id, text: draft.text, kind: draft.kind, when: draft.when });
    saveDrafts(drafts);
    return { ok: true };
  }
}

/* ------------------------------------------------------------------ */
/*  Real server adapter + switch point                                 */
/* ------------------------------------------------------------------ */

class RealApiAdapter {
  constructor({ baseUrl = '', groupId = 'family' } = {}) {
    this.baseUrl = baseUrl.replace(/\/$/, '');
    this.groupId = groupId;
  }

  async request(path, options = {}) {
    const response = await fetch(this.baseUrl + path, {
      headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
      ...options,
    });
    const body = await response.json();
    if (!response.ok) throw new Error(body.error || `Request failed (${response.status})`);
    return body;
  }

  async getDashboard() {
    const body = await this.request(`/api/board?group=${encodeURIComponent(this.groupId)}`);
    const byKind = body.by_kind || {};
    const toItem = (item) => ({ ...item, text: item.text || item.normalized_text });
    return {
      todayLabel: new Date().toLocaleDateString('th-TH', { weekday: 'long', day: 'numeric', month: 'long' }),
      today: (byKind.event || []).filter((item) => item.created_at?.slice(0, 10) === new Date().toISOString().slice(0, 10)).map(toItem),
      events: (byKind.event || []).map(toItem),
      tasks: (byKind.task || []).map(toItem),
      notes: (byKind.note || []).map(toItem),
      shopping: (byKind.shopping || []).map(toItem),
      source: 'server',
    };
  }

  async capture(text) {
    const body = await this.request('/api/capture/preview', {
      method: 'POST',
      body: JSON.stringify({ group: this.groupId, text }),
    });
    return { ok: true, draft: { ...body.preview, id: `preview-${Date.now()}`, text: body.preview.normalized_text, kind: body.preview.kind } };
  }

  async recordCapture(draft) {
    return this.request('/api/capture/commit', {
      method: 'POST',
      body: JSON.stringify({ group: this.groupId, kind: draft.kind, normalized_text: draft.text }),
    });
  }
}

const params = new URLSearchParams(window.location.search);
const live = params.get('mode') === 'live';
export const api = live
  ? new RealApiAdapter({ baseUrl: params.get('api') || '', groupId: params.get('group') || 'family' })
  : new MockApiAdapter();
export { KIND_META, STORAGE_KEY, RealApiAdapter };