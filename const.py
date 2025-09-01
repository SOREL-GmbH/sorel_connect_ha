DOMAIN = "sorel_connect"

CONF_MODE = "mode"  # "supervisor" | "external"
CONF_BROKER_HOST = "broker_host"
CONF_BROKER_PORT = "broker_port"
CONF_BROKER_USERNAME = "broker_username"
CONF_BROKER_PASSWORD = "broker_password"
CONF_BROKER_TLS = "broker_tls"
CONF_TOPIC_PREFIX = "topic_prefix"  # z.B. "vendor"
CONF_META_BASEURL = "meta_baseurl"  # z.B. "https://meta.example.com"
CONF_AUTO_ONBOARD = "auto_onboard"  # bool

DEFAULT_PORT = 1883
DEFAULT_PREFIX = "vendor"
DISCOVERY_PREFIX = "homeassistant"

SIGNAL_NEW_DEVICE = f"{DOMAIN}_new_device"
