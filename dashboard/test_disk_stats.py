from dashboard.knowledge.stats import NamespaceStatsComputer
from pathlib import Path
import tempfile
import os

with tempfile.TemporaryDirectory() as tmpdir:
    test_dir = Path(tmpdir) / "test-ns"
    test_dir.mkdir()
    
    file1 = test_dir / "f1.bin"
    file1.write_bytes(b"\0" * 1024)
    
    file2 = test_dir / "f2.bin"
    file2.write_bytes(b"\0" * 2048)
    
    expected = 1024 + 2048
    
    computer = NamespaceStatsComputer()
    stats = computer.get_stats("test-ns", test_dir)
    print(f"Expected: {expected}, Got: {stats['disk_bytes']}")
    
    import subprocess
    try:
        res = subprocess.run(["du", "-sk", str(test_dir)], capture_output=True, text=True)
        print(f"du -sk: {res.stdout.strip()}")
    except:
        pass
