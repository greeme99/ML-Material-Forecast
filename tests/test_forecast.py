"""P1 테스트 — Plan.md 15장 / 데이터셋 Test_Cases 시트 기준.

실행: (프로젝트 루트에서) pytest -q
"""

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend.app import app
from backend.data_service import (
    FEATURE_COLUMNS,
    REQUIRED_COLUMNS,
    build_statistics,
    get_part_frame,
    get_parts,
    load_data,
    prepare_features,
)
from backend.model import (
    PLANNED_HOLDOUT_START,
    ForecastError,
    compute_wape,
    generate_forecast,
)

client = TestClient(app)


# --- 데이터 계약 (TC: schema / 품질) ----------------------------------------
def test_schema_and_quality():
    df = load_data()
    assert set(REQUIRED_COLUMNS).issubset(df.columns)
    assert df["week_start"].notna().all()
    assert (df["demand_qty"] >= 0).all()
    assert not df.duplicated(subset=["part_id", "week_start"]).any()


def test_parts_list():
    parts = get_parts()
    assert len(parts) == 5
    assert {"part_id", "part_name", "lead_time_days"} <= set(parts[0])


# --- Feature / Leakage (TC02) ------------------------------------------------
def test_features_have_no_leakage():
    """lag/rolling은 모두 t-1 이하 정보만 사용해야 한다."""
    df = prepare_features(get_part_frame("MAT-1001"))
    raw = get_part_frame("MAT-1001").sort_values("week_start").reset_index(drop=True)
    demand = raw["demand_qty"].tolist()
    offset = len(raw) - len(df)
    for i in range(len(df)):
        t = i + offset
        assert df["lag_1"].iloc[i] == demand[t - 1]
        assert df["rolling_mean_4"].iloc[i] == pytest.approx(np.mean(demand[t - 4 : t]))
    assert set(FEATURE_COLUMNS).issubset(df.columns)


def test_time_split_excludes_future_from_train():
    df = prepare_features(get_part_frame("MAT-1001"))
    res = generate_forecast(get_part_frame("MAT-1001"), 8, 0)
    assert res["evaluation"]["holdout_start"] == PLANNED_HOLDOUT_START.strftime("%Y-%m-%d")
    assert res["evaluation"]["holdout_weeks"] == 8
    assert res["evaluation"]["train_weeks"] == len(
        df[df["week_start"] < PLANNED_HOLDOUT_START]
    )


# --- 지표 (WAPE) -------------------------------------------------------------
def test_wape_calculation():
    assert compute_wape([100, 100], [90, 120]) == pytest.approx(30 / 200)
    assert compute_wape([0, 0], [1, 2]) is None  # 분모 0은 정의 불가


def test_zero_demand_part_does_not_crash():
    """MAT-1005: 간헐 수요(0 포함) 부품에서도 계산 오류가 없어야 한다."""
    res = generate_forecast(get_part_frame("MAT-1005"), 12, 0)
    assert all(f["forecast"] >= 0 for f in res["future"])
    assert build_statistics(get_part_frame("MAT-1005"))["zero_demand_weeks"] > 0


def test_baseline_is_always_reported():
    res = generate_forecast(get_part_frame("MAT-1002"), 4, 0)
    assert {"naive", "seasonal_naive", "ml"} == set(res["metrics"])


# --- Horizon / Scenario (TC03, TC 시나리오) ----------------------------------
@pytest.mark.parametrize("horizon", [4, 8, 12])
def test_forecast_horizon_length(horizon):
    res = generate_forecast(get_part_frame("MAT-1003"), horizon, 0)
    assert len(res["future"]) == horizon
    weeks = pd.to_datetime([f["week_start"] for f in res["future"]])
    assert (weeks.to_series().diff().dropna() == pd.Timedelta(days=7)).all()


def test_invalid_horizon_rejected():
    with pytest.raises(ForecastError):
        generate_forecast(get_part_frame("MAT-1001"), 5, 0)


def test_scenario_applies_pct():
    res = generate_forecast(get_part_frame("MAT-1001"), 4, 20)
    for f in res["future"]:
        assert f["scenario"] == pytest.approx(f["forecast"] * 1.2, abs=0.02)
    assert res["scenario"]["diff_qty"] > 0


def test_scenario_zero_is_identity():
    res = generate_forecast(get_part_frame("MAT-1001"), 4, 0)
    assert res["scenario"]["diff_qty"] == pytest.approx(0, abs=0.05)


def test_reproducible_with_fixed_seed():
    a = generate_forecast(get_part_frame("MAT-1004"), 8, 0)["future"]
    b = generate_forecast(get_part_frame("MAT-1004"), 8, 0)["future"]
    assert a == b


# --- API ---------------------------------------------------------------------
def test_api_health():
    r = client.get("/api/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_api_parts_and_history():
    assert len(client.get("/api/parts").json()["parts"]) == 5
    assert len(client.get("/api/history/MAT-1001").json()["history"]) > 100
    assert client.get("/api/history/NOPE").status_code == 404


def test_api_forecast_success_and_failure():
    ok = client.post(
        "/api/forecast",
        json={"part_id": "MAT-1001", "horizon_weeks": 8, "scenario_adjustment_pct": -10},
    )
    assert ok.status_code == 200
    assert len(ok.json()["future"]) == 8

    assert client.post("/api/forecast", json={"part_id": "NOPE"}).status_code == 404
    assert (
        client.post(
            "/api/forecast", json={"part_id": "MAT-1001", "horizon_weeks": 5}
        ).status_code
        == 400
    )
    assert (
        client.post(
            "/api/forecast",
            json={"part_id": "MAT-1001", "scenario_adjustment_pct": 500},
        ).status_code
        == 422
    )
