#!/usr/bin/env python3
"""Build Tushare-only index and constituent cross-sectional volatility data."""

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
OUTPUT_PATH = DATA_DIR / "market_volatility_runtime.json"
LOOKBACK = 250
INDEX_WINDOW = 20
CROSS_SECTION_WINDOW = 5
REQUEST_INTERVAL = 0.13
INDEX_UNIVERSE = [
    ("沪深300", "000300.SH"),
    ("中证500", "000905.SH"),
    ("中证1000", "000852.SH"),
    ("中证2000", "932000.CSI"),
    ("中证红利", "000922.CSI"),
    ("创业板指", "399006.SZ"),
    ("科创50", "000688.SH"),
]
INDEX_SERIES = INDEX_UNIVERSE
CROSS_SECTION = INDEX_UNIVERSE


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
    calendar = retry("trade_cal", lambda: pro.trade_cal(exchange="SSE", end_date=requested, is_open="1", fields="cal_date"))
    if calendar.empty:
        raise RuntimeError("No open trading date returned by Tushare")
    return str(calendar["cal_date"].max())


def trade_dates(pro, end_date):
    start = (datetime.strptime(end_date, "%Y%m%d") - timedelta(days=450)).strftime("%Y%m%d")
    calendar = retry("trade_cal", lambda: pro.trade_cal(exchange="SSE", start_date=start, end_date=end_date, is_open="1", fields="cal_date"))
    dates = sorted(calendar["cal_date"].astype(str).tolist())
    if len(dates) < LOOKBACK + INDEX_WINDOW:
        raise RuntimeError(f"Need at least {LOOKBACK + INDEX_WINDOW} open days, got {len(dates)}")
    return dates


def cache_path(date):
    path = RAW_DIR / "equity_daily_volatility"
    path.mkdir(parents=True, exist_ok=True)
    return path / f"{date}.csv.gz"


def fetch_daily_returns(pro, dates):
    frames = []
    for index, date in enumerate(dates, 1):
        path = cache_path(date)
        frame = None
        if path.exists():
            try:
                frame = pd.read_csv(path, dtype={"ts_code": str, "trade_date": str})
            except (OSError, pd.errors.EmptyDataError, ValueError):
                path.unlink(missing_ok=True)
        if frame is None or frame.empty or "pct_chg" not in frame.columns:
            frame = retry(
                f"daily {date}",
                lambda date=date: pro.daily(trade_date=date, fields="ts_code,trade_date,pct_chg"),
            )
            if frame.empty:
                raise RuntimeError(f"No daily return data for {date}")
            frame.to_csv(path, index=False, compression="gzip")
        frames.append(frame[["ts_code", "trade_date", "pct_chg"]])
        if index % 50 == 0 or index == len(dates):
            print(f"  股票日收益率 {index}/{len(dates)}", flush=True)
    data = pd.concat(frames, ignore_index=True)
    data["trade_date"] = data["trade_date"].astype(str)
    data["pct_chg"] = pd.to_numeric(data["pct_chg"], errors="coerce")
    return data[data["ts_code"].str.endswith((".SH", ".SZ"), na=False)].dropna(subset=["pct_chg"])


def month_windows(start_date, end_date):
    current = datetime.strptime(start_date, "%Y%m%d").replace(day=1)
    end = datetime.strptime(end_date, "%Y%m%d")
    while current <= end:
        next_month = (current.replace(day=28) + timedelta(days=4)).replace(day=1)
        yield current.strftime("%Y%m%d"), min(next_month - timedelta(days=1), end).strftime("%Y%m%d")
        current = next_month


def fetch_memberships(pro, start_date, end_date):
    snapshots = {}
    monthly_start = (datetime.strptime(start_date, "%Y%m%d") - timedelta(days=40)).strftime("%Y%m%d")
    for name, code in CROSS_SECTION:
        frames = []
        for window_start, window_end in month_windows(monthly_start, end_date):
            frame = retry(
                f"index_weight {code} {window_start}-{window_end}",
                lambda code=code, window_start=window_start, window_end=window_end: pro.index_weight(
                    index_code=code,
                    start_date=window_start,
                    end_date=window_end,
                    fields="index_code,con_code,trade_date,weight",
                ),
            )
            if not frame.empty:
                frames.append(frame)
        if not frames:
            raise RuntimeError(f"No membership snapshots returned for {name}")
        combined = pd.concat(frames, ignore_index=True).drop_duplicates(subset=["con_code", "trade_date"])
        combined["trade_date"] = combined["trade_date"].astype(str)
        snapshots[code] = {date: set(day["con_code"].astype(str)) for date, day in combined.groupby("trade_date")}
        prior = [date for date in snapshots[code] if date <= start_date]
        if not prior:
            raise RuntimeError(f"No {name} membership snapshot on or before {start_date}")
        print(f"  {name} 成分快照 {len(snapshots[code])} 个", flush=True)
    return snapshots


