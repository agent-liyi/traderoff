# 生产部署与运行时恢复

本文记录 Traderoff 的标准 HTTPS 部署方式、低配置服务器上的运行时恢复方案，以及验收口径。业务代码、Docker 镜像和 Git 跟踪的 Compose 主配置均不需要为本方案修改。

## 架构

```text
Internet
  |
  | TCP 80 / 443
  v
Caddy container
  |  HTTP reverse proxy
  v
Traderoff container :8788
  |
  v
/app/data (host ./data volume)
```

- Caddy 对外发布 `80`、`443` 和 UDP `443`，自动申请、保存并续期 TLS 证书。
- Traderoff 仅在 Docker 网络中暴露 `8788`，不直接发布到主机端口。
- `./data` 挂载到容器 `/app/data`，存放运行时 JSON、Tushare 缓存和用户数据库。

## 前置条件

1. 域名的 A/AAAA 记录已解析到服务器。
2. 防火墙或云安全组已放通 TCP `80`、`443`；若要启用 HTTP/3，再放通 UDP `443`。
3. 服务器已安装 Docker Engine、Docker Compose 和 Git。
4. 部署用户有执行 Docker 命令的权限。
5. `.env` 仅保存在服务器，至少包含：

   ```dotenv
   TUSHARE_TOKEN=replace-with-server-secret
   TRADEROFF_DOMAIN=traderoff.example.com
   WECHAT_AUTH_MODE=development
   ```

不要将 `.env`、Token、OAuth 密钥、SQLite 用户库或 `data/` 提交到仓库。

## 标准部署

```sh
mkdir -p ~/apps
cd ~/apps
git clone https://github.com/agent-liyi/traderoff.git
cd traderoff
cp .env.example .env
# 编辑 .env，填入仅服务器保存的 TUSHARE_TOKEN 和实际域名
docker compose up -d --build
```

检查容器：

```sh
docker compose ps
docker compose logs --tail=100 traderoff
docker compose logs --tail=100 caddy
```

首次全量刷新需要从 Tushare 获取长期历史数据。在低内存服务器上，这个过程可能耗时较长并占用明显的 CPU 和内存；此时 Caddy 可能可用，但应用尚未监听内部端口，公网会暂时返回 `502`。

## 本次低内存服务器恢复方案

### 触发条件

本次生产恢复针对以下情况：

- `traderoff` 容器反复重启；
- Caddy 日志出现 `connect: connection refused`，公网返回 `502`；
- 启动时的 Tushare 刷新因空或损坏缓存失败；
- 启动脚本在 Node 服务之前执行全量刷新，使小规格主机长期高负载、难以 SSH。

### 数据保护与恢复

先停止应用容器，Caddy 可保持运行：

```sh
cd ~/apps/traderoff
docker compose stop traderoff
```

不要直接删除现有 `data/`。先移动到备份目录：

```sh
stamp=$(date +%Y%m%d-%H%M%S)
mkdir -p data-backups
mv data "data-backups/data-${stamp}"
mkdir data
```

再恢复已校验的运行时数据和 Tushare 缓存。来源可以是受控的备份或另一台已验证的部署，归档内容必须保留以下路径：

```text
data/fear_greed_runtime.json
data/market_environment_runtime.json
data/tushare_raw/
```

恢复后应验证：

```sh
test -s data/fear_greed_runtime.json
test -s data/market_environment_runtime.json
find data -type f -size 0 -print
```

前两条命令必须成功，最后一条不应输出任何文件。

### 服务器本地运行时覆盖

当前恢复后的运行时覆盖文件为 `docker-compose.override.yml`。该文件只保存在服务器，不提交到仓库：

```yaml
services:
  traderoff:
    command: ["node", "/app/web/server.js"]
    environment:
      FEAR_GREED_DATA_DIR: /app/data
      FEAR_GREED_DATA: /app/data/fear_greed_runtime.json
      MARKET_ENVIRONMENT_DATA: /app/data/market_environment_runtime.json
```

该覆盖有两个目的：

1. 让 Node 数据服务使用持久化的 `/app/data`，避免读取镜像默认的临时目录；后续恢复刷新器时也必须保留该数据目录变量。
2. 覆盖默认启动脚本，直接启动 Node 服务，使已有验证数据先对外可用。

