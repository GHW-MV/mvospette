from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import Optional, Tuple

import pandas as pd
from fastapi import Depends, FastAPI, HTTPException, Header, Query, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DATA_PATH = BASE_DIR / "data" / "territory_assignments.parquet"
CSV_FALLBACK = BASE_DIR / "data" / "territory_assignments.csv"
API_TOKEN_ENV = "TERRITORY_API_TOKEN"

app = FastAPI(title="Territory Intelligence API", version="0.1.0")
DATA_FRAME: Optional[pd.DataFrame] = None
logger = logging.getLogger("territory_api")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# CORS to allow landing page (mvospette.com) to call app subdomain.
ALLOWED_ORIGINS = [
    "https://mvospette.com",
    "https://app.mvospette.com",
    "http://localhost:8000",
    "http://localhost:8501",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_token() -> str:
    token = os.getenv(API_TOKEN_ENV, "").strip()
    if not token:
        raise RuntimeError(f"Missing API token in env var {API_TOKEN_ENV}")
    return token


def auth_dependency(token: str = Depends(get_token), authorization: str = Header(None)) -> None:
    """Simple bearer token check from Authorization header."""
    provided = ""
    if authorization:
        parts = authorization.split()
        provided = parts[-1] if parts else ""
    if not provided:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing token")
    if provided != token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


@app.middleware("http")
async def log_requests(request, call_next):
    start = time.monotonic()
    response = None
    try:
        response = await call_next(request)
        return response
    finally:
        duration_ms = (time.monotonic() - start) * 1000
        logger.info(
            "request",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status": getattr(response, "status_code", "n/a"),
                "duration_ms": round(duration_ms, 2),
                "client": request.client.host if request.client else "n/a",
            },
        )


def load_data() -> pd.DataFrame:
    if DEFAULT_DATA_PATH.exists():
        return pd.read_parquet(DEFAULT_DATA_PATH)
    if CSV_FALLBACK.exists():
        return pd.read_csv(CSV_FALLBACK)
    raise FileNotFoundError(f"Neither {DEFAULT_DATA_PATH} nor {CSV_FALLBACK} exists.")


def apply_filters(df: pd.DataFrame, zip_prefix: Optional[str], city: Optional[str], state: Optional[str], status_filter: Optional[str]) -> pd.DataFrame:
    filtered = df
    if zip_prefix:
        zp = zip_prefix.strip()
        filtered = filtered[filtered["zip"].astype(str).str.startswith(zp)]
    if city:
        c = city.strip().lower()
        filtered = filtered[filtered["city"].str.lower().str.contains(c)]
    if state:
        s = state.strip().upper()
        filtered = filtered[filtered["state_id"].str.upper() == s]
    if status_filter:
        sf = status_filter.strip().upper()
        filtered = filtered[filtered["owner_status"].fillna("PROSPECTIVE").str.upper() == sf]
    return filtered


def paginate(df: pd.DataFrame, page: int, size: int) -> Tuple[int, pd.DataFrame]:
    total = len(df)
    start = (page - 1) * size
    end = start + size
    return total, df.iloc[start:end]


@app.on_event("startup")
def startup() -> None:
    global DATA_FRAME
    DATA_FRAME = load_data()


@app.get("/health", dependencies=[Depends(auth_dependency)])
def health() -> dict:
    global DATA_FRAME
    count = len(DATA_FRAME) if DATA_FRAME is not None else 0
    return {"status": "ok", "rows": count, "data_path": str(DEFAULT_DATA_PATH)}


@app.get("/assignments")
def assignments(
    zip_prefix: Optional[str] = Query(None, description="ZIP code prefix filter"),
    city: Optional[str] = Query(None, description="Case-insensitive city substring"),
    state: Optional[str] = Query(None, description="State ID (e.g., CA)"),
    status_filter: Optional[str] = Query(None, description="ACTIVE or PROSPECTIVE"),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=500),
    _: None = Depends(auth_dependency),
):
    global DATA_FRAME
    if DATA_FRAME is None:
        raise HTTPException(status_code=500, detail="Data not loaded")
    filtered = apply_filters(DATA_FRAME, zip_prefix, city, state, status_filter)
    total, page_df = paginate(filtered, page, size)
    payload = {
        "total": total,
        "page": page,
        "size": size,
        "items": page_df.to_dict(orient="records"),
    }
    return JSONResponse(payload)


@app.get("/stats")
def stats(_: None = Depends(auth_dependency)) -> dict:
    global DATA_FRAME
    if DATA_FRAME is None:
        raise HTTPException(status_code=500, detail="Data not loaded")
    df = DATA_FRAME
    owned = df["owner_email"].notna().sum()
    total = len(df)
    prospective = total - owned
    return {
        "total": total,
        "owned": int(owned),
        "prospective": int(prospective),
    }


@app.get("/export.csv")
def export_csv(_: None = Depends(auth_dependency)) -> Response:
    if CSV_FALLBACK.exists():
        return FileResponse(CSV_FALLBACK, media_type="text/csv", filename=CSV_FALLBACK.name)
    raise HTTPException(status_code=404, detail="CSV export not found")


@app.get("/export.parquet")
def export_parquet(_: None = Depends(auth_dependency)) -> Response:
    if DEFAULT_DATA_PATH.exists():
        return FileResponse(DEFAULT_DATA_PATH, media_type="application/octet-stream", filename=DEFAULT_DATA_PATH.name)
    raise HTTPException(status_code=404, detail="Parquet export not found")
