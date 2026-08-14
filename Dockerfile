FROM node:24-bookworm-slim

LABEL description="A-share market sentiment dashboard with direct Tushare refresh"

RUN sed -i 's/deb.debian.org/mirrors.tuna.tsinghua.edu.cn/g' /etc/apt/sources.list.d/debian.sources
RUN apt-get update && apt-get install -y --no-install-recommends python3 python3-pip python3-venv build-essential gfortran libopenblas-dev liblapack-dev tzdata && rm -rf /var/lib/apt/lists/*
RUN ln -snf /usr/share/zoneinfo/Asia/Shanghai /etc/localtime && echo Asia/Shanghai > /etc/timezone

WORKDIR /app
COPY requirements.txt ./
RUN pip3 install --break-system-packages --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt

WORKDIR /app/web
COPY web/package.json web/package-lock.json ./
RUN npm ci --omit=dev
COPY web/server.js ./
COPY web/tests ./tests
COPY web/static ./static
COPY notebooks/ /app/notebooks/
COPY db/ /app/db/
COPY start-traderoff.sh /app/start-traderoff.sh
COPY refresh-market-data.sh /app/refresh-market-data.sh
COPY schedule-market-refresh.sh /app/schedule-market-refresh.sh
RUN chmod +x /app/start-traderoff.sh /app/refresh-market-data.sh /app/schedule-market-refresh.sh && mkdir -p /app/data /app/web/data /app/data/tushare_raw

ENV TZ=Asia/Shanghai
ENV NODE_ENV=production
ENV PORT=8788
ENV FEAR_GREED_DATA=/app/data/fear_greed_runtime.json
ENV FEAR_GREED_DATA_DIR=/app/data
ENV MARKET_ENVIRONMENT_DATA=/app/data/market_environment_runtime.json
ENV MARKET_STYLE_DATA=/app/data/market_style_runtime.json
ENV INDUSTRY_PRICE_DATA=/app/data/industry_price_runtime.json
ENV MARKET_VOLUME_DATA=/app/data/market_volume_runtime.json
ENV MARKET_VOLATILITY_DATA=/app/data/market_volatility_runtime.json
ENV MARKET_TURNOVER_DATA=/app/data/market_turnover_runtime.json
ENV MARKET_BREADTH_DATA=/app/data/market_breadth_runtime.json
ENV FACTOR_EXPOSURE_DATA=/app/data/factor_exposure_runtime.json
ENV MARKET_DATA_BACKEND=postgres
ENV USERS_DB=/app/web/data/users.sqlite

EXPOSE 8788
CMD ["/app/start-traderoff.sh"]
