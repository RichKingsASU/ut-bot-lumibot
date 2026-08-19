import json
from pathlib import Path
import subprocess
import sys


def test_pure_logic_import_is_hermetic_and_does_not_pollute_modules():
    root = Path(__file__).resolve().parents[1]
    code = """
import json
import socket
import sys

class BlockThetaData:
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "thetadata" or fullname.startswith("thetadata."):
            raise ModuleNotFoundError("thetadata deliberately unavailable")
        return None

def forbidden_network(*args, **kwargs):
    raise AssertionError("network access attempted during import")

socket.create_connection = forbidden_network
socket.socket.connect = forbidden_network
sys.meta_path.insert(0, BlockThetaData())
before = set(sys.modules)
import strategies.ut_bot_logic
loaded = set(sys.modules) - before
forbidden = ("lumibot", "thetadata", "alpaca", "supabase", "anthropic", "openai")
print(json.dumps(sorted(name for name in loaded if name.startswith(forbidden))))
"""
    completed = subprocess.run(
        [sys.executable, "-I", "-c", f"import sys; sys.path.insert(0, {str(root)!r});" + code],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert json.loads(completed.stdout) == []
