# 数据模型与架构

> 生成时间:2026-08-18 (UTC+08)
> 范围:数据管道、持久化、表结构

## 数据源
- Tushare Pro(token 从 TUSHARE_TOKEN 环境变量)
- 拉取 250 交易日历史 + 每日增量

## 数据管道(每日刷新)
```
refresher.py (工作日21:10, subprocess)
   -> refresh-market-data.sh
   -> notebooks/update_*.py (逐数据集)
   -> data/*_runtime.json (中间 JSON)
   -> sync_market_data.py (upsert 到 PostgreSQL)
```

notebooks 模块:
- `_fgg_common.py`: 恐惧贪婪 fetch/calc 共享工具(LOCKBACK, latest_open_date, calc_* 等)
- `update_fear_greed_incremental.py`: 恐惧贪婪增量入库(替代全量,内存友好)
- `update_{environment,style,industry,volume,volatility,turnover,breadth,factor}_tushare.py`: 各数据集拉取
- `market_database.py`: PostgreSQL 持久化(schema, upsert)
- `sync_market_data.py`: 数据目录 → PostgreSQL 同步入口

## PostgreSQL 表
| 表 | 用途 |
|---|---|
| market_refresh_runs | 每次刷新运行记录(status/起止/target_trade_date) |
| market_runtime_snapshots | 9 个数据集的完整 JSON payload(as_of, payload JSONB, sha256) |
| market_fear_greed_daily | 恐惧贪婪逐交易日(scoring + raw)历史 |
| tushare_raw_cache | Tushare 原生响应缓存(压缩) |
| market_documents | 文档/向量(pgvector, 预留) |

schema: db/init/001_market_data.sql

## 数据读取(web)
- 9 个数据 API 从 `market_runtime_snapshots` 读 JSON(payload 校验后返回)
- dashboard 从 `market_fear_greed_daily` 读历史做聚合
- 后端双模式:MARKET_DATA_BACKEND=postgres(生产)| file(测试/本地,读 data/*.json)

## 用户/会话(SQLite)
- web/data/users.sqlite: users / sessions / oauth_states
- 会话 token sha256 存库,Cookie session HttpOnly;SameSite=Lax

## 数据文件(data/ 目录,gitignored)
- 9 个 *_runtime.json(刷新产物,生产经 psycopg 入库)
- data/tushare_raw/*.csv.gz(Tushare 缓存)
- 持久化卷: docker compose 挂载 ./data:/app/data
