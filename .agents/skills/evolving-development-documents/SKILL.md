---
name: evolving-development-documents
description: S3 ML 기반 자재 수요 예측 프로젝트의 요구사항·아키텍처·구현 현황·개발 지침을 담은 진화형 개발 문서(SSOT) 스킬입니다.
---

# S3 ML 기반 자재 수요 예측 — 개발 문서 (Evolving Development Document)

> **Summary**: 웹 UI + Python(FastAPI) ML 백엔드로 부품별 주간 수요를 예측·시뮬레이션·통계 리포트하는 S3 데모.
> 현재 상태는 **v0.3 / MVP 기능 구현 완료 · P1 테스트 17건 통과 · 브라우저 화면 QA 완료**이며, 워크벤치 Demo 카드 연결 산출물까지 완료되어 사용자 PC 배치만 남았다.
>
> - 문서 버전: **v0.3** (2026-09-07) · 기준 소스: `Plan.md` v0.1 + 실제 구현 코드
> - 이 문서가 프로젝트의 **단일 진실 공급원(SSOT)**이다. 코드와 문서가 다르면 **코드를 확인한 뒤 이 문서를 갱신**한다.

---

## 0. 문서 지도

| 문서 | 역할 | 갱신 시점 |
|---|---|---|
| `.agents/skills/evolving-development-documents/SKILL.md` (본 문서) | 요구사항·아키텍처·API·구현 현황 SSOT | 스펙/구조/상태 변경 시 |
| `Plan.md` | 최초 기획 원본(v0.1). 이력 보존용, 수정 최소화 | 기획 자체가 바뀔 때만 |
| `README.md` | 실행/시연 Quick Start | 실행 절차 변경 시 |
| `docs/DEV_PLAN.md` | 개발 계획·진행 현황·백로그·변경 이력 | 작업 단위 완료 시 |
| `tests/test_forecast.py` | P1 검증 기준(실행 가능한 명세) | 규칙 변경 시 |

---

## 1. 프로젝트 정의

- **목표**: 과거 SCM 주간 수요 데이터와 선택 부품을 입력받아, 웹 화면에서 Python ML 백엔드가 수요 예측·시뮬레이션·통계 리포트를 반환하는 S3 지능형 데이터 웹앱 데모 구축
- **분류**: S3 지능형 데이터 웹앱 / T5 후보(예측·분석형 산업 AI). LLM은 개발 보조에만 사용하며 운영 예측 경로에 포함하지 않는다.
- **대상 사용자**: 자재·SCM 담당자, 생산계획 담당자, AX 과제 시연 검토자
- **경계**: 예측값은 **의사결정 참고용**이며 실제 발주 자동 실행은 Out-of-Scope. 데이터는 **교육·시연용 합성 데이터**이며 실제 SCM 데이터가 아니다.

### 핵심 흐름
부품 선택 → 과거 이력 조회 → Horizon(4/8/12주) 선택 → 예측 실행 → Holdout 성능(WAPE/MAE/RMSE) 확인 → 시나리오(-20%~+30%) 조정 → Baseline vs Scenario 비교 → 통계 리포트 확인

---

## 2. 범위 (Scope)

**In-Scope (MVP)** — 전 항목 구현 완료
부품 선택 / 과거 주간 수요 조회 / Baseline(Naive·Seasonal Naive) / ML(HistGradientBoosting) / Time-based Train·Holdout split / 4·8·12주 Forecast / WAPE·MAE·RMSE / Actual vs Predicted 차트 / Scenario adjustment / 기초 통계 / 오류·빈 상태 UI / 로컬 Python API

**Out-of-Scope** — ERP·SCM 실연동, 실제 발주 생성, 클라우드 배포·인증, 다사용자 협업, LLM/RAG, 운영 의사결정 자동화, 공급사 자동 통보

---

## 3. 아키텍처 (As-Built)

```
브라우저 (frontend/index.html + app.js + Chart.js CDN)
        │  fetch  http://127.0.0.1:8000/api/*
        ▼
FastAPI  backend/app.py            ← 라우팅 · 입력검증 · HTTP 오류 매핑
        ├─ backend/data_service.py ← 엑셀 로드(캐시) · 데이터 계약 검증 · Feature 생성 · 기초 통계
        └─ backend/model.py        ← Train/Holdout 분할 · Baseline 2종 · ML 학습 · 재귀 예측 · 시나리오
        ▼
S3_ML_자재수요예측_개발테스트데이터.xlsx (시트: SCM_History)
```

