# Traderoff

[English](README.md) | 简体中文

基于 Tushare Pro 的 A 股市场情绪看板，包含五项恐惧贪婪指标与主要市场环境追踪。

## 功能

- 五项 A 股市场情绪指标：QVIX 波动率、股价强度、IF 期货升贴水、成交量偏离、股债避险需求。
- A股、港股、美股主要指数的区间收益表与250个交易日归一化相对收益走势。
- 容器启动时刷新 Tushare 数据，之后每5分钟检查一次更新。
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

4. 在浏览器访问 `http://localhost:8788`。

首次启动时会从 Tushare 获取计算所需的历史序列，并写入 `data/`。该目录通过卷挂载保留，因此后续启动可以复用数据缓存。

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

Docker 镜像内包含定时刷新所需的 Python、NumPy、Pandas、SciPy 与 Tushare。启动服务并生成运行时数据后，也可以在容器内执行测试：

```sh
docker compose exec traderoff sh -lc 'cd /app/web && npm test'
```

## 数据来源与安全

所有行情数据来自 [Tushare Pro](https://tushare.pro/)。本仓库不追踪 Tushare Token、微信凭据、用户数据库或运行时行情数据。
