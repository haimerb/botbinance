import argparse

from src.models.trainer import train_model
from src.config import DEFAULT_SYMBOLS, INTERVAL


def main(argv=None):
    parser = argparse.ArgumentParser(description="Entrenar modelo ML para binance bot")
    parser.add_argument("--symbols", nargs="+", default=DEFAULT_SYMBOLS,
                        help="Símbolos para entrenar (ej: BTCUSDT ETHUSDT)")
    parser.add_argument("--interval", default=INTERVAL,
                        help="Intervalo de velas (ej: 1h, 4h, 1d)")
    parser.add_argument("--limit", type=int, default=5000,
                        help="Límite de velas por símbolo")
    args = parser.parse_args(argv)
    train_model(symbols=args.symbols, interval=args.interval, limit=args.limit)


if __name__ == "__main__":
    main()
