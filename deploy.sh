#!/bin/bash
# ============================================
# 动态平衡播客 — 一键部署脚本
# ============================================
# 在腾讯云服务器上执行：
#   chmod +x deploy.sh
#   ./deploy.sh
# ============================================

set -e

APP_DIR="/app/podcast-site"
DATA_DIR="/data/podcast"
REPO_URL="git@github.com:agent-liyi/traderoff.git"
BRANCH="main"

echo "🚀 动态平衡播客 — 开始部署"

# 1. 创建数据和日志目录
echo "  📁 创建目录..."
sudo mkdir -p "$DATA_DIR" /var/log/podcast
sudo chown -R $USER:$USER "$DATA_DIR" /var/log/podcast

# 2. 克隆 / 拉取代码
if [ -d "$APP_DIR/.git" ]; then
  echo "  📦 拉取最新代码..."
  cd "$APP_DIR"
  git fetch origin
  git reset --hard "origin/$BRANCH"
else
  echo "  📦 克隆仓库..."
  sudo mkdir -p "$APP_DIR"
  sudo chown -R $USER:$USER "$APP_DIR"
  git clone "$REPO_URL" "$APP_DIR"
  cd "$APP_DIR"
fi

# 3. 配置环境变量
if [ ! -f "$APP_DIR/.env.production" ]; then
  if [ -f "$APP_DIR/.env.production.template" ]; then
    echo "  ⚙️  从模板创建 .env.production..."
    cp "$APP_DIR/.env.production.template" "$APP_DIR/.env.production"
    echo "  ⚠️  请编辑 $APP_DIR/.env.production 设置密码和域名！"
  else
    echo "  ⚙️  创建 .env.production..."
    cat > "$APP_DIR/.env.production" << EOF
SQLITE_DB_PATH=file:$DATA_DIR/podcast.db
ADMIN_PASSWORD=请修改此密码
NEXT_PUBLIC_SITE_URL=https://dongtaipingheng.com
PORT=3000
EOF
    echo "  ⚠️  请编辑 $APP_DIR/.env.production 设置密码和域名！"
  fi
else
  echo "  ⚙️  .env.production 已存在，跳过"
fi

# 4. 安装依赖
echo "  📦 安装依赖..."
npm install

# 5. 初始化数据库
echo "  🗄️  初始化数据库..."
npx tsx scripts/init-db.ts

# 6. 构建
echo "  🔨 构建 Next.js..."
npm run build

# 7. 重启服务
if command -v pm2 &> /dev/null; then
  if pm2 list | grep -q dongtaipingheng; then
    echo "  🔄 重启 PM2 进程..."
    pm2 restart dongtaipingheng
  else
    echo "  🟢 启动 PM2 进程..."
    pm2 start ecosystem.config.cjs
    pm2 save
    pm2 startup | grep "sudo" | bash 2>/dev/null || true
  fi
  pm2 status
else
  echo "  ⚠️  PM2 未安装，请手动启动：npm start"
fi

echo "✅ 部署完成！"
echo "   访问: https://dongtaipingheng.com"
echo "   数据库: $DATA_DIR/podcast.db"
echo "   日志: /var/log/podcast/"
