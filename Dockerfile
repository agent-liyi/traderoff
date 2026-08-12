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
COPY web/static ./static
COPY notebooks/update_fear_greed_tushare.py /app/notebooks/update_fear_greed_tushare.py
COPY notebooks/update_market_environment_tushare.py /app/notebooks/update_market_environment_tushare.py
COPY start-traderoff.sh /app/start-traderoff.sh
RUN chmod +x /app/start-traderoff.sh && mkdir -p /app/data /app/web/data /app/data/tushare_raw

ENV TZ=Asia/Shanghai
ENV NODE_ENV=production
ENV PORT=8788
ENV FEAR_GREED_DATA=/app/data/fear_greed_runtime.json
ENV FEAR_GREED_DATA_DIR=/app/data
ENV MARKET_ENVIRONMENT_DATA=/app/data/market_environment_runtime.json
ENV USERS_DB=/app/web/data/users.sqlite

EXPOSE 8788
CMD ["/app/start-traderoff.sh"]
