from __future__ import annotations
import logging
import json
import time
from collections import defaultdict
from typing import Dict, Set, List, Tuple, Any
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send
from .const import DOMAIN, SIGNAL_NEW_DEVICE, SIGNAL_DP_UPDATE
from .topic_parser import parse_topic, ParsedTopic

_LOGGER = logging.getLogger(__name__)

STALE_REGISTER_MAX_AGE = 10.0  # Maximum age in seconds for related registers to be considered fresh

class Coordinator:
    def __init__(self, hass: HomeAssistant, mqtt_gw, meta_client, topic_prefix: str, auto_onboard: bool):
        self.hass = hass
        self.mqtt = mqtt_gw
        self.meta = meta_client
        self.prefix = topic_prefix
        self.auto = auto_onboard
        self._known_devices: Set[str] = set()

        # Register storage: device_key -> { address: (value, timestamp) }
        self._registers: dict[str, dict[int, Tuple[int, float]]] = defaultdict(dict)
        # Datapoint metadata: device_key -> List[dict]
        self._datapoints: dict[str, List[dict]] = defaultdict(list)
        # Decoded values: device_key -> { datapoint_start_address: decoded_value }
        self._dp_value_cache: dict[str, dict[int, Any]] = defaultdict(dict)

    async def start(self):
        self.mqtt.subscribe("+/device/+/+/+/+/dp/+/+")
        _LOGGER.debug("Subscribed to topic wildcard for device datapoints")

    async def handle_message(self, topic: str, payload: bytes):
        pt = parse_topic(topic)
        if not pt:
            _LOGGER.debug("Ignored topic (no match): %s", topic)
            return

        # New device discovered?
        if pt.device_key not in self._known_devices:
            self._known_devices.add(pt.device_key)
            _LOGGER.info("Discovered new device: %s (%s:%s)", pt.device_key, getattr(pt, "oem_name", "?"), getattr(pt, "device_name", "?"))
            # Load metadata using IDs from MQTT topic
            organization_id = pt.oem_id
            device_enum_id = getattr(pt, "device_id", None)
            if device_enum_id:
                try:
                    meta = await self.meta.get_metadata(organization_id, device_enum_id)
                    if meta:
                        datapoints = meta.get("datapoints", [])
                        self.register_datapoints(pt.device_key, datapoints)
                        _LOGGER.info("Metadata for device %s loaded (%d datapoints)", pt.device_key, len(datapoints))
                    else:
                        _LOGGER.warning(f"No metadata available for device {pt.device_key}")
                except Exception as e:
                    _LOGGER.warning(f"Failed to load metadata for device {pt.device_key}: {e}")
            async_dispatcher_send(self.hass, SIGNAL_NEW_DEVICE, pt)

        # Attempt to extract register value
        address, value = self._extract_register(topic, payload, pt)
        if address is not None and value is not None:
            self.update_register(pt.device_key, address, value)

    # --- Datapoint Management -------------------------------------------------

    def register_datapoints(self, device_key: str, datapoints: List[dict]):
        self._datapoints[device_key] = datapoints

    def get_datapoint_value(self, device_key: str, address: int):
        return self._dp_value_cache.get(device_key, {}).get(address)

    def is_device_metadata_available(self, device_key: str) -> bool:
        """
        Check if metadata is available for a device.
        Returns False if metadata fetch failed or device not found.
        """
        # Get parsed topic to extract device_id
        parsed_topics = self.hass.data.get(DOMAIN, {}).get("parsed_topics", {})
        pt = parsed_topics.get(device_key)
        if not pt:
            # Device not yet fully registered, assume unavailable
            return False

        # Check metadata status via meta client
        organization_id = pt.oem_id
        device_enum_id = getattr(pt, "device_id", None)
        if not device_enum_id:
            return False

        status = self.meta.get_device_status(organization_id, device_enum_id)
        return status == "ok"

    # --- Register Update + Decoding -------------------------------------------

    def update_register(self, device_key: str, address: int, value: int):
        now = time.time()
        self._registers[device_key][address] = (value & 0xFFFF, now)

        # Check datapoints linearly (optimization possible later)
        for dp in self._datapoints.get(device_key, []):
            start = int(dp.get("address", -1))
            if start < 0:
                continue
            length_bytes = int(dp.get("length", 0))
            if length_bytes <= 0:
                continue
            reg_needed = (length_bytes + 1) // 2
            if not (start <= address < start + reg_needed):
                continue
            decoded = self._try_decode_dp(device_key, dp, start, reg_needed, length_bytes)
            if decoded is not None:
                prev = self._dp_value_cache[device_key].get(start)
                if decoded != prev:
                    self._dp_value_cache[device_key][start] = decoded
                    async_dispatcher_send(
                        self.hass,
                        SIGNAL_DP_UPDATE,
                        device_key,
                        start,
                        decoded
                    )

    def _try_decode_dp(self, device_key: str, dp: dict, start: int, reg_count: int, length_bytes: int):
        regs = self._registers.get(device_key, {})
        words: list[int] = []
        now = time.time()
        for off in range(reg_count):
            a = start + off
            item = regs.get(a)
            if item is None:
                return None
            val, ts = item
            if now - ts > STALE_REGISTER_MAX_AGE:
                return None
            words.append(val)

        raw_bytes = bytearray()
        for w in words:
            raw_bytes.extend(w.to_bytes(2, "big"))
        raw_bytes = raw_bytes[:length_bytes]

        dtype = (dp.get("type") or "").lower()
        try:

            value = None

            if dtype in ("uns8", "uint8"):
                value = int.from_bytes(raw_bytes, "big", signed=False)
            elif dtype in ("uns16", "uint16"):
                value = int.from_bytes(raw_bytes, "big", signed=False)
            elif dtype in ("int16","sig16"):
                value = int.from_bytes(raw_bytes, "big", signed=True)
            elif dtype in ("uns32", "uint32"):
                value =  int.from_bytes(raw_bytes.ljust(4, b"\x00"), "big", signed=False)
            elif dtype in ("int32","sig32"):
                value = int.from_bytes(raw_bytes.ljust(4, b"\x00"), "big", signed=True)
            elif dtype in ("float32", "float"):
                if len(raw_bytes) < 4:
                    return None
                import struct
                value = struct.unpack(">f", raw_bytes[:4])[0]
            elif dtype in ("bool", "boolean"):
                return bool(raw_bytes[0] & 0x01)
            elif dtype.startswith("str") or dtype.startswith("char"):
                return raw_bytes.decode("utf-8", errors="ignore").rstrip("\x00")

            if value is not None:


                value = value * dp.get("step", 1)


                if dp.get("format", 1) != "":
                    # if given the format is structured like {\r\n    \"0\": \"Off\",\r\n    \"1\": \"Daily\",\r\n    \"2\": \"Weekly\"\r\n}
                    try:
                        fmt = json.loads(dp.get("format"))
                        # _LOGGER.debug(f"Applying format mapping for DP '{dp.get('name')}': {fmt}")
                        if isinstance(fmt, dict):
                            value_str = str(value)
                            if value_str in fmt:
                                return fmt[value_str] # return formatted string
                            else:
                                _LOGGER.warning(f"Value '{value_str}' not found in format mapping for DP '{dp.get('name')}'. Available keys: {list(fmt.keys())}. Returning raw value.")
                        else:
                            _LOGGER.warning(f"Format mapping for DP '{dp.get('name')}' is not a dictionary. Returning raw value.")
                    except Exception:
                        _LOGGER.warning(f"Error applying format: '{dp.get('format')}' for value: '{value}' of DP '{dp.get('name')}'. Returning raw value.")

                # if value < dp.get("minValue") or value > dp.get("maxValue"):
                #     return None

                return value

            # Fallback to hex representation
            _LOGGER.warning(f"Unknown data type: {dtype}, raw bytes: {raw_bytes.hex()}")
            return raw_bytes.hex()

        except Exception:
            return None

    # --- Helper Functions -----------------------------------------------------

    def _extract_register(self, topic: str, payload: bytes, pt: ParsedTopic):
        """
        Attempts to extract address + value from topic/payload.
        Heuristics:
        1. JSON with {"address":X,"value":Y}
        2. JSON with {"value":Y} + address in topic (last or second-to-last segments)
        3. "addr=value" plain text
        4. Only number (value) + address from topic
        """
        text = ""
        try:
            text = payload.decode("utf-8", errors="ignore").strip()
        except Exception:
            return None, None

        address = None
        value = None

        # Extract numeric candidates from topic
        parts = topic.split("/")
        # Look for segments that look like numbers (second-to-last might be address)
        numeric_parts = [p for p in parts if p.isdigit()]

        # 1) JSON format
        if text.startswith("{"):
            try:
                obj = json.loads(text)
                if isinstance(obj, dict):
                    value = obj.get("value")
                    address = obj.get("address")
                    if address is None and numeric_parts:
                        # Heuristic: use largest number as address if value is present
                        try:
                            address = int(max(numeric_parts, key=lambda x: len(x)))
                        except Exception:
                            pass
            except Exception:
                pass

        # 2) Plain "addr=value" format
        if value is None and "=" in text:
            left, right = text.split("=", 1)
            if left.isdigit():
                try:
                    address = int(left)
                    value = int(right)
                except Exception:
                    pass

        # 3) Only number (value) format
        if value is None and text.isdigit():
            try:
                value = int(text)
                # Extract address from topic if available
                if address is None and numeric_parts:
                    try:
                        address = int(max(numeric_parts, key=lambda x: len(x)))
                    except Exception:
                        pass
            except Exception:
                pass

        # 4) Attributes in ParsedTopic (if implemented)
        for attr in ("register", "register_address", "address"):
            if address is None and hasattr(pt, attr):
                try:
                    candidate = int(getattr(pt, attr))
                    address = candidate
                except Exception:
                    pass

        if address is None or value is None:
            return None, None
        return address, value
