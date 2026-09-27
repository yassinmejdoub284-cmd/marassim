const { test } = require('node:test');
const assert = require('node:assert/strict');
const { normalizeServer, request } = require('../electron/transport.cjs');
test('connection accepts only a plain HTTPS server origin', () => {
  assert.equal(normalizeServer('https://192.168.1.10:7443/'), 'https://192.168.1.10:7443');
  for (const url of ['http://192.168.1.10', 'file:///C:/x', 'https://user:secret@host', 'https://host/api', 'https://host/?token=x']) assert.throws(() => normalizeServer(url));
});
test('unpaired connections cannot send secrets', () => {
  assert.throws(() => request('https://localhost:7443', '/login', { body: { password: 'x' } }));
  assert.throws(() => request('https://localhost:7443', '/login', { probe: true }));
  assert.throws(() => request('https://localhost:7443', '/health', { probe: true, token: 'x' }));
});
test('API path cannot escape to another host or filesystem', () => {
  for (const pathname of ['//attacker.example', '/../../file', 'https://attacker', '/file#fragment']) assert.throws(() => request('https://localhost:7443', pathname));
});
