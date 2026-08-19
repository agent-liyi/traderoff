# 前端结构地图

> 生成时间:2026-08-18 (UTC+08)
> 范围:web/static(原生 JS + HTML,无构建步骤)

## 文件
| 文件 | 职责 |
|---|---|
| index.html | 页面骨架:9 个标签页视图 + 导航 |
| app.js | 全部前端逻辑(数据加载、渲染、图表) |
| styles.css | 布局/主题 |
| assets/traderoff-logo.png | 图标 |
| vendor/echarts.min.js, vendor/lucide.min.js | 第三方库(本地引入) |

## 标签页视图
| view | 数据端点 | 说明 |
|---|---|---|
| sentiment | /api/dashboard | 市场情绪(dashboard) |
| environment | /api/market-environment | 价格指数 |
| style | /api/market-style | 市场风格 |
| industry | /api/industry-price | 行业价格 |
| volume | /api/market-volume | 成交量 |
| volatility | /api/market-volatility | 波动率 |
| turnover | /api/market-turnover | 换手率 |
| breadth | /api/market-breadth | 涨跌分布 |
| factors | /api/factor-exposure | 多因子(已暂时隐藏 data-view=factors hidden) |

## app.js 结构(主要函数)
- 数据加载: loadDashboard / loadEnvironment / loadStyle / loadIndustry / loadVolume / loadVolatility / loadTurnover / loadBreadth / loadFactors / loadMe
- 渲染: render / renderEnvironment / renderStyle / renderIndustry / renderVolume / renderVolatility / renderTurnover / renderBreadth / renderFactors / renderGauge / renderMain / renderIndicators
- 交互: switchView / openDetail / closeDetail
- 通用: percent / sparkline / axisStyle / chartGrid / disposeCharts / watchChart
- 认证: 微信登录元素渲染 + /api/me + /api/logout 调用

## 数据绑定
- 所有日期(asOf、"250个交易日"范围)均从 API 响应动态读取,无硬编码
- 图表用 echarts,图标用 lucide

## 前端特性
- 匿名访问 dashboard 时指标 value=0(掩码);登录后显示真实 raw 值
- range 参数支持 6m/1y/3y/all(dashboard 默认 1y)
- 纯静态,经 Caddy 反代 + FastAPI 静态服务提供
