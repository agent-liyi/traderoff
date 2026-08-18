#!/usr/bin/env python3
"""Incrementally append new Fear & Greed trading days directly into PostgreSQL.

Alternative to the full-rebuild update_fear_greed_tushare.py. Instead of
recomputing the whole history (which concats ~1600 cached trading days and
can OOM a 1.9GiB box), this script:

1. Reads the latest trade_date already in `market_fear_greed_daily`.
2. Computes the pending open trading dates after that up to the latest
   available trading date.
3. Reuses update_fear_greed_tushare's fetch/calc over a *recent window*
   (~LOOKBACK + pending) so rolling metrics (250-day) are correct but the
   in-memory footprint stays small.
4. Inserts/updates only the pending rows into `market_fear_greed_daily`.
5. Refreshes the `fear-greed` snapshot in `market_runtime_snapshots` by
   merging the appended rows into the existing payload.

Reuse is safe: importing update_fear_greed_tushare runs only module-level
constants and imports (no side-effecting top-level execution).
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import sys
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

import psycopg

# Reuse the fetch/calc helpers from the full-rebuild script.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import update_fear_greed_tushare as fg

LOOKBACK = fg.LOOKBACK
WINDOW_EXTRA = 12  # extra trading days so pending rows' rolling(250) is full


def _connect() -> psycopg.Connection:
    from market_database import database_url

    return psycopg.connect(database_url(), connect_timeout=15)


def _latest_in_db(conn) -> datetime.date | None:
    with conn.cursor() as cur:
        cur.execute("SELECT max(trade_date) FROM market_fear_greed_daily")
        return cur.fetchone()[0]


def _existing_history(conn) -> list[dict]:
    """All existing fear-greed rows oldest->newest (for snapshot rebuild)."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT trade_date::text AS date, score_qvix AS \"QVIX\","
            " score_strength AS \"股价强度\", score_futures AS \"期货升贴水\","
            " score_volume AS \"成交量\", score_safety AS \"避险需求\","
            " our_index, our_zone, shanghai_index,"
            " raw_qvix, raw_strength, raw_futures, raw_volume, raw_safety"
            " FROM market_fear_greed_daily ORDER BY trade_date"
        )
        cols = [d.name for d in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    out = []
    for r in rows:
        out.append({
            "date": str(r["date"]),
            "QVIX": float(r["QVIX"]) if r["QVIX"] is not None else None,
            "股价强度": float(r["股价强度"]) if r["股价强度"] is not None else None,
            "期货升贴水": float(r["期货升贴水"]) if r["期货升贴水"] is not None else None,
            "成交量": float(r["成交量"]) if r["成交量"] is not None else None,
            "避险需求": float(r["避险需求"]) if r["避险需求"] is not None else None,
            "our_index": float(r["our_index"]),
            "our_zone": r["our_zone"],
            "shanghai_index": float(r["shanghai_index"]),
            "raw_qvix": float(r["raw_qvix"]) if r["raw_qvix"] is not None else None,
            "raw_strength": float(r["raw_strength"]) if r["raw_strength"] is not None else None,
            "raw_futures": float(r["raw_futures"]) if r["raw_futures"] is not None else None,
            "raw_volume": float(r["raw_volume"]) if r["raw_volume"] is not None else None,
            "raw_safety": float(r["raw_safety"]) if r["raw_safety"] is not None else None,
        })
    return out


def calculate_window(pro, window_dates: list[str]) -> pd.DataFrame:
    """Compute raw indicators + rolling scores over a recent window of dates."""
    print(f"[1/5] equity 250日新高 ({len(window_dates)} 天)", flush=True)
    equity = fg.fetch_equity_daily(pro, window_dates)
    strength, volume = fg.calc_price_strength_and_volume(equity)

    print("[2/5] 50ETF QVIX", flush=True)
    options = fg.fetch_option_daily(pro, window_dates)
    qvix = fg.calc_qvix(pro, window_dates, options).rename(columns={"date": "trade_date"})

    print("[3/5] IF 次月年化升贴水", flush=True)
    futures, hs300 = fg.calc_futures(pro, window_dates)

    print("[4/5] 股债避险需求", flush=True)
    safety = fg.calc_safe_haven(pro, window_dates, hs300)

    print("[5/5] 上证指数与综合分", flush=True)
    shanghai = fg.fetch_shanghai_index(pro, window_dates)

    result = pd.DataFrame({"trade_date": window_dates})
    for frame in [qvix, strength, futures, volume, safety, shanghai]:
        result = result.merge(frame, on="trade_date", how="left")
    result = result.sort_values("trade_date")

    for col in ["raw_qvix", "raw_futures"]:
        result[col] = result[col].interpolate(method="linear", limit_area="inside")

    result["QVIX"] = fg.rolling_percentile(result["raw_qvix"], invert=True)
    result["股价强度"] = fg.rolling_percentile(result["raw_strength"])
    result["期货升贴水"] = fg.rolling_percentile(result["raw_futures"])
    result["成交量"] = fg.rolling_percentile(result["raw_volume"])
    result["避险需求"] = fg.rolling_percentile(result["raw_safety"])

    score_cols = ["QVIX", "股价强度", "期货升贴水", "成交量", "避险需求"]
    result["our_index"] = result[score_cols].mean(axis=1, skipna=False)
    result["our_zone"] = pd.cut(
        result["our_index"], bins=[0, 25, 40, 60, 75, 100],
        labels=["极度恐惧", "恐惧", "中性", "贪婪", "极度贪婪"], include_lowest=True,
    ).astype(str)
    result["date"] = pd.to_datetime(result["trade_date"]).dt.strftime("%Y-%m-%d")
    return result


def _upsert_rows(conn, rows: list[Mapping]) -> None:
    if not rows:
        return
    sql = """
        INSERT INTO market_fear_greed_daily
          (trade_date, score_qvix, score_strength, score_futures, score_volume,
           score_safety, our_index, our_zone, shanghai_index,
           raw_qvix, raw_strength, raw_futures, raw_volume, raw_safety)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (trade_date) DO UPDATE SET
          score_qvix=EXCLUDED.score_qvix, score_strength=EXCLUDED.score_strength,
          score_futures=EXCLUDED.score_futures, score_volume=EXCLUDED.score_volume,
          score_safety=EXCLUDED.score_safety, our_index=EXCLUDED.our_index,
          our_zone=EXCLUDED.our_zone, shanghai_index=EXCLUDED.shanghai_index,
          raw_qvix=EXCLUDED.raw_qvix, raw_strength=EXCLUDED.raw_strength,
          raw_futures=EXCLUDED.raw_futures, raw_volume=EXCLUDED.raw_volume,
          raw_safety=EXCLUDED.raw_safety, updated_at=now()
    """
    with conn.cursor() as cur:
        for r in rows:
            cur.execute(sql, (
                r["trade_date"],
                None if _isnan(r.get("QVIX")) else r.get("QVIX"),
                None if _isnan(r.get("股价强度")) else r.get("股价强度"),
                None if _isnan(r.get("期货升贴水")) else r.get("期货升贴水"),
                None if _isnan(r.get("成交量")) else r.get("成交量"),
                None if _isnan(r.get("避险需求")) else r.get("避险需求"),
                None if _isnan(r.get("our_index")) else r.get("our_index"),
                r.get("our_zone"),
                None if _isnan(r.get("shanghai_index")) else r.get("shanghai_index"),
                None if _isnan(r.get("raw_qvix")) else r.get("raw_qvix"),
                None if _isnan(r.get("raw_strength")) else r.get("raw_strength"),
                None if _isnan(r.get("raw_futures")) else r.get("raw_futures"),
                None if _isnan(r.get("raw_volume")) else r.get("raw_volume"),
                None if _isnan(r.get("raw_safety")) else r.get("raw_safety"),
            ))
    conn.commit()


def _isnan(value) -> bool:
    try:
        return bool(math.isnan(value))
    except (TypeError, ValueError):
        return False


def _js(value):
    return value


def _update_snapshot(conn, history: list[dict], new_rows: list[dict]) -> list[dict]:
    """Rebuild full fear-greed payload (history + new rows), upsert snapshot, return payload."""
    # Map existing history to the payload record shape, then append new rows.
    payload = list(history)
    for r in new_rows:
        payload.append({
            "date": r["date"],
            "QVIX": _js(r.get("QVIX")), "股价强度": _js(r.get("股价强度")),
            "期货升贴水": _js(r.get("期货升贴水")), "成交量": _js(r.get("成交量")),
            "避险需求": _js(r.get("避险需求")),
            "our_index": _js(r.get("our_index")), "our_zone": r.get("our_zone"),
            "shanghai_index": _js(r.get("shanghai_index")),
            "raw_qvix": _js(r.get("raw_qvix")), "raw_strength": _js(r.get("raw_strength")),
            "raw_futures": _js(r.get("raw_futures")), "raw_volume": _js(r.get("raw_volume")),
            "raw_safety": _js(r.get("raw_safety")),
        })
    payload_bytes = json.dumps(payload, ensure_ascii=False)
    digest = hashlib.sha256(payload_bytes.encode("utf-8")).hexdigest()
    as_of = payload[-1]["date"]
    generated_at = datetime.now(ZoneInfo("Asia/Shanghai"))
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO market_runtime_snapshots
              (dataset, as_of, generated_at, payload, payload_sha256)
            VALUES ('fear-greed', %s, %s, %s::jsonb, %s)
            ON CONFLICT (dataset) DO UPDATE SET
              as_of=EXCLUDED.as_of, generated_at=EXCLUDED.generated_at,
              payload=EXCLUDED.payload, payload_sha256=EXCLUDED.payload_sha256,
              updated_at=now()
            """,
            (as_of, generated_at, payload_bytes, digest),
        )
    conn.commit()
    return payload


def _write_json(payload: list[dict]) -> None:
    """Persist the full fear-greed payload to the runtime JSON file.

    Keeps data/fear_greed_runtime.json consistent with the database so a later
    `sync_market_data.py` reads the appended rows instead of stale ones.
    """
    fg.OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    fg.OUTPUT_PATH.write_text(
        json.dumps(payload, ensure_ascii=False), encoding="utf-8"
    )
    print(f"已刷新 {fg.OUTPUT_PATH} ({len(payload)} 行)")


def main() -> None:
    pro = fg.ts.pro_api()
    latest_open = fg.latest_open_date(pro)
    conn = _connect()
    try:
        last_db = _latest_in_db(conn)
        if last_db is None:
            raise SystemExit("数据库无 fear-greed 历史；请用全量脚本初始化")

        pending = fg.trading_dates(pro, last_db.strftime("%Y%m%d"), f"{int(latest_open)}")
        pending = [d for d in pending if d > last_db.strftime("%Y%m%d")]
        print(f"库中最新: {last_db}  最新可交易日: {latest_open}")
        print(f"待追加交易日: {pending or '无'}")

        if not pending:
            # Ensure the runtime JSON matches the DB (stale json could otherwise
            # overwrite the snapshot at the next full sync).
            history = _existing_history(conn)
            if history:
                _write_json(history)
            print("已是最新，无需增量")
            return

        # window = latest LOOKBACK + len(pending) + extra trading days ending at latest_open
        all_dates = fg.trading_dates(pro, "20200101", f"{int(latest_open)}")
        window = all_dates[-(LOOKBACK + len(pending) + WINDOW_EXTRA):]
        print(f"计算窗口: {window[0]} ~ {window[-1]} ({len(window)} 天)")
        if window[-1] != latest_open:
            raise SystemExit(f"窗口末尾 {window[-1]} != 最新开市日 {latest_open}，中止")

        cols = calculate_window(pro, window)
        # pick pending rows
        pending_set = set(pending)
        row_df = cols[cols["trade_date"].isin(pending_set)]
        if row_df.empty:
            print("窗口计算无待追加行(可能 raw 数据缺失)，中止")
            return
        print(row_df[["trade_date", "our_index", "our_zone"]].to_string(index=False))

        rows = row_df.to_dict("records")
        _upsert_rows(conn, rows)

        # Refresh snapshot + json: existing full history + appended rows.
        history = _existing_history(conn)
        payload = _update_snapshot(conn, history, rows)
        _write_json(payload)

        print(f"增量同步完成：已追加 {len(rows)} 个交易日到 market_fear_greed_daily")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