应用覆盖并启动：

```sh
docker compose config >/dev/null
docker compose up -d --force-recreate traderoff
```

确认应用没有重启且正在读取正确数据目录：

```sh
docker inspect traderoff --format 'restart={{.RestartCount}} running={{.State.Running}} oom={{.State.OOMKilled}} exit={{.State.ExitCode}}'
docker exec traderoff sh -c 'printf "dir=%s\n" "$FEAR_GREED_DATA_DIR"; test -s "$FEAR_GREED_DATA" && echo fear-data=ok; test -s "$MARKET_ENVIRONMENT_DATA" && echo market-data=ok'
```

预期：`restart=0`、`running=true`、`oom=false`、`dir=/app/data`，并显示两条 `*-data=ok`。

> 注意：此运行时覆盖会禁用 `start-traderoff.sh` 中的启动刷新和五分钟刷新循环。因此部署恢复后不会自动更新 Tushare 数据。正式恢复自动刷新前，需要在代码层将刷新流程改为“先启动网站，后在后台刷新”，并让空或损坏缓存自动重新拉取。该代码改动不属于本次恢复方案。

## 公网验收

将 `traderoff.example.com` 替换为实际域名。可在部署服务器或任意能解析该域名的机器上执行：

```sh
curl -I http://traderoff.example.com/
curl -fsS https://traderoff.example.com/ -o /dev/null
curl -fsS 'https://traderoff.example.com/api/dashboard?range=1y' -o /tmp/dashboard.json
curl -fsS https://traderoff.example.com/api/market-environment -o /tmp/market-environment.json
```

HTTP 响应应为 `308 Permanent Redirect`，并包含：

```text
Location: https://traderoff.example.com/
```

校验 API 结构：

```sh
node - <<'NODE'
const dashboard = require('/tmp/dashboard.json');
const market = require('/tmp/market-environment.json');
if (!dashboard.asOf || !Number.isFinite(dashboard.index?.score)) throw new Error('dashboard index is invalid');
if (dashboard.series?.length !== 250) throw new Error('expected 250 dashboard rows for range=1y');
if (dashboard.indicators?.length !== 5) throw new Error('expected five indicators');
if (!market.asOf || market.indices?.length !== 12) throw new Error('expected twelve market indices');
if (market.indices.some((item) => item.history?.length !== 250)) throw new Error('expected 250 history rows for each index');
console.log('deployment verification passed');
NODE
```

还应确认首页静态资源可访问：

```sh
for asset in /app.js /styles.css /assets/traderoff-logo.png; do
  curl -fsS -o /dev/null "https://traderoff.example.com${asset}"
done
```

## 本次生产验收基线

恢复完成后，以下结果已经通过：

| 检查项 | 结果 |
| --- | --- |
| HTTP 首页 | `308` 跳转 HTTPS |
| HTTPS 首页 | HTTP/2 `200` |
| `/api/dashboard?range=1y` | `200`，250条历史、5项指标 |
| `/api/dashboard?range=6m` | `200`，126条历史 |
| `/api/market-environment` | `200`，12个指数、每个250日序列 |
| 首页脚本、样式、Logo | 均返回 `200` |
| 应用容器 | `running=true`、`restart=0`、未发生 OOM |
| 运行时目录 | `/app/data`，两份 JSON 均存在且非空 |

当时运行时数据最新日期为 `2026-08-11`。该日期会在自动刷新恢复后随交易日更新。

## 日常运维

查看状态和日志：

```sh
cd ~/apps/traderoff
docker compose ps
docker compose logs --tail=100 traderoff
docker compose logs --tail=100 caddy
```

重启服务时，保留服务器本地的 `docker-compose.override.yml`：

```sh
docker compose up -d --force-recreate
```

更新镜像或拉取仓库代码前，先检查运行时覆盖与新的 Compose 配置是否仍兼容：

```sh
git pull --ff-only
docker compose config >/dev/null
docker compose up -d --build
```

不要通过 `git clean -fd` 清理部署目录，它会移除未跟踪的运行时覆盖文件和可能存在的运维文件。
