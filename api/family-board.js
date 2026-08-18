const OPERATIONS = {
  health: { method: 'GET', path: '/api/healthz', group: false },
  board: { method: 'GET', path: '/api/board', group: true },
  preview: { method: 'POST', path: '/api/capture/preview', group: true },
  commit: { method: 'POST', path: '/api/capture/commit', group: true },
};

function fail(message, status = 400) {
  const error = new Error(message);
  error.status = status;
  throw error;
}

function queryOf(req) {
  return new URL(req.url || '', 'http://localhost').searchParams;
}

function groupOf(req, body, op) {
  const group = op.method === 'GET' ? queryOf(req).get('group') : body.group;
  if (typeof group !== 'string' || !group.trim() || group.length > 100 || /[\u0000-\u001f]/.test(group)) {
    fail(op.method === 'GET' ? 'Missing required query param: group' : 'Missing required field: group');
  }
  return group.trim();
}

async function bodyOf(req) {
  if (req.body && typeof req.body === 'object') return req.body;
  if (!req.body) return {};
  try {
    return JSON.parse(req.body);
  } catch {
    fail('Request body must be valid JSON');
  }
}

function jsonResponse(res, status, body) {
  if (!res) return { status, body };
  res.status(status).json(body);
}

async function handler(req, res, fetcher = fetch) {
  try {
    const query = queryOf(req);
    const name = query.get('op');
    const op = OPERATIONS[name];
    if (!op) fail('Unsupported operation', 404);
    if (req.method !== op.method) fail(`Method ${req.method} not allowed for ${name}`, 405);

    const body = op.method === 'POST' ? await bodyOf(req) : {};
    const group = op.group ? groupOf(req, body, op) : '';
    const upstream = new URL(process.env.RENDER_API_URL || '');
    upstream.pathname = op.path;
    upstream.search = group ? `?group=${encodeURIComponent(group)}` : '';
    const payload = op.method === 'POST'
      ? { ...body, group }
      : undefined;
    const response = await fetcher(upstream, {
      method: op.method,
      headers: {
        Accept: 'application/json',
        Authorization: `Bearer ${process.env.FAMILY_BOARD_API_TOKEN || ''}`,
        ...(payload ? { 'Content-Type': 'application/json' } : {}),
      },
      ...(payload ? { body: JSON.stringify(payload) } : {}),
    });
    const text = await response.text();
    let result;
    try { result = JSON.parse(text); } catch { result = { error: 'Upstream returned invalid JSON' }; }
    return jsonResponse(res, response.status, result);
  } catch (error) {
    return jsonResponse(res, error.status || 500, { error: error.message || 'Proxy request failed' });
  }
}

module.exports = { handler };
