"""실행 전 환경 점검 · 사용 가능한 포트 선택.

사용법:
    python tools/check_env.py              # 점검 결과 출력 (실패 시 종료코드 1)
    python tools/check_env.py --port-only  # 사용 가능한 포트 번호만 출력
"""

from __future__ import annotations

import os
import socket
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_FILE = os.path.join(ROOT, "S3_ML_자재수요예측_개발테스트데이터.xlsx")
PORT_CANDIDATES = [8000, 8001, 8002, 8003, 8010]
REQUIRED_MODULES = [
    ("fastapi", "FastAPI"),
    ("uvicorn", "uvicorn"),
    ("pandas", "pandas"),
    ("numpy", "numpy"),
    ("sklearn", "scikit-learn"),
    ("openpyxl", "openpyxl"),
]


def port_is_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


def pick_port() -> int | None:
    for port in PORT_CANDIDATES:
        if port_is_free(port):
            return port
    return None


def main() -> int:
    if "--port-only" in sys.argv:
        port = pick_port()
        print(port if port else 0)
        return 0

    problems = []

    print(f"  Python      : {sys.version.split()[0]}  ({sys.executable})")
    if sys.version_info < (3, 10):
        problems.append("Python 3.10 이상이 필요합니다.")

    missing = []
    for module, name in REQUIRED_MODULES:
        try:
            __import__(module)
        except Exception as exc:  # noqa: BLE001
            missing.append(f"{name} ({exc.__class__.__name__})")
    if missing:
        problems.append(
            "패키지 누락: " + ", ".join(missing) + "  →  pip install -r requirements.txt"
        )
        print(f"  패키지      : 누락 {len(missing)}건")
    else:
        print(f"  패키지      : {len(REQUIRED_MODULES)}종 정상")

    if os.path.exists(DATA_FILE):
        print(f"  데이터 파일 : OK ({os.path.getsize(DATA_FILE) // 1024} KB)")
    else:
        problems.append(f"데이터 파일을 찾을 수 없습니다: {DATA_FILE}")
        print("  데이터 파일 : 없음")

    if not os.path.isfile(os.path.join(ROOT, "backend", "app.py")):
        problems.append("backend/app.py를 찾을 수 없습니다. 프로젝트 루트에서 실행하세요.")

    chart = os.path.join(ROOT, "frontend", "vendor", "chart.umd.min.js")
    print(f"  차트 번들   : {'OK' if os.path.exists(chart) else '없음(차트만 미표시, 표·KPI는 정상)'}")

    port = pick_port()
    if port is None:
        problems.append(
            "사용 가능한 포트가 없습니다(" + ", ".join(map(str, PORT_CANDIDATES)) + "). "
            "이미 실행 중인 서버가 있는지 확인하세요."
        )
        print("  포트        : 사용 가능 없음")
    else:
        print(f"  포트        : {port} 사용 가능" + ("" if port == 8000 else "  (8000이 사용 중)"))

    if problems:
        print("\n  [해결 필요]")
        for i, p in enumerate(problems, 1):
            print(f"   {i}. {p}")
        return 1

    print("\n  점검 결과: 이상 없음")
    return 0


if __name__ == "__main__":
    sys.exit(main())
