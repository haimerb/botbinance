# 🤖 Bot de Trading Binance

Bot de trading automatizado para Binance con **backend en FastAPI**, **frontend en React (Vite)** y **shell de escritorio con Electron**. Combina estrategias clásicas (cruce de medias móviles) con un **modelo de machine learning** (ensemble de stacking) para generar señales de compra/venta, gestión de riesgo con stop-loss/take-profit dinámico y un panel de control en tiempo real vía WebSocket.

Todo el código, la interfaz y los registros están en **español**.

---

## ✨ Características

- **Backend REST** con FastAPI + autenticación JWT (registro/login por email).
- **Bot ejecutándose en un hilo** con estado compartido seguro (thread-safe).
- **Dos modos de operación**:
  - `MOCK_MODE=true` — **simulación** (precios sintéticos, sin dinero real). Es el valor por defecto.
  - `MOCK_MODE=false` — **operación real** con las API keys de Binance del usuario (almacenadas cifradas en la BD).
- **Estrategia de cruce de medias móviles** (MA rápida/lenta configurables).
- **Estrategia mejorada** (Theil-Sen + MACD + Bollinger + RSI + volumen) y filtro de sentimiento.
- **Estrategia ML** con ensemble de stacking (XGBoost + LightGBM + CatBoost) y pipeline de volatilidad.
- **Gestión de riesgo**: stop-loss, take-profit, trailing stop, time-exit, take-profit parciales, tamaño máximo de posición y stop-loss adaptativo por ATR (opcional).
- **Gestión de cartera**: reparto de capital entre símbolos (igual, inverso a la volatilidad, por volatilidad o por confianza ML).
- **Backtesting** con comisiones, slippage, Sharpe/Sortino, max drawdown, profit factor y walk-forward.
- **Tareas asíncronas con Celery** (notificaciones, reportes diarios, limpieza de logs, backtests).
- **Notificaciones** por Telegram/Discord (trades, circuit breaker, alertas de seguridad).
- **Monitoring** con Prometheus + Grafana + Alertmanager.
- **Panel web en tiempo real**: precios, señales, posiciones, balance y P&L actualizados por WebSocket cada 1 segundo.
- **Historial de trades** con estadísticas (win-rate, P&L, mejor/peor operación).
- **Sugerencia automática de configuración** según volatilidad y precio del mercado.
- **Frontend** con componentes modulares, dark theme y `ErrorBoundary`.
- **App de escritorio Electron** que empaqueta backend + frontend.

---

## 🧱 Arquitectura

### Diagrama de componentes

```mermaid
flowchart LR
    subgraph Cliente["Cliente"]
        UI["React / Vite<br/>(frontend)"]
        ELE["Electron shell"]
        NAV["Navegador"]
    end

    subgraph Backend["Backend FastAPI (backend/)"]
        API["API REST /api<br/>+ WebSocket /api/ws"]
        BR["BotRunner<br/>(hilo de bot)"]
    end

    subgraph Estrategias["Estrategias (src/)"]
        DC["BinanceDataClient<br/>(datos de mercado)"]
        MA["MACrossoverStrategy"]
        ML["MLStrategy<br/>(stacking ensemble)"]
        RM["RiskManager"]
        EX["TradeExecutor"]
    end

    DB[(PostgreSQL<br/>users, user_configs, trades)]

    Binance[[Binance API<br/>testnet / real]]

    UI <-->|REST + WS| API
    NAV <-->|REST + WS| API
    ELE --> UI
    API --> BR
    BR --> DC
    BR --> MA
    BR --> ML
    BR --> RM
    BR --> EX
    BR --> DB
    DC --> Binance
    EX --> Binance
```

### Arquitectura por capas

