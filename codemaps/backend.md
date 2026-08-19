# 后端结构地图

> 生成时间:2026-08-18 (UTC+08)
> 范围:web/app(FastAPI 应用)+ 运维脚本

## 模块图

```
main.py ──────────────── 入口:FastAPI路由 + lifespan(可选调度器)
  │ import: auth, config, market_data, dashboard, refresher
  │ 路由: /api/dashboard, /api/market-*, /api/industry-price,
  │       /api/factor-exposure, /api/me, /api/auth/wechat(*), /api/logout
  │ 静态: /{path} SPA fallback -> web/static
  │ 错误: MarketDataError->503, ValidationError->500, 其他->404/500
  │
  ├─ auth.py       认证:sqlite users/sessions/oauth_states + 微信OAuth(state防CSRF)
  │                 依赖: sqlite3(stdlib), httpx(build authorize/exchange code)
  ├─ config.py     环境变量/路径常量(与 docker-compose env 对接)
  ├─ market_data.py 行情读取:psycopg(postgres) 或 file(json) 双后端
  │                 校验: 9 数据集 payload 完整性校验 -> ValidationError/MarketDataError
  ├─ dashboard.py  恐慌贪婪聚合:INDICATORS, zone, rolling, 匿名掩码
  └─ refresher.py  每日刷新调度:BackgroundScheduler(工作日21:10) -> subprocess refresh-market-data.sh
```

## 关键依赖
| 模块 | 外部依赖 | 职责 |
|---|---|---|
| auth.py | sqlite3, httpx | 会话/微信登录 |
| market_data.py | psycopg, json | postgres/file 行情+校验 |
| main.py | fastapi, starlette, uvicorn | HTTP 路由/静态/错误 |
| refresher.py | APScheduler, subprocess | 每日数据刷新定时 |
| dashboard.py | (纯计算) | 指标聚合 |

## 模块间引用
- `main.py` -> auth, config, market_data, dashboard, refresher
- `auth.py` -> config
- `market_data.py` -> config
- `dashboard.py` -> market_data

## 运维/启动
- `start-traderoff.sh`: `uvicorn web.app.main:app --host 0.0.0.0 --port 8788 --workers 1`
- `refresh-market-data.sh`: 逐脚本跑 notebooks + sync 入库
- `schedule-market-refresh.sh`: 旧调度器(已停用,功能并入 refresher.py)
- `deploy-no-build.sh`: 服务器无构建部署(git pull + compose up --no-build)

## 认证流程
微信 OAuth: `/api/auth/wechat` 生成 state -> 回调 `/api/auth/wechat/callback` -> 校验 state/单次消费 -> 建/找用户 -> Set-Cookie session(sha256 hash 存库) -> `/api/me` 返回用户
