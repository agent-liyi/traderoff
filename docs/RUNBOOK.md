# 运维手册 (RUNBOOK.md)

> 生成:2026-08-18
> 架构:腾讯云 CVM · Docker Compose(3 容器)· FastAPI · PostgreSQL 16 + pgvector · Caddy

## 部署流程

### 自动部署(推荐)
每次 push 到 `main`,GitHub Actions(见 `docs/github-actions.md`)自动:
1. 跑测试(89+ 用例)
2. 通过后 SSH 到腾讯云:`git reset --hard origin/main` -> `docker compose build` -> `docker compose up`

所需的 GitHub Secrets:`SSH_HOST`、`SSH_USER`、`SSH_PRIVATE_KEY`、`SSH_PORT`。

### 手动部署
```sh
ssh traderoff@<server_ip>
cd ~/apps/traderoff
git fetch origin main && git reset --hard origin/main
docker compose build traderoff
docker compose up -d --no-deps --force-recreate traderoff
docker compose ps
```

## 服务/容器

| 容器 | 职责 | 端口 |
|---|---|---|
| traderoff | FastAPI + APScheduler 每日刷新 | 8788(内部) |
| postgres | PostgreSQL 16 + pgvector | 内部 |
| caddy | HTTPS 反代/TLS | 80/443 |

> 每日数据刷新由 traderoff 进程内 APScheduler 承担(工作日 21:10 Asia/Shanghai),无独立 market-updater 容器。

## 监控与告警

- **访问监控**:公网 `https://traderoff.top` 应返回 200;`/api/dashboard` 等端点可探活。
- **每日刷新**:查看 `market_refresh_runs` 表最近一行 `status`/`target_trade_date`;失败时数据库保留上次完整数据。
- **容器健康**:`docker ps` 应显示 traderoff/postgres(healthy)/caddy 均 Up。
- **日志**:`docker logs traderoff`(web+调度器)、`docker logs traderoff-postgres`。
- **资源**:1.9GiB 小内存机;关注 `free -h`,刷新时避免 OOM(增量脚本控制窗口大小)。
- **数据新鲜度**:`/api/dashboard` 的 `asOf` 应为最近交易日;滞后说明刷新失败。

## 常见问题与修复 (FAQ)

### 1. 网站 502 / 首页打不开
- `docker ps` 检查容器;`docker logs traderoff` 看报错
- 常见:容器未重启/镜像旧。执行 `docker compose up -d --no-deps --force-recreate traderoff`
- 若 Caddy 反代连不上 → 确认 traderoff 在 `traderoff_default` 网络且监听 8788

### 2. 数据显示不是最新交易日
- 每日刷新失败(查看 `market_refresh_runs`)
- 手动触发:`docker exec traderoff sh -c "bash /app/refresh-market-data.sh"`(或直接跑 `update_fear_greed_incremental.py`)
- 服务器到 GitHub 网络不稳时 `git fetch` 会失败 → 部署受阻;网络恢复后重跑 CI 或手动部署

### 3. 每日刷新在 21:10 未执行
- 确认 traderoff 容器内 APScheduler 已启动:`docker exec traderoff python3 -c "from web.app import refresher; print(refresher._scheduler)"`(非 None 且 running)
- 检查 `docker logs traderoff` 是否有 refresher 日志

### 4. 微信登录异常
- `WECHAT_AUTH_MODE=production` 需要正确的 `WECHAT_APP_ID/SECRET/REDIRECT_URI`
- development 模式用模拟用户,无需真实微信

### 5. 数据库问题
- postgres 不 healthy → `docker logs traderoff-postgres`
- 数据卷持久化于 `traderoff_postgres_data`

## 回滚流程

1. **回滚代码**:`git` 到上一个 commit
   ```sh
   cd ~/apps/traderoff
   git checkout <previous_sha>
   docker compose build traderoff
   docker compose up -d --no-deps --force-recreate traderoff
   ```
2. **回滚数据**:数据库卷 `traderoff_postgres_data` 是持久化的;如需回到某日,从备份恢复(见 `docs/market-database.md`)。
3. **紧急回退**:保留旧镜像 tag;`docker compose up` 用指定镜像行重启。

## 备份
- PostgreSQL:建议定期 `pg_dump`(见表结构 `db/init/001_market_data.sql`)
- 用户库 `web/data/users.sqlite`:随 `./web/data` 卷持久化
- 生产密钥 `.env` 与 `docker-compose.override.yml`(若用)不入 git,必要时单独备份
