import subprocess
import sys
import os
import threading

ROOT = os.path.dirname(os.path.abspath(__file__))


def _wait_and_exit(proc, name, stop_event):
    proc.wait()
    if not stop_event.is_set():
        print(f"\n  [{name}] Proceso terminado inesperadamente.")
        stop_event.set()


def main():
    print("=" * 50)
    print("  Binance Trading Bot - Full Stack")
    print("=" * 50)
    print()

    backend = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "backend.main:app",
         "--host", "0.0.0.0", "--port", "8000"],
        cwd=ROOT,
    )
    print("  [BACKEND]  http://localhost:8000")
    print("  [BACKEND]  API docs http://localhost:8000/docs")

    frontend = subprocess.Popen(
        ["npm", "run", "dev", "--", "--host", "0.0.0.0"],
        cwd=os.path.join(ROOT, "frontend"),
        shell=True,
    )
    print("  [FRONTEND] http://localhost:5173")
    print()
    print("  Presiona Ctrl+C para detener ambos servicios.")
    print()

    stop_event = threading.Event()

    t1 = threading.Thread(target=_wait_and_exit, args=(backend, "BACKEND", stop_event), daemon=True)
    t2 = threading.Thread(target=_wait_and_exit, args=(frontend, "FRONTEND", stop_event), daemon=True)
    t1.start()
    t2.start()

    try:
        stop_event.wait()
    except KeyboardInterrupt:
        pass

    print("\n  Deteniendo servicios...")
    backend.terminate()
    frontend.terminate()
    backend.wait()
    frontend.wait()
    print("  Servenicios detenidos.")


if __name__ == "__main__":
    main()
