import os
from contextlib import contextmanager
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, Float, String, Text, DateTime, ForeignKey, func, text
from sqlalchemy.orm import declarative_base, sessionmaker

from backend.crypto import encrypt_value, decrypt_value

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://bot:bot123@localhost:5432/binance_bot"
)

engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(Text, nullable=False)
    binance_api_key = Column(Text, default="")
    binance_api_secret = Column(Text, default="")
    mfa_secret = Column(Text, default="")
    mfa_enabled = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class UserConfig(Base):
    __tablename__ = "user_configs"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)
    symbols = Column(Text, default='["BTCUSDT"]')
    interval = Column(String(10), default="1h")
    trade_quantity = Column(Float, default=0.001)
    stop_loss_pct = Column(Float, default=0.02)
    take_profit_pct = Column(Float, default=0.03)
    max_position_size = Column(Float, default=0.01)
    ma_fast_period = Column(Integer, default=9)
    ma_slow_period = Column(Integer, default=21)
    ml_confidence_threshold = Column(Float, default=0.55)
    balance_allocation_pct = Column(Float, default=100.0)
    ai_stop_loss_enabled = Column(Integer, default=0)
    ai_optimize_enabled = Column(Integer, default=0)
    trailing_stop_pct = Column(Float, default=0.01)
    trailing_activation_pct = Column(Float, default=0.015)
    time_exit_hours = Column(Integer, default=24)
    partial_tp1_pct = Column(Float, default=0.015)
    partial_tp1_qty = Column(Float, default=0.3)
    partial_tp2_pct = Column(Float, default=0.03)
    partial_tp2_qty = Column(Float, default=0.3)
    partial_tp3_pct = Column(Float, default=0.05)
    partial_tp3_qty = Column(Float, default=0.4)
    enable_trailing = Column(Integer, default=1)
    enable_time_exit = Column(Integer, default=1)
    enable_partial_tp = Column(Integer, default=1)
    max_daily_loss_pct = Column(Float, default=5.0)
    max_total_loss_pct = Column(Float, default=10.0)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class Trade(Base):
    __tablename__ = "trades"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    symbol = Column(String(20), default="BTCUSDT")
    side = Column(String(10), nullable=False)
    price = Column(Float, nullable=False)
    qty = Column(Float, nullable=False)
    trade_type = Column(String(20), nullable=False)
    pnl_pct = Column(Float, nullable=True)
    timestamp = Column(DateTime, default=datetime.now)


class BotState(Base):
    __tablename__ = "bot_state"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    key = Column(String(100), nullable=False)
    value = Column(Text, default="")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class ErrorLog(Base):
    __tablename__ = "error_logs"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    message = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.now)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    event_type = Column(String(50), nullable=False)
    event_data = Column(Text, default="")
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=datetime.now, index=True)


def init_db():
    Base.metadata.create_all(engine)
    with get_session() as session:
        for stmt in [
            "ALTER TABLE trades ADD COLUMN IF NOT EXISTS symbol VARCHAR(20) DEFAULT 'BTCUSDT'",
            "ALTER TABLE user_configs ADD COLUMN IF NOT EXISTS balance_allocation_pct FLOAT DEFAULT 100.0",
            "ALTER TABLE user_configs ADD COLUMN IF NOT EXISTS ai_stop_loss_enabled INTEGER DEFAULT 0",
            "ALTER TABLE user_configs ADD COLUMN IF NOT EXISTS ai_optimize_enabled INTEGER DEFAULT 0",
            "ALTER TABLE user_configs ADD COLUMN IF NOT EXISTS trailing_stop_pct FLOAT DEFAULT 0.01",
            "ALTER TABLE user_configs ADD COLUMN IF NOT EXISTS trailing_activation_pct FLOAT DEFAULT 0.015",
            "ALTER TABLE user_configs ADD COLUMN IF NOT EXISTS time_exit_hours INTEGER DEFAULT 24",
            "ALTER TABLE user_configs ADD COLUMN IF NOT EXISTS partial_tp1_pct FLOAT DEFAULT 0.015",
            "ALTER TABLE user_configs ADD COLUMN IF NOT EXISTS partial_tp1_qty FLOAT DEFAULT 0.3",
            "ALTER TABLE user_configs ADD COLUMN IF NOT EXISTS partial_tp2_pct FLOAT DEFAULT 0.03",
            "ALTER TABLE user_configs ADD COLUMN IF NOT EXISTS partial_tp2_qty FLOAT DEFAULT 0.3",
            "ALTER TABLE user_configs ADD COLUMN IF NOT EXISTS partial_tp3_pct FLOAT DEFAULT 0.05",
            "ALTER TABLE user_configs ADD COLUMN IF NOT EXISTS partial_tp3_qty FLOAT DEFAULT 0.4",
            "ALTER TABLE user_configs ADD COLUMN IF NOT EXISTS enable_trailing INTEGER DEFAULT 1",
            "ALTER TABLE user_configs ADD COLUMN IF NOT EXISTS enable_time_exit INTEGER DEFAULT 1",
            "ALTER TABLE user_configs ADD COLUMN IF NOT EXISTS enable_partial_tp INTEGER DEFAULT 1",
            "ALTER TABLE user_configs ADD COLUMN IF NOT EXISTS max_daily_loss_pct FLOAT DEFAULT 5.0",
            "ALTER TABLE user_configs ADD COLUMN IF NOT EXISTS max_total_loss_pct FLOAT DEFAULT 10.0",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS mfa_secret TEXT DEFAULT ''",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS mfa_enabled INTEGER DEFAULT 0",
        ]:
            try:
                session.execute(text(stmt))
            except Exception:
                session.rollback()


