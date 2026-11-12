import unittest

from scripts.prerequisites import supported_host, supported_node, supported_python


class SetupPrerequisiteTests(unittest.TestCase):
    def test_supported_python_range_is_310_through_312(self):
        self.assertTrue(supported_python((3, 10, 0)))
        self.assertTrue(supported_python((3, 11, 9)))
        self.assertTrue(supported_python((3, 12, 0)))
        self.assertFalse(supported_python((3, 9, 18)))
        self.assertFalse(supported_python((3, 13, 0)))

    def test_supported_node_releases(self):
        self.assertTrue(supported_node("v22.12.0"))
        self.assertTrue(supported_node("24.1.0"))
        self.assertFalse(supported_node("v22.11.0"))
        self.assertFalse(supported_node("v23.0.0"))
        self.assertFalse(supported_node("not-node"))

    def test_supported_platforms_and_architectures(self):
        self.assertTrue(supported_host("Darwin", "arm64"))
        self.assertTrue(supported_host("Darwin", "x86_64"))
        self.assertTrue(supported_host("Windows", "AMD64"))
        self.assertFalse(supported_host("Windows", "ARM64"))
        self.assertFalse(supported_host("Linux", "x86_64"))
