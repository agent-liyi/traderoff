#!/usr/bin/env python3
"""Build the A-share Fear & Greed Index from Tushare-only raw data.

The script caches high-volume daily responses under /workspace/data/tushare_raw
and writes the website-ready series to /workspace/data/fear_greed_runtime.json.
"""

from __future__ import annotations

import argparse
import math
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import tushare as ts
from scipy.stats import norm

DATA_DIR = Path(os.getenv("FEAR_GREED_DATA_DIR", "/workspace/data"))
RAW_DIR = DATA_DIR / "tushare_raw"
OUTPUT_PATH = DATA_DIR / "fear_greed_runtime.json"
LOOKBACK = 250
REQUEST_INTERVAL = 0.13


def retry(name, request, attempts=4):
    for attempt in range(attempts):
        try:
            result = request()
            time.sleep(REQUEST_INTERVAL)
            return result
        except Exception as exc:
            if attempt == attempts - 1:
                raise RuntimeError(f"Tushare {name} failed: {exc}") from exc
            time.sleep(2 ** attempt)


def latest_open_date(pro, requested=None):
    if requested is None:
        now = datetime.now(ZoneInfo("Asia/Shanghai"))
        available_date = now.date() if (now.hour, now.minute) >= (21, 0) else now.date() - timedelta(days=1)
        requested = available_date.strftime("%Y%m%d")
    cal = retry("trade_cal", lambda: pro.trade_cal(exchange="SSE", end_date=requested, is_open="1", fields="cal_date"))
    if cal.empty:
        raise RuntimeError("No open trading date returned by Tushare")
    return str(cal["cal_date"].max())


def trading_dates(pro, start, end):
    cal = retry(
        "trade_cal",
        lambda: pro.trade_cal(exchange="SSE", start_date=start, end_date=end, is_open="1", fields="cal_date"),
    )
    return sorted(cal["cal_date"].astype(str).tolist())


def cache_path(category, date):
    path = RAW_DIR / category
    path.mkdir(parents=True, exist_ok=True)
    return path / f"{date}.csv.gz"


def fetch_equity_daily(pro, dates):
    frames = []
    for index, date in enumerate(dates, 1):
        path = cache_path("equity_daily", date)
        if path.exists():
            frame = pd.read_csv(path, dtype={"ts_code": str, "trade_date": str})
        else:
            frame = pd.DataFrame()
        if frame.empty or "vol" not in frame.columns:
            frame = retry(
                f"daily {date}",
                lambda date=date: pro.daily(
                    trade_date=date,
                    fields="ts_code,trade_date,high,close,vol,amount",
                ),
            )
            if frame.empty:
                continue
            frame.to_csv(path, index=False, compression="gzip")
        frames.append(frame)
        if index % 50 == 0 or index == len(dates):
            print(f"  股票日线 {index}/{len(dates)}", flush=True)
    if not frames:
        raise RuntimeError("No equity daily data available")
    data = pd.concat(frames, ignore_index=True)
    data["trade_date"] = data["trade_date"].astype(str)
    return data


def fetch_option_daily(pro, dates):
    frames = []
    missing = []
    for date in dates:
        path = cache_path("option_daily", date)
        if path.exists():
            frames.append(pd.read_csv(path, dtype={"ts_code": str, "trade_date": str}))
        else:
            missing.append(date)

    # One call can safely carry about eight option trading days under Tushare row limits.
    for offset in range(0, len(missing), 8):
        batch = missing[offset:offset + 8]
        frame = retry(
            f"opt_daily {batch[0]}-{batch[-1]}",
            lambda batch=batch: pro.opt_daily(
                exchange="SSE", start_date=batch[0], end_date=batch[-1],
                fields="ts_code,trade_date,close,settle",
            ),
        )
        if not frame.empty:
            frame["trade_date"] = frame["trade_date"].astype(str)
            for date, day in frame.groupby("trade_date"):
                day.to_csv(cache_path("option_daily", date), index=False, compression="gzip")
                frames.append(day)
        print(f"  期权日线 {min(offset + 8, len(missing))}/{len(missing)} 个缺失日", flush=True)

    if not frames:
        raise RuntimeError("No option daily data available")
    return pd.concat(frames, ignore_index=True)


