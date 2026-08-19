# 贡献指南 (CONTRIB.md)

> 生成:2026-08-18
> 唯一数据源说明:本项目曾为 Node.js(有 package.json),迁移到 FastAPI 后已删除。
> 以下脚本/环境信息从 `.env.example`、根脚本、`requirements.txt`、`.github/workflows/ci.yml` 同步。

## 项目结构

```
web/app/        FastAPI 后端(路由/认证/数据/调度)
web/static/     前端(原生 JS + HTML)
web/tests/      pytest 测试(自包含,离线可跑)
notebooks/      数据刷新管道(Tushare 拉取→入库)
codemaps/       架构文档
docs/           运维与贡献文档
```

## 开发工作流

1. 改后端 `web/app/**` 或前端 `web/static/**`
2. 改 `notebooks/**` 数据管道
3. 本地跑测试(见下)
4. push 到 `main`,GitHub Actions 自动:测试 → 通过后 SSH 部署腾讯云

## 可用脚本(原 package.json scripts → 根 shell 脚本)

| 脚本 | 用途 |
|---|---|
| `start-traderoff.sh` | 启动 FastAPI:`uvicorn web.app.main:app --port 8788` |
| `refresh-market-data.sh` | 手动刷新全部市场数据(拉 Tushare→写 JSON→入库) |
| `deploy-no-build.sh` | 服务器无构建部署(git pull + compose up --no-build) |
| `schedule-market-refresh.sh` | 旧独立调度器(已停用——每日刷新已并入 `web/app/refresher.py` 的 APScheduler) |

## 依赖

`requirements.txt`:
```
numpy pandas scipy tushare psycopg[binary] fastapi uvicorn httpx APScheduler
```

## 环境设置(来自 .env.example)

| 变量 | 用途 | 格式/说明 |
|---|---|---|
| `TUSHARE_TOKEN` | Tushare Pro 数据拉取令牌 | 必填;Tushare 注册获取 |
| `POSTGRES_PASSWORD` | PostgreSQL 密码(compose 用) | 必填;URL-safe 随机值,勿含 `@ : / ? # %` |
| `TRADEROFF_DOMAIN` | 公网域名(Caddy HTTPS/微信回调) | 默认 `localhost`;生产设 A 记录指向服务器 |
| `WECHAT_AUTH_MODE` | 微信登录模式 | `development`(模拟)/`production` |
| `WECHAT_APP_ID` | 微信开放平台 AppID | 生产必填 |
| `WECHAT_APP_SECRET` | 微信开放平台 AppSecret | 生产必填 |
| `WECHAT_REDIRECT_URI` | 微信登录回调地址 | 生产设置 `https://<domain>/api/auth/wechat/callback` |
| `MARKET_DATABASE_URL` | 外部 PostgreSQL 连接串(可选) | 仅独立进程/外部库时设置;compose 自动注入 |

复制方式:`cp .env.example .env` 后编辑,`.env` 已被 gitignore。

## 测试流程

最小环境(离线,不需 Tushare/数据库):
```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt pytest pytest-cov
.venv/bin/python -m pytest web/tests/ --cov=web.app
```

- 测试**自包含**:conftest 生成最小数据快照,不依赖 `data/*.json`
- 覆盖率:总体 ≥80%,关键模块(auth/dashboard/refresher)100%
- CI 用 `.github/workflows/ci.yml`:python 3.11,`--cov-fail-under=75`

## 代码规范
- 后端:FastAPI 同步端点(避免 async 混用),类型注解
- 数据库:参数化查询(sqlite `?` / psycopg `%s`),禁止拼接
- 认证:会话 token sha256 存库,Cookie HttpOnly;SameSite=Lax
