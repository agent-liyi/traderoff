# Traderoff

A-share market sentiment dashboard backed directly by Tushare Pro. It combines a five-factor fear and greed index with major-market performance tracking.

## Features

- Five-factor A-share sentiment index: QVIX, price strength, IF futures basis, volume deviation, and stock-bond safety demand.
- Market environment table and normalized 250-trading-day relative-performance charts for A shares, Hong Kong, and US markets.
- Tushare refresh worker runs at startup and checks for updates every five minutes.
- China market close gate: before 21:00 Asia/Shanghai time, the refresh uses the prior open trading day.
- Optional WeChat OAuth login controls access to raw sentiment factor values.

## Run With Docker

1. Create an environment file and provide a Tushare Pro token:

   ```sh
   cp .env.example .env
   ```

2. Edit `.env` and set `TUSHARE_TOKEN`.

3. Start the service:

   ```sh
   docker compose up -d --build
   ```

4. Open `http://localhost:8788`.

The initial refresh fetches the required historical series from Tushare and writes runtime files to `data/`. The directory is mounted so subsequent starts reuse the data cache.

## WeChat Login

`WECHAT_AUTH_MODE=development` is suitable for local use and simulates a test user. For production, set the following environment variables and configure the callback URL in the WeChat Open Platform:

```text
WECHAT_AUTH_MODE=production
WECHAT_APP_ID=...
WECHAT_APP_SECRET=...
WECHAT_REDIRECT_URI=https://your-domain.example/api/auth/wechat/callback
```

## Development

The dashboard server lives in `web/`. Run tests with:

```sh
cd web
npm ci
npm test
```

The Docker image includes Python, NumPy, Pandas, SciPy, and Tushare for the scheduled refresh tasks. After `docker compose up -d --build` has produced the runtime data, run the server tests inside the container with:

```sh
docker compose exec traderoff sh -lc 'cd /app/web && npm test'
```

## Data Source

All market data is fetched from [Tushare Pro](https://tushare.pro/). No credentials, user database, or runtime market data are tracked in this repository.
