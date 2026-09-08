"""데이터 로딩 및 Feature 생성 계층.

- 엑셀 원천(SCM_History)을 읽어 정렬/타입 정규화 및 데이터 계약 검증
- ML 학습용 lag / rolling feature 생성 (Leakage 방지)
- 화면용 기초 통계 산출
"""

from __future__ import annotations

import os
from functools import lru_cache

import pandas as pd

# 실행 위치(cwd)와 무관하게 동작하도록 프로젝트 루트 기준 절대경로 사용
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_FILE = os.path.join(PROJECT_ROOT, "S3_ML_자재수요예측_개발테스트데이터.xlsx")
SHEET_NAME = "SCM_History"

REQUIRED_COLUMNS = [
    "week_start",
    "part_id",
    "part_name",
    "lead_time_days",
    "production_plan_qty",
    "demand_qty",
]

FEATURE_COLUMNS = [
    "lag_1",
    "lag_2",
    "lag_4",
    "lag_8",
    "rolling_mean_4",
    "rolling_mean_8",
    "rolling_std_4",
    "month",
    "week_of_year",
]
TARGET_COLUMN = "demand_qty"


class DataError(Exception):
    """원천 데이터 계약 위반."""


@lru_cache(maxsize=1)
def load_data() -> pd.DataFrame:
    """원천 데이터를 로드하고 데이터 계약을 검증한다(1회 캐시)."""
    if not os.path.exists(DATA_FILE):
        raise DataError(f"데이터 파일을 찾을 수 없습니다: {DATA_FILE}")

    df = pd.read_excel(DATA_FILE, sheet_name=SHEET_NAME)

    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise DataError(f"필수 컬럼 누락: {', '.join(missing)}")

    df["week_start"] = pd.to_datetime(df["week_start"], errors="coerce")
    if df["week_start"].isna().any():
        raise DataError("week_start에 유효하지 않은 날짜가 있습니다.")

    if df["part_id"].isna().any() or (df["part_id"].astype(str).str.strip() == "").any():
        raise DataError("part_id가 비어 있는 행이 있습니다.")

    if (df[TARGET_COLUMN] < 0).any():
        raise DataError("demand_qty에 음수가 있습니다.")

    dup = int(df.duplicated(subset=["part_id", "week_start"]).sum())
    if dup:
        raise DataError(f"part_id+week_start 중복 {dup}건이 있습니다.")

    return df.sort_values(["part_id", "week_start"]).reset_index(drop=True)


def get_parts() -> list:
    df = load_data()
    cols = ["part_id", "part_name", "lead_time_days"]
    return df[cols].drop_duplicates().to_dict(orient="records")


def get_part_frame(part_id: str) -> pd.DataFrame:
    df = load_data()
    return df[df["part_id"] == part_id].copy()


def get_history(part_id: str) -> list:
    df_part = get_part_frame(part_id)
    if df_part.empty:
        return []
    out = df_part.copy()
    out["week_start"] = out["week_start"].dt.strftime("%Y-%m-%d")
    return out.to_dict(orient="records")


def prepare_features(df_part: pd.DataFrame) -> pd.DataFrame:
    """lag / rolling feature 생성.

    모든 파생값은 shift(1) 이후 계산하므로 당주(t) 실적이 feature에 들어가지 않는다
    (Leakage 방지). feature/target에 결측이 있는 행만 제거한다.
    """
    df = df_part.sort_values("week_start").copy()
    prev = df[TARGET_COLUMN].shift(1)

    df["lag_1"] = prev
    df["lag_2"] = df[TARGET_COLUMN].shift(2)
    df["lag_4"] = df[TARGET_COLUMN].shift(4)
    df["lag_8"] = df[TARGET_COLUMN].shift(8)
    df["rolling_mean_4"] = prev.rolling(window=4).mean()
    df["rolling_mean_8"] = prev.rolling(window=8).mean()
    df["rolling_std_4"] = prev.rolling(window=4).std()
    df["month"] = df["week_start"].dt.month
    df["week_of_year"] = df["week_start"].dt.isocalendar().week.astype(int)

    # 전체 컬럼이 아니라 feature+target 기준으로만 결측 제거
    return df.dropna(subset=FEATURE_COLUMNS + [TARGET_COLUMN]).reset_index(drop=True)


def build_statistics(df_part: pd.DataFrame) -> dict:
    """화면 통계 리포트용 기초 통계."""
    s = df_part.sort_values("week_start")[TARGET_COLUMN].astype(float)
    mean = float(s.mean()) if len(s) else 0.0
    std = float(s.std(ddof=1)) if len(s) > 1 else 0.0

    def tail_mean(n: int) -> float:
        return float(s.tail(n).mean()) if len(s) else 0.0

    return {
        "weeks": int(len(s)),
        "mean": round(mean, 2),
        "std": round(std, 2),
        "cv": round(std / mean, 4) if mean > 0 else None,
        "recent_4w_avg": round(tail_mean(4), 2),
        "recent_8w_avg": round(tail_mean(8), 2),
        "recent_12w_avg": round(tail_mean(12), 2),
        "zero_demand_weeks": int((s == 0).sum()),
        "max": float(s.max()) if len(s) else 0.0,
        "min": float(s.min()) if len(s) else 0.0,
    }
