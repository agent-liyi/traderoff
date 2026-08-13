#!/usr/bin/env python3
"""Build a compact CNLT-style 16-factor reference snapshot from Tushare data.

The proxies are independently designed and transparent. This is not an MSCI
Barra model and does not claim authorization, reproduction, or equivalence.
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import tushare as ts

DATA_DIR = Path(os.getenv("FEAR_GREED_DATA_DIR", "/workspace/data"))
RAW_DIR = DATA_DIR / "tushare_raw"
CACHE_DIR = RAW_DIR / "factor_exposure"
OUTPUT_PATH = DATA_DIR / "factor_exposure_runtime.json"
REQUEST_INTERVAL = 0.34
HISTORY_DAYS = 1250
MIN_COVERAGE = 0.05
INDEXES = [("沪深300", "000300.SH"), ("中证500", "000905.SH"), ("中证1000", "000852.SH")]

FACTORS = [
    ("size", "规模", "ln(总市值)", "daily_basic.total_mv"),
    ("nonlinearSize", "非线性规模", "规模暴露三次项对规模线性回归的残差", "daily_basic.total_mv"),
    ("beta", "贝塔", "近250日个股收益对股票池等权收益回归斜率", "缓存日线收盘价"),
    ("momentum", "动量", "过去12个月剔除最近1个月累计收益", "缓存日线收盘价"),
    ("residualVolatility", "残差波动", "近250日市场模型残差年化波动率", "缓存日线收盘价"),
    ("liquidity", "流动性", "近20日成交额均值占流通市值比例", "daily.amount + daily_basic.circ_mv"),
    ("bookToPrice", "账面市值比", "1 / PB", "daily_basic.pb"),
    ("earningsYield", "盈利收益率", "1 / PE(TTM)", "daily_basic.pe_ttm"),
    ("growth", "成长", "最新营收同比与净利润同比均值", "fina_indicator.or_yoy, netprofit_yoy"),
    ("dividendYield", "股息率", "近12个月股息率", "daily_basic.dv_ttm"),
    ("leverage", "杠杆", "最新资产负债率", "fina_indicator.debt_to_assets"),
    ("earningsVariability", "盈利波动", "最近8期ROE与净利润同比的时间序列标准差均值", "多期 fina_indicator"),
    ("earningsQuality", "盈利质量", "最新经营现金流占营业收入比例", "fina_indicator.ocf_to_or"),
    ("profitability", "盈利能力", "最新ROE与总资产净利率均值", "fina_indicator.roe, roa"),
    ("investmentQuality", "投资质量", "最新总资产同比增速的相反数", "fina_indicator.assets_yoy"),
    ("longTermReversal", "长期反转", "3至5年前到1年前累计收益的相反数", "约1250个缓存交易日收盘价"),
]


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


def cache_path(name):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR / f"{name}.csv.gz"


def cached(name, request, required):
    path = cache_path(name)
    frame = None
    if path.exists():
        try:
            frame = pd.read_csv(path, dtype=str)
        except (OSError, ValueError, pd.errors.EmptyDataError):
            frame = None
    if frame is None or frame.empty or not set(required).issubset(frame.columns):
        frame = retry(name, request)
        if not frame.empty:
            frame.to_csv(path, index=False, compression="gzip")
    return frame


def latest_cached_dates(limit=HISTORY_DAYS):
    files = sorted((RAW_DIR / "equity_daily").glob("*.csv.gz"))
    if len(files) < limit:
        raise RuntimeError(f"Need {limit} cached equity_daily files, found {len(files)}")
    return [path.name.removesuffix(".csv.gz") for path in files[-limit:]]


def index_memberships(pro, end_date):
    result = {}
    start = (datetime.strptime(end_date, "%Y%m%d") - timedelta(days=60)).strftime("%Y%m%d")
    for name, code in INDEXES:
        frame = cached(
            f"members_{code.replace('.', '_')}_{end_date}",
            lambda code=code: pro.index_weight(index_code=code, start_date=start, end_date=end_date, fields="con_code,trade_date,weight"),
            {"con_code", "trade_date"},
        )
        if frame.empty:
            raise RuntimeError(f"No constituent snapshot for {name}")
        frame["trade_date"] = frame["trade_date"].astype(str)
        latest = frame["trade_date"].max()
        result[code] = set(frame.loc[frame["trade_date"] == latest, "con_code"].astype(str))
    return result


def sw2021_industries(pro, universe, warnings):
    try:
        classifications = cached(
            "sw2021_l1_classify",
            lambda: pro.index_classify(level="L1", src="SW2021", fields="index_code,industry_name,is_pub"),
            {"index_code", "industry_name"},
        )
        if "is_pub" in classifications:
            classifications = classifications[classifications["is_pub"].astype(str) == "1"]
        mapping = {}
        for row in classifications.itertuples(index=False):
            code = str(row.index_code)
            members = cached(
                f"sw2021_members_{code.replace('.', '_')}",
                lambda code=code: pro.index_member(index_code=code, fields="index_code,con_code,in_date,out_date,is_new"),
                {"con_code"},
            )
            if members.empty:
                continue
            if "is_new" in members and (members["is_new"].astype(str) == "Y").any():
                members = members[members["is_new"].astype(str) == "Y"]
            elif "out_date" in members:
                members = members[members["out_date"].isna() | members["out_date"].astype(str).isin(["", "None", "nan"])]
            for stock_code in set(members["con_code"].astype(str)).intersection(universe):
                mapping[stock_code] = str(row.industry_name)
        coverage = len(mapping) / len(universe) if universe else 0
        if coverage < 0.8:
            warnings.append(f"SW2021一级行业成员覆盖率仅 {coverage:.1%}，未覆盖股票归为未分类。")
        return pd.Series(mapping, dtype="object")
    except RuntimeError as exc:
        warnings.append(f"SW2021行业成员拉取受限：{str(exc).split(':', 1)[-1].strip()}；行业图仅显示未分类。")
        return pd.Series(dtype="object")


def load_price_history(dates, universe):
    close_rows = []
    amount_rows = []
    amount_dates = set(dates[-20:])
    for position, date in enumerate(dates, 1):
        path = RAW_DIR / "equity_daily" / f"{date}.csv.gz"
        usecols = ["ts_code", "close", "amount"] if date in amount_dates else ["ts_code", "close"]
        frame = pd.read_csv(path, usecols=usecols, dtype={"ts_code": str})
        frame = frame[frame["ts_code"].isin(universe)].set_index("ts_code")
        close_rows.append(frame["close"].rename(date))
        if date in amount_dates:
            amount_rows.append(frame["amount"].rename(date))
        if position % 250 == 0 or position == len(dates):
            print(f"  长期价格缓存 {position}/{len(dates)}", flush=True)
    close = pd.DataFrame(close_rows).apply(pd.to_numeric, errors="coerce")
    amount = pd.DataFrame(amount_rows).apply(pd.to_numeric, errors="coerce")
    return close, amount


def latest_basics(pro, end_date):
    frame = cached(
        f"daily_basic_{end_date}",
        lambda: pro.daily_basic(trade_date=end_date, fields="ts_code,trade_date,total_mv,circ_mv,pe_ttm,pb,dv_ttm"),
        {"ts_code", "total_mv", "circ_mv"},
    )
    frame = frame.drop_duplicates("ts_code").set_index("ts_code")
    for column in ["total_mv", "circ_mv", "pe_ttm", "pb", "dv_ttm"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame


def stock_financial_cache_path(ts_code, end_date):
    path = CACHE_DIR / "financials"
    path.mkdir(parents=True, exist_ok=True)
    # A monthly cache key refreshes newly announced reports without re-fetching
    # all 1,800 stocks on every daily snapshot.
    return path / f"{ts_code.replace('.', '_')}_{end_date[:6]}.csv.gz"


def stock_financial_history(pro, ts_code, end_date):
    path = stock_financial_cache_path(ts_code, end_date)
    required = {"ts_code", "ann_date", "end_date", "roe", "roa", "debt_to_assets", "or_yoy", "netprofit_yoy", "assets_yoy", "ocf_to_or"}
    if path.exists():
        try:
            frame = pd.read_csv(path, dtype={"ts_code": str, "ann_date": str, "end_date": str})
            if not frame.empty and required.issubset(frame.columns):
                return frame
        except (OSError, ValueError, pd.errors.EmptyDataError):
            pass
    start_date = (datetime.strptime(end_date, "%Y%m%d") - timedelta(days=6 * 366)).strftime("%Y%m%d")
    frame = retry(
        f"fina_indicator {ts_code}",
        lambda: pro.fina_indicator(
            ts_code=ts_code, start_date=start_date, end_date=end_date,
            fields="ts_code,ann_date,end_date,roe,roa,debt_to_assets,or_yoy,netprofit_yoy,assets_yoy,ocf_to_or",
        ),
        attempts=2,
    )
    if not frame.empty:
        frame.to_csv(path, index=False, compression="gzip")
    return frame


def financial_history(pro, end_date, universe, warnings):
    frames = []
    failures = []
    for position, ts_code in enumerate(sorted(universe), 1):
        try:
            frame = stock_financial_history(pro, ts_code, end_date)
            if frame.empty:
                failures.append(f"{ts_code}: 空结果")
                continue
            frame["ann_date"] = frame["ann_date"].astype(str)
            frame["end_date"] = frame["end_date"].astype(str)
            frame = frame[frame["ann_date"].str.fullmatch(r"\d{8}", na=False) & (frame["ann_date"] <= end_date)]
            frame = frame.sort_values(["ann_date", "end_date"]).drop_duplicates("end_date", keep="last").tail(12)
            if not frame.empty:
                frames.append(frame)
        except RuntimeError as exc:
            failures.append(f"{ts_code}: {str(exc).split(':', 1)[-1].strip()}")
        if position % 100 == 0 or position == len(universe):
            print(f"  财务指标 {position}/{len(universe)} (失败 {len(failures)})", flush=True)
    if failures:
        sample = "；".join(failures[:5])
        warnings.append(f"逐股财务指标有 {len(failures)}/{len(universe)} 只失败并保持为空；示例：{sample}")
    if not frames:
        return pd.DataFrame()
    frame = pd.concat(frames, ignore_index=True).drop_duplicates(["ts_code", "ann_date", "end_date"])
    for column in ["roe", "roa", "debt_to_assets", "or_yoy", "netprofit_yoy", "assets_yoy", "ocf_to_or"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame.sort_values(["ts_code", "ann_date", "end_date"])


def standardize(series):
    values = pd.to_numeric(series, errors="coerce").replace([np.inf, -np.inf], np.nan)
    valid = values.dropna()
    if len(valid) < 10 or valid.std(ddof=0) == 0:
        return pd.Series(np.nan, index=series.index)
    low, high = valid.quantile([0.01, 0.99])
    clipped = values.clip(low, high)
    return ((clipped - clipped.mean()) / clipped.std(ddof=0)).clip(-3, 3)


def guarded_returns(close, warnings):
    returns = close.pct_change(fill_method=None)
    jumps = returns.abs() > 0.22
    jump_count = int(jumps.sum().sum())
    returns = returns.mask(jumps)
    warnings.append(
        f"价格类代理使用未复权缓存收盘价；已将绝对单日收益超过22%的 {jump_count} 个异常跳变置空，仍可能受除权除息影响。"
    )
    return returns


def market_model(returns):
    market = returns.mean(axis=1, skipna=True)
    market_var = market.var(ddof=1)
    beta = returns.apply(lambda values: values.cov(market) / market_var if values.count() >= 120 and market_var > 0 else np.nan)
    predicted = market.to_frame().dot(beta.to_frame().T)
    residual = returns - predicted
    return beta, residual.std(ddof=1) * np.sqrt(252)


def latest_financial_values(history, universe):
    if history.empty:
        return pd.DataFrame(index=pd.Index(sorted(universe), name="ts_code"))
    return history.drop_duplicates("ts_code", keep="last").set_index("ts_code").reindex(sorted(universe))


def earnings_variability(history, universe):
    result = pd.Series(np.nan, index=sorted(universe), dtype=float)
    if history.empty:
        return result
    for code, reports in history.groupby("ts_code"):
        reports = reports.drop_duplicates("end_date", keep="last").tail(8)
        if len(reports) < 6:
            continue
        components = [reports[column].std(ddof=1) for column in ["roe", "netprofit_yoy"] if reports[column].notna().sum() >= 6]
        if len(components) == 2:
            result.loc[code] = float(np.mean(components))
    return result


def build_payload(pro):
    warnings = []
    dates = latest_cached_dates()
    end_date = dates[-1]
    print(f"因子快照: {dates[0]} - {end_date} ({len(dates)}个缓存交易日)", flush=True)
    member_sets = index_memberships(pro, end_date)
    universe = set().union(*member_sets.values())
    close, amount = load_price_history(dates, universe)
    basics = latest_basics(pro, end_date).reindex(sorted(universe))
    financials = financial_history(pro, end_date, universe, warnings)
    latest_financials = latest_financial_values(financials, universe)
    stocks = basics.copy()
    stock_basic = cached("stock_basic_listed", lambda: pro.stock_basic(exchange="", list_status="L", fields="ts_code,name"), {"ts_code", "name"})
    names = stock_basic.drop_duplicates("ts_code").set_index("ts_code")["name"] if not stock_basic.empty else pd.Series(dtype="object")
    stocks["name"] = names.reindex(stocks.index).fillna(pd.Series(stocks.index, index=stocks.index))
    industries = sw2021_industries(pro, universe, warnings)
    stocks["industry"] = industries.reindex(stocks.index).fillna("未分类")

    returns = guarded_returns(close, warnings)
    beta, residual_volatility = market_model(returns.tail(250))
    raw = pd.DataFrame(index=stocks.index)
    raw["size"] = np.log(stocks["total_mv"].where(stocks["total_mv"] > 0))
    size_z = standardize(raw["size"])
    valid_size = size_z.dropna()
    coefficients = np.polyfit(valid_size, valid_size**3, 1)
    raw["nonlinearSize"] = valid_size**3 - np.polyval(coefficients, valid_size)
    raw["beta"] = beta
    raw["momentum"] = close.iloc[-22] / close.iloc[-253] - 1
    raw["residualVolatility"] = residual_volatility
    # daily.amount is in CNY thousands; daily_basic.circ_mv is in CNY ten-thousands.
    raw["liquidity"] = amount.mean() / (stocks["circ_mv"].replace(0, np.nan) * 10)
    raw["bookToPrice"] = 1 / stocks["pb"].where(stocks["pb"] > 0)
    raw["earningsYield"] = 1 / stocks["pe_ttm"].where(stocks["pe_ttm"] > 0)
    raw["growth"] = pd.concat([latest_financials.get("or_yoy"), latest_financials.get("netprofit_yoy")], axis=1).mean(axis=1, skipna=False) if not latest_financials.empty else np.nan
    raw["dividendYield"] = stocks["dv_ttm"]
    raw["leverage"] = latest_financials.get("debt_to_assets")
    raw["earningsVariability"] = earnings_variability(financials, universe)
    raw["earningsQuality"] = latest_financials.get("ocf_to_or")
    raw["profitability"] = pd.concat([latest_financials.get("roe"), latest_financials.get("roa")], axis=1).mean(axis=1, skipna=False) if not latest_financials.empty else np.nan
    raw["investmentQuality"] = -latest_financials.get("assets_yoy") if "assets_yoy" in latest_financials else np.nan
    raw["longTermReversal"] = -(close.iloc[-253] / close.iloc[-1250] - 1)
    exposures = raw.apply(standardize)

    factor_items = []
    distributions = []
    for key, name, proxy, source in FACTORS:
        series = exposures[key]
        count = int(series.notna().sum())
        coverage = count / len(stocks) if len(stocks) else 0
        quality = "high" if coverage >= 0.9 else "medium" if coverage >= 0.6 else "low"
        factor_items.append({"key": key, "name": name, "proxy": proxy, "source": source, "coverage": round(coverage, 4), "count": count, "quality": quality})
        counts = pd.cut(series, bins=[-3, -2, -1, 0, 1, 2, 3.0001], right=False).value_counts(sort=False)
        distributions.append({"key": key, "name": name, "bins": [{"label": label, "count": int(value)} for label, value in zip(["[-3,-2)", "[-2,-1)", "[-1,0)", "[0,1)", "[1,2)", "[2,3]"], counts)]})
        if coverage < MIN_COVERAGE:
            warnings.append(f"{name}因子有效覆盖率仅 {coverage:.1%}，暴露保持为空，不做插值。")

    index_rows = []
    for name, code in [*INDEXES, ("中证1800", "CSI1800")]:
        members = universe if code == "CSI1800" else member_sets[code]
        weights = stocks.loc[stocks.index.intersection(members), "total_mv"].clip(lower=0)
        values = {}
        coverages = {}
        for key, *_ in FACTORS:
            available = exposures.loc[weights.index, key].dropna()
            usable_weights = weights.reindex(available.index)
            coverage = len(available) / len(weights) if len(weights) else 0
            coverages[key] = round(coverage, 4)
            values[key] = round(float(np.average(available, weights=usable_weights)), 4) if coverage >= 0.6 and usable_weights.sum() > 0 else None
        index_rows.append({"name": name, "code": code, "count": len(weights), "coverages": coverages, "exposures": values})

    industry_counts = stocks.groupby("industry").size().sort_values(ascending=False)
    industry_names = [name for name in industry_counts[industry_counts >= 5].index[:31] if name != "未分类"]
    heatmap = []
    for industry in industry_names:
        members = stocks.index[stocks["industry"] == industry]
        for key, name, *_ in FACTORS:
            value = exposures.loc[members, key].mean()
            heatmap.append({"industry": industry, "factor": key, "factorName": name, "value": round(float(value), 4) if pd.notna(value) else None})

    table_factors = ["size", "beta", "momentum", "residualVolatility", "liquidity", "bookToPrice", "earningsYield", "profitability"]
    stock_rows = []
    for code in stocks["total_mv"].nlargest(300).index:
        stock_rows.append({
            "code": code, "name": str(stocks.at[code, "name"]), "industry": str(stocks.at[code, "industry"]),
            "marketCap": round(float(stocks.at[code, "total_mv"] / 10000), 2) if pd.notna(stocks.at[code, "total_mv"]) else None,
            "exposures": {key: round(float(exposures.at[code, key]), 4) if pd.notna(exposures.at[code, key]) else None for key in table_factors},
        })

    methodology = {
        "price": "价格、贝塔、波动、动量与反转代理基于已有 daily.close 缓存。未使用复权因子；绝对单日收益超过22%的观测置空。",
        "financial": "财务代理逐股票请求并按月独立缓存，使用公告日在快照日前的最新报告；盈利波动最多取最近8个不同报告期且至少需要6期。单股失败继续，缺失不回填。",
        "industry": "行业仅使用申万2021一级 index_classify/index_member 当前成员映射。",
        "weighting": "指数暴露为可得个股标准化暴露按总市值加权均值。",
    }
    return {
        "schemaVersion": 1,
        "asOf": datetime.strptime(end_date, "%Y%m%d").strftime("%Y-%m-%d"),
        "generatedAt": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"),
        "model": {"name": "CNLT 风格参考多因子代理", "disclaimer": "独立构建的研究参考代理，非 MSCI Barra 官方模型，不代表授权、复现或等价实现。", "universe": "沪深300、中证500与中证1000最近可得成分快照并集（中证1800参考股票池）", "standardization": "截面1%/99%缩尾后标准化并截断至[-3,3]", "methodology": methodology},
        "quality": {"universeCount": len(stocks), "priceHistoryDays": len(close), "financialReportRows": len(financials), "swIndustryCovered": int((stocks["industry"] != "未分类").sum()), "warnings": list(dict.fromkeys(warnings))},
        "factors": factor_items,
        "indices": index_rows,
        "distributions": distributions,
        "industries": industry_names,
        "heatmap": heatmap,
        "stockTableFactors": table_factors,
        "stocks": stock_rows,
    }


def main():
    payload = build_payload(ts.pro_api())
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    temporary = OUTPUT_PATH.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False), encoding="utf-8")
    temporary.replace(OUTPUT_PATH)
    print(f"完成: {OUTPUT_PATH} ({payload['quality']['universeCount']}只, {len(payload['factors'])}因子)", flush=True)
    for warning in payload["quality"]["warnings"]:
        print(f"  WARNING: {warning}", flush=True)


if __name__ == "__main__":
    main()
