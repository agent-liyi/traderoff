FROM node:24-bookworm-slim

LABEL description="A-share market sentiment dashboard with direct Tushare refresh"

RUN sed -i 's/deb.debian.org/mirrors.tuna.tsinghua.edu.cn/g' /etc/apt/sources.list.d/debian.sources
RUN apt-get update && apt-get install -y --no-install-recommends python3 python3-pip python3-venv build-essential gfortran libopenblas-dev liblapack-dev && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt ./
RUN pip3 install --break-system-packages --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt

WORKDIR /app/web
COPY web/package.json web/package-lock.json ./
RUN npm ci --omit=dev
COPY web/server.js ./
COPY web/tests ./tests
COPY web/static ./static
COPY notebooks/update_fear_greed_tushare.py /app/notebooks/update_fear_greed_tushare.py
COPY notebooks/update_market_environment_tushare.py /app/notebooks/update_market_environment_tushare.py
COPY notebooks/update_market_style_tushare.py /app/notebooks/update_market_style_tushare.py
COPY notebooks/update_industry_price_tushare.py /app/notebooks/update_industry_price_tushare.py
COPY notebooks/update_market_volume_tushare.py /app/notebooks/update_market_volume_tushare.py
COPY notebooks/update_market_volatility_tushare.py /app/notebooks/update_market_volatility_tushare.py
COPY notebooks/update_market_turnover_tushare.py /app/notebooks/update_market_turnover_tushare.py
COPY notebooks/update_market_breadth_tushare.py /app/notebooks/update_market_breadth_tushare.py
COPY notebooks/update_factor_exposure_tushare.py /app/notebooks/update_factor_exposure_tushare.py
COPY start-traderoff.sh /app/start-traderoff.sh
RUN chmod +x /app/start-traderoff.sh && mkdir -p /app/data /app/web/data /app/data/tushare_raw

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
ENV USERS_DB=/app/web/data/users.sqlite

EXPOSE 8788
CMD ["/app/start-traderoff.sh"]
