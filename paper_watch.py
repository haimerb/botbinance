import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

METRICAS = (
    "botbinance_funding_running",
    "botbinance_funding_cycles_total",
    "botbinance_funding_decisions_total",
    "botbinance_funding_errors_total",
    "botbinance_funding_liquidation_pressure",
)


def peticion(url, token=None):
    req = urllib.request.Request(url, headers={"Accept": "application/json, text/plain"})
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=10) as resp:
        return resp.read().decode("utf-8")


def valores_metrica(texto, nombre):
    patron = rf"^\s*{re.escape(nombre)}(?:\{{[^}}]*\}})?\s+([-+0-9.eE]+)\s*$"
    return [float(valor) for valor in re.findall(patron, texto, re.MULTILINE)]


def valor_metrica(texto, nombre):
    valores = valores_metrica(texto, nombre)
    return valores[0] if valores else None


def sumar_metrica(texto, nombre):
    valores = valores_metrica(texto, nombre)
    return sum(valores) if valores else None


def maxima_metrica(texto, nombre):
    valores = valores_metrica(texto, nombre)
    return max(valores) if valores else None


def resumen(estado, texto_metricas):
    oportunidades = estado.get("opportunities") or []
    mejor = max(oportunidades, key=lambda item: item.get("annual_net_pct") or 0, default=None)
    contabilidad = estado.get("accounting") or {}
    posicion = estado.get("position") or {}
    execution = estado.get("execution") or {}
    fills = execution.get("fills") or []
    slippages = [
        float(fill["slippage_bps"])
        for fill in fills
        if fill.get("slippage_bps") is not None
    ]
    return {
        "estado": estado.get("status"),
        "ciclos": estado.get("cycles", 0),
        "mejor_simbolo": mejor.get("symbol") if mejor else None,
        "mejor_neto_anual_pct": round(mejor.get("annual_net_pct") or 0, 3) if mejor else 0,
        "persistencia_entrenada": (estado.get("gate") or {}).get("persistence_trained", False),
        "posicion": posicion.get("symbol"),
        "cubierta": posicion.get("is_hedged"),
        "pnl_neto_usd": round(contabilidad.get("net", 0), 4),
        "decisiones": sumar_metrica(texto_metricas, "botbinance_funding_decisions_total"),
        "errores": sumar_metrica(texto_metricas, "botbinance_funding_errors_total"),
        "presion_liquidacion": maxima_metrica(texto_metricas, "botbinance_funding_liquidation_pressure"),
        "ultima_ejecucion": execution.get("last_execution"),
        "fills_registrados": len(fills),
        "slippage_promedio_bps": round(sum(slippages) / len(slippages), 2) if slippages else None,
        "metricas_ok": all(nombre in texto_metricas for nombre in METRICAS),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Monitor de paper trading de funding")
    parser.add_argument("--url", default="http://localhost:8000", help="URL base del backend")
    parser.add_argument("--token", help="JWT; por defecto BOTBINANCE_TOKEN")
    parser.add_argument("--intervalo", type=int, default=60, help="Segundos entre lecturas")
    parser.add_argument("--iteraciones", type=int, default=0, help="0 = sin límite")
    args = parser.parse_args(argv)

    token = args.token or os.environ.get("BOTBINANCE_TOKEN")
    if not token:
        print("ERROR: define BOTBINANCE_TOKEN o pasa --token", file=sys.stderr)
        return 2

    base = args.url.rstrip("/")
    iteracion = 0
    while True:
        try:
            estado = json.loads(peticion(f"{base}/api/funding/status", token))
            metricas = peticion(f"{base}/metrics", token)
            print(json.dumps(resumen(estado, metricas), ensure_ascii=False), flush=True)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            print(f"ERROR: {exc}", file=sys.stderr, flush=True)
        iteracion += 1
        if args.iteraciones and iteracion >= args.iteraciones:
            break
        time.sleep(args.intervalo)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
