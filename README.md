# Traderoff

[English](README.md) | [简体中文](README.zh-CN.md)

A-share market sentiment dashboard backed directly by Tushare Pro. It combines a five-factor fear and greed index with major-market performance tracking.

For production HTTPS deployment, low-memory server recovery, and verification commands, see the [production deployment guide](docs/production-deployment.md).

## Features

- Five-factor A-share sentiment index: QVIX, price strength, IF futures basis, volume deviation, and stock-bond safety demand.
- Market environment table and normalized 250-trading-day relative-performance charts for A shares, Hong Kong, and US markets.
- A 16-factor CNLT-style reference profile for the CSI 1800 reference universe, including coverage, index comparison, cross-sectional distributions, an SW2021 industry heatmap, and representative stocks.
- The factor module uses independently designed transparent proxies and is not an MSCI Barra official model. Missing financial data remains null and is disclosed through warnings.
- A dedicated `market-updater` container refreshes all nine datasets (including the 16-factor profile) on every weekday at 21:10 Asia/Shanghai time. The web service starts independently and never waits for a refresh.
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

4. Open `https://localhost`. Caddy listens on standard HTTP/HTTPS ports (`80` and `443`) and redirects HTTP traffic to HTTPS.

The initial refresh fetches the required historical series from Tushare and writes runtime files to `data/`. The directory is mounted so subsequent starts reuse the data cache. See the [production deployment guide](docs/production-deployment.md) for the low-memory server recovery procedure and verification commands.

## HTTPS And Public Deployment

The Compose stack uses Caddy as the public reverse proxy. The dashboard itself remains private on the Docker network, while Caddy publishes standard ports `80` and `443`.

For a public deployment, set `TRADEROFF_DOMAIN` in `.env`, point that domain's A/AAAA record at the server, and allow inbound TCP ports `80` and `443`. Caddy then obtains and renews the TLS certificate automatically and redirects HTTP requests to HTTPS:

```text
TRADEROFF_DOMAIN=traderoff.example.com
WECHAT_REDIRECT_URI=https://traderoff.example.com/api/auth/wechat/callback
```

For local development, retain `TRADEROFF_DOMAIN=localhost` and open `https://localhost`. Your browser may ask you to trust Caddy's local development certificate on first use.

## WeChat Login

`WECHAT_AUTH_MODE=development` is suitable for local use and simulates a test user. For production, set the following environment variables and configure the callback URL in the WeChat Open Platform:

```text
WECHAT_AUTH_MODE=production
WECHAT_APP_ID=...
WECHAT_APP_SECRET=...
WECHAT_REDIRECT_URI=https://your-domain.example/api/auth/wechat/callback
```

## Development

The dashboard server lives in `web/` (FastAPI backend + static pages). The tests read the generated `data/*.json` snapshots (file backend), which are not tracked in the repository. With `TUSHARE_TOKEN` set in `.env`, produce them once first — e.g. `docker compose run --rm market-updater /app/refresh-market-data.sh` — then set up dependencies and run:

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest web/tests/
```

The Docker image includes Python, NumPy, Pandas, SciPy, and Tushare for the scheduled refresh tasks, plus FastAPI, Uvicorn, and httpx for the web service. You can also generate the factor snapshot manually from the repository root with:

```sh
set -a; . ./.env; set +a
FEAR_GREED_DATA_DIR="$PWD/data" python3 notebooks/update_factor_exposure_tushare.py
```

The generator reuses `data/tushare_raw/equity_daily`. If financial API access is unavailable, it still writes a valid snapshot with null financial exposures and explicit `quality.warnings`. It runs as part of the daily refresh batch; if it fails, that batch is not imported and the site keeps serving the last complete snapshot.

After the runtime data has been produced (see above), run the server tests inside the container with:

```sh
docker compose exec traderoff sh -lc 'cd /app/web && python3 -m pytest tests'
```

## Data Source

All market data is fetched from [Tushare Pro](https://tushare.pro/). No credentials, user database, or runtime market data are tracked in this repository.
