# Copyright 2026 Tony Aiuto
#
# See LICENSE.txt
"""Integration test: the .deb and docker image built in this package come
from the exact same tar (see BUILD), so DebReader and DockerReader must
read back identical trees. Exercises both readers against real package
formats instead of synthetic fixtures.

Requires a local docker daemon to build :package_readers_docker, so this
target is tagged "manual" and must be run explicitly:
  bazelisk test //distribution:integration_test
"""

import unittest

from python.runfiles import runfiles

from tools.tree_size_compare import InputFactory, load_tree_from_reader, stream_compare


def get_runfile(path):
    """Get the path to a runfile."""
    r = runfiles.Create()
    return r.Rlocation("_main/" + path)


def _default_flags():
    return {
        "max_allowed_absolute_increase": 0,
        "max_allowed_percent_increase": 0,
        "show_decreases": True,
        "minimum_compare_size": 0,
        "include_patterns": [],
        "exclude_patterns": [],
        "compare_uid_gid": True,
    }


class DistributionIntegrationTest(unittest.TestCase):

    def test_deb_and_docker_contents_match(self):
        """The .deb and the docker image must extract to identical trees."""
        deb_path = get_runfile("distribution/package_readers_deb.deb")
        docker_path = get_runfile("distribution/package_readers.docker")

        expected = load_tree_from_reader(InputFactory.create(deb_path))
        got_reader = InputFactory.create(docker_path)

        results = stream_compare(expected, got_reader, _default_flags())

        self.assertEqual(results["only_in_expected"], [])
        self.assertEqual(results["only_in_got"], [])
        self.assertEqual(results["symlink_target_changed"], [])
        self.assertEqual(results["metadata_changed"], [])
        self.assertEqual(results["size_changed"], [])

    def test_expected_tools_present(self):
        """Sanity check the package actually contains the three tools."""
        deb_path = get_runfile("distribution/package_readers_deb.deb")
        tree = load_tree_from_reader(InputFactory.create(deb_path))

        for name in ("usr/bin/tree_size_compare", "usr/bin/rpm_info", "usr/bin/cpio-ls"):
            self.assertIn(name, tree)
            self.assertFalse(tree[name].is_dir)
            self.assertGreater(tree[name].size, 0)


if __name__ == "__main__":
    unittest.main()