def bs_price(spot, strike, years, rate, sigma, call_put):
    if years <= 0 or sigma <= 0:
        return max(spot - strike, 0) if call_put == "C" else max(strike - spot, 0)
    root_t = math.sqrt(years)
    d1 = (math.log(spot / strike) + (rate + 0.5 * sigma * sigma) * years) / (sigma * root_t)
    d2 = d1 - sigma * root_t
    if call_put == "C":
        return spot * norm.cdf(d1) - strike * math.exp(-rate * years) * norm.cdf(d2)
    return strike * math.exp(-rate * years) * norm.cdf(-d2) - spot * norm.cdf(-d1)


def implied_vol(spot, strike, years, rate, market_price, call_put):
    if not all(np.isfinite([spot, strike, years, rate, market_price])) or market_price <= 0:
        return np.nan
    low, high = 0.005, 3.0
    low_price = bs_price(spot, strike, years, rate, low, call_put)
    high_price = bs_price(spot, strike, years, rate, high, call_put)
    if market_price < low_price or market_price > high_price:
        return np.nan
    for _ in range(70):
        mid = (low + high) / 2
        value = bs_price(spot, strike, years, rate, mid, call_put)
        if value > market_price:
            high = mid
        else:
            low = mid
    return (low + high) / 2


def option_variance(expiry_chain, rate):
    years = float(expiry_chain["days_left"].iloc[0]) / 365
    pairs = expiry_chain.pivot_table(
        index="exercise_price", columns="call_put", values="price", aggfunc="first"
    ).dropna(subset=["C", "P"])
    if len(pairs) < 3:
        return None
    pivot_strike = (pairs["C"] - pairs["P"]).abs().idxmin()
    forward = pivot_strike + math.exp(rate * years) * (
        pairs.loc[pivot_strike, "C"] - pairs.loc[pivot_strike, "P"]
    )
    strikes = np.array(sorted(pairs.index.astype(float)))
    below_forward = strikes[strikes <= forward]
    if len(below_forward) == 0:
        return None
    k0 = below_forward.max()
    contribution = 0.0
    for index, strike in enumerate(strikes):
        if strike < k0:
            option_price = pairs.loc[strike, "P"]
        elif strike > k0:
            option_price = pairs.loc[strike, "C"]
        else:
            option_price = (pairs.loc[strike, "C"] + pairs.loc[strike, "P"]) / 2
        if not np.isfinite(option_price) or option_price <= 0:
            continue
        if index == 0:
            delta_k = strikes[1] - strikes[0]
        elif index == len(strikes) - 1:
            delta_k = strikes[-1] - strikes[-2]
        else:
            delta_k = (strikes[index + 1] - strikes[index - 1]) / 2
        contribution += delta_k / strike ** 2 * math.exp(rate * years) * option_price
    variance = 2 / years * contribution - (forward / k0 - 1) ** 2 / years
    return years, variance


def calc_qvix(pro, dates, option_daily):
    """Rebuild the Notebook's 50ETF QVIX definition from Tushare option chains."""
    basic = retry(
        "opt_basic",
        lambda: pro.opt_basic(
            exchange="SSE",
            fields="ts_code,name,call_put,exercise_price,list_date,delist_date",
        ),
    )
    basic = basic[basic["name"].str.contains("50ETF", na=False)].copy()
    shibor = retry(
        "shibor",
        lambda: pro.shibor(start_date=dates[0], end_date=dates[-1], fields="date,1m"),
    )
    rate_map = dict(zip(shibor["date"].astype(str), shibor["1m"] / 100)) if not shibor.empty else {}
    option_daily = option_daily.merge(basic, on="ts_code", how="inner")
    option_daily["trade_date"] = option_daily["trade_date"].astype(str)
    option_daily["price"] = option_daily["close"].where(option_daily["close"] > 0, option_daily["settle"])

    result = []
    for index, (date, day) in enumerate(option_daily.groupby("trade_date"), 1):
        day = day[(day["list_date"] <= date) & (day["delist_date"] > date)].copy()
        day["days_left"] = (pd.to_datetime(day["delist_date"]) - pd.to_datetime(date)).dt.days
        expiries = sorted(day.loc[day["days_left"] > 7, "delist_date"].unique())[:2]
        if len(expiries) < 2:
            continue
        rate = float(rate_map.get(date, 0.015))
        variances = [option_variance(day[day["delist_date"] == expiry], rate) for expiry in expiries]
        if any(value is None or value[1] <= 0 for value in variances):
            continue
        (t1, variance1), (t2, variance2) = variances
        n1, n2, n30 = t1 * 365, t2 * 365, 30
        variance30 = (
            t1 * variance1 * (n2 - n30) / (n2 - n1)
            + t2 * variance2 * (n30 - n1) / (n2 - n1)
        ) * 365 / n30
        if variance30 > 0:
            result.append({"date": date, "raw_qvix": math.sqrt(variance30) * 100})
        if index % 100 == 0:
            print(f"  QVIX 已计算 {index} 日", flush=True)
    return pd.DataFrame(result)


