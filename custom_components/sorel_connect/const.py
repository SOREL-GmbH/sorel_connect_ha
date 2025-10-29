DOMAIN = "sorel_connect"

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

# --- Relay Modes --------------------------------------------------------------

# Relay modes are only used for display purposes in the UI.
# By now all Relay values are calculated to display percentages (0-100%).
RELAY_MODES = {
    0: "switched",        # on/off (for older devices, previous SDK2)
    1: "phase control",   # phase angle speed control (for older devices, previous SDK2)
    2: "pwm",             # PWM control (for older devices, previous SDK2)
    3: "voltage control", # voltage control (for older devices, previous SDK2)
    4: "direct pwm",      # direct PWM (for older devices, previous SDK2)
    5: "direct voltage",  # direct voltage (for older devices, previous SDK2)

    6: "switched",               # simple on/off control
    7: "switched cycle",         # percent-based on/off cycle control
    8: "phase control",          # phase angle speed control
    9: "pwm control",            # PWM control
    10: "voltage control",       # voltage control
    11: "voltage straight",      # direct voltage, no PWM min/max checks
    12: "pwm straight",          # direct PWM, no PWM min/max checks

    13: "n modes",               # total number of valid relay modes
    14: "internal",              # internal index (e.g., display PWM)
    15: "error",                 # mutex failure or internal error
    16: "invalid",               # relay not in list / invalid mode
}

# --- Sensor Types -------------------------------------------------------------
SENSOR_TYPES = {
    1:  {"type_name": "sensorContact",           "base_unit": None,   "device_class": None,           "temp_dependent": False},
    2:  {"type_name": "sensorTemperature",       "base_unit": "°C",   "device_class": "temperature",  "temp_dependent": True},
    3:  {"type_name": "sensorHumidity",          "base_unit": "%",    "device_class": "humidity",     "temp_dependent": False},
    4:  {"type_name": "sensorBrightness",        "base_unit": "lux",  "device_class": "illuminance",  "temp_dependent": False},
    5:  {"type_name": "sensorGlobalRadiation",   "base_unit": "W/m²", "device_class": "irradiance",   "temp_dependent": False},
    6:  {"type_name": "sensorMotion",            "base_unit": None,   "device_class": None,           "temp_dependent": False},
    7:  {"type_name": "sensorPresence",          "base_unit": None,   "device_class": None,           "temp_dependent": False},
    8:  {"type_name": "targetTemperatureAir",    "base_unit": "°C",   "device_class": "temperature",  "temp_dependent": True},
    9:  {"type_name": "switchBinaryGeneric",     "base_unit": None,   "device_class": None,           "temp_dependent": False},
    10: {"type_name": "switchPower",             "base_unit": "W",    "device_class": "power",        "temp_dependent": False},
    11: {"type_name": "switchMultilevelGeneric", "base_unit": None,   "device_class": None,           "temp_dependent": False},
    12: {"type_name": "switchMultilevelPower",   "base_unit": "W",    "device_class": "power",        "temp_dependent": False},
    13: {"type_name": "outputPwm",               "base_unit": "%",    "device_class": None,           "temp_dependent": False},
    14: {"type_name": "outputDacPwm",            "base_unit": "%",    "device_class": None,           "temp_dependent": False},
    15: {"type_name": "outputDac",               "base_unit": None,   "device_class": None,           "temp_dependent": False},
    16: {"type_name": "thermostatHeatingMode",   "base_unit": None,   "device_class": None,           "temp_dependent": False},
    17: {"type_name": "roomLocation",            "base_unit": None,   "device_class": None,           "temp_dependent": False},
    18: {"type_name": "CO2Concentration",        "base_unit": "ppm",  "device_class": None,           "temp_dependent": False},
    19: {"type_name": "AirPressure",             "base_unit": "hPa",  "device_class": "pressure",     "temp_dependent": False},
    20: {"type_name": "IndoorAirQuality",        "base_unit": None,   "device_class": None,           "temp_dependent": False},
    21: {"type_name": "targetTemperatureCLite",  "base_unit": "°C",   "device_class": "temperature",  "temp_dependent": True},
    22: {"type_name": "wheel",                   "base_unit": None,   "device_class": None,           "temp_dependent": False},
    23: {"type_name": "sensorFlow",              "base_unit": "L/min","device_class": None,           "temp_dependent": False},
    24: {"type_name": "sensorFrequency",         "base_unit": "Hz",   "device_class": "frequency",    "temp_dependent": False},
    25: {"type_name": "sensorDuty",              "base_unit": "%",    "device_class": None,           "temp_dependent": False},
    26: {"type_name": "sensorPulse (flow)",      "base_unit": "L",    "device_class": None,           "temp_dependent": False},
    27: {"type_name": "sensorPressure",          "base_unit": "bar",  "device_class": "pressure",     "temp_dependent": False},
}
