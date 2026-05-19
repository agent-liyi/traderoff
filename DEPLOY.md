# 动态平衡播客 — 腾讯云服务器部署指南

## 架构

```
用户浏览器
    │
    ▼
nginx (80/443) ──→ Next.js (PM2 cluster, :3000) ──→ SQLite (/data/podcast/podcast.db)
                                                           │
                                             ┌─────────────┼─────────────┐
                                             │             │             │
                                        文案 (TEXT)   封面图 (BLOB)   音频 (BLOB)
```

所有数据（文案、封面图、音频）都存在本地 SQLite 数据库中，不依赖任何外部托管。

---

## 第一步：服务器准备

### 硬件建议
- **配置**：2 核 4GB（腾讯云轻量应用服务器即可）
- **系统**：Ubuntu 22.04 LTS
- **带宽**：3Mbps 起步（播客听众不多的话够用）

### 基础环境

```bash
# 更新系统
sudo apt update && sudo apt upgrade -y

# 安装 Node.js 20
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs

# 安装 PM2 进程管理器
sudo npm install -g pm2

# 安装 nginx
sudo apt install -y nginx

# 安装 git
sudo apt install -y git

# 验证
node -v   # 应该显示 v20.x
npm -v
pm2 -v
nginx -v
```

---

## 第二步：拉取代码并配置

```bash
# 创建应用目录
sudo mkdir -p /app /data/podcast /var/log/podcast
sudo chown -R $USER:$USER /app /data/podcast /var/log/podcast

# 克隆代码
git clone git@github.com:agent-liyi/traderoff.git /app/podcast-site
cd /app/podcast-site

# 安装依赖
npm install

# 配置环境变量
cp .env.production.template .env.production
nano .env.production   # 修改 ADMIN_PASSWORD 和域名
```

`.env.production` 内容：
```env
SQLITE_DB_PATH=file:/data/podcast/podcast.db
ADMIN_PASSWORD=你的安全密码
NEXT_PUBLIC_SITE_URL=https://dongtaipingheng.com
PORT=3000
```

---

## 第三步：初始化数据库

```bash
npx tsx scripts/init-db.ts
```

输出应显示 `✅ Database initialized successfully`。

---

## 第四步：构建并启动

```bash
# 构建
npm run build

# 测试启动（确认没有报错后 Ctrl+C 退出）
npm start

# PM2 正式启动
pm2 start ecosystem.config.cjs
pm2 save
pm2 startup   # 设置开机自启，按提示执行输出的 sudo 命令
```

检查状态：
```bash
pm2 status
pm2 logs dongtaipingheng
```

---

## 第五步：配置 nginx

```bash
# 复制 nginx 配置
sudo cp /app/podcast-site/nginx.conf /etc/nginx/sites-available/dongtaipingheng
sudo ln -s /etc/nginx/sites-available/dongtaipingheng /etc/nginx/sites-enabled/

# 测试配置
sudo nginx -t

# 重载
sudo nginx -s reload
```

---

## 第六步：配置域名 DNS

在域名管理后台（腾讯云 DNSPod）添加 A 记录：
```
dongtaipingheng.com  →  你的服务器公网 IP
www.dongtaipingheng.com  →  你的服务器公网 IP
```

---

## 第七步：配置 SSL（HTTPS）

```bash
# 安装 certbot
sudo apt install -y certbot python3-certbot-nginx

# 申请证书
sudo certbot --nginx -d dongtaipingheng.com -d www.dongtaipingheng.com

# 证书会自动续期，验证一下
sudo certbot renew --dry-run
```

申请成功后，编辑 `/etc/nginx/sites-available/dongtaipingheng`，取消 SSL server block 的注释，重载 nginx。

---

## 日常维护

### 部署新版本

```bash
cd /app/podcast-site
./deploy.sh
```

### 备份数据库

```bash
# 手动备份
cp /data/podcast/podcast.db /data/podcast/backup-$(date +%Y%m%d).db

# 定时备份（crontab -e）
0 3 * * * cp /data/podcast/podcast.db /data/podcast/backup-$(date +\%Y\%m\%d).db
```

### 查看日志

```bash
pm2 logs dongtaipingheng --lines 50
tail -f /var/log/nginx/access.log
```

---

## 文件结构

```
/app/podcast-site/          # 项目代码
/data/podcast/podcast.db    # SQLite 数据库（所有内容都在这里）
/var/log/podcast/           # PM2 日志
/etc/nginx/sites-available/ # nginx 配置
```
