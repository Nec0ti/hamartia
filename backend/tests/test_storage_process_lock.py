import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path


class StorageProcessLockTests(unittest.TestCase):
    def test_independent_processes_append_without_losing_records(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            data = root / "data"
            ready = root / "ready"
            ready.mkdir()
            gate = root / "start"
            code = (
                "import sys,time; from pathlib import Path; "
                "from app.services.storage import StorageService; "
                "data, worker, ready, gate = Path(sys.argv[1]), int(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4]); "
                "s=StorageService(data); ready.touch(); "
                "\nwhile not gate.exists(): time.sleep(.002)\n"
                "\nfor i in range(4): s.append_list('rows.json', {'id': f'{worker}-{i}'}, dict)\n"
            )
            env = os.environ.copy()
            backend = str(Path(__file__).resolve().parents[1])
            env["PYTHONPATH"] = os.pathsep.join([backend, env.get("PYTHONPATH", "")])
            processes = [
                subprocess.Popen([sys.executable, "-c", code, str(data), str(worker), str(ready / str(worker)), str(gate)], env=env)
                for worker in range(3)
            ]
            deadline = time.monotonic() + 10
            while len(list(ready.iterdir())) < len(processes) and time.monotonic() < deadline:
                time.sleep(.005)
            self.assertEqual(len(list(ready.iterdir())), len(processes))
            gate.touch()
            for process in processes:
                self.assertEqual(process.wait(timeout=15), 0)
            records = json.loads((data / "rows.json").read_text(encoding="utf-8"))
            self.assertEqual({record["id"] for record in records}, {f"{worker}-{i}" for worker in range(3) for i in range(4)})


if __name__ == "__main__":
    unittest.main()
