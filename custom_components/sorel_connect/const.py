DOMAIN = "sorel_connect"

CONF_MODE = "mode"  # "supervisor" | "external"
CONF_BROKER_HOST = "broker_host"
CONF_BROKER_PORT = "broker_port"
CONF_BROKER_USERNAME = "broker_username"
CONF_BROKER_PASSWORD = "broker_password"
CONF_BROKER_TLS = "broker_tls"
CONF_API_SERVER = "api_server"  # e.g. "connect.sorel.de"
CONF_API_URL = "api_url"  # e.g. "/api/public/{organizationId}/device/{deviceEnumId}/metadata?language=en"

DEFAULT_PORT = 1883
DEFAULT_API_SERVER = "connect.sorel.de"
DEFAULT_API_URL = "/api/public/{organizationId}/device/{deviceEnumId}/metadata?language=en"

SIGNAL_NEW_DEVICE = f"{DOMAIN}_new_device"
SIGNAL_DP_UPDATE = "sorel_dp_update"
SIGNAL_MQTT_CONNECTION_STATE = f"{DOMAIN}_mqtt_connection_state"
