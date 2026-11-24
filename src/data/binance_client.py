import pandas as pd
from binance.spot import Spot
from binance.error import ClientError, ServerError
from src.config import BINANCE_API_KEY, BINANCE_API_SECRET, BINANCE_BASE_URL


# La API de Binance entrega como máximo 1000 klines por request
KLINE_API_MAX_LIMIT = 1000

KLINE_COLUMNS = [
    "timestamp", "open", "high", "low", "close", "volume",
    "close_time", "quote_asset_volume", "number_of_trades",
    "taker_buy_base_vol", "taker_buy_quote_vol", "ignore",
]


class BinanceDataClient:
    def __init__(self, api_key: str = None, api_secret: str = None):
        key = api_key if api_key is not None else BINANCE_API_KEY
        secret = api_secret if api_secret is not None else BINANCE_API_SECRET
        self.client = Spot(api_key=key, api_secret=secret, base_url=BINANCE_BASE_URL)

    def fetch_klines(
        self, symbol: str, interval: str, limit: int = 500,
        use_real_api: bool = False
    ) -> pd.DataFrame:
        """Descarga las ``limit`` velas más recientes, paginando hacia atrás.

        La API entrega como máximo ``KLINE_API_MAX_LIMIT`` velas por request;
        para límites mayores se encadenan llamadas con ``endTime`` hasta
        completar (o hasta el inicio del historial). Para ``limit <= 1000``
        es una única llamada, igual que antes.
        """
        try:
            if use_real_api:
                client = Spot(base_url="https://api.binance.com")
            else:
                client = self.client

            collected = []
            end_time = None
            remaining = max(0, int(limit))
            while remaining > 0:
                chunk_size = min(KLINE_API_MAX_LIMIT, remaining)
                batch = client.klines(
                    symbol=symbol, interval=interval,
                    limit=chunk_size, endTime=end_time,
                )
                if not batch:
                    break
                # cada batch con endTime trae velas más viejas que lo acumulado
                collected = batch + collected
                remaining -= len(batch)
                if len(batch) < chunk_size:
                    break  # inicio del historial alcanzado
                end_time = int(batch[0][0]) - 1

            if not collected:
                return pd.DataFrame()
            df = pd.DataFrame(collected, columns=KLINE_COLUMNS)
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
            for col in ["open", "high", "low", "close", "volume"]:
                df[col] = df[col].astype(float)
            df = (df.drop_duplicates(subset="timestamp")
                    .sort_values("timestamp")
                    .reset_index(drop=True))
            return df[["timestamp", "open", "high", "low", "close", "volume"]].head(int(limit))
        except (ClientError, ServerError) as e:
            print(f"Error fetching data: {e}")
            return pd.DataFrame()

    def get_account_info(self):
        try:
            return self.client.account()
        except (ClientError, ServerError) as e:
            print(f"Error getting account info: {e}")
            return {}
