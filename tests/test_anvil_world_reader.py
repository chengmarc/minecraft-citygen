import os
import unittest

from engine.anvil_world_reader import World


class AnvilWorldReaderTests(unittest.TestCase):
    def test_world_reports_checked_region_paths_when_region_dir_is_missing(self):
        with self.assertRaises(FileNotFoundError) as exc_info:
            World(
                region_dir="C:/missing/world/region",
                save_path="C:/missing/world",
            )

        message = str(exc_info.exception)
        self.assertIn("Configured save: C:/missing/world", message)
        self.assertIn(os.path.normpath("C:/missing/world/region"), message)


if __name__ == "__main__":
    unittest.main()
