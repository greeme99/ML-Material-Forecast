# S3 ML 기반 자재 수요 예측 — Vibe Coding Plan v0.1

> **[2026-09-07 안내]** 본 문서는 최초 기획 원본(v0.1)이며 이력 보존용입니다.
> 현행 요구사항·아키텍처·API·구현 현황은 `.agents/skills/evolving-development-documents/SKILL.md`(SSOT),
> 진행 현황과 백로그는 `docs/DEV_PLAN.md`를 참조하세요.

## 1. 프로젝트 정의
과거 SCM 주간 수요 데이터와 선택 부품을 입력으로 받아, 웹 화면에서 Python ML 백엔드가
수요 예측·시뮬레이션·통계 리포트를 반환하는 **S3 지능형 데이터 웹앱 데모**.

## 2. Tiny Win
브라우저에서 부품 1개를 선택하면:
1. 과거 수요 추이를 조회하고
2. Python 백엔드가 4/8/12주 수요를 예측하며
3. Holdout 성능(WAPE/MAE)을 보여주고
4. 사용자가 수요 시나리오를 조정하면 예측/재고 영향을 즉시 비교한다.

## 3. 분류와 AI 역할
- 구현 단계: **S3 지능형 데이터 웹앱**
- 실제 기술: HTML/CSS/JavaScript + Python 분석 API + ML
- T유형: 현 분류표상 예측/분석형 산업 AI에 가장 가까운 **T5 후보**
- LLM: 개발 보조에만 사용하며 운영 예측 모델에는 포함하지 않음
- 중요 경계: 모델 결과는 의사결정 참고용이며 실제 발주 자동 실행은 Out-of-Scope

## 4. 대상 사용자
- 자재/SCM 담당자
- 생산계획 담당자
- AX 과제 시연 검토자

## 5. 핵심 시연 흐름
① 데모 페이지 진입
→ ② 부품 선택
→ ③ 과거 수요/재고 통계 조회
→ ④ 예측 Horizon(4/8/12주) 선택
→ ⑤ ML 예측 실행
→ ⑥ Actual vs Forecast 차트 및 WAPE/MAE 확인
→ ⑦ Scenario 조정(-20%~+30% 권장)
→ ⑧ Baseline vs Scenario 비교
→ ⑨ 통계 리포트 확인

## 6. MVP In-Scope
- 부품 선택
- 과거 주간 수요 조회
- Baseline 모델
- ML 모델 1종 이상
- Time-based Train/Holdout split
- 4/8/12주 Forecast
- WAPE / MAE / RMSE
- Actual vs Forecast 차트
- Scenario adjustment
- 기본 통계: 평균, 표준편차, 최근 4/8/12주 평균, 변동계수
- 오류/빈 상태 UI
- 로컬 Python API 실행
- AX 과제 워크벤치 Demo 카드에서 로컬 앱으로 이동/실행 안내

## 7. Out-of-Scope
- ERP/SCM 실운영 시스템 직접 연결
- 실제 구매발주 자동 생성
- 클라우드 배포/인증
- 실시간 다사용자 협업
- LLM/RAG
- 운영 의사결정 자동화
- 공급사 자동 통보

## 8. 데이터 계약
### 필수 입력
- week_start
- part_id
- part_name
- lead_time_days
- production_plan_qty
- demand_qty

### 선택 Feature
- category
- supplier
- holiday_flag
- inventory/receipt 관련 컬럼

### Target
- demand_qty

### 데이터 품질 규칙
- week_start는 유효 날짜
- demand_qty는 0 이상
- part_id는 비어 있지 않음
- 동일 part_id/week_start 중복은 오류 또는 사전 집계
- 미래 데이터는 학습 데이터에 포함 금지
- 결측 Target은 학습 전 명시적으로 제거/오류 처리

## 9. 모델 설계안
### Baseline
- Naive: 최근 주 수요
- Seasonal Naive: 4주 또는 52주 lag 중 데이터 길이에 맞는 기준

### ML 후보
MVP 권장: `scikit-learn` 기반 Gradient Boosting 또는 Random Forest 계열.

Feature 후보:
- lag_1, lag_2, lag_4, lag_8, lag_13
- rolling_mean_4, rolling_mean_8, rolling_std_4
- week_of_year, month
- production_plan_qty
- holiday_flag

선정 원칙:
- 복잡한 모델보다 재현성과 설명 가능성을 우선
- 동일 Holdout 구간에서 Baseline과 비교
- ML이 Baseline보다 나쁘면 이를 숨기지 않고 Baseline 결과도 함께 표시

## 10. 평가 설계
- Train: ~ 2026-06-29
- Holdout: 2026-07-06 ~ 2026-08-24, 8주
- Primary: WAPE = Σ|Actual-Forecast| / ΣActual
- Secondary: MAE, RMSE
- MAPE는 0 수요가 있는 자재에서 왜곡되므로 Primary에서 제외

