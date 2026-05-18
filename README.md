# 动态平衡 - 播客网站

一个基于 Next.js 的播客展示与管理网站。

## 技术栈

- Next.js 14 (App Router)
- TypeScript
- Tailwind CSS
- Turso / libSQL（@libsql/client，支持本地 SQLite 和云端 Turso）
- TipTap 富文本编辑器

## 快速开始

```bash
# 安装依赖
npm install

# 初始化数据库并插入示例数据
npm run db:seed

# 启动开发服务器
npm run dev
```

打开 http://localhost:3000 查看网站。

本地开发默认使用 `file:./data/podcast.db`，不需要 Turso 账号。

## 后台管理

访问 http://localhost:3000/admin 进入后台管理。

默认密码：`admin123`（可在 `.env.local` 中修改 `ADMIN_PASSWORD`）

### 后台功能

- 查看/编辑/删除节目
- 新建节目（支持富文本编辑器）
- 上传封面图

## 项目结构

```
podcast-site/
├── src/
│   ├── app/
│   │   ├── page.tsx              # 首页
│   │   ├── about/page.tsx        # 关于页
│   │   ├── episodes/[id]/page.tsx # 节目详情
│   │   ├── admin/                # 后台管理
│   │   │   ├── layout.tsx        # 后台布局（含登录）
│   │   │   ├── page.tsx          # 节目列表
│   │   │   ├── new/page.tsx      # 新建节目
│   │   │   └── episodes/[id]/edit/page.tsx # 编辑节目
│   │   └── api/                  # API 路由
│   │       ├── episodes/         # CRUD
│   │       ├── upload/           # 图片上传
│   │       └── auth/             # 登录验证
│   ├── components/
│   │   ├── RichTextEditor.tsx    # TipTap 编辑器
│   │   └── EpisodeForm.tsx       # 节目表单
│   └── lib/
│       ├── db.ts                 # 数据库连接（@libsql/client）
│       └── types.ts              # TypeScript 类型
├── data/                         # 本地 SQLite 数据库文件（不提交到 git）
├── public/uploads/               # 上传的封面图
├── scripts/
│   ├── init-db.ts                # 仅建表（不插入数据）
│   └── seed.ts                   # 建表 + 插入示例数据
└── .env.local                    # 环境变量
```

## 环境变量

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `ADMIN_PASSWORD` | 后台管理密码 | `admin123` |
| `NEXT_PUBLIC_SITE_URL` | 网站基础 URL | `https://dongtaipingheng.com` |
| `TURSO_DATABASE_URL` | 数据库 URL | `file:./data/podcast.db`（本地） |
| `TURSO_AUTH_TOKEN` | Turso 认证 Token | 本地开发留空即可 |

## 数据库脚本

```bash
# 仅初始化表结构（不插入数据）
npm run db:init

# 建表 + 插入示例数据
npm run db:seed
```

## 部署到 Vercel + Turso

1. 在 [Turso](https://turso.tech) 创建数据库，获取 URL 和 Token
2. 在 Vercel 项目的 Environment Variables 中设置：
   - `TURSO_DATABASE_URL` = `libsql://your-db.turso.io`
   - `TURSO_AUTH_TOKEN` = `your-token`
3. 在本地运行 `TURSO_DATABASE_URL=libsql://your-db.turso.io TURSO_AUTH_TOKEN=your-token npm run db:seed` 初始化云端数据库
4. Push 代码，Vercel 自动部署

本地开发只需 `TURSO_DATABASE_URL=file:./data/podcast.db`，无需 Turso 账号。
