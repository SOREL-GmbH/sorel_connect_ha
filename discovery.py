import hashlib

def object_id(domain: str, client_id: str, capability: str) -> str:
    base = f"{client_id}_{capability}_{domain}"
    return hashlib.sha1(base.encode()).hexdigest()[:12]

def build_light_config(discovery_prefix, client_id, name, state_topic, cmd_topic, availability_topic):
    obj_id = object_id("light", client_id, name)
    return (
        f"{discovery_prefix}/light/{client_id}_{obj_id}/config",
        {
            "name": name,
            "unique_id": f"{client_id}-{obj_id}",
            "state_topic": state_topic,
            "command_topic": cmd_topic,
            "availability": [{"topic": availability_topic}],
            "payload_on": "ON",
            "payload_off": "OFF",
            "qos": 0,
            "retain": True
        }
    )

# Analog: switch/sensor/number/select/climate etc., je nach Metadaten