def calc_price_strength_and_volume(equity):
    equity = equity.sort_values(["ts_code", "trade_date"]).copy()
    rolling_high = equity.groupby("ts_code", sort=False)["close"].transform(
        lambda values: values.rolling(LOOKBACK, min_periods=1).max()
    )
    equity["is_new_high"] = equity["close"].ge(rolling_high)
    strength = equity.groupby("trade_date").agg(
        new_high_count=("is_new_high", "sum"), total_stocks=("ts_code", "size")
    )
    strength["raw_strength"] = strength["new_high_count"] / strength["total_stocks"] * 100

    volume = equity.groupby("trade_date", as_index=False)["vol"].sum().sort_values("trade_date")
    volume["volume_ma20"] = volume["vol"].rolling(20).mean()
    volume["raw_volume"] = volume["vol"] / volume["volume_ma20"] - 1
    return (
        strength.reset_index()[["trade_date", "raw_strength"]],
        volume[["trade_date", "raw_volume"]],
    )


def calc_futures(pro, dates):
    basic = retry(
        "fut_basic",
        lambda: pro.fut_basic(
            exchange="CFFEX", fut_type="1",
            fields="ts_code,symbol,list_date,delist_date",
        ),
    )
    basic = basic[basic["symbol"].str.startswith("IF", na=False)].copy()
    basic = basic[(basic["delist_date"] >= dates[0]) & (basic["list_date"] <= dates[-1])]
    frames = []
    futures_cache = RAW_DIR / "if_futures"
    futures_cache.mkdir(parents=True, exist_ok=True)
    for index, row in enumerate(basic.itertuples(), 1):
        path = futures_cache / f"{row.ts_code.replace('.', '_')}.csv.gz"
        contract_closed = str(row.delist_date) < dates[-1]
        if path.exists() and contract_closed:
            frame = pd.read_csv(path, dtype={"ts_code": str, "trade_date": str})
        else:
            frame = retry(
                f"fut_daily {row.ts_code}",
                lambda code=row.ts_code: pro.fut_daily(
                    ts_code=code, start_date=dates[0], end_date=dates[-1],
                    fields="ts_code,trade_date,settle,close",
                ),
            )
            if not frame.empty:
                frame.to_csv(path, index=False, compression="gzip")
        if not frame.empty:
            frames.append(frame)
        if index % 20 == 0:
            print(f"  IF合约 {index}/{len(basic)}", flush=True)
    if not frames:
        raise RuntimeError("No IF futures data available")
    futures = pd.concat(frames, ignore_index=True).merge(
        basic[["ts_code", "delist_date"]], on="ts_code", how="left"
    )
    futures["trade_date"] = futures["trade_date"].astype(str)
    futures["days_left"] = (pd.to_datetime(futures["delist_date"]) - pd.to_datetime(futures["trade_date"])).dt.days
    futures = futures[futures["days_left"] > 0]
    futures = futures.sort_values(["trade_date", "delist_date"])
    next_month = futures.groupby("trade_date", as_index=False).nth(1).reset_index(drop=True)
    next_month["futures_price"] = next_month["close"].where(next_month["close"] > 0, next_month["settle"])

    spot = retry(
        "index_daily 000300.SH",
        lambda: pro.index_daily(
            ts_code="000300.SH", start_date=dates[0], end_date=dates[-1],
            fields="trade_date,close",
        ),
    )
    merged = next_month.merge(spot, on="trade_date", how="inner", suffixes=("_fut", "_spot"))
    merged["raw_futures_daily"] = (merged["futures_price"] / merged["close_spot"] - 1) * 365 / merged["days_left"] * 100
    merged = merged.sort_values("trade_date")
    merged["raw_futures"] = merged["raw_futures_daily"].rolling(10).mean()
    return merged[["trade_date", "raw_futures"]], spot


def fetch_shanghai_index(pro, dates):
    frame = retry(
        "index_daily 000001.SH",
        lambda: pro.index_daily(
            ts_code="000001.SH", start_date=dates[0], end_date=dates[-1],
            fields="trade_date,close",
        ),
    )
    return frame.rename(columns={"close": "shanghai_index"})[["trade_date", "shanghai_index"]]


