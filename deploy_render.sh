#!/bin/bash
# ============================================================================
# DEPLOY BINANCE BOT A RENDER.COM - GRATIS
# ----------------------------------------------------
# Script para despliegue en Render.com usando el plan gratuito.
# Preserva tus configuraciones actuales en .env (no se modifica).
# ============================================================================

set -e

# --- INICIO ---
echo "=========================================="
echo "Binance Bot - Despliegue Gratuito en Render.com"
echo "=========================================="
echo

# 1. Verificar que git está disponible
echo "[1/6] Verificando git..."
if ! command -v git &> /dev/null; then
    echo "ERROR: git no encontrado. Instálalo primero."
    exit 1
fi
if [ ! -d .git ]; then
    echo "No hay repositorio git local. Ejecuta: git init && git add . && git commit -m 'init'"
    read -p "PresionaEnter para continuar o Ctrl+C para cancelar " -n 1 -r
    exit 1
fi
echo " OK: Repositorio git encontrado"

# 2. Confirmar variables de entorno críticas
echo
echo "[2/6] Verificando configuraciones críticas..."

if [ ! -f .env ]; then
    echo "WARNING: No existe .env. Creando uno con valores por defecto..."
    cat > .env <<'EOF'
JWT_SECRET=pega_aqui_un_token_urlsafe_largo
MOCK_MODE=true
USE_TESTNET=true
DATABASE_URL=postgresql://bot:bot123@localhost:5432/binance_bot
EOF
    echo " Archivo .env creado con valores por defecto."
    echo " IMPORTANTE: Revisa y personaliza JWT_SECRET antes de desplegar."
fi

# Leer valores críticos
JWT_SECRET=$(grep '^JWT_SECRET=' .env | cut -d= -f2)
MOCK_MODE=$(grep '^MOCK_MODE=' .env | cut -d= -f2)
USE_TESTNET=$(grep '^USE_TESTNET=' .env | cut -d= -f2)

echo " JWT_SECRET: ${JWT_SECRET:0:8}..."
echo " MOCK_MODE: $MOCK_MODE"
echo " USE_TESTNET: $USE_TESTNET"

read -p "Continuar con el despliegue? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Cancelado por el usuario."
    exit 0
fi

# 3. Subir a GitHub (instrucciones)
echo
echo "[3/6] Subiendo a GitHub..."
echo "Pasos necesarios:"
echo "  1. Crear repositorio en GitHub (nuevo o existente)"
echo "  2. Ejecutar los siguientes comandos:"
echo "   git remote add origin https://github.com/TU-USUARIO/binance-bot.git"
echo "   git branch -M main"
echo "   git push -u origin main"
echo
read -p "PresionaEnter para continuar " -n 1 -r

# 4. Instrucciones para Render.com
echo
echo "================================================"
echo "4/6) Despliegue en Render.com (Free Tier)"
echo "================================================"
echo

echo "=== PASO A: Base de datos PostgreSQL gratuita ==="
echo "1. Ve a https://render.com y crea una cuenta (gratis)"
echo "2. New > PostgreSQL -> Free plan"
echo "3. Anota el DATABASE_URL que te proporcione Render (similar a:"
echo "    postgresql://bot:bot123@db-abc123.onrender.com:5432/burla-db)"
echo "4. El servicio tardará ~1 min en estar listo"

echo
echo "=== PASO B: Desplegar Backend FastAPI ==="
echo "1. New > Web Service > Python"
echo "2. Configuracion:"
echo "   - Build Command: pip install -r requirements.txt"
echo "   - Start Command: uvicorn backend.main:app --host 0.0.0.0 --port \$PORT"
echo "   - Environment Variables (¡MUY IMPORTANTE!):"
echo "       JWT_SECRET:     $JWT_SECRET"
echo "       MOCK_MODE:      $MOCK_MODE"
echo "       USE_TESTNET:    $USE_TESTNET"
echo "       DATABASE_URL:   postgresql://bot:bot123@db-abc123.onrender.com:5432/burla-db"
echo "   - Servicio gratuito: 750 hrs/mes (suficiente para siempre-on)"

echo
echo "=== PASO C: Desplegar Frontend (React + Vite) ==="
echo "1. New > Static Site > Free plan"
echo "2. Configuracion:"
echo "   - Build Command: npm install && npm run build"
echo "   - Publish Directory: frontend/dist"
echo "   - Agrega variable: VITE_API_URL=https://tu-backend.onrender.com"
echo "   - En 'Redirects headers' agregar _redirects con:"
echo "     /api/*  https://tu-backend.onrender.com/alpha  308"

echo
echo "=== PASO D: Configurar WebSocket ==="
echo "El archivo nginx.conf ya está preparado en frontend/nginx.conf:"
echo " - proxy_pass http://backend:8000;"
echo " - proxy_set_header Upgrade \$http_upgrade;"
echo " - proxy_set_header Connection \"upgrade;\""
echo " Esto permite que /api/ws funcione en tiempo real."

echo
echo "=== PASO E: Ver dominio ==="
echo " - Frontend: https-tu-usuario.onrender.com"
echo " - Backend:  https-tu-servicio.onrender.com"
echo " - WS: wss-tu-servicio.onrender.com/api/ws"

echo
echo "=== PASO F: Post-despliegue ==="
echo "Pruebas rapidas despues del deploy:"
echo "  • API Docs: https-tu-backend.onrender.com/docs"
echo "  • Estado:   https-tu-backend.onrender.com/api/status"
echo "  • WS: Conecta a /api/ws y deberia recibir updates cada 1s"
echo "  • Frontend: https-tu-frontend.onrender.com"
echo
echo "Si MOCK_MODE=true (por defecto):"
echo "  - El bot usa precios sinteticos, sin dinero real"
echo "  - Senales generadas cada 2 segundos internamente"
echo "  - Ideal para probar la UI sin riesgo"
echo
echo "Si MOCK_MODE=false: requiere API keys de Binance guardadas"
echo "   via /api/auth/keys en el panel web."
echo

echo "=============================================="
echo "FIN DEL SCRIPT"
echo "=============================================="
echo
echo "Resumen rapido:"
echo "  1. Sube repo a GitHub"
echo "  2. Crea PostgreSQL gratis en Render"
echo "  3. Crea Backend Python en Render"
echo "  4. Crea Static Site en Render (frontend)"
echo "  5. Configura las env vars (JWT_SECRET, MOCK_MODE, etc.)"
echo "  6. Listo! Tu bot en https-tu-servicio.onrender.com"
echo

read -p "PresionaEnter para salir " -n 1 -r