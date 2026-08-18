import test from 'node:test';
import assert from 'node:assert/strict';
import { handler } from '../api/family-board.js';

process.env.RENDER_API_URL = 'https://api.example.test';
process.env.FAMILY_BOARD_API_TOKEN = 'secret';

function request(url, options = {}) {
  return { method: 'GET', query: {}, headers: {}, url, ...options };
}

test('proxy forwards board requests with the server-side bearer token', async () => {
  const calls = [];
  const response = await handler(
    request('/api/family-board?op=board&group=family'),
    null,
    async (url, options) => {
      calls.push({ url, options });
      return new Response(JSON.stringify({ group: 'family' }), { status: 200 });
    },
  );

  assert.deepEqual(response.body, { group: 'family' });
  assert.equal(calls[0].url.toString(), 'https://api.example.test/api/board?group=family');
  assert.equal(calls[0].options.headers.Authorization, 'Bearer secret');
});

test('proxy rejects unsupported operations and missing groups before forwarding', async () => {
  const fetcher = async () => assert.fail('must not forward');
  assert.equal((await handler(request('/api/family-board?op=nope'), null, fetcher)).status, 404);
  assert.match((await handler(request('/api/family-board?op=board'), null, fetcher)).body.error, /Missing required query param: group/);
});

test('proxy enforces operation methods', async () => {
  const response = await handler(request('/api/family-board?op=commit&group=family', { method: 'GET' }), null, async () => {});
  assert.equal(response.status, 405);
  assert.match(response.body.error, /Method GET not allowed for commit/);
});
