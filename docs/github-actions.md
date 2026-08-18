# GitHub Actions · CI/CD 部署配置

本仓库使用 GitHub Actions(见 `.github/workflows/ci.yml`)：

- **每次 push 到 `main`** 自动运行测试；
- 测试通过后自动通过 SSH 部署到腾讯云(重建镜像 + 重启容器)。

## 第一步：配置 GitHub Secrets

在 GitHub 仓库 `Settings → Secrets and variables → Actions → New repository secret`
添加以下机密项。

| Secret 名称 | 必填 | 说明 | 示例 |
|---|---|---|---|
| `SSH_HOST` | ✅ | 腾讯云服务器公网 IP | `192.144.130.81` |
| `SSH_USER` | ✅ | 服务器 SSH 用户名 | `traderoff` |
| `SSH_PASSWORD` | ✅ | 用户 `SSH_USER` 的 SSH 密码 | ⚠️ 请勿在示例中写真实值 |
| `SSH_PORT` | 可选 | SSH 端口，默认 `22` | `22` |

> ⚠️ 安全提示：`SSH_PASSWORD` 会明文存于 GitHub 机密（GitHub 会加密保存，但
> Actions runner 上脚本可见）。长期运行建议改用 **SSH 私钥**（`SSH_PRIVATE_KEY`），
> 并在服务器仅保留该公钥的认证方式，避免长期使用明文密码。

## 第二步：/ First push 触发

- 工作流对 push 到 `main` 生效；你也可以在 Actions 页手动 `Run workflow`。
- 部署 step 会执行：
  1. 在服务器 `~/apps/traderoff` 执行 `git fetch && git reset --hard origin/main`；
  2. `docker compose build traderoff market-updater`（重建镜像，需 python:3.11 / fastapi 等，耗时较长）；
  3. `docker compose up -d --no-deps --force-recreate traderoff market-updater`（重启服务）。

> 注意：服务器需能从 GitHub 拉取仓库(`github.com/agent-liyi/traderoff-market-ct`)；
> 若服务器到 GitHub 网络不稳定，部署可能失败，需重试或改为手工同步。

## 何时触发

- 单次提交/推送 → 测试 + 部署一次。
- 仅修改 docs/ 等不影响服务的文件，默认仍会触发完整 CI/CD；如需细化可后续按路径拆分 job。
