import asyncio
from app.services.backtest_engine import run_backtest
import json

result = run_backtest("RELIANCE", 20, "2016-03-01", "2025-01-01", "1D")
import math

def find_nans(obj, path=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            find_nans(v, path + f".{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            find_nans(v, path + f"[{i}]")
    elif isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            print(f"NaN or Inf found at {path}: {obj}")

find_nans(result)