@contextmanager
def get_session():
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_session_simple():
    return SessionLocal()


def add_user(email: str, password_hash: str) -> User:
    session = get_session_simple()
    user = User(email=email, password_hash=password_hash)
    session.add(user)
    session.commit()
    session.refresh(user)
    session.close()
    return user


def get_user_by_email(email: str):
    session = get_session_simple()
    user = session.query(User).filter(User.email == email).first()
    session.close()
    return user


def get_user_by_id(user_id: int):
    session = get_session_simple()
    user = session.query(User).filter(User.id == user_id).first()
    session.close()
    return user


def get_user_by_id_with_keys(user_id: int):
    user = get_user_by_id(user_id)
    if user:
        user.binance_api_key = decrypt_value(user.binance_api_key)
        user.binance_api_secret = decrypt_value(user.binance_api_secret)
    return user


def update_binance_keys(user_id: int, api_key: str, api_secret: str):
    with get_session() as session:
        session.query(User).filter(User.id == user_id).update({
            "binance_api_key": encrypt_value(api_key),
            "binance_api_secret": encrypt_value(api_secret),
            "updated_at": datetime.now(),
        })


def get_or_create_user_config(user_id: int):
    session = get_session_simple()
    cfg = session.query(UserConfig).filter(UserConfig.user_id == user_id).first()
    if not cfg:
        cfg = UserConfig(user_id=user_id)
        session.add(cfg)
        session.commit()
        session.refresh(cfg)
    session.close()
    return cfg


def update_user_config(user_id: int, **kwargs):
    with get_session() as session:
        cfg = session.query(UserConfig).filter(UserConfig.user_id == user_id).first()
        if not cfg:
            cfg = UserConfig(user_id=user_id)
            session.add(cfg)
        for k, v in kwargs.items():
            if hasattr(cfg, k):
                setattr(cfg, k, v)
        cfg.updated_at = datetime.now()


def add_trade(user_id: int, side: str, price: float, qty: float, trade_type: str,
              pnl_pct: float = None, symbol: str = "BTCUSDT") -> int:
    with get_session() as session:
        trade = Trade(user_id=user_id, symbol=symbol, side=side, price=price, qty=qty,
                      trade_type=trade_type, pnl_pct=pnl_pct)
        session.add(trade)
        session.flush()
        trade_id = trade.id
        return trade_id


def get_trades(user_id: int, limit: int = 50) -> list:
    with get_session() as session:
        rows = session.query(Trade).filter(Trade.user_id == user_id) \
            .order_by(Trade.id.desc()).limit(limit).all()
        return [
            {
                "id": r.id,
                "side": r.side,
                "symbol": r.symbol,
                "price": r.price,
                "qty": r.qty,
                "type": r.trade_type,
                "pnl_pct": r.pnl_pct,
                "timestamp": r.timestamp.isoformat() if r.timestamp else None,
            }
            for r in rows
        ]


def get_trade_stats(user_id: int) -> dict:
    with get_session() as session:
        total = session.query(func.count(Trade.id)).filter(Trade.user_id == user_id).scalar() or 0

        exits_q = session.query(Trade).filter(
            Trade.user_id == user_id,
            Trade.trade_type.in_(["exit", "stop_loss", "take_profit"]),
            Trade.pnl_pct.isnot(None),
        )
        exits = exits_q.all()
        wins = [r for r in exits if r.pnl_pct >= 0]
        losses = [r for r in exits if r.pnl_pct < 0]
        total_pnl = sum(r.pnl_pct for r in exits) if exits else 0.0
        return {
            "total_trades": total,
            "exits": len(exits),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": round(len(wins) / len(exits) * 100, 1) if exits else 0.0,
            "total_pnl_pct": round(total_pnl, 2),
            "avg_pnl_pct": round(total_pnl / len(exits), 2) if exits else 0.0,
            "best_trade": round(max(r.pnl_pct for r in exits), 2) if exits else 0.0,
            "worst_trade": round(min(r.pnl_pct for r in exits), 2) if exits else 0.0,
        }


def get_recent_trades(user_id: int, since_id: int = 0) -> list:
    with get_session() as session:
        rows = session.query(Trade).filter(Trade.user_id == user_id, Trade.id > since_id) \
            .order_by(Trade.id.asc()).all()
        return [
            {
                "id": r.id,
                "side": r.side,
                "symbol": r.symbol,
                "price": r.price,
                "qty": r.qty,
                "type": r.trade_type,
                "pnl_pct": r.pnl_pct,
                "timestamp": r.timestamp.isoformat() if r.timestamp else None,
            }
            for r in rows
        ]


def log_error(user_id: int | None, message: str):
    with get_session() as session:
        err = ErrorLog(user_id=user_id, message=message)
        session.add(err)


def log_audit(
    user_id: int | None,
    event_type: str,
    event_data: str = "",
    ip_address: str | None = None,
    user_agent: str | None = None,
):
    with get_session() as session:
        audit = AuditLog(
            user_id=user_id,
            event_type=event_type,
            event_data=event_data,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        session.add(audit)