def calc_safe_haven(pro, dates, hs300):
    bond = retry(
        "index_daily H11001.CSI",
        lambda: pro.index_daily(
            ts_code="H11001.CSI", start_date=dates[0], end_date=dates[-1],
            fields="trade_date,close",
        ),
    )
    merged = hs300.merge(bond, on="trade_date", how="inner", suffixes=("_stock", "_bond"))
    merged = merged.sort_values("trade_date")
    merged["raw_safety"] = merged["close_stock"].pct_change(20) - merged["close_bond"].pct_change(20)
    return merged[["trade_date", "raw_safety"]]


def rolling_percentile(series, invert=False):
    score = series.rolling(LOOKBACK, min_periods=20).apply(
        lambda window: (window < window.iloc[-1]).mean() * 100,
        raw=False,
    )
    return 100 - score if invert else score


def build_index(pro, start, end):
    dates = trading_dates(pro, start, end)
    if len(dates) < LOOKBACK:
        raise RuntimeError(f"Need at least {LOOKBACK} trading days, got {len(dates)}")
    print(f"Tushare-only update: {dates[0]} - {dates[-1]} ({len(dates)} days)")

    print("[1/5] 全市场250日新高占比", flush=True)
    equity = fetch_equity_daily(pro, dates)
    strength, volume = calc_price_strength_and_volume(equity)

    print("[2/5] 50ETF QVIX", flush=True)
    options = fetch_option_daily(pro, dates)
    qvix = calc_qvix(pro, dates, options)

    print("[3/5] IF次月年化升贴水", flush=True)
    futures, hs300 = calc_futures(pro, dates)

    print("[4/5] 股债避险需求", flush=True)
    safety = calc_safe_haven(pro, dates, hs300)

    print("[5/5] 滚动百分位与综合指数", flush=True)
    shanghai = fetch_shanghai_index(pro, dates)
    result = pd.DataFrame({"trade_date": dates})
    for frame in [qvix.rename(columns={"date": "trade_date"}), strength, futures, volume, safety, shanghai]:
        result = result.merge(frame, on="trade_date", how="left")
    result = result.sort_values("trade_date")
    raw_columns = ["raw_qvix", "raw_strength", "raw_futures", "raw_volume", "raw_safety"]
    result["raw_qvix"] = result["raw_qvix"].interpolate(method="linear", limit_area="inside")
    result["raw_futures"] = result["raw_futures"].interpolate(method="linear", limit_area="inside")
    result["QVIX"] = rolling_percentile(result["raw_qvix"], invert=True)
    result["股价强度"] = rolling_percentile(result["raw_strength"])
    result["期货升贴水"] = rolling_percentile(result["raw_futures"])
    result["成交量"] = rolling_percentile(result["raw_volume"])
    result["避险需求"] = rolling_percentile(result["raw_safety"])
    score_columns = ["QVIX", "股价强度", "期货升贴水", "成交量", "避险需求"]
    result["our_index"] = result[score_columns].mean(axis=1, skipna=False)
    result = result.dropna(subset=["our_index"]).copy()
    result["date"] = pd.to_datetime(result["trade_date"]).dt.strftime("%Y-%m-%d")
    result["our_zone"] = pd.cut(
        result["our_index"], bins=[0, 25, 40, 60, 75, 100],
        labels=["极度恐惧", "恐惧", "中性", "贪婪", "极度贪婪"], include_lowest=True,
    )
    output_columns = ["date", *score_columns, "our_index", "our_zone", "shanghai_index", *raw_columns]
    result[output_columns].to_json(OUTPUT_PATH, orient="records", force_ascii=False)
    latest = result.iloc[-1]
    print(f"完成: {OUTPUT_PATH}")
    print(f"最新 {latest['date']}: {latest['our_index']:.1f} ({latest['our_zone']})")
    return result[output_columns]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", default="20200101", help="History start date, YYYYMMDD")
    parser.add_argument("--end", help="End date, defaults to latest open date")
    args = parser.parse_args()
    pro = ts.pro_api()
    end = latest_open_date(pro, args.end)
    if not args.end and OUTPUT_PATH.exists():
        try:
            existing = pd.read_json(OUTPUT_PATH)
            first_date = str(existing.iloc[0]["date"]).replace("-", "")
            if not existing.empty and first_date <= args.start and str(existing.iloc[-1]["date"]).replace("-", "") == end:
                print(f"跳过: {end} 已是最新可用交易日")
                return
        except (OSError, ValueError, KeyError, IndexError):
            pass
    build_index(pro, args.start, end)


if __name__ == "__main__":
    main()