계층 규칙:
- `app.py`는 **HTTP 관심사만** 담당한다. 계산 로직을 넣지 않는다.
- `data_service.py`는 **데이터 계약과 Feature 정의의 유일한 소유자**다. Feature를 바꾸면 `FEATURE_COLUMNS`만 수정한다.
- `model.py`는 pandas DataFrame을 입력받고 dict를 반환한다. 파일 I/O와 HTTP를 알지 못한다.
- 정적 파일 마운트(`/`)는 **반드시 API 라우트 등록 이후**에 위치한다.

---

## 4. 데이터 계약

| 항목 | 내용 |
|---|---|
| 원천 | `S3_ML_자재수요예측_개발테스트데이터.xlsx` / 시트 `SCM_History` (695행, 5부품 × 139주, 2024-01-01 ~ 2026-08-24) |
| 필수 컬럼 | `week_start`, `part_id`, `part_name`, `lead_time_days`, `production_plan_qty`, `demand_qty` |
| 선택 컬럼 | `category`, `supplier`, `unit_price_krw`, `opening_inventory`, `planned_receipt_qty`, `closing_inventory`, `stockout_flag`, `holiday_flag` |
| Target | `demand_qty` |
| 검증 규칙 (`load_data`) | week_start 유효 날짜 / part_id 비어있지 않음 / demand_qty ≥ 0 / (part_id, week_start) 중복 금지 → 위반 시 `DataError` |
| 결측 처리 | Feature·Target 기준으로만 행 제거(`dropna(subset=...)`). 선택 컬럼 결측이 학습 데이터를 지우지 않는다. |

**Feature 정의** (`FEATURE_COLUMNS`, 9종):
`lag_1, lag_2, lag_4, lag_8, rolling_mean_4, rolling_mean_8, rolling_std_4, month, week_of_year`

> **Leakage 방지 규칙(불변)**: 모든 rolling은 `shift(1)` 이후 계산한다. 당주(t) 실적은 어떤 feature에도 들어가지 않는다. 이 규칙은 `test_features_have_no_leakage`가 강제한다.

---

## 5. 모델 및 평가 설계

| 모델 | 정의 | 역할 |
|---|---|---|
| Naive | 직전 주 실적(`lag_1`) | 최소 기준선 |
| Seasonal Naive | 52주 전 실적(데이터 < 60주면 4주 lag) | 계절성 기준선 |
| ML | `HistGradientBoostingRegressor(random_state=42)` | 후보 모델 |

- **분할**: Train ~ 2026-06-29 / Holdout 2026-07-06 ~ 2026-08-24 (8주). 데이터가 이 구간을 만족하지 않으면 **마지막 8주 자동 대체**(`split_mode: fallback_last_n_weeks`)로 500 오류 대신 동작을 이어간다.
- **지표**: Primary **WAPE** = Σ|Actual−Forecast| / ΣActual, Secondary MAE·RMSE. **MAPE는 사용하지 않는다**(0 수요 왜곡). ΣActual=0이면 WAPE는 `null`(정의 불가)로 반환하며 0으로 위장하지 않는다.
- **미래 예측**: 최종 모델은 전체 유효 구간으로 재학습 후 **재귀(다단계)** 예측. 예측값을 다시 lag에 넣어 Horizon만큼 진행하고 음수는 0으로 절단한다.

> **정직성 규칙(불변)**: Baseline 2종의 지표를 항상 함께 반환·표시하고, ML이 열세인 경우에도 숨기지 않는다. `best_model`은 WAPE 최저 모델을 그대로 표기한다.

### 현재 측정값 (Holdout 8주, 1-step-ahead, seed 42)

