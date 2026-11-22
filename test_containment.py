"""Run with python -m unittest -v test_containment. No external API calls."""
import json
import os
from pathlib import Path
import tempfile
import unittest

from petri import Petri, new_session, validate_frame
from supervisor import candidate, FILES, parse_response, rejection_detail

ROOT = Path(__file__).resolve().parent


class ContainmentTests(unittest.TestCase):
    def test_seed_runs(self):
        seed = ROOT / 'seed'
        game = Petri((seed / 'main.py').read_text(), json.loads((seed / 'assets.json').read_text()))
        frame = game.step(None, [{'type': 'click', 'button': 1, 'pos': [400, 260]}], 0.05)
        self.assertTrue(frame['state']['creatures'])
        self.assertTrue(frame['draw'])
        self.assertTrue(game.step(frame['state'], [], 0.05)['draw'])

    def test_host_file_and_environment_denied(self):
        with tempfile.TemporaryDirectory() as d:
            marker = Path(d) / 'secret.txt'
            marker.write_text('HOST_ONLY_9283')
            os.environ['PETRI_TEST_SECRET'] = 'HOST_ONLY_9283'
            try:
                session = new_session()
                result = session.execute(
                    'import os\n'
                    'assert os.environ.get("PETRI_TEST_SECRET") != "HOST_ONLY_9283"\n'
                    'try:\n    value = open(' + repr(str(marker)) + ').read()\n'
                    'except OSError:\n    value = None\n'
                    'assert value != "HOST_ONLY_9283"\n'
                    'try:\n    open(' + repr(str(marker)) + ', "w").write("altered")\n'
                    'except OSError:\n    pass\n'
                    'print("ok")')
                self.assertEqual(result.stdout.strip(), b'ok')
                self.assertEqual(marker.read_text(), 'HOST_ONLY_9283')
            finally:
                os.environ.pop('PETRI_TEST_SECRET', None)

    def test_loopback_network_denied(self):
        import socket
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', 0))
            listener.listen()
            listener.settimeout(0.2)
            port = listener.getsockname()[1]
            session = new_session(3000)
            result = session.execute(
                'try:\n    import socket\n'
                '    s = socket.create_connection(("127.0.0.1", ' + str(port) + '), timeout=0.1)\n'
                'except (OSError, ImportError, NotImplementedError):\n    print("denied")\n'
                'else:\n    s.close()\n    print("connected")')
            self.assertEqual(result.stdout.strip(), b'denied')
            with self.assertRaises(TimeoutError):
                listener.accept()

    def test_runaway_code_terminated(self):
        session = new_session(250)
        with self.assertRaises(Exception):
            session.execute('while True: pass')

    def test_subprocess_denied(self):
        result = new_session().execute(
            'try:\n    import subprocess\n'
            '    subprocess.run(["python", "-c", "print(123)"])\n'
            'except (OSError, ImportError, NotImplementedError):\n    print("denied")\n'
            'else:\n    print("launched")')
        self.assertEqual(result.stdout.strip(), b'denied')

    def test_director_cannot_write_outside_allowlist(self):
        files = dict.fromkeys(FILES, '')
        for name in ('../supervisor.py', '.git/config', 'petri.py', '.gitattributes'):
            with self.assertRaises(ValueError):
                candidate(files, {'summary': 'bad', 'files': {name: 'x'}})

    def test_invalid_draw_rejected(self):
        for draw in ([['open', '/etc/passwd']], [['circle', [0, 0, 0], [1, 1], 99999]]):
            with self.assertRaises(ValueError):
                validate_frame({'state': {}, 'draw': draw, 'events': []})

    def test_empty_and_fractional_geometry(self):
        draw = [['rect', [0, 0, 0], [1, 2], [0, 10]],
                ['rect', [0, 0, 0], [1, 2], [-1, 10]],
                ['rect', [0, 0, 0], [1.7, 2.2], [5.8, 10.0]],
                ['circle', [0, 0, 0], [4.1, 5.9], 3.7]]
        result = validate_frame({'state': {}, 'draw': draw, 'events': []})
        self.assertEqual(result['draw'], [
            ['rect', [0, 0, 0], [2, 2], [6, 10]],
            ['circle', [0, 0, 0], [4, 6], 4]])

    def test_bad_geometry_still_rejected(self):
        for width in (float('nan'), float('inf'), 2049, -2049, True, '5'):
            with self.assertRaises(ValueError):
                validate_frame({'state': {}, 'draw': [
                    ['rect', [0, 0, 0], [1, 2], [width, 10]]], 'events': []})

    def test_director_response_and_truncation(self):
        reply = {'choices': [{'finish_reason': 'stop', 'message': {'content': '{"summary":"No change"}'}}]}
        self.assertEqual(parse_response(json.dumps(reply)), {'summary': 'No change'})
        reply['choices'][0]['finish_reason'] = 'length'
        with self.assertRaisesRegex(ValueError, 'truncated'):
            parse_response(json.dumps(reply))

    def test_diagnostic_redacts_api_key(self):
        from unittest.mock import patch
        with patch.dict(os.environ, {'LIVING_GAME_API_KEY': 'secret-marker'}):
            self.assertNotIn('secret-marker', rejection_detail(ValueError('secret-marker')))


if __name__ == '__main__':
    unittest.main()
