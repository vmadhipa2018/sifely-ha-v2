"""Constants for the Sifely Smart Lock integration (Open API, API key auth)."""

DOMAIN = "sifely"

API_BASE_URL = "https://cus-openapi.sifely.com"

# Endpoints confirmed against apidocs.sifely.com and tested with a live key
API_LOCK_LIST = "/v3/lock/list"              # POST, no gateway needed
API_LOCK_DETAIL = "/v3/lock/detail"          # GET, no gateway needed
API_PASSCODE_LIST = "/v3/lock/listKeyboardPwd"  # GET, no gateway needed
API_RECORD_LIST = "/v3/lockRecord/list"      # GET, no gateway needed

# Gateway-dependent (return code -2012 without a gateway)
API_LOCK_OPEN_STATE = "/v3/lock/queryOpenState"  # GET
API_LOCK_LOCK = "/v3/lock/lock"                  # POST
API_LOCK_UNLOCK = "/v3/lock/unlock"              # POST

CONF_API_KEY = "api_key"

# Error code returned when the lock is not paired to a gateway
ERR_GATEWAY_REQUIRED = -2012

# Open state values. Mapping carried over from the legacy integration;
# verify on the first gateway test.
OPEN_STATE_LOCKED = 0
OPEN_STATE_UNLOCKED = 1

# Poll intervals in seconds. Budget for 3 locks is about 3,240 calls/month,
# inside the Developer plan's 10,000 call cap.
COORDINATOR_INTERVAL = 1800   # coordinator wakes every 30 min and checks what is due
LIST_INTERVAL = 3600          # lock list: hourly
DETAIL_INTERVAL = 7200        # lock detail per lock: every 2 h
RECORD_INTERVAL = 7200        # activity records per lock: every 2 h
PASSCODE_INTERVAL = 21600     # passcode list per lock: every 6 h
STATE_INTERVAL = 1800         # open state per lock (gateway locks only): every 30 min

# Activity records: one call per poll asks for this many days, up to the
# API maximum page size, and keeps the newest entries.
RECORD_WINDOW_DAYS = 30
RECORD_PAGE_SIZE = 200

# Home Assistant event fired for each new activity record
EVENT_ACTIVITY = f"{DOMAIN}_activity"

# Allowlists. Only these fields are kept in memory. Secrets such as adminPwd,
# lockKey, aesKeyStr, noKeyPwd and keyboardPwd are dropped on purpose.
DETAIL_FIELDS = (
    "lockAlias",
    "lockName",
    "firmwareRevision",
    "hardwareRevision",
    "electricQuantity",
    "autoLockTime",
    "soundVolume",
    "passageMode",
    "hasGateway",
    "lockUpdateDate",
)

PASSCODE_FIELDS = (
    "keyboardPwdId",
    "keyboardPwdName",
    "keyboardPwdType",
    "startDate",
    "endDate",
    "status",
)

RECORD_FIELDS = (
    "recordId",
    "recordType",
    "success",
    "username",
    "lockDate",
    "serverDate",
)
