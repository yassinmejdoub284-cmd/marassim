// Used only with Vite's development server and the isolated UI test fixture.
let token;
export const integrationBridge = {
  config: async () => ({ ok: true, value: { configured: true, mode: 'server', serverUrl: 'http://127.0.0.1:18744 · TEST ISOLÉ' } }),
  request: async (path, options = {}) => {
    try {
      const headers = { 'Content-Type': 'application/json' };
      if (token) headers.Authorization = 'Bearer ' + token;
      if (options.idempotencyKey) headers['Idempotency-Key'] = options.idempotencyKey;
      const response = await fetch('/api' + path, { method: options.method || 'GET', headers, body: options.body ? JSON.stringify(options.body) : undefined });
      const value = await response.json();
      if (!response.ok) return { ok: false, error: value.error, status: response.status };
      if (path === '/login') { token = value.token; return { ok: true, value: { user: value.user } }; }
      return { ok: true, value };
    } catch (error) { return { ok: false, error: error.message }; }
  },
  logout: async () => { token = null; return { ok: true }; },
  saveFile: async file => ({ ok: true, value: file?.base64?.length > 100 ? { saved: true } : { canceled: true } })
};
