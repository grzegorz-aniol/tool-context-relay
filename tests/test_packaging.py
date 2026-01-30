import importlib.metadata as metadata
import unittest


class PackagingTests(unittest.TestCase):
    def test_distribution_is_installed(self):
        dist = metadata.distribution("tool-context-relay")
        self.assertTrue(dist.version)

    def test_console_script_entry_point_exists(self):
        entry_points = metadata.entry_points()
        if hasattr(entry_points, "select"):
            scripts = entry_points.select(group="console_scripts")
        else:
            scripts = entry_points.get("console_scripts", [])

        script_names = {entry_point.name for entry_point in scripts}
        self.assertIn("tool-context-relay", script_names)
