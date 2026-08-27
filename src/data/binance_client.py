import pandas as pd
from binance.client import Client
from binance.exceptions import BinanceAPIException
from src.config import BINANCE_API_KEY, BINANCE_API_SECRET, USE_TESTNET


class BinanceDataClient:
    def __init__(self, api_key: str = None, api_secret: str = None):
        key = api_key if api_key is not None else BINANCE_API_KEY
        secret = api_secret if api_secret is not None else BINANCE_API_SECRET
        self.client = Client(key, secret)
        if USE_TESTNET:
            self.client.API_URL = "https://testnet.binance.vision/api"

    def fetch_klines(
        self, symbol: str, interval: str, limit: int = 500,
        use_real_api: bool = False
    ) -> pd.DataFrame:
        try:
            if use_real_api:
                temp_client = Client()
                klines = temp_client.get_klines(
                    symbol=symbol, interval=interval, limit=limit
                )
            else:
                klines = self.client.get_klines(
                    symbol=symbol, interval=interval, limit=limit
                )
            df = pd.DataFrame(klines, columns=[
                "timestamp", "open", "high", "low", "close", "volume",
                "close_time", "quote_asset_volume", "number_of_trades",
                "taker_buy_base_vol", "taker_buy_quote_vol", "ignore"
            ])
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
            for col in ["open", "high", "low", "close", "volume"]:
                df[col] = df[col].astype(float)
            return df[["timestamp", "open", "high", "low", "close", "volume"]]
        except BinanceAPIException as e:
            print(f"Error fetching data: {e}")
            return pd.DataFrame()

    def get_account_info(self):
        try:
            return self.client.get_account()
        except BinanceAPIException as e:
            print(f"Error getting account info: {e}")
            return {}
