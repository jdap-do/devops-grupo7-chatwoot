"""Comprobar que el camino rapido rechaza contenido y procedencias incorrectos."""
from datetime import datetime, timezone, timedelta
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('promotion', Path(__file__).with_name('reuse_candidate.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
SOURCE, TREE = 'a' * 40, 'b' * 40


class CandidateTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 5, 12, tzinfo=timezone.utc)
        self.image = {'Created': self.now.isoformat(), 'Config': {'Labels': {
            'org.opencontainers.image.revision': SOURCE, 'io.grupo7.source-tree': TREE}}}
        self.run = {'head_sha': SOURCE, 'head_branch': 'develop', 'event': 'push',
                    'conclusion': 'success', 'head_repository': {'id': 1413754542}}

    def validate(self, commit_tree=TREE):
        return module.validate_candidate(self.image, TREE, commit_tree,
                                         [self.run], 1413754542, self.now)

    def test_identical_tree_from_successful_develop(self):
        self.assertEqual(self.validate(), SOURCE)

    def test_different_git_commit_content(self):
        self.assertIsNone(self.validate('c' * 40))

    def test_label_does_not_match_git_tree(self):
        self.image['Config']['Labels']['io.grupo7.source-tree'] = 'c' * 40
        self.assertIsNone(self.validate())

    def test_pull_request_never_authorizes_promotion(self):
        self.run['event'] = 'pull_request'
        self.assertIsNone(self.validate())

    def test_failure_or_in_progress_never_authorizes(self):
        for conclusion in (None, 'failure', 'cancelled'):
            self.run['conclusion'] = conclusion
            self.assertIsNone(self.validate())

    def test_wrong_repository_or_branch(self):
        self.run['head_repository']['id'] = 99
        self.assertIsNone(self.validate())
        self.run['head_repository']['id'] = 1413754542
        self.run['head_branch'] = 'untrusted'
        self.assertIsNone(self.validate())

    def test_expired_and_future_image(self):
        for delta in (timedelta(hours=-25), timedelta(hours=1)):
            self.image['Created'] = (self.now + delta).isoformat()
            self.assertIsNone(self.validate())

    def test_invalid_source_revision(self):
        self.image['Config']['Labels']['org.opencontainers.image.revision'] = 'bad;input'
        self.assertIsNone(self.validate())


if __name__ == '__main__':
    unittest.main()
