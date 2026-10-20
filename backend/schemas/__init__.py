from pydantic import BaseModel, field_validator, model_validator


class RegisterRequest(BaseModel):
    email: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str
    mfa_code: str | None = None


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class BinanceKeysRequest(BaseModel):
    api_key: str
    api_secret: str


class MFASetupRequest(BaseModel):
    pass


class MFAVerifyRequest(BaseModel):
    code: str


class MFADisableRequest(BaseModel):
    password: str


class UserConfigUpdate(BaseModel):
    symbols: list[str] | None = None
    interval: str | None = None
    trade_quantity: float | None = None
    stop_loss_pct: float | None = None
    take_profit_pct: float | None = None
    max_position_size: float | None = None
    ma_fast_period: int | None = None
    ma_slow_period: int | None = None
    ml_confidence_threshold: float | None = None
    balance_allocation_pct: float | None = None
    ai_stop_loss_enabled: bool | None = None
    ai_optimize_enabled: bool | None = None
    trailing_stop_pct: float | None = None
    trailing_activation_pct: float | None = None
    time_exit_hours: int | None = None
    partial_tp1_pct: float | None = None
    partial_tp1_qty: float | None = None
    partial_tp2_pct: float | None = None
    partial_tp2_qty: float | None = None
    partial_tp3_pct: float | None = None
    partial_tp3_qty: float | None = None
    enable_trailing: bool | None = None
    enable_time_exit: bool | None = None
    enable_partial_tp: bool | None = None
    max_daily_loss_pct: float | None = None
    max_total_loss_pct: float | None = None
    sentiment_enabled: bool | None = None
    portfolio_allocation_mode: str | None = None

    @field_validator("portfolio_allocation_mode")
    @classmethod
    def validate_allocation_mode(cls, v):
        allowed = ["equal", "volatility", "confidence", "inverse_vol"]
        if v and v not in allowed:
            raise ValueError(f"Modo de asignación debe ser uno de: {allowed}")
        return v

    @field_validator("interval")
    @classmethod
    def validate_interval(cls, v):
        allowed = ["15m", "30m", "1h", "4h", "1d"]
        if v and v not in allowed:
            raise ValueError(f"Intervalo debe ser uno de: {allowed}")
        return v

    @field_validator("trade_quantity")
    @classmethod
    def validate_trade_quantity(cls, v):
        if v is not None and (v <= 0 or v > 100):
            raise ValueError("Cantidad por trade debe ser > 0 y <= 100")
        return v

    @field_validator("stop_loss_pct")
    @classmethod
    def validate_stop_loss(cls, v):
        if v is not None and (v <= 0 or v > 0.5):
            raise ValueError("Stop loss debe ser > 0% y <= 50%")
        return v

    @field_validator("take_profit_pct")
    @classmethod
    def validate_take_profit(cls, v):
        if v is not None and (v <= 0 or v > 1.0):
            raise ValueError("Take profit debe ser > 0% y <= 100%")
        return v

    @field_validator("max_position_size")
    @classmethod
    def validate_max_position(cls, v):
        if v is not None and (v <= 0 or v > 1.0):
            raise ValueError("Tamaño máx. posición debe ser > 0 y <= 100%")
        return v

    @field_validator("ma_fast_period", "ma_slow_period")
    @classmethod
    def validate_ma_periods(cls, v):
        if v is not None and (v < 2 or v > 500):
            raise ValueError("Período MA debe ser >= 2 y <= 500")
        return v

    @field_validator("ml_confidence_threshold")
    @classmethod
    def validate_ml_confidence(cls, v):
        if v is not None and (v < 0.01 or v > 0.99):
            raise ValueError("Confianza ML debe ser entre 1% y 99%")
        return v

    @field_validator("balance_allocation_pct")
    @classmethod
    def validate_balance_allocation(cls, v):
        if v is not None and (v < 1 or v > 100):
            raise ValueError("Balance asignado debe ser entre 1% y 100%")
        return v

    @field_validator("trailing_stop_pct", "trailing_activation_pct")
    @classmethod
    def validate_trailing(cls, v):
        if v is not None and (v <= 0 or v > 0.5):
            raise ValueError("Trailing debe ser > 0% y <= 50%")
        return v

    @field_validator("time_exit_hours")
    @classmethod
    def validate_time_exit(cls, v):
        if v is not None and (v < 0 or v > 168):
            raise ValueError("Time exit debe ser entre 0 y 168 horas")
        return v

    @field_validator("partial_tp1_pct", "partial_tp2_pct", "partial_tp3_pct")
    @classmethod
    def validate_partial_tp_pct(cls, v):
        if v is not None and (v <= 0 or v > 1.0):
            raise ValueError("Partial TP % debe ser > 0% y <= 100%")
        return v

    @field_validator("partial_tp1_qty", "partial_tp2_qty", "partial_tp3_qty")
    @classmethod
    def validate_partial_tp_qty(cls, v):
        if v is not None and (v <= 0 or v > 1.0):
            raise ValueError("Partial TP qty debe ser > 0% y <= 100%")
        return v

    @field_validator("max_daily_loss_pct", "max_total_loss_pct")
    @classmethod
    def validate_circuit_breaker(cls, v):
        if v is not None and (v < 0.1 or v > 50.0):
            raise ValueError("Límite de pérdida debe ser entre 0.1% y 50%")
        return v

    @model_validator(mode="after")
    def validate_ma_order(self):
        if self.ma_fast_period and self.ma_slow_period:
            if self.ma_fast_period >= self.ma_slow_period:
                raise ValueError("MA rápido debe ser menor que MA lento")
        return self
