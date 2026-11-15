import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path


class StorageProcessLockTests(unittest.TestCase):
    def test_held_process_lock_blocks_writer_until_release(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            data = root / "data"
            ready, started, release, done = [root / name for name in ("ready", "started", "release", "done")]
            env = os.environ.copy()
            env["PYTHONPATH"] = os.pathsep.join([str(Path(__file__).resolve().parents[1]), env.get("PYTHONPATH", "")])
            holder_code = (
                "import sys,time; from pathlib import Path; from app.services.storage import data_mutation_guard; "
                "data,ready,release=map(Path,sys.argv[1:]); "
                "\nwith data_mutation_guard(data):\n ready.touch()\n while not release.exists(): time.sleep(.01)\n"
            )
            writer_code = (
                "import sys; from pathlib import Path; from app.services.storage import StorageService; "
                "data,started,done=map(Path,sys.argv[1:]); started.touch(); "
                "StorageService(data).append_list('rows.json', {'id':'after-release'}, dict); done.touch()"
            )
            probe_code = (
                "import os,sys; from pathlib import Path; data=Path(sys.argv[1]).resolve(); "
                "path=data.with_name('.'+data.name+'.mutation.lock'); f=path.open('a+b'); "
                "\nif os.name=='nt':\n import msvcrt; f.seek(0)\n try: msvcrt.locking(f.fileno(),msvcrt.LK_NBLCK,1)\n except OSError: sys.exit(0)\n msvcrt.locking(f.fileno(),msvcrt.LK_UNLCK,1)\n"
                "\nelse:\n import fcntl\n try: fcntl.flock(f.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)\n except OSError: sys.exit(0)\n fcntl.flock(f.fileno(),fcntl.LOCK_UN)\n"
                "\nsys.exit(1)\n"
            )
            holder = subprocess.Popen([sys.executable, "-c", holder_code, str(data), str(ready), str(release)], env=env)
            writer = None
            try:
                deadline = time.monotonic() + 10
                while not ready.exists() and time.monotonic() < deadline:
                    time.sleep(.005)
                self.assertTrue(ready.exists(), "lock holder did not acquire the process lock")
                writer = subprocess.Popen([sys.executable, "-c", writer_code, str(data), str(started), str(done)], env=env)
                while not started.exists() and time.monotonic() < deadline:
                    time.sleep(.005)
                self.assertTrue(started.exists(), "contending writer did not start")
                blocked = subprocess.run([sys.executable, "-c", probe_code, str(data)], env=env, timeout=10)
                self.assertEqual(blocked.returncode, 0, "OS lock probe must confirm the held lock blocks acquisition")
                self.assertFalse(done.exists(), "writer must remain blocked while another process holds the lock")
            finally:
                release.touch()
            self.assertEqual(holder.wait(timeout=10), 0)
            available = subprocess.run([sys.executable, "-c", probe_code, str(data)], env=env, timeout=10)
            self.assertEqual(available.returncode, 1, "OS lock probe must acquire the lock after holder release")
            self.assertEqual(writer.wait(timeout=10), 0)
            self.assertTrue(done.exists(), "writer should finish after lock release")
            records = json.loads((data / "rows.json").read_text(encoding="utf-8"))
            self.assertEqual(records, [{"id": "after-release"}])

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
