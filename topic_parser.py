from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)
class ParsedTopic:
    raw: str
    oem_name: str
    oem_id: str
    mac: str
    tag: str
    network_id: str
    device_name: str
    device_id: str
    unit_id: str
    address: str

    @property
    def device_key(self) -> str:
        # stabiler Schlüssel pro physischem Gerät
        return f"{self.mac.lower()}::{self.network_id.lower()}"

    @property
    def model_key(self) -> str:
        return self.device_id.lower()

def parse_topic(topic: str) -> Optional[ParsedTopic]:
    parts = topic.split("/")
    # Erwartet genau 9 Segmente (0..8)
    if len(parts) != 9:
        return None

    oem_seg      = parts[0]  # "<oem_name>:<oem_id>"
    device_kw    = parts[1]  # "device"
    mac          = parts[2]
    tag          = parts[3]  # "id"
    network_id   = parts[4]
    dev_seg      = parts[5]  # "<device_name>:<device_id>"
    dp_kw        = parts[6]  # "dp"
    unit_id      = parts[7]  # "00"
    address      = parts[8]  # "40037" etc.

    if device_kw != "device" or dp_kw != "dp":
        return None
    if ":" not in oem_seg or ":" not in dev_seg:
        return None

    oem_name, oem_id = oem_seg.split(":", 1)
    device_name, device_id = dev_seg.split(":", 1)

    return ParsedTopic(
        raw=topic,
        oem_name=oem_name, oem_id=oem_id,
        mac=mac, tag=tag, network_id=network_id,
        device_name=device_name, device_id=device_id,
        unit_id=unit_id, address=address,
    )
