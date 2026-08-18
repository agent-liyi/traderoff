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
| `SSH_PRIVATE_KEY` | ✅ | **私钥**(非公钥)的完整内容，用于 Key 认证 | `-----BEGIN OPENSSH PRIVATE KEY-----…` |
| `SSH_PORT` | 可选 | SSH 端口，默认 `22` | `22` |

> 需要同时把对应用户的**公钥**放到服务器 `~/.ssh/authorized_keys`，
> 见下文「第二步：配置服务器公钥」。
> 不再需要 `SSH_PASSWORD`(避免明文密码)。

## 第二步：配置服务器公钥

为了让 GitHub Actions 能以 `SSH_USER` 免密登录服务器，把私钥对应的公钥追加到
服务器的 `~/.ssh/authorized_keys`：

```sh
# 本机(有私钥的机器)导出公钥，或直接从已生成的私钥计算
ssh-keygen -y -f /path/to/private_key
# 或直接拷贝已有公钥文件内容

# 在服务器以 SSH_USER 登录后追加
mkdir -p ~/.ssh && chmod 700 ~/.ssh
echo "ssh-ed25519 AAAA... your-comment" >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
```

验证服务器可用该公钥免密登录：

```sh
ssh -i /path/to/private_key traderoff@192.144.130.81 'echo OK'
```

之后把 `private_key` 的**整份内容**填到 GitHub `SSH_PRIVATE_KEY`。

## 第三步 / First push 触发

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
