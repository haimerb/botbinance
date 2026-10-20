import pandas as pd
from binance.spot import Spot
from binance.error import ClientError, ServerError
from src.config import BINANCE_API_KEY, BINANCE_API_SECRET, BINANCE_BASE_URL


class BinanceDataClient:
    def __init__(self, api_key: str = None, api_secret: str = None):
        key = api_key if api_key is not None else BINANCE_API_KEY
        secret = api_secret if api_secret is not None else BINANCE_API_SECRET
        self.client = Spot(api_key=key, api_secret=secret, base_url=BINANCE_BASE_URL)

    def fetch_klines(
        self, symbol: str, interval: str, limit: int = 500,
        use_real_api: bool = False
    ) -> pd.DataFrame:
        try:
            if use_real_api:
                temp_client = Spot(base_url="https://api.binance.com")
                klines = temp_client.klines(symbol=symbol, interval=interval, limit=limit)
            else:
                klines = self.client.klines(symbol=symbol, interval=interval, limit=limit)
            df = pd.DataFrame(klines, columns=[
                "timestamp", "open", "high", "low", "close", "volume",
                "close_time", "quote_asset_volume", "number_of_trades",
                "taker_buy_base_vol", "taker_buy_quote_vol", "ignore"
            ])
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
            for col in ["open", "high", "low", "close", "volume"]:
                df[col] = df[col].astype(float)
            return df[["timestamp", "open", "high", "low", "close", "volume"]]
        except (ClientError, ServerError) as e:
            print(f"Error fetching data: {e}")
            return pd.DataFrame()

    def get_account_info(self):
        try:
            return self.client.account()
        except (ClientError, ServerError) as e:
            print(f"Error getting account info: {e}")
            return {}
