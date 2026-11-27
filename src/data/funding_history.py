class FundingHistoryClient:
    """Descarga históricos alineados de funding, basis y open interest.

    Binance devuelve las filas en orden ascendente y limita cada página
    (funding 1000, klines 1000, OI 500). Este cliente pagina hacia adelante
    y elimina duplicados por timestamp.
    """

    def __init__(self, futures_client, *, funding_limit=1000,
                 kline_limit=1000, oi_limit=500):
        self.client = futures_client
        self.funding_limit = funding_limit
        self.kline_limit = kline_limit
        self.oi_limit = oi_limit

    def funding(self, symbol, start_ms=None, end_ms=None, limit=None):
        rows = []
        cursor = start_ms
        seen = set()
        page_size = self.funding_limit
        if limit is not None:
            page_size = max(1, min(page_size, limit))
        while True:
            kwargs = {"limit": page_size}
            if cursor is not None:
                kwargs["startTime"] = cursor
            if end_ms is not None:
                kwargs["endTime"] = end_ms
            batch = self.client.funding_rate(symbol, **kwargs)
            if not batch:
                break
            for item in batch:
                ts = int(item["fundingTime"])
                if ts not in seen:
                    seen.add(ts)
                    rows.append({
                        "funding_time": ts,
                        "funding_rate": float(item["fundingRate"]),
                    })
            last = max(int(item["fundingTime"]) for item in batch)
            if limit is not None and len(rows) >= limit:
                return rows[:limit]
            if len(batch) < page_size:
                break
            if end_ms is not None and last >= end_ms:
                break
            next_cursor = last + 1
            if cursor is not None and next_cursor <= cursor:
                break
            cursor = next_cursor
        rows.sort(key=lambda r: r["funding_time"])
        return rows

    def _klines(self, fetch, start_ms=None, end_ms=None):
        rows = []
        cursor = start_ms
        seen = set()
        while True:
            kwargs = {"limit": self.kline_limit}
            if cursor is not None:
                kwargs["startTime"] = cursor
            if end_ms is not None:
                kwargs["endTime"] = end_ms
            batch = fetch(**kwargs)
            if not batch:
                break
            for item in batch:
                ts = int(item[0])
                if ts not in seen:
                    seen.add(ts)
                    rows.append(item)
            last = max(int(item[0]) for item in batch)
            if len(batch) < self.kline_limit:
                break
            if end_ms is not None and last >= end_ms:
                break
            next_cursor = last + 1
            if cursor is not None and next_cursor <= cursor:
                break
            cursor = next_cursor
        rows.sort(key=lambda r: int(r[0]))
        return rows

    def mark_index(self, symbol, interval="8h", start_ms=None, end_ms=None):
        marks = self._klines(
            lambda **kw: self.client.mark_price_klines(symbol, interval, **kw),
            start_ms, end_ms,
        )
        indexes = self._klines(
            lambda **kw: self.client.index_price_klines(symbol, interval, **kw),
            start_ms, end_ms,
        )
        index_by_time = {int(row[0]): float(row[4]) for row in indexes}
        result = []
        for row in marks:
            ts = int(row[0])
            mark = float(row[4])
            index = index_by_time.get(ts)
            basis = (mark / index - 1) * 100 if index else None
            result.append({
                "open_time": ts,
                "mark_price": mark,
                "index_price": index,
                "basis_pct": basis,
            })
        return result

    def open_interest(self, symbol, period="4h", start_ms=None, end_ms=None):
        rows = []
        cursor = start_ms
        seen = set()
        while True:
            kwargs = {"limit": self.oi_limit}
            if cursor is not None:
                kwargs["startTime"] = cursor
            if end_ms is not None:
                kwargs["endTime"] = end_ms
            batch = self.client.open_interest_hist(symbol, period, **kwargs)
            if not batch:
                break
            for item in batch:
                ts = int(item["timestamp"])
                if ts not in seen:
                    seen.add(ts)
                    rows.append({
                        "open_time": ts,
                        "open_interest": float(
                            item.get("sumOpenInterest", item.get("openInterest", 0)) or 0
                        ),
                        "open_interest_value": float(
                            item.get("sumOpenInterestValue", 0) or 0
                        ),
                    })
            last = max(int(item["timestamp"]) for item in batch)
            if len(batch) < self.oi_limit:
                break
            if end_ms is not None and last >= end_ms:
                break
            next_cursor = last + 1
            if cursor is not None and next_cursor <= cursor:
                break
            cursor = next_cursor
        rows.sort(key=lambda r: r["open_time"])
        return rows

    def dataset(self, symbol, start_ms=None, end_ms=None):
        """Une las tres series por timestamp de funding."""
        funding = self.funding(symbol, start_ms, end_ms)
        basis_by_time = {
            r["open_time"]: r for r in self.mark_index(symbol, start_ms=start_ms, end_ms=end_ms)
        }
        oi_by_time = {
            r["open_time"]: r for r in self.open_interest(symbol, start_ms=start_ms, end_ms=end_ms)
        }
        result = []
        for item in funding:
            ts = item["funding_time"]
            basis = basis_by_time.get(ts, {})
            oi = oi_by_time.get(ts, {})
            result.append({
                "funding_time": ts,
                "funding_rate": item["funding_rate"],
                "mark_price": basis.get("mark_price"),
                "index_price": basis.get("index_price"),
                "basis_pct": basis.get("basis_pct"),
                "open_interest": oi.get("open_interest"),
                "open_interest_value": oi.get("open_interest_value"),
            })
        return result