### 데모 성공 기준 제안
- API 예측 요청 성공
- Holdout 지표가 화면에 표시
- Forecast 길이가 선택 Horizon과 일치
- 실제/예측 차트 렌더링
- Scenario 변화가 비교표/차트에 반영
- MAT-1005처럼 0 수요가 있는 부품에서도 계산 오류 없음
- 데이터 Leakage 없음

주의: “ML이 반드시 특정 WAPE 이하”는 데이터/모델 검증 후 확정한다.

## 11. 시뮬레이션 설계
MVP 기본안:
- 사용자 입력: Scenario Adjustment %
- 범위 권장: -20% ~ +30%
- 결과:
  - Baseline Forecast
  - Scenario Demand
  - 차이 수량
  - 리드타임 기간 예상 누적 수요

Post-MVP:
- 안전재고
- 서비스레벨
- 발주점(ROP)
- 공급 리드타임 변동성

## 12. 화면 정의
### Header
S3 ML 기반 자재 수요 예측 / Demo 배지 / Python API 연결 상태

### Control Panel
- Part dropdown
- Forecast Horizon: 4 / 8 / 12
- Scenario Adjustment slider/input
- Predict 버튼

### KPI
- 최근 4주 평균 수요
- 변동계수
- Forecast 합계
- Holdout WAPE
- Lead Time

### Charts
1. Historical Demand
2. Holdout Actual vs Predicted
3. Future Baseline vs Scenario

### Tables
- Forecast 주차별 결과
- 통계 리포트
- 모델 성능 비교

## 13. API 초안
### GET /api/health
Python backend 상태 확인

### GET /api/parts
선택 가능한 부품 목록

### GET /api/history/{part_id}
과거 수요/재고 이력

### POST /api/forecast
Request:
- part_id
- horizon_weeks
- scenario_adjustment_pct

Response:
- model_name
- metrics
- holdout_actual
- holdout_prediction
- future_forecast
- scenario_forecast
- statistics

코딩 전 API naming은 최종 협의 가능.

## 14. 프로젝트 구조 초안
```
s3-demand-forecast/
  Plan.md
  data/
    scm_demand_history.csv
    train_data.csv
    holdout_test_data.csv
    future_scenario_input.csv
  backend/
    app.py
    model.py
    data_service.py
  frontend/
    index.html
    app.js
    styles.css
  tests/
    test_data.py
    test_model.py
    test_api.py
  requirements.txt
  README.md
```

MVP에서는 파일 수를 더 줄이는 방안도 가능.

## 15. 테스트 전략
P1:
- 데이터 schema 검증
- 시간 분할 검증
- lag feature leakage 검증
- 0 demand 처리
- 음수/결측 입력
- 부품 미존재
- forecast horizon
- WAPE 계산
- API success/failure
- Scenario 계산

P2:
- model serialization
- 동일 seed 재현성
- 응답 속도
- UI 모바일 기본 대응

## 16. 제공 데이터셋
- 5개 부품
- 2024-01부터 2026-08까지 주간 History
- Train/Holdout 분리본
- 12주 Future Scenario 입력
- 계절성, 추세, 변동성, 간헐수요 패턴 포함
- 교육·시연용 Synthetic 데이터이며 실제 SCM 데이터가 아님

## 17. AX 과제 워크벤치 연결안
대상:
`AX_과제_워크벤치.html > 과제 시연 > 2. 시연(Demo)`

Demo 카드:
- 제목: `S3 | ML 기반 자재 수요 예측`
- 설명: `과거 SCM 데이터를 학습한 Python ML 백엔드로 선택 부품의 주간 수요를 예측하고 시나리오를 비교합니다.`
- 버튼 후보:
  - `데모 실행`
  - `시연 가이드`
  - `샘플 데이터`

현재 `file:///C:/.../AX_과제_워크벤치.html`은 이 환경에서 직접 수정하지 않는다.
실제 연결 단계에서는 HTML 파일을 확인한 뒤 기존 Demo 카드 UI 패턴을 유지하여 최소 변경한다.

## 18. 결정 게이트 — 코딩 전 최종 협의
1. Python API Framework: **FastAPI 권장** vs Flask
2. ML MVP: **Gradient Boosting 계열 1종 + Baseline 비교**로 확정할지
3. Forecast 단위: **주간** / 4·8·12주로 확정할지
4. Scenario를 단순 수요 ±%로 시작할지
5. UI를 독립 페이지로 만들고 워크벤치에서 링크할지, 워크벤치 내부 iframe/영역으로 넣을지

## 19. 구현 보류
현재 단계는 Plan + 데이터/테스트 준비까지만 완료한다.
사용자와 위 결정 게이트를 최종 협의하기 전에는 frontend/backend/ML 코드를 구현하지 않는다.
