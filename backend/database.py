import os
from contextlib import contextmanager
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, Float, String, Text, DateTime, ForeignKey, func, text
from sqlalchemy.orm import declarative_base, sessionmaker

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


def init_db():
    Base.metadata.create_all(engine)
    with get_session() as session:
        for stmt in [
            "ALTER TABLE trades ADD COLUMN IF NOT EXISTS symbol VARCHAR(20) DEFAULT 'BTCUSDT'",
            "ALTER TABLE user_configs ADD COLUMN IF NOT EXISTS balance_allocation_pct FLOAT DEFAULT 100.0",
            "ALTER TABLE user_configs ADD COLUMN IF NOT EXISTS ai_stop_loss_enabled INTEGER DEFAULT 0",
            "ALTER TABLE user_configs ADD COLUMN IF NOT EXISTS ai_optimize_enabled INTEGER DEFAULT 0",
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


def update_binance_keys(user_id: int, api_key: str, api_secret: str):
    with get_session() as session:
        session.query(User).filter(User.id == user_id).update({
            "binance_api_key": api_key,
            "binance_api_secret": api_secret,
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