```mermaid
flowchart TD
    subgraph Presentación
        C["frontend/src/ · React 18 + Vite 5"]
        C --> C1["App.jsx (orquestador) + ErrorBoundary"]
        C --> C2["components/ (Dashboard, SymbolCard, TradeTable, ...)"]
        C --> C3["api.js (fetch + WebSocket con reconexión)"]
    end

    subgraph API["Capa API (backend/)"]
        A["main.py · FastAPI + CORS (app factory)"]
        A --> A1["api/ · routers (auth, bot, trades, market, ...)"]
        A --> A2["core/ · config compartida + deps"]
        A --> A3["services/ · database, auth, metrics, notifications"]
        A --> A4["workers/ · Celery (tasks async)"]
    end

    subgraph Dominio["Capa de dominio (src/)"]
        D1["config.py · constantes + .env"]
        D2["data/binance_client.py"]
        D3["strategy/ma_crossover.py + enhanced_strategy.py"]
        D4["strategy/ml_strategy.py"]
        D5["risk/risk_manager.py + portfolio_manager.py"]
        D6["execution/trade_executor.py"]
    end

    subgraph Estado
        B["services/bot_runner.py · BotRunner (thread + lock)"]
    end

    C --> A
    A --> B
    B --> D1
    B --> D2
    B --> D3
    B --> D4
    B --> D5
    B --> D6
    A3 --> DB[(PostgreSQL)]
```

### Flujo de una señal de trading

```mermaid
sequenceDiagram
    participant BR as BotRunner (hilo)
    participant DC as BinanceDataClient
    participant MA as MACrossoverStrategy
    participant ML as MLStrategy
    participant RM as RiskManager
    participant EX as TradeExecutor
    participant BIN as Binance API

    loop cada 60 s (live) / 2 s (mock)
        BR->>DC: fetch_klines(symbol, interval)
        DC-->>BR: DataFrame OHLCV
        BR->>MA: generate_signal(df)
        BR->>ML: generate_signal(df)
        MA-->>BR: BUY / SELL / HOLD
        ML-->>BR: BUY / SELL / HOLD
        BR->>BR: consensus = señal si MA == ML
        alt consenso BUY y sin posición
            BR->>RM: open_position(price, qty)
            RM-->>BR: ok
            BR->>EX: execute_order("BUY", qty, symbol)
            EX->>BIN: create_order(MARKET)
            BR->>BR: actualiza estado + registra trade
        else posición abierta
            BR->>RM: check_stop_loss(price) / check_take_profit(price)
            alt se dispara SL o TP
                BR->>EX: execute_order("SELL", qty, symbol)
                BR->>BR: registra trade con pnl_pct
            end
        end
        BR->>BR: publica estado (WS /api/ws)
    end
```

### Diagrama de despliegue (Docker)

```mermaid
flowchart LR
    subgraph Docker["Docker Compose"]
        PG[("PostgreSQL 16<br/>:5432")]
        RD[("Redis 7<br/>:6379")]
        BE["backend:8000<br/>uvicorn backend.main:app"]
        CW["celery-worker<br/>backend.workers.celery_app"]
        CB["celery-beat<br/>backend.workers.celery_app"]
        FE["frontend:80<br/>nginx (build Vite)"]
    end

    PG -->|DATABASE_URL| BE
    RD -->|REDIS_URL| BE
    RD --> CW
    CW --> PG
    CB --> RD
    FE -->|proxy /api y /api/ws| BE

    subgraph Externo
        BROWSER["Navegador → :5173"]
        BIN2[Binance API]
    end

    BROWSER --> FE
    BE --> BIN2
```

---

## 🛠️ Stack tecnológico

| Capa | Tecnología |
|------|------------|
| Backend | Python 3.11 · FastAPI · Uvicorn · SQLAlchemy |
| Frontend | React 18 · Vite 5 · Electron 28 · pnpm |
| Base de datos | PostgreSQL (psycopg2) |
| Cola / tareas | Redis · Celery (worker + beat) |
| Monitoring | Prometheus · Grafana · Alertmanager |
| ML | XGBoost · LightGBM · CatBoost · scikit-learn · imbalanced-learn · joblib |
| Criptografía | bcrypt · PyJWT |
| Contenedores | Docker · Docker Compose |

---

## 🚀 Inicio rápido

### Opción A — Docker (recomendada)

