# Traderoff

[English](README.md) | 简体中文

基于 Tushare Pro 的 A 股市场情绪看板，包含五项恐惧贪婪指标与主要市场环境追踪。

生产 HTTPS 部署、低内存服务器恢复与验收清单见[生产部署文档](docs/production-deployment.md)。

## 功能

- 五项 A 股市场情绪指标：QVIX 波动率、股价强度、IF 期货升贴水、成交量偏离、股债避险需求。
- A股、港股、美股主要指数的区间收益表与250个交易日归一化相对收益走势。
- 中证1800参考股票池的16项CNLT风格多因子画像，包含数据覆盖率、主要指数暴露、截面分布、申万2021行业热力图和代表个股明细。
- 多因子模块是独立构建的透明代理，非 MSCI Barra 官方模型；缺失财务数据保持为空并展示 warning，不插值伪造。
- 容器启动时刷新 Tushare 数据，之后每5分钟检查一次更新。因子生成成本较高，不进入默认启动刷新链，需按需执行。
- A股数据按中国市场收盘时间处理：北京时间21:00前使用最近一个已开市交易日的数据。
- 可选的微信 OAuth 登录，用于控制五项情绪指标原始数值的查看权限。

## 使用 Docker 运行

1. 创建环境变量文件并填入 Tushare Pro Token：

   ```sh
   cp .env.example .env
   ```

2. 编辑 `.env`，设置 `TUSHARE_TOKEN`。

3. 构建并启动服务：

   ```sh
   docker compose up -d --build
   ```

4. 在浏览器访问 `https://localhost`。Caddy 监听标准 HTTP/HTTPS 端口（`80`、`443`），并自动将 HTTP 请求跳转到 HTTPS。

首次启动时会从 Tushare 获取计算所需的历史序列，并写入 `data/`。该目录通过卷挂载保留，因此后续启动可以复用数据缓存。低内存服务器的运行时恢复方案及验证命令见[生产部署文档](docs/production-deployment.md)。

## HTTPS 与公网部署

Compose 使用 Caddy 作为对外反向代理。应用容器只在 Docker 内部网络监听，Caddy 对外发布标准端口 `80` 和 `443`。

公网部署时，在 `.env` 中设置 `TRADEROFF_DOMAIN`，将该域名的 A/AAAA 记录解析到服务器，并在防火墙或安全组中开放 TCP `80` 与 `443`。Caddy 会自动申请和续期 TLS 证书，并将 HTTP 自动跳转到 HTTPS：

```text
TRADEROFF_DOMAIN=traderoff.example.com
WECHAT_REDIRECT_URI=https://traderoff.example.com/api/auth/wechat/callback
```

本地开发可保留 `TRADEROFF_DOMAIN=localhost`，通过 `https://localhost` 访问。首次访问时，浏览器可能要求信任 Caddy 的本地开发证书。

## 微信登录

本地开发可保持 `WECHAT_AUTH_MODE=development`，系统会模拟一个微信测试账户。

生产环境需要在微信开放平台配置回调地址，并在 `.env` 中设置：

```text
WECHAT_AUTH_MODE=production
WECHAT_APP_ID=...
WECHAT_APP_SECRET=...
WECHAT_REDIRECT_URI=https://your-domain.example/api/auth/wechat/callback
```

## 开发与测试

前端服务位于 `web/`。可在本地安装依赖并执行测试：

```sh
cd web
npm ci
npm test
```

Docker 镜像内包含定时刷新所需的 Python、NumPy、Pandas、SciPy 与 Tushare。多因子快照可在项目根目录显式生成，脚本优先复用 `data/tushare_raw/equity_daily` 长期缓存，并将结果写入 `data/factor_exposure_runtime.json`：

```sh
set -a; . ./.env; set +a
FEAR_GREED_DATA_DIR="$PWD/data" python3 notebooks/update_factor_exposure_tushare.py
```

财务接口权限不足时生成仍会完成，相关因子的覆盖率为零、指数暴露为 `null`，限制会记录在 `quality.warnings`。该脚本不会由 `start-traderoff.sh` 默认调用，因此失败不会阻塞服务。

启动服务并生成运行时数据后，也可以在容器内执行测试：

```sh
docker compose exec traderoff sh -lc 'cd /app/web && npm test'
```

## 数据来源与安全

所有行情数据来自 [Tushare Pro](https://tushare.pro/)。本仓库不追踪 Tushare Token、微信凭据、用户数据库或运行时行情数据。
