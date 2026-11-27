from src.strategy.funding_arbitrage import (
    evaluate_opportunity,
    FundingOpportunity,
)


class FundingScanner:
    """Descubre y ordena oportunidades de funding por rentabilidad neta."""

    def __init__(self, futures_client, *, min_annual_pct=8.0,
                 entry_cost=0.0004, exit_cost=0.0004, hold_days=30.0):
        self.client = futures_client
        self.min_annual_pct = min_annual_pct
        self.entry_cost = entry_cost
        self.exit_cost = exit_cost
        self.hold_days = hold_days

    def scan(self, symbols) -> list:
        """Devuelve oportunidades ordenadas de mayor a menor retorno neto."""
        opportunities = []
        for symbol in symbols:
            try:
                data = self.client.mark_price(symbol)
            except Exception:
                continue
            opp = evaluate_opportunity(
                symbol, data,
                min_annual_pct=self.min_annual_pct,
                entry_cost=self.entry_cost,
                exit_cost=self.exit_cost,
                hold_days=self.hold_days,
            )
            if opp is not None:
                opportunities.append(opp)
        opportunities.sort(key=lambda o: o.annual_net_pct, reverse=True)
        return opportunities

    def best(self, symbols) -> FundingOpportunity | None:
        opportunities = self.scan(symbols)
        return opportunities[0] if opportunities else None