Requisitos: [Docker](https://www.docker.com/) con Docker Compose.

```bash
# 1) Crear el .env (solo JWT_SECRET es obligatorio)
cp .env.example .env
#    o genera una clave:
python -c "import secrets; print(secrets.token_urlsafe(32))"

# 2) Levantar toda la pila (Postgres + Redis + backend + workers + frontend)
docker compose up --build

# 3) Abrir
#    Frontend:    http://localhost:5173
#    API docs:    http://localhost:8000/docs
#    Monitoring:  docker compose -f docker-compose.monitoring.yml up -d
```

> Por defecto arranca en **modo simulación** (`MOCK_MODE=true`). Para operar en vivo:
> `MOCK_MODE=false` en `.env` y guarda tus API keys de Binance desde el panel.

### Opción B — Desarrollo local (sin Docker)

Requisitos: Python 3.10+ y Node.js 18+.

```bash
# 1) Variables de entorno (.env en la raíz)
cp .env.example .env   # y rellena JWT_SECRET

# 2) Backend (desde la raíz del repo)
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000

# 3) Frontend (otra terminal)
cd frontend
pnpm install
pnpm run dev
```

### Opción C — Todo a la vez

```bash
python start.py    # levanta backend :8000 y frontend :5173 juntos
```

### Opción D — App de escritorio (Electron)

```bash
cd frontend
pnpm install
pnpm run electron:build    # genera el instalador en frontend/release/
```

---

## 🔐 Variables de entorno

| Variable | Obligatoria | Valor por defecto | Descripción |
|----------|-------------|-------------------|-------------|
| `JWT_SECRET` | ✅ Sí | — | Secreto para firmar tokens JWT. Sin ella, el backend no arranca. |
| `ENCRYPTION_KEY` | ✅ Sí | — | Clave (base64 urlsafe 32 bytes) para cifrar las API keys en la BD. |
| `DATABASE_URL` | No | `postgresql://bot:bot123@localhost:5432/binance_bot` | Cadena de conexión de PostgreSQL. |
| `MOCK_MODE` | No | `true` | `true` = simulación, `false` = operación real. |
| `USE_TESTNET` | No | `true` | Usa la API de testnet de Binance para datos/órdenes. |
| `REDIS_URL` | No | `redis://redis:6379/0` | Broker/backend de resultados de Celery. |
| `ALLOWED_ORIGINS` | No | `http://localhost:5173,http://localhost:8000` | Orígenes permitidos para CORS. |
| `BINANCE_API_KEY` / `BINANCE_API_SECRET` | No | — | Keys usadas por el cliente de datos/ejecución (los usuarios guardan las suyas en la BD). |
| `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` | No | — | Notificaciones por Telegram. |
| `DISCORD_WEBHOOK_URL` | No | — | Notificaciones por Discord. |
| `SENTIMENT_ENABLED` / `SENTIMENT_API_KEY` | No | `false` | Filtro de sentimiento (NewsAPI). |
| `GRAFANA_PASSWORD` | No | `admin123` | Contraseña del dashboard de Grafana. |

> `.env` no se versiona. Usa `.env.example` como plantilla.

---

## 🧠 Entrenar el modelo ML

El bot usa `src/models/trained_model.pkl` (incluido en el repo). Para reentrenarlo:

```bash
# requisitos extras no incluidos en requirements.txt
pip install xgboost imbalanced-learn

python train_model.py --symbols BTCUSDT ETHUSDT --interval 1h --limit 5000
```

El entrenamiento: descarga velas históricas → calcula ~30 features técnicas → entrena un **ensemble de stacking** (XGBoost/LightGBM/CatBoost + LogisticRegression) para dirección y un RandomForest para volatilidad, con `SMOTE` y validación `TimeSeriesSplit`. Guarda ambos modelos en `src/models/trained_model.pkl`.

> Sin el modelo, `MLStrategy` registra "Modelo ML no encontrado" y emite siempre `HOLD`.

---

## ✅ Tests

```bash
python -m pytest tests/ -q
```

34 tests que cubren `src/strategy/ma_crossover.py`, `src/risk/risk_manager.py`, `src/backtest/engine.py`, `src/risk/portfolio_manager.py` y `src/strategy/sentiment.py`.

---

## 📁 Estructura del proyecto

```
botbinance/
├── backend/                  # API FastAPI (app factory delgada)
│   ├── main.py               # middleware + montaje de routers
│   ├── core/                 # config compartida, deps, security headers
│   ├── api/                  # routers: auth, mfa, bot, trades, market,
│   │                         #   user, alerts, ws, health, backtest
│   ├── services/             # auth, database, crypto, metrics,
│   │                         #   notifications, user_config, bot_runner
│   ├── workers/              # celery_app.py + tasks.py (tareas async)
│   └── schemas/              # modelos Pydantic compartidos
├── src/                      # dominio / negocio
│   ├── config.py             # constantes + .env
│   ├── data/binance_client.py
│   ├── strategy/
│   │   ├── ma_crossover.py   # estrategia clásica
│   │   ├── enhanced_strategy.py  # Theil-Sen + MACD + BB + RSI
│   │   ├── ml_strategy.py    # estrategia ML
│   │   └── sentiment.py      # filtro de sentimiento
│   ├── risk/
│   │   ├── risk_manager.py   # SL/TP/trailing/time-exit
│   │   └── portfolio_manager.py  # asignación entre símbolos
│   ├── backtest/engine.py    # backtest + walk-forward
│   ├── execution/trade_executor.py
│   └── models/trainer.py     # entrenamiento ML
├── frontend/                 # React + Vite + Electron
│   ├── src/components/       # componentes de UI
│   ├── src/api.js            # fetch + WebSocket
│   └── package.json
├── monitoring/               # Prometheus, Grafana, Alertmanager
├── electron/main.js          # shell de escritorio
├── tests/                    # pytest
├── start.py                  # backend + frontend juntos
├── train_model.py            # entrenamiento del modelo
├── docker-compose.yml        # PostgreSQL + Redis + backend + workers + frontend
└── docker-compose.monitoring.yml
```

---

## 🔌 Endpoints de la API

| Método | Ruta | Descripción |
|--------|------|-------------|
| `POST` | `/api/auth/register` | Registro de usuario → token JWT |
| `POST` | `/api/auth/login` | Login → token JWT |
| `GET` | `/api/auth/me` | Perfil del usuario actual |
| `POST` | `/api/auth/keys` | Guarda API keys de Binance |
| `GET` | `/api/user/config` | Configuración del usuario |
| `PUT` | `/api/user/config` | Actualiza configuración |
| `GET` | `/api/user/profile` | Perfil + configuración |
| `GET` | `/api/status` | Estado del bot |
| `POST` | `/api/start` | Inicia el bot |
| `POST` | `/api/stop` | Detiene el bot |
| `GET` | `/api/trades` | Últimos trades |
| `GET` | `/api/trades/stats` | Estadísticas de trades |
| `GET` | `/api/trades/recent` | Trades nuevos (incremental) |
| `GET` | `/api/config/suggest` | Sugerencias de configuración |
| `GET` | `/api/market/klines` | Velas OHLCV para gráficos |
| `POST` | `/api/backtest` | Backtest asíncrono (encola `backtest_symbol`) |
| `POST` | `/api/alerts/webhook` | Receptor de alertas de Alertmanager |
| `GET` | `/health` | Healthcheck (api / database / redis) |
| `GET` | `/metrics` | Métricas Prometheus |
| `WS` | `/api/ws` | Estado del bot en tiempo real (1s) |

---

## 📈 Monitoring

El stack de observabilidad se levanta aparte, sobre la misma red de Compose:

```bash
docker compose -f docker-compose.monitoring.yml up -d
```

| Servicio | Puerto | Credenciales |
|----------|--------|--------------|
| Prometheus | 9090 | — |
| Grafana | 3000 | `admin` / `admin123` |
| Alertmanager | 9093 | — |

El backend expone `/metrics` (conteos HTTP, auth, conexiones WS, P&L, circuit breaker) y responde en `/health` el estado de PostgreSQL y Redis.

---

## ⚙️ Tareas asíncronas (Celery)

Los workers usan Redis como broker y backend de resultados. Se lanzan con:

```bash
celery -A backend.workers.celery_app worker --loglevel=info   # worker
celery -A backend.workers.celery_app beat --loglevel=info      # scheduler
```

Tareas: `cleanup_old_logs`, `send_daily_report`, `send_trade_notification`, `send_circuit_breaker_alert`, `backtest_symbol`.

---

## ⚠️ Aviso

Este software es **con fines educativos**. Operar criptomonedas conlleva riesgo financiero real. Usa siempre el modo simulación (`MOCK_MODE=true`) hasta comprender el comportamiento del bot, y nunca compartas tus API keys.