| part_id | 부품명 | Naive WAPE | Seasonal WAPE | ML WAPE | Best |
|---|---|---|---|---|---|
| MAT-1001 | 베어링 6204 | 0.1248 | **0.0873** | 0.0975 | seasonal_naive |
| MAT-1002 | 알루미늄 하우징 | 0.0606 | 0.1342 | **0.0598** | ml |
| MAT-1003 | 제어 PCB | 0.1067 | 0.2830 | **0.0807** | ml |
| MAT-1004 | O-Ring 40mm | 0.0701 | **0.0342** | 0.0378 | seasonal_naive |
| MAT-1005 | 서보모터 400W | 0.8146 | **0.7351** | 0.8873 | seasonal_naive |

**해석(시연 시 그대로 설명할 것)**: 5개 중 2개에서만 ML이 최우수다. 간헐 수요(MAT-1005, 수요 0인 주 47회)는 세 모델 모두 WAPE 0.7 이상으로 **주간 단위 예측이 부적합**하다 — 이는 결함이 아니라 데이터 특성이며, "ML이 항상 이긴다"는 과장 없이 Baseline 비교의 필요성을 보여주는 사례다.

---

## 6. API 규격 (As-Built, v0.2)

Base: `http://127.0.0.1:8000`

| Method | Path | 요청 | 응답 요약 | 오류 |
|---|---|---|---|---|
| GET | `/api/health` | – | `status`, `rows`, `parts`, `last_week` | 데이터 문제 시 `status: degraded` |
| GET | `/api/parts` | – | `parts[]`: part_id, part_name, lead_time_days | 500 (DataError) |
| GET | `/api/history/{part_id}` | – | `history[]`: 원천 행 전체(week_start는 `YYYY-MM-DD`) | 404 부품 없음 |
| POST | `/api/forecast` | `part_id`, `horizon_weeks`(4/8/12), `scenario_adjustment_pct`(-100~100) | 아래 참조 | 404 부품 없음 / 400 예측 불가 / 422 스키마 위반 |

`POST /api/forecast` 응답 키:

```jsonc
{
  "part_id", "part_name", "model_name",
  "evaluation": { "holdout_start", "holdout_weeks", "train_weeks",
                  "split_mode", "seasonal_lag_weeks", "primary_metric",
                  "best_model", "note" },
  "metrics":    { "naive": {WAPE, MAE, RMSE}, "seasonal_naive": {...}, "ml": {...} },
  "ml_metrics", "baseline_metrics",          // 하위 호환 별칭
  "holdout":    { "dates[]", "actual[]", "baseline[]", "seasonal[]", "ml_pred[]" },
  "future":     [ { "week_start", "baseline", "seasonal_naive", "forecast", "scenario" } ],
  "scenario":   { "adjustment_pct", "baseline_sum", "scenario_sum", "diff_qty",
                  "lead_time_days", "lead_time_weeks", "lead_time_cumulative_demand" },
  "statistics": { "weeks", "mean", "std", "cv", "recent_4w_avg", "recent_8w_avg",
                  "recent_12w_avg", "zero_demand_weeks", "max", "min" }
}
```

계약 규칙: 기존 키는 **삭제하지 않고 추가**한다. 삭제·이름 변경 시 `frontend/app.js`와 본 문서를 같은 커밋에서 함께 고친다.

---

## 7. 화면 구성 (As-Built)

- **Header**: 타이틀 · Demo 배지 · API 연결 상태
- **Control Panel**: Part dropdown / Horizon(4·8·12주) / Scenario 슬라이더(-20%~+30%) / Predict 버튼
- **KPI**: Holdout WAPE · 최근 4주 평균 수요 · 변동계수(CV) · 시나리오 예측 합계 · Baseline 예측 합계 · Lead Time과 기간 누적수요
- **Charts**: ① Historical Demand + Holdout(Actual / ML / Seasonal Naive) ② Future Forecast(ML vs Scenario)
- **Tables**: ① 주차별 예측 상세 ② 모델 성능 비교(★ = best) ③ 통계 리포트

