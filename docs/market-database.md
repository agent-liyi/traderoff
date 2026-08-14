# 行情数据库与自动更新

## 持久化边界

PostgreSQL 16 + pgvector 是行情数据的唯一持久化来源：

- `market_fear_greed_daily`：恐惧贪婪指数逐交易日明细，可按日期直接查询。
- `market_runtime_snapshots`：八个市场页面与多因子页面的完整 API 快照；Web 服务只从该表读取。
- `tushare_raw_cache`：所有生成器已获取的 Tushare 压缩 CSV 原始响应，带 SHA-256 校验和及来源路径。
- `market_refresh_runs`：每次刷新状态、目标交易日与失败原因。
- `market_documents`：为 AI 检索预留的 pgvector 文档表，行情入库不生成或伪造 embedding。

`data/*.json` 和 `data/tushare_raw/` 只用于生成器计算、初始迁移与本地缓存；它们不是网站读取的数据源。

## 首次迁移

1. 在服务器的 `.env` 设置 `POSTGRES_PASSWORD`。密码必须使用 URL 安全字符，不能包含 `@`、`:`、`/`、`?`、`#` 或 `%`。
2. 先启动数据库并等待健康检查：

```sh
cd /home/traderoff/apps/traderoff
docker compose up -d postgres
docker compose ps postgres
```

3. 将当前已有 JSON 和全部 `data/tushare_raw/` 原始缓存导入数据库：

```sh
docker compose run --rm --no-deps market-updater \
  python3 /app/notebooks/sync_market_data.py --data-dir /app/data
```

4. 验证行数与快照日期：

```sh
docker compose exec postgres psql -U traderoff -d traderoff -c \
  "SELECT dataset, as_of, updated_at FROM market_runtime_snapshots ORDER BY dataset;"
docker compose exec postgres psql -U traderoff -d traderoff -c \
  "SELECT count(*) AS fear_greed_days, max(trade_date) AS latest_day FROM market_fear_greed_daily;"
docker compose exec postgres psql -U traderoff -d traderoff -c \
  "SELECT status, target_trade_date, completed_at FROM market_refresh_runs ORDER BY started_at DESC LIMIT 5;"
```

5. 启动网站和定时更新服务：

```sh
docker compose up -d traderoff market-updater caddy
```

只有第 3 步成功后，才切换 Web 服务到数据库读取；若数据库没有完整快照，接口会返回 `503`，不会静默回退到旧 JSON。

## 自动更新

`market-updater` 是独立容器，按 `Asia/Shanghai` 时区在每个工作日 `21:10` 执行。21:00 是数据可用闸门，预留 10 分钟给 Tushare 数据落库；各生成器仍会使用自己的交易日历校验，并在节假日回退到最近开市日。

更新顺序为：拉取或复用 Tushare 缓存，生成九份页面快照，最后在一个 PostgreSQL 事务中导入全部快照与新增原始响应。任何生成步骤失败时，导入不会发生，网站继续服务上一份成功行情。

查看下一次调度和最近一次结果：

```sh
docker compose logs --tail=100 market-updater
docker compose exec postgres psql -U traderoff -d traderoff -c \
  "SELECT status, target_trade_date, started_at, completed_at, error_message FROM market_refresh_runs ORDER BY started_at DESC LIMIT 10;"
```

## 备份与恢复

每天更新前或数据库升级前执行逻辑备份：

```sh
mkdir -p backups
docker compose exec -T postgres pg_dump -U traderoff -d traderoff -Fc > backups/traderoff-$(date +%F).dump
```

恢复到空库：

```sh
cat backups/traderoff-YYYY-MM-DD.dump | docker compose exec -T postgres pg_restore -U traderoff -d traderoff --clean --if-exists
```

不要把 `.env`、`data/`、PostgreSQL volume 或备份文件提交 Git。
