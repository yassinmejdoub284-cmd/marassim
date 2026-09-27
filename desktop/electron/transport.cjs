const https = require('node:https');
const { X509Certificate } = require('node:crypto');

function normalizeServer(value) {
  const url = new URL(value);
  if (url.protocol !== 'https:' || url.username || url.password || (url.pathname !== '/' && url.pathname !== '') || url.search || url.hash) {
    throw new Error('Utilisez une adresse HTTPS du serveur, par exemple https://192.168.1.10:7443.');
  }
  return url.origin;
}

function request(serverUrl, path, { method = 'GET', body, certificate, token, bootstrap, idempotencyKey, probe = false } = {}) {
  const server = normalizeServer(serverUrl);
  if (!/^\/[a-z0-9/?=&_.%-]*$/i.test(path) || path.includes('..') || path.startsWith('//')) throw new Error('Adresse de requête invalide.');
  if (!certificate && !probe) throw new Error('Associez le certificat du serveur avant de vous connecter.');
  if (probe && (path !== '/health' || body || token || bootstrap)) throw new Error('La vérification initiale est limitée à l’état public du serveur.');
  const serialized = body === undefined ? undefined : JSON.stringify(body);
  return new Promise((resolve, reject) => {
    const headers = { Accept: 'application/json' };
    if (serialized) Object.assign(headers, { 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(serialized) });
    if (token) headers.Authorization = `Bearer ${token}`;
    if (bootstrap) headers['X-Bootstrap-Key'] = bootstrap;
    if (idempotencyKey) headers['Idempotency-Key'] = idempotencyKey;
    const options = { method, headers, rejectUnauthorized: !probe, minVersion: 'TLSv1.2', timeout: 35000 };
    if (certificate) {
      const expected = new X509Certificate(certificate).fingerprint256;
      options.ca = certificate;
      options.checkServerIdentity = (_host, cert) => cert.fingerprint256 === expected ? undefined : new Error('Le certificat du serveur a changé. Vérifiez le PC serveur avant une nouvelle association.');
    }
    const req = https.request(server + '/api' + path, options, res => {
      const chunks = [];
      let bytes = 0;
      let pem;
      if (probe) {
        const peer = res.socket.getPeerCertificate();
        if (!peer.raw) { res.destroy(); return reject(new Error('Certificat serveur introuvable.')); }
        pem = new X509Certificate(peer.raw).toString();
      }
      res.on('data', chunk => {
        bytes += chunk.length;
        if (bytes > 64 * 1024 * 1024) { req.destroy(new Error('Réponse trop volumineuse.')); return; }
        chunks.push(chunk);
      });
      res.on('end', () => {
        try {
          const result = JSON.parse(Buffer.concat(chunks).toString('utf8'));
          if (res.statusCode >= 400) {
            const error = new Error(result.error || 'Opération refusée par le serveur.');
            error.status = res.statusCode;
            reject(error);
          } else {
            if (probe && result.application !== 'marassim') throw new Error('Ce serveur n’est pas un serveur Marassim.');
            resolve(probe ? { ...result, certificate: pem, serverUrl: server } : result);
          }
        } catch (error) { reject(error); }
      });
      res.on('error', reject);
    });
    req.on('timeout', () => req.destroy(new Error('Le serveur ne répond pas. Vérifiez la connexion réseau puis réessayez.')));
    req.on('error', reject);
    if (serialized) req.write(serialized);
    req.end();
  });
}
module.exports = { request, normalizeServer };