표시 규칙 / 프런트엔드 불변 규칙:
- 지표가 `null`이면 `N/A`로 표시한다(0%로 표시 금지).
- **오프라인 우선**: 외부 CDN에 의존하지 않는다. Chart.js는 `frontend/vendor/chart.umd.min.js`(v4.4.2)를 로컬 로드한다. 폰트 CDN은 실패해도 폴백 스택으로 동작해야 한다.
- **부분 실패 격리**: `renderAll()`이 KPI → 표 → 차트 순으로 각각 try/catch로 호출한다. 한 영역이 실패해도 나머지는 표시되어야 하며, 오류는 `alert()`가 아니라 화면 내 오류 배너로 알린다.
- **API 주소 고정 금지**: `API_BASE`는 `location.origin` 기반으로 만든다(포트를 바꿔 서비스해도 동작). `file://`로 열었을 때만 `127.0.0.1:8000`으로 폴백한다.
- 900px 이하에서는 좌우 2단을 상하 1단으로 전환하고, 표는 컨테이너 안에서 가로 스크롤한다.

---

## 8. 확정된 결정 사항 (기존 결정 게이트)

| # | 항목 | 결정 | 근거 |
|---|---|---|---|
| 1 | API Framework | **FastAPI** | Pydantic 입력검증 + 자동 문서(`/docs`) |
| 2 | ML MVP | **HistGradientBoosting 1종 + Baseline 2종 비교** | 재현성·설명 가능성 우선 |
| 3 | Forecast 단위 | **주간 / 4·8·12주 고정** | 데이터 주기와 일치 |
| 4 | Scenario | **수요 ±% 단순 조정 + 리드타임 누적수요** | MVP 최소 구현 |
| 5 | UI 배포 | **독립 페이지**(FastAPI가 `/`로 정적 서빙), 워크벤치에서 링크 | 브라우저 보안·경로 문제 회피 |

| 6 | 워크벤치 연결 방식 | **상대경로 안내 페이지 경유**(`demos/S3/시연가이드.html`) | 워크벤치의 `safeDemoHref()`가 `http:` 등 모든 스킴과 절대경로를 차단하므로 서버 주소 직접 링크 불가. S1/S2와 동일한 상대경로 규칙을 지키면서 "서버 먼저 실행" 절차를 안내한다. |

> 워크벤치 연결 상세(변경 지점·배치 절차)는 `docs/DEV_PLAN.md` P4 참조.

---

## 9. 테스트 전략

`tests/test_forecast.py` — **P1 17건 전부 통과**(2026-09-07 기준).
커버: schema/품질 검증, 부품 목록, Leakage 검증, 시간 분할, WAPE 계산·0분모, 간헐수요(0 demand), Baseline 동시보고, Horizon 4/8/12 길이·주간 간격, 잘못된 Horizon 거부, Scenario ±% 반영·0% 항등, seed 재현성, API 성공/404/400/422.

실행: 프로젝트 루트에서 `pytest -q`

**브라우저 화면 QA(Playwright)** — 2026-09-07 실측: 외부 네트워크 전면 차단 상태에서 KPI 6종·표 3종·차트 2종 정상 렌더, 콘솔 오류 0건, 데스크톱 1440px·모바일 390px 모두 가로 스크롤 없음. 상세 결함·조치 이력은 `docs/DEV_PLAN.md` 2-1절 참조.

추가 필요(P2 백로그): 모델 직렬화, 응답 속도 측정, 첫 로드 시 자동 예측.

---

## 10. 에이전트 행동 지침

1. 본 문서를 SSOT로 삼고, 작업 착수 전 **Scope·불변 규칙·확정 사항**을 먼저 확인한다.
2. 코드를 바꾸면 **같은 작업 안에서** 본 문서(및 필요 시 `README.md`, `docs/DEV_PLAN.md`)를 갱신한다. 문서 미갱신 상태로 작업을 종료하지 않는다.
3. 불변 규칙을 깨는 변경은 임의로 하지 않는다: Leakage 방지, Baseline 동시 표기, MAPE 미사용, 음수 예측 금지, 시연 데이터만 사용.
4. 단순성 우선(Ponytail): 시연 목적에 필요한 최소 구현. 요청 범위 밖 리팩터링·의존성 추가 금지.
5. 검증 없는 완료 보고 금지: 변경 후 `pytest -q`를 실행하고, 실행하지 못했다면 그 사실과 이유를 명시한다.
6. 예측 성능을 확정 사실처럼 표현하지 않는다. 수치는 측정 조건(Holdout 8주, 1-step-ahead, seed 42)과 함께 제시한다.
