# 死代码分析报告

生成日期:2026-08-18
分析工具:`vulture`(Python)+ 手动依赖/前端检查
分析范围:`web/app`、`notebooks`、`requirements.txt`、`web/static/app.js`

> 说明:本仓库为 Python(FastAPI + notebooks 脚本)+ 原生 JS 前端,无 TypeScript/npm 依赖,
> 故不使用 knip / depcheck / ts-prune（针对 Node/TS 生态）。

## 发现汇总

| # | 严重度 | 位置 | 内容 | 处置 |
|---|---|---|---|---|
| 1 | 🔴 安全 | `web/app/auth.py` | 未使用 import `urlparse`、`parse_qs`、`hmac` | ✅ 已删除 |
| 2 | 🔴 安全 | `web/app/config.py` | 未使用变量 `MARKET_DB_POOL_SIZE` | ✅ 已删除 |
| 3 | 🔴 安全 | `notebooks/_fgg_common.py` | 未使用函数 `bs_price`、`implied_vol` | ✅ 已删除 |
| 4 | 🔴 安全 | `notebooks/_fgg_common.py` | 未使用 import `scipy.stats.norm` | ✅ 已删除 |
| 5 | 🟡 谨慎 | `requirements.txt` | `scipy` 未在任何代码中 import | ⏸ 建议移除(保留避免生产镜像重建) |
| 6 | 🟡 谨慎 | `web/static/app.js` | 多个 `render*`/`render*Trend` 回调函数难以静态确认是否全被事件/init 引用 | ⏸ 保留(前端已上线,误删有风险) |
| 7 | ⚪ 危险(误报) | `web/app/main.py` | `api_*`、`*_error_handler`、`serve_frontend` | ✅ 不删(FastAPI 装饰器注册,不可删除) |

## 已删除项(是否测试通过)

删除前/后均运行完整测试套件,结论统一:`89 passed`。

- 删除 1:auth.py 移除 `urlparse`/`parse_qs`/`hmac` —— web 测试 89 通过
- 删除 2:config.py 移除 `MARKET_DB_POOL_SIZE` —— 89 通过
- 删除 3+4:_fgg_common.py 移除 `bs_price`/`implied_vol` 及 `scipy.stats.norm` —— 89 通过

## 保留项说明

### 谨慎级(建议但暂不删除)

- **`requirements.txt` → `scipy`**:现无代码 `import scipy`。保留是因生产 Docker 校验镜像重建较耗时/有风险;从 requirements 移除后可在下次重建镜像时一并生效。
- **`web/static/app.js` render 函数**:这些是图表渲染回调,可能被 `index.html` 事件或 `render()` 主流程调用。静态分析难以完全确认调用链,且前端已稳定上线,删除存在回归/空白页面风险,故保留待有针对性验证后处理。

### 危险级(FastAPI 路由——vulture 误报,不可删除)

`web/app/main.py` 的 `api_dashboard`、`api_market_environment`、...、`serve_frontend`、`market_data_error_handler`、`validation_error_handler`、`http_exception_handler` 等均被 `@app.get()`、`@app.exception_handler()` 等装饰器注册。vulture 不识别装饰器调用而误报"unused",实为 FastAPI 核心路由与异常处理,删除会使服务瘫痪。**一律保留**。

## 结论

- 已安全删除 **4 项**(死 import ×4 + 死变量 ×1 + 死函数 ×2,计 3 个文件)。
- 测试全程通过,**无回归**。
- 保留 2 项谨慎级(建议后续处理)与 1 组危险级误报(不删)。

## 验证方式

每次删除源码后:`.venv/bin/python -m pytest web/tests/ -q`(或等效)全绿。
