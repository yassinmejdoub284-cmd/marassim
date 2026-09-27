"""Isolated, loopback-only fixture. Never imports the real database."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'server'))
from app import Application, serve
root = Path(__file__).resolve().parents[1] / 'test-results/ui-fixture'
application = Application(root)
with application.storage.transaction() as conn:
    exists = conn.execute('SELECT COUNT(*) FROM users').fetchone()[0]
if not exists:
    application.dispatch('POST', '/api/setup', {'X-Bootstrap-Key': application.bootstrap.read_text()}, {'username': 'ui-test', 'password': 'ui-test-password'})
server = serve(application, '127.0.0.1', 18744, insecure=True)
try: server.serve_forever()
finally: server.server_close()
