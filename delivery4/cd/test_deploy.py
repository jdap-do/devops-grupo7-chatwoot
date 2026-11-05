"""Pruebas de corte y recuperacion sin tocar una VM o una base de datos."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('deployment', Path(__file__).with_name('deploy.py'))
cd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cd)
SHA = 'a' * 40
IMAGE = 'ghcr.io/jdap-do/devops-grupo7-chatwoot@sha256:' + 'b' * 64


class DeploymentTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.root_patch = patch.object(cd, 'ROOT', self.root)
        self.root_patch.start()
        self.addCleanup(self.root_patch.stop)
        (self.root / 'routes').mkdir()
        self.old = {'slot': 'legacy', 'revision': 'c' * 40, 'image': 'old'}
        (self.root / 'state.json').write_text(json.dumps({'active': self.old, 'previous': None}))
        (self.root / 'routes/active.conf').write_text('original')
        self.client = self.root / 'client.json'
        self.client.write_text(json.dumps({'token': 'fixture', 'account_id': 1, 'conversation_id': 1}))
        self.client_patch = patch.object(cd, 'CLIENT', self.client)
        self.client_patch.start()
        self.addCleanup(self.client_patch.stop)

    def test_demo_is_bound_to_its_release(self):
        with patch.object(cd, 'SOURCE', Path('/srv/chatwoot/releases/first/delivery4/cd')):
            first = cd.slot_environment(IMAGE, 'blue')
        with patch.object(cd, 'SOURCE', Path('/srv/chatwoot/releases/second/delivery4/cd')):
            second = cd.slot_environment(IMAGE, 'green')
        self.assertIn('DEMO_FILE=/srv/chatwoot/releases/first/delivery4/app/demo-gcp.html\n', first)
        self.assertIn('DEMO_FILE=/srv/chatwoot/releases/second/delivery4/app/demo-gcp.html\n', second)
        self.assertNotIn('/second/', first)

    def test_route_rejects_injection(self):
        with self.assertRaises(ValueError):
            cd.route('blue;bad', SHA)
        with self.assertRaises(ValueError):
            cd.route('blue', 'a;bad')

    def test_nginx_rejects_candidate_restores_config(self):
        calls = []

        def command(*args, **kwargs):
            calls.append(args)
            if len(calls) == 1:
                raise RuntimeError('nginx -t rejected candidate')

        with patch.object(cd, 'run', side_effect=command):
            with self.assertRaises(RuntimeError):
                cd.switch({'slot': 'blue', 'revision': SHA})
        self.assertEqual((self.root / 'routes/active.conf').read_text(), 'original')
        self.assertEqual(calls[-1][-2:], ('-s', 'reload'))

    def test_pending_migrations_never_switch_traffic(self):
        def command(*args, **kwargs):
            return ''

        def compose(slot, *args):
            if 'db:abort_if_pending_migrations' in args:
                raise RuntimeError('pending migrations')

        with patch.object(cd, 'run', side_effect=command), patch.object(cd, 'compose', side_effect=compose), patch.object(cd, 'switch') as switch:
            with self.assertRaises(RuntimeError):
                cd.deploy(IMAGE, SHA)
        switch.assert_not_called()
        self.assertEqual(json.loads((self.root / 'state.json').read_text())['active'], self.old)

    def test_draining_connections_prevent_slot_reuse(self):
        with patch.object(cd, 'run', return_value='nginx: worker process is shutting down'), patch.object(cd, 'compose') as compose:
            with self.assertRaises(RuntimeError):
                cd.deploy(IMAGE, SHA)
        compose.assert_not_called()

    def test_failed_post_switch_check_rolls_back(self):
        def command(*args, **kwargs):
            if 'cat' in args:
                return SHA
            if '{{.State.Running}}' in args:
                return 'true'
            return ''

        class Watch:
            counts = {'failed': 0}
            thread = type('Thread', (), {'start': lambda self: None})()
            def __init__(self, client):
                pass
            def finish(self):
                return {'failed': 1, '200_json': 10}

        with patch.object(cd, 'run', side_effect=command), patch.object(cd, 'compose'), patch.object(cd, 'ready'), patch.object(cd, 'Continuity', Watch), patch.object(cd.time, 'sleep'), patch.object(cd, 'read_api', side_effect=ValueError('wrong revision')), patch.object(cd, 'switch') as switch:
            with self.assertRaises(RuntimeError):
                cd.deploy(IMAGE, SHA)
        self.assertEqual(switch.call_count, 2)
        self.assertEqual(switch.call_args.args[0], self.old)
        evidence = json.loads(next(self.root.glob('deployment-*.json')).read_text())
        self.assertFalse(evidence['committed'])

    def test_promoted_image_keeps_distinct_source_and_release_revisions(self):
        source, tree = 'd' * 40, 'e' * 40

        def command(*args, **kwargs):
            if '/app/.git_sha' in args:
                return source
            if '/app/.source_tree' in args:
                return tree
            return ''

        with patch.object(cd, 'run', side_effect=command), patch.object(cd, 'compose'), patch.object(cd, 'ready', side_effect=RuntimeError('reached-readiness')) as ready:
            with self.assertRaisesRegex(RuntimeError, 'reached-readiness'):
                cd.deploy(IMAGE, SHA, source_revision=source, source_tree=tree)
        self.assertEqual(ready.call_args.args[0]['revision'], SHA)
        self.assertEqual(ready.call_args.args[0]['source_revision'], source)
        self.assertEqual(ready.call_args.args[0]['source_tree'], tree)

    def test_wrong_image_source_or_content_never_reaches_readiness(self):
        for actual_source, actual_tree in [('f' * 40, 'e' * 40), ('d' * 40, 'f' * 40)]:
            def command(*args, **kwargs):
                if '/app/.git_sha' in args:
                    return actual_source
                if '/app/.source_tree' in args:
                    return actual_tree
                return ''

            with patch.object(cd, 'run', side_effect=command), patch.object(cd, 'compose'), patch.object(cd, 'ready') as ready:
                with self.assertRaises(RuntimeError):
                    cd.deploy(IMAGE, SHA, source_revision='d' * 40, source_tree='e' * 40)
            ready.assert_not_called()


if __name__ == '__main__':
    unittest.main()
