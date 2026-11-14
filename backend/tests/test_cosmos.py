import asyncio
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi import HTTPException

from app.api.cosmos import assault_node, create_node, unlock_sector
from app.models.schemas import CosmosData
from app.services.storage import StorageService


class CosmosMutationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.storage = StorageService(Path(self.temp_dir.name))

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_parallel_duplicate_nodes_increment_without_creating_duplicates(self):
        def create(_):
            return asyncio.run(create_node({"subject": "Matematik", "tag": "[Knowledge Gap]"}, self.storage))

        with ThreadPoolExecutor(max_workers=8) as pool:
            nodes = list(pool.map(create, range(24)))

        saved = self.storage.load_doc("cosmos.json", CosmosData)
        self.assertEqual(len(saved.nodes), 1)
        self.assertEqual(saved.nodes[0].error_count, 23)
        self.assertEqual(len({node.id for node in nodes}), 1)

    def test_parallel_unique_nodes_are_all_retained(self):
        def create(index):
            return asyncio.run(create_node({"subject": f"Topic {index}"}, self.storage))

        with ThreadPoolExecutor(max_workers=8) as pool:
            nodes = list(pool.map(create, range(24)))

        saved = self.storage.load_doc("cosmos.json", CosmosData)
        self.assertEqual(len(saved.nodes), 24)
        self.assertEqual(len({node.id for node in nodes}), 24)

    def test_parallel_sector_unlocks_preserve_each_sector(self):
        sectors = ["sector_1", "sector_2", "sector_3"]

        def unlock(sector):
            return asyncio.run(unlock_sector(sector, self.storage))

        with ThreadPoolExecutor(max_workers=3) as pool:
            list(pool.map(unlock, sectors))

        saved = self.storage.load_doc("cosmos.json", CosmosData)
        self.assertEqual(set(saved.unlocked_sectors), {"sector_0", *sectors})
        self.assertEqual(len(saved.unlocked_sectors), 4)
        same = asyncio.run(unlock_sector("sector_1", self.storage))
        self.assertEqual(set(same.unlocked_sectors), {"sector_0", *sectors})

    def test_assault_is_retired_without_changing_stored_files(self):
        cosmos_path = Path(self.temp_dir.name) / "cosmos.json"
        user_path = Path(self.temp_dir.name) / "user.json"
        cosmos_path.write_text('{ "nodes": [], "unlocked_sectors": ["sector_0"] }')
        user_path.write_text('{"total_xp": 12}')
        before = (cosmos_path.read_bytes(), user_path.read_bytes())

        with self.assertRaises(HTTPException) as raised:
            asyncio.run(assault_node("node-1"))

        self.assertEqual(raised.exception.status_code, 410)
        self.assertEqual((cosmos_path.read_bytes(), user_path.read_bytes()), before)

    def test_invalid_sector_does_not_create_or_modify_cosmos(self):
        with self.assertRaises(HTTPException) as raised:
            asyncio.run(unlock_sector("unknown", self.storage))

        self.assertEqual(raised.exception.status_code, 422)
        self.assertFalse((Path(self.temp_dir.name) / "cosmos.json").exists())


if __name__ == "__main__":
    unittest.main()
