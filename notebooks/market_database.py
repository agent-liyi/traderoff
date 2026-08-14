"""PostgreSQL persistence for the market-data pipeline.

Runtime JSON and compressed Tushare responses remain transient compute inputs.
The database is the durable source consumed by the web service.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from datetime import date, datetime
from pathlib import Path
from typing import Any

import psycopg
from psycopg.types.json import Jsonb

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "db" / "init" / "001_market_data.sql"
DATASET_FILES = {
    "fear-greed": "fear_greed_runtime.json",
    "market-environment": "market_environment_runtime.json",
    "market-style": "market_style_runtime.json",
    "industry-price": "industry_price_runtime.json",
    "market-volume": "market_volume_runtime.json",
    "market-volatility": "market_volatility_runtime.json",
    "market-turnover": "market_turnover_runtime.json",
    "market-breadth": "market_breadth_runtime.json",
    "factor-exposure": "factor_exposure_runtime.json",
}


def database_url() -> str:
    value = os.getenv("MARKET_DATABASE_URL") or os.getenv("DATABASE_URL")
    if not value:
        raise RuntimeError("MARKET_DATABASE_URL or DATABASE_URL is required for market persistence")
    return value


def connect():
    return psycopg.connect(database_url(), connect_timeout=15)


def ensure_schema(connection) -> None:
    connection.execute(SCHEMA_PATH.read_text(encoding="utf-8"))


def parse_date(value: str | None) -> date | None:
    if not value:
        return None
    match = re.search(r"(\d{4})[-_]?(\d{2})[-_]?(\d{2})", value)
    if not match:
        return None
    return date(*map(int, match.groups()))


def generated_at(payload: Any) -> datetime:
    value = payload.get("generatedAt") if isinstance(payload, dict) else None
    if value:
        return datetime.fromisoformat(value)
    return datetime.now().astimezone()


def snapshot_as_of(dataset: str, payload: Any) -> date:
    if isinstance(payload, dict) and payload.get("asOf"):
        result = parse_date(str(payload["asOf"]))
        if result:
            return result
    if dataset == "fear-greed" and isinstance(payload, list) and payload:
        result = parse_date(str(payload[-1].get("date", "")))
        if result:
            return result
    raise RuntimeError(f"{dataset} payload has no valid as-of date")


def payload_bytes(payload: Any) -> bytes:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")


def upsert_snapshot(connection, dataset: str, payload: Any, refresh_id: uuid.UUID) -> None:
    digest = hashlib.sha256(payload_bytes(payload)).hexdigest()
    connection.execute(
        """
        INSERT INTO market_runtime_snapshots
          (dataset, as_of, generated_at, payload, payload_sha256, refresh_id)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (dataset) DO UPDATE SET
          as_of = EXCLUDED.as_of,
          generated_at = EXCLUDED.generated_at,
          payload = EXCLUDED.payload,
          payload_sha256 = EXCLUDED.payload_sha256,
          refresh_id = EXCLUDED.refresh_id,
          updated_at = now()
        """,
        (dataset, snapshot_as_of(dataset, payload), generated_at(payload), Jsonb(payload), digest, refresh_id),
    )


def upsert_fear_greed_rows(connection, rows: list[dict[str, Any]], refresh_id: uuid.UUID) -> None:
    records = []
    for row in rows:
        records.append((
            parse_date(str(row["date"])), row["QVIX"], row["股价强度"], row["期货升贴水"], row["成交量"],
            row["避险需求"], row["our_index"], row["our_zone"], row["shanghai_index"], row["raw_qvix"],
            row["raw_strength"], row["raw_futures"], row["raw_volume"], row["raw_safety"], refresh_id,
        ))
    with connection.cursor() as cursor:
        cursor.executemany(
            """
            INSERT INTO market_fear_greed_daily (
              trade_date, score_qvix, score_strength, score_futures, score_volume, score_safety, our_index, our_zone,
              shanghai_index, raw_qvix, raw_strength, raw_futures, raw_volume, raw_safety, refresh_id
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (trade_date) DO UPDATE SET
              score_qvix = EXCLUDED.score_qvix, score_strength = EXCLUDED.score_strength,
              score_futures = EXCLUDED.score_futures, score_volume = EXCLUDED.score_volume,
              score_safety = EXCLUDED.score_safety, our_index = EXCLUDED.our_index, our_zone = EXCLUDED.our_zone,
              shanghai_index = EXCLUDED.shanghai_index, raw_qvix = EXCLUDED.raw_qvix,
              raw_strength = EXCLUDED.raw_strength, raw_futures = EXCLUDED.raw_futures,
              raw_volume = EXCLUDED.raw_volume, raw_safety = EXCLUDED.raw_safety,
              refresh_id = EXCLUDED.refresh_id, updated_at = now()
            """,
            records,
        )


def raw_source(path: Path, raw_dir: Path) -> tuple[str, date | None]:
    relative = path.relative_to(raw_dir).as_posix()
    return relative.split("/", 1)[0], parse_date(path.stem)


def sync_raw_cache(connection, raw_dir: Path, refresh_id: uuid.UUID) -> tuple[int, int]:
    inserted = skipped = 0
    if not raw_dir.exists():
        return inserted, skipped
    for path in sorted(raw_dir.rglob("*.csv.gz")):
        content = path.read_bytes()
        digest = hashlib.sha256(content).hexdigest()
        relative = path.relative_to(raw_dir).as_posix()
        prior = connection.execute("SELECT content_sha256 FROM tushare_raw_cache WHERE cache_key = %s", (relative,)).fetchone()
        if prior and prior[0] == digest:
            skipped += 1
            continue
        source, trade_date = raw_source(path, raw_dir)
        connection.execute(
            """
            INSERT INTO tushare_raw_cache
              (cache_key, source_path, source_name, trade_date, content_gzip, content_sha256, byte_size, refresh_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (cache_key) DO UPDATE SET
              source_path = EXCLUDED.source_path, source_name = EXCLUDED.source_name, trade_date = EXCLUDED.trade_date,
              content_gzip = EXCLUDED.content_gzip, content_sha256 = EXCLUDED.content_sha256,
              byte_size = EXCLUDED.byte_size, refresh_id = EXCLUDED.refresh_id, updated_at = now()
            """,
            (relative, relative, source, trade_date, content, digest, len(content), refresh_id),
        )
        inserted += 1
    return inserted, skipped


def sync_data_dir(data_dir: Path, include_raw: bool = True) -> dict[str, int | str]:
    run_id = uuid.uuid4()
    with connect() as connection:
        ensure_schema(connection)
        connection.commit()
        connection.execute(
            "INSERT INTO market_refresh_runs (id, status) VALUES (%s, 'running')",
            (run_id,),
        )
        connection.commit()
        try:
            with connection.transaction():
                snapshots = 0
                target_date = None
                for dataset, filename in DATASET_FILES.items():
                    path = data_dir / filename
                    if not path.exists():
                        if dataset == "factor-exposure":
                            continue
                        raise RuntimeError(f"required runtime output is missing: {path}")
                    payload = json.loads(path.read_text(encoding="utf-8"))
                    upsert_snapshot(connection, dataset, payload, run_id)
                    if dataset == "fear-greed":
                        upsert_fear_greed_rows(connection, payload, run_id)
                    as_of = snapshot_as_of(dataset, payload)
                    target_date = as_of if target_date is None else max(target_date, as_of)
                    snapshots += 1
                raw_added, raw_skipped = sync_raw_cache(connection, data_dir / "tushare_raw", run_id) if include_raw else (0, 0)
                connection.execute(
                    "UPDATE market_refresh_runs SET status = 'succeeded', target_trade_date = %s, completed_at = now() WHERE id = %s",
                    (target_date, run_id),
                )
            return {"run_id": str(run_id), "snapshots": snapshots, "raw_added": raw_added, "raw_skipped": raw_skipped}
        except Exception as exc:
            with connection.transaction():
                connection.execute(
                    "UPDATE market_refresh_runs SET status = 'failed', error_message = %s, completed_at = now() WHERE id = %s",
                    (str(exc)[:4000], run_id),
                )
            raise
