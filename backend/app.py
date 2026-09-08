"""S3 ML 기반 자재 수요 예측 — FastAPI 진입점.

실행: (프로젝트 루트에서) uvicorn backend.app:app --reload --port 8000
화면: http://127.0.0.1:8000/
"""

from __future__ import annotations

import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from backend.data_service import (
    DataError,
    get_history,
    get_part_frame,
    get_parts,
    load_data,
)
from backend.model import ForecastError, generate_forecast

app = FastAPI(title="S3 Demand Forecast API", version="0.2.0")

# 데모용: 로컬 정적 페이지/워크벤치 HTML에서의 호출 허용
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ForecastRequest(BaseModel):
    part_id: str
    horizon_weeks: int = Field(default=4, description="4 / 8 / 12 중 하나")
    scenario_adjustment_pct: float = Field(default=0.0, ge=-100, le=100)


@app.get("/api/health")
def health_check():
    try:
        df = load_data()
    except DataError as exc:
        return {"status": "degraded", "detail": str(exc)}
    return {
        "status": "ok",
        "rows": int(len(df)),
        "parts": int(df["part_id"].nunique()),
        "last_week": df["week_start"].max().strftime("%Y-%m-%d"),
    }


@app.get("/api/parts")
def api_get_parts():
    try:
        return {"parts": get_parts()}
    except DataError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/history/{part_id}")
def api_get_history(part_id: str):
    try:
        history = get_history(part_id)
    except DataError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    if not history:
        raise HTTPException(status_code=404, detail=f"부품을 찾을 수 없습니다: {part_id}")
    return {"history": history}


@app.post("/api/forecast")
def api_forecast(req: ForecastRequest):
    try:
        df_part = get_part_frame(req.part_id)
    except DataError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    if df_part.empty:
        raise HTTPException(status_code=404, detail=f"부품을 찾을 수 없습니다: {req.part_id}")

    try:
        return generate_forecast(df_part, req.horizon_weeks, req.scenario_adjustment_pct)
    except ForecastError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


# 프런트엔드 정적 서빙 (API 라우트 등록 이후에 마운트)
_frontend_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
if os.path.isdir(_frontend_dir):
    app.mount("/", StaticFiles(directory=_frontend_dir, html=True), name="frontend")
