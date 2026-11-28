import argparse
import json
import os
import sys
import time
import urllib.error
from pathlib import Path

from paper_watch import peticion, resumen


SALIDA_PREDETERMINADA = "evidence/paper_forward.jsonl"


def leer_snapshot(base, token):
    estado = json.loads(peticion(f"{base}/api/funding/status", token))
    metricas = peticion(f"{base}/metrics", token)
    return {"ts": time.time(), **resumen(estado, metricas)}


def append_snapshot(ruta, snapshot):
    destino = Path(ruta)
    destino.parent.mkdir(parents=True, exist_ok=True)
    with destino.open("a", encoding="utf-8") as archivo:
        archivo.write(json.dumps(snapshot, ensure_ascii=False) + "\n")


def resumir_snapshots(ruta):
    destino = Path(ruta)
    if not destino.exists():
        return {"snapshots": 0}
    snapshots = []
    with destino.open("r", encoding="utf-8") as archivo:
        for linea in archivo:
            if linea.strip():
                snapshots.append(json.loads(linea))
    if not snapshots:
        return {"snapshots": 0}

    def max_valor(campo):
        valores = [item.get(campo) for item in snapshots if item.get(campo) is not None]
        return max(valores) if valores else None

    slippages = [
        item["slippage_promedio_bps"]
        for item in snapshots
        if item.get("slippage_promedio_bps") is not None
    ]
    return {
        "snapshots": len(snapshots),
        "primer_ts": min(item["ts"] for item in snapshots),
        "ultimo_ts": max(item["ts"] for item in snapshots),
        "ciclos": max_valor("ciclos"),
        "pnl_neto_usd": snapshots[-1].get("pnl_neto_usd"),
        "drawdown_usd": max_valor("drawdown_usd"),
        "drawdown_pct": max_valor("drawdown_pct"),
        "puntos_equity": max_valor("puntos_equity"),
        "decisiones": max_valor("decisiones"),
        "errores": max_valor("errores"),
        "fills_registrados": max_valor("fills_registrados"),
        "slippage_promedio_bps": (
            round(sum(slippages) / len(slippages), 2) if slippages else None
        ),
        "metricas_ok": snapshots[-1].get("metricas_ok", False),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Evidencia continua de paper trading de funding")
    parser.add_argument("--url", default="http://localhost:8000", help="URL base del backend")
    parser.add_argument("--token", help="JWT; por defecto BOTBINANCE_TOKEN")
    parser.add_argument("--salida", default=SALIDA_PREDETERMINADA, help="Ruta del JSONL")
    parser.add_argument("--intervalo", type=int, default=60, help="Segundos entre lecturas")
    parser.add_argument("--iteraciones", type=int, default=0, help="0 = sin límite")
    parser.add_argument("--resumen", action="store_true", help="Imprimir resumen acumulado y salir")
    args = parser.parse_args(argv)

    if args.resumen:
        print(json.dumps(resumir_snapshots(args.salida), ensure_ascii=False))
        return 0

    token = args.token or os.environ.get("BOTBINANCE_TOKEN")
    if not token:
        print("ERROR: define BOTBINANCE_TOKEN o pasa --token", file=sys.stderr)
        return 2

    base = args.url.rstrip("/")
    iteracion = 0
    while True:
        try:
            snapshot = leer_snapshot(base, token)
            append_snapshot(args.salida, snapshot)
            print(json.dumps(snapshot, ensure_ascii=False), flush=True)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            print(f"ERROR: {exc}", file=sys.stderr, flush=True)
        iteracion += 1
        if args.iteraciones and iteracion >= args.iteraciones:
            break
        time.sleep(args.intervalo)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
