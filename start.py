import subprocess
import sys
import os

ROOT = os.path.dirname(os.path.abspath(__file__))


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

    try:
        backend.wait()
        frontend.wait()
    except KeyboardInterrupt:
        print("\n  Deteniendo servicios...")
        backend.terminate()
        frontend.terminate()
        backend.wait()
        frontend.wait()
        print("  Servicios detenidos.")


if __name__ == "__main__":
    main()
