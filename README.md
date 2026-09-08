# S3 ML 기반 자재 수요 예측 (Demo)

> 과거 SCM 주간 수요 데이터를 학습한 Python ML 백엔드로 선택 부품의 주간 수요를 예측하고,
> Baseline과 비교하며 수요 시나리오를 시뮬레이션하는 **AX 과제 시연용 웹앱**입니다.
> 데이터는 교육·시연용 합성 데이터이며 실제 SCM 데이터가 아닙니다.

## Quick Start (5분)

```bash
# 1) 프로젝트 루트로 이동
cd S3_ML기반_자재수요예측

# 2) 가상환경 (이미 .venv가 있으면 활성화만)
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS/Linux

# 3) 의존성 설치
pip install -r requirements.txt

# 4) 서버 실행 (반드시 프로젝트 루트에서)
uvicorn backend.app:app --reload --port 8000
```

브라우저에서 **http://127.0.0.1:8000/** 접속 → 화면 우측 상단에 `API Connected` 표시 확인.

- API 문서(Swagger): http://127.0.0.1:8000/docs
- 헬스 체크: http://127.0.0.1:8000/api/health

## 시연 시나리오 (3분)

| # | 조작 | 확인 포인트 |
|---|---|---|
| 1 | 부품 `MAT-1003 제어 PCB` 선택, Horizon `8주`, **예측 실행** | Holdout 차트에 Actual/ML/Seasonal 3개 선, WAPE KPI 표시 |
| 2 | **모델 성능 비교** 표 확인 | ML(★)이 Baseline 2종보다 우수 — 비교 없이 "좋다"고 말하지 않는 구조 |
| 3 | 부품 `MAT-1005 서보모터 400W`로 변경 후 재실행 | 간헐 수요(0인 주 47회)에서는 **Baseline이 더 낫다**는 사실을 그대로 표시 |
| 4 | 시나리오 슬라이더 `+20%` 후 재실행 | Future 차트/표와 KPI(시나리오 합계·리드타임 누적수요)가 즉시 반영 |
| 5 | 통계 리포트 표 확인 | 평균·표준편차·CV·최근 4/8/12주 평균·수요 0 주차 |

## 테스트

```bash
pytest -q      # P1 17건 (데이터 계약 · Leakage · 지표 · Horizon · 시나리오 · API)
```

## 구조

```
S3_ML기반_자재수요예측/
├─ backend/            app.py(API) · data_service.py(데이터·Feature) · model.py(예측)
├─ frontend/           index.html · app.js · styles.css · vendor/chart.umd.min.js (로컬 번들)
├─ tests/              test_forecast.py
├─ docs/DEV_PLAN.md    개발 계획 · 진행 현황 · 백로그
├─ Plan.md             최초 기획서 v0.1 (이력 보존)
├─ .agents/skills/evolving-development-documents/SKILL.md   ← 개발 문서 SSOT
└─ S3_ML_자재수요예측_개발테스트데이터.xlsx
```

## 알아둘 점

- 서버는 **프로젝트 루트에서** 실행해야 합니다(`backend.app:app` 모듈 경로 기준).
- **오프라인/사내망에서도 동작합니다.** Chart.js를 로컬 번들로 포함했고, API 주소는 접속한 origin을 따르므로 포트를 바꿔도(`--port 9000` 등) 그대로 작동합니다.
- 예측값은 **의사결정 참고용**이며 발주 자동 실행 기능은 없습니다.
- 성능 수치는 Holdout 8주·1-step-ahead·seed 42 기준입니다. 미래 예측은 재귀 방식이라 오차가 더 커질 수 있습니다.
- 상세 스펙·설계 근거·불변 규칙은 [개발 문서(SKILL.md)](.agents/skills/evolving-development-documents/SKILL.md)를 참조하세요.
