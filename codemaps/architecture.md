# Traderoff 架构地图

> 生成时间:2026-08-18 (UTC+08)
> 说明:高层架构概览。聚焦模块与数据流,非实现细节。

## 总体架构

```
浏览器 (web/static: index.html + app.js + echarts/lucide)
        │  HTTPS
        ▼
Caddy 反向代理 (docker compose: caddy)  :443 -> Traderoff :8788
        │
        ▼
FastAPI 应用 (web/app: main.py)  :8788
        ├── HTTP 路由 (/api/*)                 -> main.py
        ├── 认证/会话/微信OAuth                 -> auth.py
        ├── 市场数据读取(postgres/file后端)     -> market_data.py
        ├── 恐慌贪婪指数聚合                    -> dashboard.py
        └── 每日数据刷新定时器(APScheduler)     -> refresher.py
              │  subprocess
              ▼
        refresh-market-data.sh
              │  python3 notebooks/update_*.py
              ▼
        Tushare Pro 行情 -> data/*.json -> PostgreSQL(psycopg)
              │
              ▼
        PostgreSQL 16 + pgvector (docker compose: postgres)
```

## 进程/容器

| 容器 | 镜像 | 职责 |
|---|---|---|
| traderoff | traderoff-traderoff:latest | FastAPI web + APScheduler 每日刷新 |
| postgres | pgvector/pgvector:pg16 | 行情持久化(市场数据 + 用户库) |
| caddy | caddy:2.10 | HTTPS 反向代理 / TLS 证书 |

> market-updater 容器已于 2026-08 移除:每日刷新改由 traderoff 进程内 APScheduler 承担。

## 数据流(每日)
1. `refresher.py` 在工作日 21:10(Asia/Shanghai)触发 `subprocess refresh-market-data.sh`
2. `refresh-market-data.sh` 逐脚本跑 `notebooks/update_*_tushare.py`(拉 Tushare → 写 data/*.json)
3. `sync_market_data.py` 把 json 增量写入 PostgreSQL(`market_runtime_snapshots` + `market_fear_greed_daily`)
4. Web 从 PostgreSQL 读取展示

## 技术栈
- 后端:Python 3.11 + FastAPI + Uvicorn + psycopg / APScheduler / httpx / sqlite3/stdlib
- 前端:原生 HTML + JavaScript(echarts、lucide 通过 vendor 引入,无构建步骤)
- 数据:Tushare Pro API、PostgreSQL 16 + pgvector、SQLite(用户会话库)
- 部署:Docker Compose + Caddy + GitHub Actions CI/CD(测试 + SSH 部署到腾讯云)
