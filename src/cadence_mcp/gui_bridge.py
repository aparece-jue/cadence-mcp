"""Host-configured, authenticated loopback bridge client. No arbitrary operations."""
from pathlib import Path
import json
import socket
import uuid

from .core import CadenceError, sha256


class GuiBridgeClient:
    def __init__(self, config_path: Path):
        self.config_path = config_path

    def status(self) -> dict:
        try:
            config = json.loads(self.config_path.read_text(encoding="utf-8"))
            endpoint = json.loads((self.config_path.parent / "endpoint.json").read_text(encoding="utf-8"))
            if (endpoint["host"] != "127.0.0.1" or type(endpoint["port"]) is not int
                    or not 1 <= endpoint["port"] <= 65535 or endpoint["protocol"] != 1
                    or endpoint["instanceId"] != config["instanceId"] or endpoint["pid"] != config["expectedPid"]):
                raise ValueError("endpoint binding mismatch")
            design = Path(config["expectedDesign"])
            if sha256(design) != config["sourceFingerprint"]:
                raise CadenceError("target_changed", "Bound design file changed; prepare a new binding.")
            request = {"protocol": 1, "requestId": uuid.uuid4().hex, "operation": "status",
                       "token": config["token"], "instanceId": config["instanceId"],
                       "expectedDesign": str(design)}
            with socket.create_connection(("127.0.0.1", endpoint["port"]), timeout=3) as channel:
                channel.settimeout(3)
                channel.sendall(json.dumps(request, ensure_ascii=False).encode("utf-8") + b"\n")
                data = bytearray()
                while b"\n" not in data:
                    block = channel.recv(4096)
                    if not block:
                        raise ValueError("bridge closed without response")
                    data.extend(block)
                    if len(data) > 16384:
                        raise ValueError("oversized response")
            row = json.loads(bytes(data).decode("utf-8"))
            if (row["requestId"] != request["requestId"] or row["instanceId"] != config["instanceId"]
                    or row["pid"] != config["expectedPid"] or row["protocol"] != 1
                    or row["readOnly"] is not True or row["capabilities"] != ["gui.status"]):
                raise ValueError("response binding mismatch")
            if row["status"] == "target_changed" or Path(row["activeDesign"]).resolve() != design.resolve():
                raise CadenceError("target_changed", "Capture active design changed; binding is not retargeted.")
            if row["status"] != "succeeded":
                raise ValueError("unexpected status")
            if sha256(design) != config["sourceFingerprint"]:
                raise CadenceError("target_changed", "Bound design file changed during request.")
            # Tokens, endpoint/config paths and request payloads are never returned.
            return {"instanceId": row["instanceId"], "pid": row["pid"], "activeDesign": row["activeDesign"],
                    "tclVersion": row["tclVersion"], "readOnly": True, "dirtyState": "unknown",
                    "capabilities": row["capabilities"], "sourceFingerprint": config["sourceFingerprint"],
                    "bindingVerified": True}
        except CadenceError:
            raise
        except (OSError, ValueError, KeyError, TypeError, UnicodeError) as error:
            raise CadenceError("bridge_unavailable", "GUI bridge unavailable or authentication/binding failed.", "gui_bridge") from error
