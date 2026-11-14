import tempfile
import unittest
from pathlib import Path

from app.services.data_lock import DataDirectoryBusy, DataDirectoryLock


class DataDirectoryLockTests(unittest.TestCase):
    def test_only_one_process_can_own_the_data_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            data_dir = Path(directory) / "data"
            first = DataDirectoryLock(data_dir)
            second = DataDirectoryLock(data_dir)

            with first:
                self.assertTrue(first.path.is_file())
                with self.assertRaises(DataDirectoryBusy):
                    second.__enter__()

            with second:
                self.assertIsNotNone(second.file)


if __name__ == "__main__":
    unittest.main()
