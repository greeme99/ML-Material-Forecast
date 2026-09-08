"""예측 모델 계층.

- Baseline: Naive(직전 주), Seasonal Naive(52주 lag, 데이터 부족 시 4주 lag)
- ML: HistGradientBoostingRegressor (scikit-learn)
- Holdout 평가(1-step-ahead) + 미래 Horizon 재귀 예측 + 시나리오 반영
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error

from backend.data_service import (
    FEATURE_COLUMNS,
    TARGET_COLUMN,
    build_statistics,
    prepare_features,
)

# Plan 기준 고정 Holdout 시작일. 데이터가 이 구간을 만족하지 못하면 마지막 N주로 대체.
PLANNED_HOLDOUT_START = pd.Timestamp("2026-07-06")
DEFAULT_HOLDOUT_WEEKS = 8
MIN_TRAIN_ROWS = 20
RANDOM_STATE = 42


class ForecastError(Exception):
    """예측 수행 불가."""


def compute_wape(y_true, y_pred):
    """WAPE = Sum|Actual-Forecast| / Sum Actual. 분모 0이면 정의 불가(None)."""
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    denom = float(np.sum(y_true))
    if denom == 0:
        return None
    return float(np.sum(np.abs(y_true - y_pred)) / denom)


def calculate_metrics(y_true, y_pred) -> dict:
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    wape = compute_wape(y_true, y_pred)
    rmse = float(np.sqrt(mean_squared_error(y_true, y_pred)))
    return {
        "WAPE": round(wape, 4) if wape is not None else None,
        "MAE": round(float(mean_absolute_error(y_true, y_pred)), 4),
        "RMSE": round(rmse, 4),
    }


def _split_train_holdout(df: pd.DataFrame):
    """시간 기반 분할. Plan 고정일을 우선 적용하고, 불가하면 마지막 8주로 대체."""
    train = df[df["week_start"] < PLANNED_HOLDOUT_START]
    holdout = df[df["week_start"] >= PLANNED_HOLDOUT_START]

    if len(train) >= MIN_TRAIN_ROWS and len(holdout) > 0:
        return train, holdout, PLANNED_HOLDOUT_START.strftime("%Y-%m-%d"), "planned"

    if len(df) < MIN_TRAIN_ROWS + 1:
        raise ForecastError(
            f"학습에 필요한 최소 데이터가 부족합니다(유효 {len(df)}주, 최소 {MIN_TRAIN_ROWS + 1}주)."
        )

    n_holdout = min(DEFAULT_HOLDOUT_WEEKS, max(1, len(df) - MIN_TRAIN_ROWS))
    train = df.iloc[:-n_holdout]
    holdout = df.iloc[-n_holdout:]
    start = holdout["week_start"].min().strftime("%Y-%m-%d")
    return train, holdout, start, "fallback_last_n_weeks"


def _seasonal_lag(n_rows: int) -> int:
    """데이터 길이에 맞는 계절 lag(52주 우선, 부족 시 4주)."""
    return 52 if n_rows > 52 + DEFAULT_HOLDOUT_WEEKS else 4


def generate_forecast(
    df_part: pd.DataFrame,
    horizon_weeks: int,
    scenario_adjustment_pct: float,
    lead_time_days=None,
) -> dict:
    if horizon_weeks not in (4, 8, 12):
        raise ForecastError("horizon_weeks는 4, 8, 12 중 하나여야 합니다.")
    if not -100 <= scenario_adjustment_pct <= 100:
        raise ForecastError("scenario_adjustment_pct는 -100 ~ 100 범위여야 합니다.")

    raw = df_part.sort_values("week_start").reset_index(drop=True)
    df = prepare_features(raw)
    if len(df) < MIN_TRAIN_ROWS + 1:
        raise ForecastError(
            f"Feature 생성 후 데이터가 부족합니다(유효 {len(df)}주, 최소 {MIN_TRAIN_ROWS + 1}주)."
        )

    train_df, holdout_df, holdout_start, split_mode = _split_train_holdout(df)
    holdout_df = holdout_df.copy()

    # --- Baseline 1: Naive (직전 주 실적) = lag_1
    holdout_df["naive_pred"] = holdout_df["lag_1"]

    # --- Baseline 2: Seasonal Naive (s주 전 실적)
    s = _seasonal_lag(len(df))
    seasonal = df[TARGET_COLUMN].shift(s)
    holdout_df["seasonal_pred"] = seasonal.loc[holdout_df.index].fillna(
        holdout_df["naive_pred"]
    )

    # --- ML 모델: Train 구간만 학습 (미래 데이터 미사용)
    model = HistGradientBoostingRegressor(random_state=RANDOM_STATE)
    model.fit(train_df[FEATURE_COLUMNS], train_df[TARGET_COLUMN])
    holdout_df["ml_pred"] = np.maximum(0.0, model.predict(holdout_df[FEATURE_COLUMNS]))

    y_true = holdout_df[TARGET_COLUMN]
    metrics = {
        "naive": calculate_metrics(y_true, holdout_df["naive_pred"]),
        "seasonal_naive": calculate_metrics(y_true, holdout_df["seasonal_pred"]),
        "ml": calculate_metrics(y_true, holdout_df["ml_pred"]),
    }

    # 최종 모델은 전체 유효 구간으로 재학습(예측 시점 기준 최신 정보 반영)
    final_model = HistGradientBoostingRegressor(random_state=RANDOM_STATE)
    final_model.fit(df[FEATURE_COLUMNS], df[TARGET_COLUMN])

    future = _forecast_future(df, final_model, horizon_weeks, scenario_adjustment_pct, s)

    statistics = build_statistics(raw)
    lt_days = int(lead_time_days) if lead_time_days else int(raw["lead_time_days"].iloc[-1])
    lt_weeks = max(1, int(np.ceil(lt_days / 7)))
    lt_cum = float(sum(f["scenario"] for f in future[:lt_weeks]))

    best = min(
        (k for k in metrics if metrics[k]["WAPE"] is not None),
        key=lambda k: metrics[k]["WAPE"],
        default="ml",
    )

    return {
        "part_id": str(raw["part_id"].iloc[0]),
        "part_name": str(raw["part_name"].iloc[0]),
        "model_name": "HistGradientBoostingRegressor",
        "evaluation": {
            "holdout_start": holdout_start,
            "holdout_weeks": int(len(holdout_df)),
            "train_weeks": int(len(train_df)),
            "split_mode": split_mode,
            "seasonal_lag_weeks": s,
            "primary_metric": "WAPE",
            "best_model": best,
            "note": "Holdout 지표는 실적 lag를 사용하는 1-step-ahead 기준이며, 미래 예측은 재귀(다단계) 방식이라 오차가 더 커질 수 있습니다.",
        },
        "metrics": metrics,
        # 하위 호환(기존 프런트 키)
        "ml_metrics": metrics["ml"],
        "baseline_metrics": metrics["naive"],
        "holdout": {
            "dates": holdout_df["week_start"].dt.strftime("%Y-%m-%d").tolist(),
            "actual": [float(v) for v in holdout_df[TARGET_COLUMN]],
            "baseline": [float(v) for v in holdout_df["naive_pred"]],
            "seasonal": [float(v) for v in holdout_df["seasonal_pred"]],
            "ml_pred": [float(v) for v in holdout_df["ml_pred"]],
        },
        "future": future,
        "scenario": {
            "adjustment_pct": float(scenario_adjustment_pct),
            "baseline_sum": round(float(sum(f["forecast"] for f in future)), 2),
            "scenario_sum": round(float(sum(f["scenario"] for f in future)), 2),
            "diff_qty": round(float(sum(f["scenario"] - f["forecast"] for f in future)), 2),
            "lead_time_days": lt_days,
            "lead_time_weeks": lt_weeks,
            "lead_time_cumulative_demand": round(lt_cum, 2),
        },
        "statistics": statistics,
    }


def _forecast_future(
    df: pd.DataFrame,
    model,
    horizon_weeks: int,
    scenario_adjustment_pct: float,
    seasonal_lag: int,
) -> list:
    """재귀 예측: 예측값을 다시 lag feature로 넣어 Horizon 만큼 진행."""
    history = [float(v) for v in df[TARGET_COLUMN].values]
    last_week = df["week_start"].max()
    future_dates = [last_week + pd.Timedelta(days=7 * (i + 1)) for i in range(horizon_weeks)]
    factor = 1.0 + scenario_adjustment_pct / 100.0

    out = []
    for dt in future_dates:
        row = {
            "lag_1": history[-1],
            "lag_2": history[-2],
            "lag_4": history[-4],
            "lag_8": history[-8],
            "rolling_mean_4": float(np.mean(history[-4:])),
            "rolling_mean_8": float(np.mean(history[-8:])),
            "rolling_std_4": float(np.std(history[-4:], ddof=1)),
            "month": dt.month,
            "week_of_year": int(dt.isocalendar().week),
        }
        x = pd.DataFrame([row], columns=FEATURE_COLUMNS)
        pred = float(max(0.0, model.predict(x)[0]))

        seasonal_ref = history[-seasonal_lag] if len(history) >= seasonal_lag else history[-1]
        out.append(
            {
                "week_start": dt.strftime("%Y-%m-%d"),
                "baseline": round(history[-1], 2),
                "seasonal_naive": round(float(seasonal_ref), 2),
                "forecast": round(pred, 2),
                "scenario": round(pred * factor, 2),
            }
        )
        history.append(pred)

    return out
