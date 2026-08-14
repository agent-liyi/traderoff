#!/usr/bin/env python3
"""Build constituent daily advance/decline distributions from Tushare Pro."""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import tushare as ts

DATA_DIR = Path(os.getenv("FEAR_GREED_DATA_DIR", "/workspace/data"))
RAW_DIR = DATA_DIR / "tushare_raw"
OUTPUT_PATH = DATA_DIR / "market_breadth_runtime.json"
REQUEST_INTERVAL = 0.13
INDICES = [
    ("沪深300", "000300.SH"),
    ("中证500", "000905.SH"),
    ("中证1000", "000852.SH"),
    ("中证2000", "932000.CSI"),
    ("中证红利", "000922.CSI"),
    ("创业板指", "399006.SZ"),
    ("科创50", "000688.SH"),
]
BIN_EDGES = list(range(-20, 21, 2))


def retry(name, request, attempts=4):
    for attempt in range(attempts):
        try:
            result = request()
            time.sleep(REQUEST_INTERVAL)
            return result
        except Exception as exc:
            if attempt == attempts - 1:
                raise RuntimeError(f"Tushare {name} failed: {exc}") from exc
            time.sleep(2**attempt)


def latest_open_date(pro):
    now = datetime.now(ZoneInfo("Asia/Shanghai"))
    requested = (now.date() if (now.hour, now.minute) >= (21, 0) else now.date() - timedelta(days=1)).strftime("%Y%m%d")
    frame = retry("trade_cal", lambda: pro.trade_cal(exchange="SSE", end_date=requested, is_open="1", fields="cal_date"))
    if frame.empty:
        raise RuntimeError("No open trading date returned by Tushare")
    return str(frame["cal_date"].max())


def cache_path(category, name):
    path = RAW_DIR / category
    path.mkdir(parents=True, exist_ok=True)
    return path / f"{name}.csv.gz"


def read_cache(path, required):
    if not path.exists():
        return None
    try:
        frame = pd.read_csv(path, dtype={"ts_code": str, "con_code": str, "trade_date": str})
    except (OSError, pd.errors.EmptyDataError, ValueError):
        path.unlink(missing_ok=True)
        return None
    return frame if not frame.empty and required.issubset(frame.columns) else None


def fetch_daily_changes(pro, trade_date):
    path = cache_path("equity_breadth", trade_date)
    frame = read_cache(path, {"ts_code", "trade_date", "pct_chg"})
    if frame is None:
        frame = retry(
            f"daily {trade_date}",
            lambda: pro.daily(trade_date=trade_date, fields="ts_code,trade_date,pct_chg"),
        )
        if frame.empty:
            raise RuntimeError(f"No stock daily data for {trade_date}")
        frame.to_csv(path, index=False, compression="gzip")
    frame["ts_code"] = frame["ts_code"].astype(str)
    frame["pct_chg"] = pd.to_numeric(frame["pct_chg"], errors="coerce")
    is_a_share = frame["ts_code"].str.match(r"^(00|30|60|68)\d{4}\.(SH|SZ)$", na=False)
    frame = frame.loc[is_a_share, ["ts_code", "pct_chg"]].dropna(subset=["pct_chg"])
    if frame.empty:
        raise RuntimeError("No Shanghai or Shenzhen A-share percentage changes available")
    return frame


def fetch_members(pro, code, end_date):
    path = cache_path("breadth_membership", f"{code.replace('.', '_')}_{end_date}")
    frame = read_cache(path, {"con_code"})
    if frame is None:
        start_date = (datetime.strptime(end_date, "%Y%m%d") - timedelta(days=45)).strftime("%Y%m%d")
        frame = retry(
            f"index_weight {code}",
            lambda: pro.index_weight(index_code=code, start_date=start_date, end_date=end_date, fields="con_code,trade_date"),
        )
        if frame.empty:
            raise RuntimeError(f"No index membership snapshot returned for {code}")
        frame["trade_date"] = frame["trade_date"].astype(str)
        snapshot_date = frame["trade_date"].max()
        frame = frame.loc[frame["trade_date"] == snapshot_date, ["con_code", "trade_date"]]
        frame.to_csv(path, index=False, compression="gzip")
    members = set(frame["con_code"].dropna().astype(str))
    snapshot = str(frame["trade_date"].astype(str).max()) if "trade_date" in frame.columns else ""
    if not members:
        raise RuntimeError(f"Empty index membership snapshot for {code}")
    return members, snapshot


def bin_definitions():
    bins = [{"label": "<-20%", "lower": None, "upper": -20}]
    for lower, upper in zip(BIN_EDGES[:-1], BIN_EDGES[1:]):
        bins.append({"label": f"[{lower},{upper})", "lower": lower, "upper": upper})
    bins.append({"label": ">=20%", "lower": 20, "upper": None})
    return bins


def distribution(values):
    counts = []
    for item in bin_definitions():
        if item["lower"] is None:
            count = int((values < item["upper"]).sum())
        elif item["upper"] is None:
            count = int((values >= item["lower"]).sum())
        else:
            count = int(((values >= item["lower"]) & (values < item["upper"])).sum())
        counts.append({"label": item["label"], "count": count})
    if sum(item["count"] for item in counts) != len(values):
        raise RuntimeError("Distribution bins do not reconcile")
    return counts


def build_group(name, code, frame, members=None, snapshot_date=None):
    selected = frame if members is None else frame[frame["ts_code"].isin(members)]
    if selected.empty:
        raise RuntimeError(f"No daily constituent changes available for {name}")
    values = selected["pct_chg"]
    return {
        "name": name,
        "code": code,
        "count": int(len(values)),
        "rise": int((values > 0).sum()),
        "flat": int((values == 0).sum()),
        "fall": int((values < 0).sum()),
        "membershipSnapshot": snapshot_date or None,
        "distribution": distribution(values),
    }


def main():
    pro = ts.pro_api()
    trade_date = latest_open_date(pro)
    print(f"Tushare-only breadth update: {trade_date}", flush=True)
    print("[1/3] 获取A股个股涨跌幅", flush=True)
    daily = fetch_daily_changes(pro, trade_date)
    groups = []
    print("[2/3] 获取主要指数成分股快照", flush=True)
    for name, code in INDICES:
        members, snapshot = fetch_members(pro, code, trade_date)
        group = build_group(name, code, daily, members, snapshot)
        if group["count"] < max(20, len(members) * 0.8):
            raise RuntimeError(f"{name} only has {group['count']}/{len(members)} daily changes")
        groups.append(group)
        print(f"  {name}: {group['count']} 只 (快照 {snapshot})", flush=True)
    print("[3/3] 校验涨跌分布", flush=True)
    if any(group["rise"] + group["flat"] + group["fall"] != group["count"] for group in groups):
        raise RuntimeError("Advance/flat/decline reconciliation failed")
    payload = {
        "asOf": datetime.strptime(trade_date, "%Y%m%d").strftime("%Y-%m-%d"),
        "generatedAt": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"),
        "definition": "使用 Tushare daily.pct_chg 按2个百分点左闭右开区间统计；各指数使用最近可得的 index_weight 成分股快照。",
        "groups": groups,
    }
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    temporary = OUTPUT_PATH.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    temporary.replace(OUTPUT_PATH)
    print(f"完成: {OUTPUT_PATH}", flush=True)


if __name__ == "__main__":
    main()
