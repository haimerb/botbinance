@echo off
:: ============================================================================
:: DEPLOY BINANCE BOT A RENDER.COM - GRATIS
:: ----------------------------------------------------
:: Script para despliegue en Render.com usando el plan gratuito.
:: Preserva tus configuraciones actuales en .env (no se modifica).
:: ============================================================================

echo.
echo ============================================================================
echo  Binance Bot - Despliegue Gratuito en Render.com
echo ============================================================================

:: 1. Verificar que git está disponible
echo.
echo [1/5] Verificando git...
if not exist .git (
    echo ERROR: No hay repositorio git local. Ejecuta: git init && git add . && git commit -m "init"
    pause
    exit /b 1
)
echo ✓ Repositorio git encontrado

:: 2. Confirmar variables de entorno críticas
echo.
echo [2/5] Verificando configuraciones críticas...

if not exist .env (
    echo WARNING: No existe .env. Creando uno con valores por defecto...
    echo JWT_SECRET=pega_aqui_un_token_urlsafe_largo > .env
    echo MOCK_MODE=true >> .env
    echo USE_TESTNET=true >> .env
    echo DATABASE_URL=postgresql://bot:bot123@localhost:5432/binance_bot >> .env
    echo.
    echo Archivo .env creado con valores por defecto.
    echo IMPORTANTE: Revisa y personaliza JWT_SECRET antes de desplegar.
)

:: Leer valores críticos
for /f "tokens=*" %%a in (.env) do (
    set "%%a"
)

echo JWT_SECRET: %JWT_SECRET%
echo MOCK_MODE: %MOCK_MODE%
echo USE_TESTNET: %USE_TESTNET%

:: 3. Subir a GitHub (instrucciones)
echo.
echo [3/5] Subiendo a GitHub...
echo.
echo "Pasos necesarios:"
echo "  1. Crear repositorio en GitHub (nuevo o existente)"
echo "  2. Ejecutar los siguientes comandos:"
echo.
echo "   git remote add origin https://github.com/TU-USUARIO/binance-bot.git"
echo "   git branch -M main"
echo "   git push -u origin main"
echo.
echo "   (Presiona cualquier tecla para continuar o Ctrl+C para cancelar)"
pause >nul

:: 4. Instrucciones para Render.com
echo.
echo ============================================================================
echo [4/5] Despliegue en Render.com (Free Tier)
echo ============================================================================

echo.
echo "=== PASO A: Crear Base de Datos PostgreSQL gratuita ==="
echo 1. Ve a https://render.com y crea una cuenta (gratis)
echo 2. New > PostgreSQL → Free plan
echo 3. Anota el DATABASE_URL que te proporcione Render (similar a:
echo     postgresql://bot:bot123@db-abc123.onrender.com:5432/burla-db)
echo 4. El servicio tardará ~1 min en estar listo

echo.
echo "=== PASO B: Desplegar Backend FastAPI ==="
echo 1. New > Web Service > Python
echo 2. Configuración:
echo     - Build Command: pip install -r requirements.txt
echo     - Start Command: uvicorn backend.main:app --host 0.0.0.0 --port $PORT
echo     - Environment Variables (¡MUY IMPORTANTE!):
echo         JWT_SECRET:     %JWT_SECRET%
echo         MOCK_MODE:      %MOCK_MODE%
echo         USE_TESTNET:    %USE_TESTNET%
echo         DATABASE_URL:   postgresql://bot:bot123@db-abc123.onrender.com:5432/burla-db
echo     - Servicio gratuito: 750 hrs/mes (suficiente para siempre-on)

echo.
echo "=== PASO C: Desplegar Frontend (React + Vite) ==="
echo 1. New > Static Site > Free plan
echo 2. Configuración:
echo     - Build Command: npm install && npm run build
echo     - Publish Directory: frontend/dist
echo     - Add variable: VITE_API_URL=https://tu-backend.onrender.com
echo     - En "Redirects headers": agregar _redirects con:
echo       /api/*  https://tu-backend.onrender.com/alpha  308

echo.
echo "=== PASO D: Configurar WebSocket ==="
echo El archivo nginx.conf ya está preparado en frontend/nginx.conf:
echo " - proxy_pass http://backend:8000;"
echo " - proxy_set_header Upgrade \$http_upgrade;"
echo " - proxy_set_header Connection \"upgrade;\"
echo Esto permite que /api/ws funcione en tiempo real.

echo.
echo "=== PASO E: Verificar dominio ==="
echo - Frontend: http://1-your-user-name.github.io (si usas GitHub Pages)
echo - Backend: https://tu-servicio.onrender.com
echo - WS: wss://tu-servicio.onrender.com/api/ws

echo.
echo ============================================================================
echo [5/5] Post-despliegue
echo ============================================================================

echo.
echo "Pruebas rápidas después del deploy:"
echo "  • API Docs: https://tu-backend.onrender.com/docs"
echo "  • Estado:   https://tu-backend.onrender.com/api/status"
echo "  • WS: Conecta a /api/ws y debería recibir updates cada 1s"
echo "  • Frontend: https://tu-frontend.onrender.com"
echo.
echo "Si MOCK_MODE=true (por defecto):"
echo "  - El bot usa precios sintéticos, sin dinero real"
echo "   - Señales generadas cada 2 segundos internamente"
echo "   - Ideal para probar la UI sin riesgo"
echo.
echo "Si MOCK_MODE=false: requiere API keys de Binance guardadas"
echo "   vía /api/auth/keys en el panel web."
echo.
echo.
echo ============================================================================
echo FIN DEL SCRIPT
echo ============================================================================
echo.
echo "Resumen rápido:"
echo "  1. Sube repo a GitHub"
echo "  2. Crea PostgreSQL gratis en Render"
echo "  3. Crea Backend Python en Render"
echo "  4. Crea Static Site en Render (frontend)"
echo "  5. Configura las env vars (JWT_SECRET, MOCK_MODE, etc.)"
echo "  6. ¡Listo! Tu bot en https://tu-servicio.onrender.com"
echo.
pause