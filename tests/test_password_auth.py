import http.client
import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path

from ai_drama_agent.store import LocalStore
from ai_drama_agent.web import DramaWebHandler


class PasswordAuthTests(unittest.TestCase):
    def test_password_lifecycle_and_removed_provider_routes(self):
        with tempfile.TemporaryDirectory() as directory:
            class Handler(DramaWebHandler):
                store = LocalStore(Path(directory) / 'state.json')

                def log_message(self, *args):
                    pass

            server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            connection = http.client.HTTPConnection(*server.server_address, timeout=5)

            def request(method, path, data=None, token=None):
                headers = {'Content-Type': 'application/json'}
                if token:
                    headers['Authorization'] = f'Bearer {token}'
                connection.request(method, path, json.dumps(data) if data is not None else None, headers)
                response = connection.getresponse()
                return response.status, json.loads(response.read())

            try:
                for method, path in [
                    ('POST', '/api/auth/sms/send'),
                    ('POST', '/api/auth/sms/login'),
                    ('POST', '/api/auth/wechat/start'),
                    ('GET', '/api/auth/wechat/status?state=test'),
                    ('GET', '/api/auth/wechat/callback?state=test&code=test'),
                ]:
                    self.assertEqual(request(method, path, {} if method == 'POST' else None)[0], 404)
                status, registered = request('POST', '/api/auth/register', {
                    'username': 'password-user', 'email': 'user@example.com', 'password': 'secret123',
                })
                self.assertEqual(status, 200)
                self.assertNotIn('password_hash', registered['user'])
                self.assertNotIn('phone', registered['user'])
                self.assertEqual(request('POST', '/api/auth/login', {'identity': 'password-user', 'password': 'wrong'})[0], 401)
                status, login = request('POST', '/api/auth/login', {'identity': 'user@example.com', 'password': 'secret123'})
                self.assertEqual(status, 200)
                token = login['token']
                self.assertEqual(request('GET', '/api/auth/me', token=token)[1]['user']['id'], registered['user']['id'])
                self.assertEqual(request('POST', '/api/auth/logout', {}, token)[0], 200)
                self.assertEqual(request('GET', '/api/auth/me', token=token)[0], 401)
            finally:
                connection.close()
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)