def active_members(snapshots, code, date):
    options = [snapshot_date for snapshot_date in snapshots[code] if snapshot_date <= date]
    if not options:
        raise RuntimeError(f"No membership snapshot for {code} on {date}")
    return snapshots[code][max(options)]


def index_volatility(pro, start_date, end_date):
    results = []
    for name, code in INDEX_SERIES:
        frame = retry(
            name,
            lambda code=code: pro.index_daily(ts_code=code, start_date=start_date, end_date=end_date, fields="ts_code,trade_date,close"),
        )
        frame["trade_date"] = frame["trade_date"].astype(str)
        frame["close"] = pd.to_numeric(frame["close"], errors="coerce")
        frame = frame.dropna().sort_values("trade_date").drop_duplicates("trade_date")
        returns = frame["close"].pct_change()
        frame["volatility"] = returns.rolling(INDEX_WINDOW).std(ddof=1) * (252**0.5) * 100
        frame = frame.dropna(subset=["volatility"]).tail(LOOKBACK)
        if len(frame) != LOOKBACK:
            raise RuntimeError(f"{name} only has {len(frame)} volatility points")
        results.append({
            "name": name,
            "code": code,
            "history": [
                {"date": datetime.strptime(row.trade_date, "%Y%m%d").strftime("%Y-%m-%d"), "value": round(float(row.volatility), 4)}
                for row in frame.itertuples()
            ],
        })
        print(f"  {name} 指数波动率 {len(frame)} 点", flush=True)
    return results


def cross_section_volatility(daily, snapshots, dates):
    rows = []
    for date, day in daily.groupby("trade_date", sort=True):
        members = {code: active_members(snapshots, code, date) for _, code in CROSS_SECTION}
        values = {}
        for name, code in CROSS_SECTION:
            selected = day.loc[day["ts_code"].isin(members[code]), "pct_chg"]
            if len(selected) < max(20, len(members[code]) * 0.8):
                raise RuntimeError(f"{name} has only {len(selected)}/{len(members[code])} valid returns on {date}")
            values[code] = float(selected.std(ddof=1))
        rows.append({"date": date, **values})
    frame = pd.DataFrame(rows).sort_values("date")
    result = []
    for name, code in CROSS_SECTION:
        smoothed = frame[code].rolling(CROSS_SECTION_WINDOW).mean()
        selected = pd.DataFrame({"date": frame["date"], "value": smoothed}).dropna().tail(LOOKBACK)
        if len(selected) != LOOKBACK:
            raise RuntimeError(f"{name} only has {len(selected)} cross-sectional points")
        result.append({
            "name": name,
            "code": code,
            "history": [
                {"date": datetime.strptime(row.date, "%Y%m%d").strftime("%Y-%m-%d"), "value": round(float(row.value), 4)}
                for row in selected.itertuples()
            ],
        })
        print(f"  {name} 截面波动率 {len(selected)} 点", flush=True)
    return result


def main():
    pro = ts.pro_api()
    end_date = latest_open_date(pro)
    dates = trade_dates(pro, end_date)
    start_date = dates[0]
    print(f"Tushare-only volatility update: {start_date} - {end_date} ({len(dates)} days)", flush=True)
    print("[1/3] 获取指数日线并计算20日年化波动率", flush=True)
    index_data = index_volatility(pro, start_date, end_date)
    print("[2/3] 获取成分股日收益率和月度成分", flush=True)
    daily = fetch_daily_returns(pro, dates)
    snapshots = fetch_memberships(pro, start_date, end_date)
    print("[3/3] 计算5日移动平均成分股截面波动率", flush=True)
    cross_data = cross_section_volatility(daily, snapshots, dates)
    payload = {
        "asOf": index_data[0]["history"][-1]["date"],
        "generatedAt": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"),
        "indexWindow": INDEX_WINDOW,
        "crossSectionWindow": CROSS_SECTION_WINDOW,
        "indexVolatility": index_data,
        "crossSectionVolatility": cross_data,
    }
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    temporary = OUTPUT_PATH.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    temporary.replace(OUTPUT_PATH)
    print(f"完成: {OUTPUT_PATH}", flush=True)


if __name__ == "__main__":
    main()
