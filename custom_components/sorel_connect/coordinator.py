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
        address, value = self._extract_register(payload, pt)
        if address is not None and value is not None:
            _LOGGER.debug("Extracted register from topic %s: address=%s, value=%s", topic, address, value)
            self.update_register(pt.device_key, address, value)
        else:
            _LOGGER.debug("Failed to extract register from topic %s, payload=%s", topic, payload.decode('utf-8', errors='ignore')[:100])

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
        _LOGGER.debug("Register updated for device %s: address=%s, value=%s (0x%04X)", device_key, address, value, value & 0xFFFF)

        # Check datapoints linearly (optimization possible later)
        datapoints = self._datapoints.get(device_key, [])
        _LOGGER.debug("Checking %d datapoints for device %s against register address %s", len(datapoints), device_key, address)
        for dp in datapoints:
            start = int(dp.get("address", -1))
            if start < 0:
                continue
            length_bytes = int(dp.get("length", 0))
            if length_bytes <= 0:
                continue
            reg_needed = (length_bytes + 1) // 2
            if not (start <= address < start + reg_needed):
                continue
            # Address matches this datapoint's range
            _LOGGER.debug("Address %s matches datapoint '%s' (start=%s, registers=%s, bytes=%s, type=%s)",
                         address, dp.get("name", "?"), start, reg_needed, length_bytes, dp.get("type", "?"))
            decoded = self._try_decode_dp(device_key, dp, start, reg_needed, length_bytes)
            if decoded is not None:
                prev = self._dp_value_cache[device_key].get(start)
                if decoded != prev:
                    self._dp_value_cache[device_key][start] = decoded
                    _LOGGER.debug("Dispatching SIGNAL_DP_UPDATE for device=%s, address=%s, value=%s (prev=%s)",
                                 device_key, start, decoded, prev)
                    async_dispatcher_send(
                        self.hass,
                        SIGNAL_DP_UPDATE,
                        device_key,
                        start,
                        decoded
                    )
                else:
                    _LOGGER.debug("DP '%s' value unchanged (%s), skipping signal dispatch", dp.get("name", "?"), decoded)

    def _try_decode_dp(self, device_key: str, dp: dict, start: int, reg_count: int, length_bytes: int):
        regs = self._registers.get(device_key, {})
        words: list[int] = []
        now = time.time()
        for off in range(reg_count):
            a = start + off
            item = regs.get(a)
            if item is None:
                _LOGGER.debug("Cannot decode DP '%s': missing register at address %s (need %s registers starting at %s)",
                             dp.get("name", "?"), a, reg_count, start)
                return None
            val, ts = item
            if now - ts > STALE_REGISTER_MAX_AGE:
                _LOGGER.debug("Cannot decode DP '%s': register at address %s is stale (%.1fs old, max %s)",
                             dp.get("name", "?"), a, now - ts, STALE_REGISTER_MAX_AGE)
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
                decoded_bool = bool(raw_bytes[0] & 0x01)
                _LOGGER.debug("Successfully decoded DP '%s' (type=%s): value=%s", dp.get("name", "?"), dtype, decoded_bool)
                return decoded_bool
            elif dtype.startswith("str") or dtype.startswith("char"):
                decoded_str = raw_bytes.decode("utf-8", errors="ignore").rstrip("\x00")
                _LOGGER.debug("Successfully decoded DP '%s' (type=%s): value='%s'", dp.get("name", "?"), dtype, decoded_str)
                return decoded_str

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
                                formatted_value = fmt[value_str]
                                _LOGGER.debug("Successfully decoded DP '%s' (type=%s): raw=%s, formatted='%s'",
                                             dp.get("name", "?"), dtype, value, formatted_value)
                                return formatted_value # return formatted string
                            else:
                                _LOGGER.warning(f"Value '{value_str}' not found in format mapping for DP '{dp.get('name')}'. Available keys: {list(fmt.keys())}. Returning raw value.")
                        else:
                            _LOGGER.warning(f"Format mapping for DP '{dp.get('name')}' is not a dictionary. Returning raw value.")
                    except Exception:
                        _LOGGER.warning(f"Error applying format: '{dp.get('format')}' for value: '{value}' of DP '{dp.get('name')}'. Returning raw value.")

                # if value < dp.get("minValue") or value > dp.get("maxValue"):
                #     return None

                _LOGGER.debug("Successfully decoded DP '%s' (type=%s): value=%s", dp.get("name", "?"), dtype, value)
                return value

            # Fallback to hex representation
            _LOGGER.warning(f"Unknown data type: {dtype}, raw bytes: {raw_bytes.hex()}")
            return raw_bytes.hex()

        except Exception as e:
            _LOGGER.warning("Decoding failed for DP '%s' (type=%s): %s", dp.get("name", "?"), dtype, e)
            return None

    # --- Helper Functions -----------------------------------------------------

    def _extract_register(self, payload: bytes, pt: ParsedTopic):
        """
        Extracts register address and value from topic and payload.
        Address comes from ParsedTopic.address (topic segment 8).
        Value is numeric, either in JSON {"value": X} or plain text.
        """
        # 1. Get address from parsed topic (segment 8)
        address = None
        try:
            address = int(pt.address)
        except (ValueError, AttributeError) as e:
            _LOGGER.debug("Failed to extract address from ParsedTopic.address='%s': %s", getattr(pt, 'address', None), e)
            return None, None

        # 2. Parse value from payload
        value = None
        try:
            text = payload.decode("utf-8", errors="ignore").strip()

            # Try JSON format: {"value": 123}
            if text.startswith("{"):
                try:
                    obj = json.loads(text)
                    if isinstance(obj, dict) and "value" in obj:
                        value = int(obj["value"])
                except (json.JSONDecodeError, ValueError, KeyError):
                    pass

            # Try plain numeric
            if value is None:
                try:
                    value = int(text)
                except ValueError:
                    pass

        except Exception as e:
            _LOGGER.debug("Failed to parse value from payload: %s", e)

        if value is None:
            _LOGGER.debug("Could not extract numeric value from payload: %s", payload.decode('utf-8', errors='ignore')[:100])
            return None, None

        return address, value
