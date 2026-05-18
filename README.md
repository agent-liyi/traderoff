# 动态平衡 - 播客网站

一个基于 Next.js 的播客展示与管理网站。

## 技术栈

- Next.js 14 (App Router)
- TypeScript
- Tailwind CSS
- SQLite (better-sqlite3)
- TipTap 富文本编辑器

## 快速开始

```bash
# 安装依赖
npm install

# 初始化数据库并插入示例数据
npm run seed

# 启动开发服务器
npm run dev
```

打开 http://localhost:3000 查看网站。

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
│       ├── db.ts                 # 数据库连接
│       └── types.ts              # TypeScript 类型
├── data/                         # SQLite 数据库文件
├── public/uploads/               # 上传的封面图
├── scripts/seed.ts               # 数据库初始化脚本
└── .env.local                    # 环境变量
```

## 环境变量

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `ADMIN_PASSWORD` | 后台管理密码 | `admin123` |
| `NEXT_PUBLIC_BASE_URL` | 网站基础 URL | `http://localhost:3000` |

## 部署

```bash
npm run build
npm run start
```

确保 `data/` 和 `public/uploads/` 目录有写入权限。
