from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.portfolio import BenchmarkOut, BenchmarkSeries, PerformanceOut
from app.services.benchmark_service import BENCHMARKS, benchmark_service
from app.services.performance_service import VALID_RANGES, performance_service

router = APIRouter(prefix="/api/performance", tags=["performance"])


@router.get("/benchmarks", response_model=list[BenchmarkOut])
def list_benchmarks():
    return [BenchmarkOut(key=b.key, label=b.label) for b in benchmark_service.list_benchmarks()]


@router.get("", response_model=PerformanceOut)
def get_performance(
    portfolio_id: int,
    range: str = "YTD",
    benchmarks: str | None = Query(default=None, description="Comma-separated benchmark keys"),
    db: Session = Depends(get_db),
):
    if range not in VALID_RANGES:
        raise HTTPException(status_code=400, detail=f"range must be one of {VALID_RANGES}")

    result = performance_service.get_range(db, portfolio_id, range)

    requested = [k for k in (benchmarks or "").split(",") if k]
    unknown = [k for k in requested if k not in BENCHMARKS]
    if unknown:
        raise HTTPException(status_code=400, detail=f"unknown benchmark(s): {unknown}")

    if requested and result["points"]:
        start = result["points"][0]["date"]
        end = result["points"][-1]["date"]
        result["benchmarks"] = [
            BenchmarkSeries(
                key=key,
                label=BENCHMARKS[key].label,
                points=[{"date": d, "value": v} for d, v in benchmark_service.get_series(db, key, start, end)],
            )
            for key in requested
        ]

    return result
