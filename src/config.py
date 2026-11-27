import os
from dotenv import load_dotenv

load_dotenv()

BINANCE_API_KEY = os.getenv("BINANCE_API_KEY", "")
BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET", "")
USE_TESTNET = os.getenv("USE_TESTNET", "true").lower() == "true"
DRY_RUN = os.getenv("DRY_RUN", "false").lower() == "true"

BINANCE_BASE_URL = "https://testnet.binance.vision" if USE_TESTNET else "https://api.binance.com"
BINANCE_WS_URL = "wss://testnet.binance.vision/ws" if USE_TESTNET else "wss://stream.binance.com:9443/ws"

BINANCE_FUTURES_BASE_URL = (
    "https://testnet.binancefuture.com" if USE_TESTNET else "https://fapi.binance.com"
)

FUNDING_ENABLED = os.getenv("FUNDING_ENABLED", "false").lower() == "true"
FUNDING_MIN_ANNUAL_PCT = float(os.getenv("FUNDING_MIN_ANNUAL_PCT", "8.0"))
FUNDING_POLL_SECONDS = float(os.getenv("FUNDING_POLL_SECONDS", "300"))
FUNDING_NOTIONAL_USDT = float(os.getenv("FUNDING_NOTIONAL_USDT", "100"))
FUNDING_LEVERAGE = int(os.getenv("FUNDING_LEVERAGE", "1"))
FUNDING_EXIT_IF_NEGATIVE = os.getenv("FUNDING_EXIT_IF_NEGATIVE", "true").lower() == "true"
FUNDING_SYMBOLS = [
    s.strip() for s in os.getenv("FUNDING_SYMBOLS", "BTCUSDT,ETHUSDT,SOLUSDT").split(",")
    if s.strip()
]
FUNDING_HISTORY_BASE_URL = os.getenv(
    "FUNDING_HISTORY_BASE_URL", "https://fapi.binance.com"
)
FUNDING_MIN_INTERVALS = int(os.getenv("FUNDING_MIN_INTERVALS", "3"))
FUNDING_MAX_ZSCORE = float(os.getenv("FUNDING_MAX_ZSCORE", "2.5"))
FUNDING_MAX_BASIS_PCT = float(os.getenv("FUNDING_MAX_BASIS_PCT", "0.5"))
FUNDING_HISTORY_WINDOW = int(os.getenv("FUNDING_HISTORY_WINDOW", "30"))
FUNDING_EVENT_BLACKOUT_MINUTES = int(os.getenv("FUNDING_EVENT_BLACKOUT_MINUTES", "120"))
FUNDING_LIQUIDATION_PRESSURE_ENABLED = os.getenv(
    "FUNDING_LIQUIDATION_PRESSURE_ENABLED", "true"
).lower() == "true"
FUNDING_MAX_LIQUIDATION_PRESSURE = float(
    os.getenv("FUNDING_MAX_LIQUIDATION_PRESSURE", "0.85")
)
FUNDING_LIQUIDATION_TARGET_RATE = float(
    os.getenv("FUNDING_LIQUIDATION_TARGET_RATE", "0.00005")
)
FUNDING_MIN_HOLD_DAYS = float(os.getenv("FUNDING_MIN_HOLD_DAYS", "7"))
FUNDING_MAKER_TIMEOUT_SECONDS = int(os.getenv("FUNDING_MAKER_TIMEOUT_SECONDS", "20"))
FUNDING_MAKER_FEE = float(os.getenv("FUNDING_MAKER_FEE", "0.0002"))
FUNDING_TAKER_FEE = float(os.getenv("FUNDING_TAKER_FEE", "0.0004"))
FUNDING_USE_MAKER = os.getenv("FUNDING_USE_MAKER", "true").lower() == "true"
FUNDING_MAKER_PRICE_OFFSET = float(os.getenv("FUNDING_MAKER_PRICE_OFFSET", "0.0001"))
FUNDING_MIN_FALLBACK_ANNUAL_PCT = float(
    os.getenv("FUNDING_MIN_FALLBACK_ANNUAL_PCT", "15.0")
)
FUNDING_USE_PERSISTENCE = os.getenv("FUNDING_USE_PERSISTENCE", "true").lower() == "true"
FUNDING_MIN_PERSISTENCE_PROB = float(
    os.getenv("FUNDING_MIN_PERSISTENCE_PROB", "0.6")
)
FUNDING_PERSISTENCE_MIN_SAMPLES = int(
    os.getenv("FUNDING_PERSISTENCE_MIN_SAMPLES", "20")
)
FUNDING_PERSISTENCE_TARGET_RATE = float(
    os.getenv("FUNDING_PERSISTENCE_TARGET_RATE", "0.00005")
)

DEFAULT_SYMBOLS = ["BTCUSDT"]
INTERVAL = "1h"
LOOKBACK_LIMIT = 500

TRADE_QUANTITY = 0.001
STOP_LOSS_PCT = 0.02
TAKE_PROFIT_PCT = 0.03
MAX_POSITION_SIZE = 0.01

MA_FAST_PERIOD = 9
MA_SLOW_PERIOD = 21
ML_CONFIDENCE_THRESHOLD = 0.55
BALANCE_ALLOCATION_PCT = 100

MODEL_PATH = "src/models/trained_model.pkl"
