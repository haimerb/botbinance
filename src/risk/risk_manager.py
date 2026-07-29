class RiskManager:
    def __init__(self, stop_loss_pct=0.02, take_profit_pct=0.03, max_position_size=0.01):
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct
        self.max_position_size = max_position_size
        self.position = None
        self.entry_price = 0.0

    def open_position(self, price: float, quantity: float):
        if quantity > self.max_position_size:
            print(f"Cantidad {quantity} excede el tamaño máximo {self.max_position_size}")
            return False
        self.position = {"side": "BUY", "entry": price, "qty": quantity}
        self.entry_price = price
        print(f"Posición abierta: BUY {quantity} @ {price}")
        return True

    def close_position(self):
        self.position = None
        self.entry_price = 0.0
        print("Posición cerrada.")

    def check_stop_loss(self, current_price: float) -> bool:
        if self.position is None:
            return False
        loss_pct = (self.entry_price - current_price) / self.entry_price
        if loss_pct >= self.stop_loss_pct:
            print(f"Stop-Loss activado. Pérdida: {loss_pct:.2%}")
            return True
        return False

    def check_take_profit(self, current_price: float) -> bool:
        if self.position is None:
            return False
        gain_pct = (current_price - self.entry_price) / self.entry_price
        if gain_pct >= self.take_profit_pct:
            print(f"Take-Profit activado. Ganancia: {gain_pct:.2%}")
            return True
        return False

    def set_dynamic_levels(self, stop_loss_pct: float, take_profit_pct: float):
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct

    def has_position(self) -> bool:
        return self.position is not None
