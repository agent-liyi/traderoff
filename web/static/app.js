const state = { range: '1y', data: null, environment: null, style: null, industry: null, volume: null, volatility: null, turnover: null, breadth: null, factors: null, environmentGroup: 'A股', breadthGroup: '000300.SH', charts: [], environmentTrendChart: null, styleTrendChart: null, industryTrendChart: null, volumeAmountChart: null, volumeShareChart: null, indexVolatilityChart: null, crossVolatilityChart: null, turnoverChart: null, breadthChart: null, factorIndexChart: null, factorDistributionChart: null, factorIndustryChart: null, user: null };
const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];
const palette = { qvix: '#5AAEF3', strength: '#333333', futures: '#E65A56', volume: '#6D61E4', safety: '#30CB13' };
const environmentPalette = ['#1F77B4', '#E15759', '#2C8C6B', '#F28E2B', '#6B5FB5', '#A05D3A', '#C6A016', '#40484F'];
const styleTrendPalette = ['#1F77B4', '#E15759', '#2C8C6B', '#F28E2B', '#6B5FB5', '#A05D3A'];
const industryTrendPalette = ['#5AAEF3', '#E65A56', '#2C8C6B', '#FF974C', '#6D61E4', '#C6A016', '#2D5B85', '#A05D3A', '#8E6F52', '#40484F', '#30CB13', '#D05A78'];
const volumePalette = ['#E65A56', '#F28E2B', '#5AAEF3', '#2C8C6B', '#6D61E4'];
const volatilityPalette = ['#1F77B4', '#F28E2B', '#73777B', '#C6A016', '#6D61E4'];
const turnoverPalette = ['#1F77B4', '#F28E2B', '#73777B', '#C6A016', '#6D61E4', '#2C8C6B'];
const score = (value) => Number(value).toFixed(1);
const change = (value) => `${value >= 0 ? '+' : ''}${Number(value).toFixed(1)}`;
const indicatorValue = (value, item) => `${Number(value).toFixed(item.precision)}${item.unit}`;
const indicatorChange = (value, item) => `${value >= 0 ? '+' : ''}${Number(value).toFixed(item.precision)}${item.unit}`;

function initIcons() { if (window.lucide) window.lucide.createIcons(); }
function disposeCharts() { state.charts.forEach((chart) => chart.dispose()); state.charts = []; }
function chartAt(element) { const chart = echarts.init(element, null, { renderer: 'canvas' }); state.charts.push(chart); return chart; }
function chartGrid(bottom = 36) { return { left: 48, right: 24, top: 25, bottom, containLabel: false }; }
function axisStyle() {
  return {
    axisLine: { lineStyle: { color: '#999' } }, axisTick: { show: false },
    axisLabel: { color: '#73777b', fontSize: 10 }, splitLine: { show: true, lineStyle: { color: '#CCCCCC', width: 1 } }
  };
}

async function loadDashboard() {
  const response = await fetch(`/api/dashboard?range=${state.range}`);
  if (!response.ok) throw new Error('数据加载失败');
  state.data = await response.json();
  render();
}

async function loadEnvironment() {
  const response = await fetch('/api/market-environment');
  if (!response.ok) throw new Error('市场环境数据加载失败');
  state.environment = await response.json();
  renderEnvironment();
}

async function loadStyle() {
  const response = await fetch('/api/market-style');
  if (!response.ok) throw new Error('市场风格指数数据加载失败');
  state.style = await response.json();
  renderStyle();
}

async function loadIndustry() {
  const response = await fetch('/api/industry-price');
  if (!response.ok) throw new Error('行业价格指数数据加载失败');
  state.industry = await response.json();
  renderIndustry();
}

async function loadVolume() {
  const response = await fetch('/api/market-volume');
  if (!response.ok) throw new Error('市场成交量数据加载失败');
  state.volume = await response.json();
  renderVolume();
}

async function loadVolatility() {
  const response = await fetch('/api/market-volatility');
  if (!response.ok) throw new Error('市场波动率数据加载失败');
  state.volatility = await response.json();
  renderVolatility();
}

async function loadTurnover() {
  const response = await fetch('/api/market-turnover');
  if (!response.ok) throw new Error('市场换手率数据加载失败');
  state.turnover = await response.json();
  renderTurnover();
}

async function loadBreadth() {
  const response = await fetch('/api/market-breadth');
  if (!response.ok) throw new Error('成分股涨跌分布数据加载失败');
  state.breadth = await response.json();
  renderBreadth();
}

async function loadFactors() {
  const response = await fetch('/api/factor-exposure');
  if (!response.ok) throw new Error('多因子画像数据加载失败');
  state.factors = await response.json();
  renderFactors();
}

function percent(value) {
  const numeric = Number(value);
  return `${numeric >= 0 ? '+' : ''}${numeric.toFixed(2)}%`;
}

function sparkline(points, positive) {
  const values = points.map((point) => Number(point.close));
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const coordinates = values.map((value, index) => `${4 + index * 22},${30 - ((value - min) / span) * 24}`).join(' ');
  const color = positive ? '#E65A56' : '#2580BE';
  return `<svg viewBox="0 0 96 36" role="img" aria-label="近一周走势"><polyline points="${coordinates}" fill="none" stroke="${color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/><circle cx="92" cy="${coordinates.split(' ').at(-1).split(',')[1]}" r="2.5" fill="${color}"/></svg>`;
}

function returnCell(value) {
  const width = Math.min(Math.abs(Number(value)) / 50 * 100, 100);
  const direction = Number(value) >= 0 ? 'gain' : 'loss';
  return `<td class="return-cell ${direction}" style="--bar:${width}%"><span>${percent(value)}</span></td>`;
}

function renderEnvironment() {
  $('#environmentDate').textContent = state.environment.asOf;
  let previousGroup = '';
  $('#environmentRows').innerHTML = state.environment.indices.map((item) => {
    const groupClass = previousGroup && previousGroup !== item.group ? ' group-start' : '';
    previousGroup = item.group;
    return `<tr class="${groupClass.trim()}" title="${item.name}数据截至 ${item.date}">
      <td><span class="market-tag market-${item.group}">${item.group}</span></td>
      <th scope="row"><strong>${item.name}</strong><small>${item.code}</small></th>
      ${returnCell(item.week)}${returnCell(item.month)}${returnCell(item.ytd)}${returnCell(item.year)}
      <td class="data-date">${item.date}</td><td class="sparkline">${sparkline(item.sparkline, item.week >= 0)}</td>
    </tr>`;
  }).join('');
  renderEnvironmentTrend();
}

function renderStyle() {
  $('#styleDate').textContent = state.style.asOf;
  let previousGroup = '';
  $('#styleRows').innerHTML = state.style.indices.map((item) => {
    const groupClass = previousGroup && previousGroup !== item.group ? ' group-start' : '';
    previousGroup = item.group;
    return `<tr class="${groupClass.trim()}" title="${item.name}数据截至 ${item.date}">
      <th scope="row"><strong>${item.name}</strong><small>${item.group} · ${item.code}</small></th>
      ${returnCell(item.week)}${returnCell(item.month)}${returnCell(item.ytd)}${returnCell(item.year)}
      <td class="sparkline">${sparkline(item.sparkline, item.week >= 0)}</td>
    </tr>`;
  }).join('');
  renderStyleTrend();
}

function renderStyleTrend() {
  const items = state.style.indices.filter((item) => item.group !== '全市场');
  if (items.length !== 6) return;
  state.styleTrendChart?.dispose();
  const chart = echarts.init($('#styleTrendChart'), null, { renderer: 'canvas' });
  state.styleTrendChart = chart;
  const dates = [...new Set(items.flatMap((item) => item.history.map((point) => point.date)))].sort();
  const compact = window.innerWidth <= 760;
  const monthStart = (index) => index === 0 || dates[index].slice(0, 7) !== dates[index - 1].slice(0, 7);
  $('#styleTrendDate').textContent = `250个交易日 · ${dates[0]} — ${dates.at(-1)} · 数据来源：Tushare Pro`;
  chart.setOption({
    animationDuration: 650,
    color: styleTrendPalette,
    tooltip: {
      trigger: 'axis', backgroundColor: '#fff', borderColor: '#ccc', textStyle: { color: '#222', fontSize: 11 },
      formatter: (rows) => `${rows[0].axisValue}<br>${rows.filter((row) => row.value !== '-').map((row) => `${row.marker}${row.seriesName} <b>${Number(row.value).toFixed(2)}%</b>`).join('<br>')}`
    },
    legend: compact
      ? { data: items.map((item) => item.name), type: 'scroll', top: 10, left: 48, right: 18, itemWidth: 16, itemHeight: 3, itemGap: 12, textStyle: { color: '#555', fontSize: 10 } }
      : { data: items.map((item) => item.name), type: 'scroll', orient: 'vertical', right: 16, top: 'center', itemWidth: 16, itemHeight: 3, itemGap: 13, textStyle: { color: '#555', fontSize: 10 } },
    grid: { left: 58, right: compact ? 20 : 150, top: compact ? 52 : 28, bottom: 42 },
    xAxis: { type: 'category', boundaryGap: false, data: dates, ...axisStyle(), axisLabel: { color: '#73777b', fontSize: 10, hideOverlap: true, formatter: (value, index) => monthStart(index) ? `${value.slice(5, 7)}月` : '' } },
    yAxis: { type: 'value', name: '累计收益率', nameTextStyle: { color: '#73777b', fontSize: 10 }, axisLabel: { color: '#73777b', fontSize: 10, formatter: (value) => `${Number(value).toFixed(0)}%` }, axisLine: { lineStyle: { color: '#999' } }, axisTick: { show: false }, splitLine: { show: true, lineStyle: { color: '#ddd', type: 'dashed' } } },
    dataZoom: [{ type: 'inside' }],
    series: items.map((item) => {
      const baseline = Number(item.history[0].close);
      const values = new Map(item.history.map((point) => [point.date, (Number(point.close) / baseline - 1) * 100]));
      return { name: item.name, type: 'line', data: dates.map((date) => values.has(date) ? values.get(date) : '-'), showSymbol: false, smooth: .13, lineStyle: { width: 2.2 }, emphasis: { focus: 'series', lineStyle: { width: 3.4 } } };
    }).concat([{ name: '0%基准', type: 'line', data: dates.map(() => 0), showSymbol: false, silent: true, tooltip: { show: false }, lineStyle: { color: '#92979b', width: 1, type: 'dashed' }, z: 0 }])
  });
}

function renderIndustry() {
  $('#industryDate').textContent = state.industry.asOf;
  const items = [...state.industry.indices].sort((left, right) => Number(right.week) - Number(left.week));
  const maxAmount = Math.max(...items.map((item) => Number(item.amount)), 1);
  $('#industryRows').innerHTML = items.map((item) => `<tr title="${item.name}数据截至 ${item.date}">
    <th scope="row"><strong>${item.name}</strong><small>${item.code}</small></th>
    ${returnCell(item.week)}${returnCell(item.month)}${returnCell(item.ytd)}${returnCell(item.year)}
    <td class="amount-cell" style="--amount-bar:${Math.max(Number(item.amount) / maxAmount * 100, 1)}%"><span>${Number(item.amount).toLocaleString('zh-CN', { maximumFractionDigits: 0 })}</span><small>亿元</small></td>
    <td class="sparkline">${sparkline(item.sparkline, item.week >= 0)}</td>
  </tr>`).join('');
  renderIndustryTrend(items);
}

function renderIndustryTrend(items) {
  state.industryTrendChart?.dispose();
  const chart = echarts.init($('#industryTrendChart'), null, { renderer: 'canvas' });
  state.industryTrendChart = chart;
  const dates = [...new Set(items.flatMap((item) => item.history.map((point) => point.date)))].sort();
  const compact = window.innerWidth <= 760;
  const monthStart = (index) => index === 0 || dates[index].slice(0, 7) !== dates[index - 1].slice(0, 7);
  $('#industryTrendDate').textContent = `250个交易日 · ${dates[0]} — ${dates.at(-1)} · 数据来源：Tushare Pro`;
  chart.setOption({
    animationDuration: 650,
    color: industryTrendPalette,
    tooltip: {
      trigger: 'axis', backgroundColor: '#fff', borderColor: '#ccc', textStyle: { color: '#222', fontSize: 11 },
      formatter: (rows) => `${rows[0].axisValue}<br>${rows.filter((row) => row.value !== '-').map((row) => `${row.marker}${row.seriesName} <b>${Number(row.value).toFixed(2)}%</b>`).join('<br>')}`
    },
    legend: compact
      ? { type: 'scroll', top: 10, left: 48, right: 18, itemWidth: 14, itemHeight: 3, itemGap: 11, textStyle: { color: '#555', fontSize: 10 } }
      : { type: 'scroll', orient: 'vertical', right: 14, top: 'center', itemWidth: 14, itemHeight: 3, itemGap: 10, textStyle: { color: '#555', fontSize: 10 } },
    grid: { left: 58, right: compact ? 20 : 152, top: compact ? 52 : 28, bottom: 42 },
    xAxis: { type: 'category', boundaryGap: false, data: dates, ...axisStyle(), axisLabel: { color: '#73777b', fontSize: 10, hideOverlap: true, formatter: (value, index) => monthStart(index) ? `${value.slice(5, 7)}月` : '' } },
    yAxis: { type: 'value', name: '累计收益率', nameTextStyle: { color: '#73777b', fontSize: 10 }, axisLabel: { color: '#73777b', fontSize: 10, formatter: (value) => `${Number(value).toFixed(0)}%` }, axisLine: { lineStyle: { color: '#999' } }, axisTick: { show: false }, splitLine: { show: true, lineStyle: { color: '#ddd', type: 'dashed' } } },
    dataZoom: [{ type: 'inside' }],
    series: items.map((item) => {
      const baseline = Number(item.history[0].close);
      const values = new Map(item.history.map((point) => [point.date, (Number(point.close) / baseline - 1) * 100]));
      return { name: item.name, type: 'line', data: dates.map((date) => values.has(date) ? values.get(date) : '-'), showSymbol: false, smooth: .12, lineStyle: { width: 1.8 }, emphasis: { focus: 'series', lineStyle: { width: 3 } } };
    }).concat([{ name: '0%基准', type: 'line', data: dates.map(() => 0), showSymbol: false, silent: true, tooltip: { show: false }, lineStyle: { color: '#92979b', width: 1, type: 'dashed' }, z: 0 }])
  });
}

function renderTurnover() {
  const { indices, asOf } = state.turnover;
  const maxValue = Math.max(...indices.map((item) => Number(item.current)), 1);
  $('#turnoverDate').textContent = asOf;
  $('#turnoverRows').innerHTML = indices.map((item) => `<tr>
    <th scope="row"><strong>${item.name}</strong><small>${item.code}</small></th>
    <td class="turnover-cell" style="--turnover-bar:${Math.max(Number(item.current) / maxValue * 100, 1)}%"><span>${Number(item.current).toFixed(2)}%</span></td>
    <td>${Number(item.weekAverage).toFixed(2)}%</td>
    <td>${Number(item.monthAverage).toFixed(2)}%</td>
    ${percentileCell(item.percentile)}
    <td class="sparkline">${turnoverSparkline(item.sparkline)}</td>
  </tr>`).join('');
  renderTurnoverTrend(indices);
}

function turnoverSparkline(points) {
  const values = points.map((point) => Number(point.value));
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const coordinates = values.map((value, index) => `${4 + index * 22},${30 - ((value - min) / span) * 24}`).join(' ');
  return `<svg viewBox="0 0 96 36" role="img" aria-label="近五日换手率走势"><polyline points="${coordinates}" fill="none" stroke="#6D61E4" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/><circle cx="92" cy="${coordinates.split(' ').at(-1).split(',')[1]}" r="2.5" fill="#6D61E4"/></svg>`;
}

function renderTurnoverTrend(items) {
  state.turnoverChart?.dispose();
  const chart = echarts.init($('#turnoverChart'), null, { renderer: 'canvas' });
  state.turnoverChart = chart;
  const dates = items[0].history.map((point) => point.date);
  const compact = window.innerWidth <= 760;
  const monthStart = (index) => index === 0 || dates[index].slice(0, 7) !== dates[index - 1].slice(0, 7);
  $('#turnoverTrendDate').textContent = `250个交易日 · ${dates[0]} — ${dates.at(-1)} · 数据来源：Tushare Pro`;
  chart.setOption({
    animationDuration: 650, color: turnoverPalette,
    tooltip: { trigger: 'axis', backgroundColor: '#fff', borderColor: '#ccc', textStyle: { color: '#222', fontSize: 11 }, formatter: (rows) => `${rows[0].axisValue}<br>${rows.map((row) => `${row.marker}${row.seriesName} <b>${Number(row.value).toFixed(2)}%</b>`).join('<br>')}` },
    legend: compact
      ? { data: items.map((item) => item.name), type: 'scroll', top: 10, left: 48, right: 18, itemWidth: 15, itemHeight: 3, itemGap: 10, textStyle: { color: '#555', fontSize: 10 } }
      : { data: items.map((item) => item.name), type: 'scroll', orient: 'vertical', right: 14, top: 'center', itemWidth: 15, itemHeight: 3, itemGap: 12, textStyle: { color: '#555', fontSize: 10 } },
    grid: { left: 58, right: compact ? 20 : 145, top: compact ? 52 : 28, bottom: 42 },
    xAxis: { type: 'category', boundaryGap: false, data: dates, ...axisStyle(), axisLabel: { color: '#73777b', fontSize: 10, hideOverlap: true, formatter: (value, index) => monthStart(index) ? `${value.slice(5, 7)}月` : '' } },
    yAxis: { type: 'value', name: '自由流通换手率', nameTextStyle: { color: '#73777b', fontSize: 10 }, axisLabel: { color: '#73777b', fontSize: 10, formatter: (value) => `${Number(value).toFixed(1)}%` }, axisLine: { lineStyle: { color: '#999' } }, axisTick: { show: false }, splitLine: { show: true, lineStyle: { color: '#ddd', type: 'dashed' } } },
    dataZoom: [{ type: 'inside' }],
    series: items.map((item) => ({ name: item.name, type: 'line', data: item.history.map((point) => point.value), showSymbol: false, smooth: .14, lineStyle: { width: 2.1 }, emphasis: { focus: 'series', lineStyle: { width: 3.3 } } }))
  });
}

function renderBreadth() {
  const group = state.breadth.groups.find((item) => item.code === state.breadthGroup) || state.breadth.groups[0];
  const { asOf } = state.breadth;
  $('#breadthDate').textContent = asOf;
  $('#breadthTrendTitle').textContent = `${group.name}个股涨跌幅度分布（共${group.count.toLocaleString('zh-CN')}只）`;
  $('#breadthDescription').textContent = `上涨 ${group.rise.toLocaleString('zh-CN')} 只 · 平盘 ${group.flat.toLocaleString('zh-CN')} 只 · 下跌 ${group.fall.toLocaleString('zh-CN')} 只 · 按2个百分点区间统计。`;
  $('#breadthChartDate').textContent = `${asOf} · 数据来源：Tushare Pro · 成分股快照 ${group.membershipSnapshot}`;
  state.breadthChart?.dispose();
  const chart = echarts.init($('#breadthChart'), null, { renderer: 'canvas' });
  state.breadthChart = chart;
  const compact = window.innerWidth <= 760;
  chart.setOption({
    animationDuration: 500,
    tooltip: {
      trigger: 'axis', axisPointer: { type: 'shadow' }, backgroundColor: '#fff', borderColor: '#ccc', textStyle: { color: '#222', fontSize: 11 },
      formatter: (rows) => { const count = Number(rows[0].value); return `${rows[0].axisValue}<br>${rows[0].marker}个股数量 <b>${count}</b> 只<br>占比 <b>${(count / group.count * 100).toFixed(2)}%</b>`; }
    },
    grid: { left: 58, right: 26, top: 28, bottom: compact ? 86 : 74 },
    xAxis: {
      type: 'category', data: group.distribution.map((item) => item.label), axisLine: { lineStyle: { color: '#999' } }, axisTick: { alignWithLabel: true, lineStyle: { color: '#999' } },
      axisLabel: { color: '#73777b', fontSize: compact ? 8 : 9, interval: 0, rotate: 45, margin: 12 }, name: '涨跌幅区间', nameLocation: 'middle', nameGap: compact ? 64 : 56, nameTextStyle: { color: '#73777b', fontSize: 10 }
    },
    yAxis: { type: 'value', minInterval: 1, name: '个股数量', nameTextStyle: { color: '#73777b', fontSize: 10 }, axisLine: { lineStyle: { color: '#999' } }, axisTick: { show: false }, axisLabel: { color: '#73777b', fontSize: 10 }, splitLine: { show: true, lineStyle: { color: '#ddd', type: 'dashed' } } },
    series: [{ name: '个股数量', type: 'bar', data: group.distribution.map((item) => item.count), barCategoryGap: '8%', itemStyle: { color: '#2D75B6' }, emphasis: { itemStyle: { color: '#1F5F97' } } }]
  });
}

function renderVolatility() {
  const data = state.volatility;
  $('#volatilityDate').textContent = data.asOf;
  renderVolatilityChart('#indexVolatilityChart', '#indexVolatilityDate', data.indexVolatility, `主要指数波动率（${data.indexWindow}日滚动年化）`, true);
  renderVolatilityChart('#crossVolatilityChart', '#crossVolatilityDate', data.crossSectionVolatility, `成分股截面波动率（${data.crossSectionWindow}日移动平均）`, false);
}

function renderVolatilityChart(selector, dateSelector, items, title, annualized) {
  const chartKey = selector === '#indexVolatilityChart' ? 'indexVolatilityChart' : 'crossVolatilityChart';
  state[chartKey]?.dispose();
  const chart = echarts.init($(selector), null, { renderer: 'canvas' });
  state[chartKey] = chart;
  const dates = items[0].history.map((point) => point.date);
  const compact = window.innerWidth <= 760;
  const monthStart = (index) => index === 0 || dates[index].slice(0, 7) !== dates[index - 1].slice(0, 7);
  $(dateSelector).textContent = `250个交易日 · ${dates[0]} — ${dates.at(-1)} · 数据来源：Tushare Pro`;
  chart.setOption({
    animationDuration: 650, color: volatilityPalette,
    tooltip: { trigger: 'axis', backgroundColor: '#fff', borderColor: '#ccc', textStyle: { color: '#222', fontSize: 11 }, formatter: (rows) => `${rows[0].axisValue}<br>${rows.map((row) => `${row.marker}${row.seriesName} <b>${Number(row.value).toFixed(2)}%</b>`).join('<br>')}` },
    legend: compact
      ? { data: items.map((item) => item.name), type: 'scroll', top: 10, left: 48, right: 18, itemWidth: 15, itemHeight: 3, itemGap: 10, textStyle: { color: '#555', fontSize: 10 } }
      : { data: items.map((item) => item.name), type: 'scroll', orient: 'vertical', right: 14, top: 'center', itemWidth: 15, itemHeight: 3, itemGap: 12, textStyle: { color: '#555', fontSize: 10 } },
    grid: { left: 58, right: compact ? 20 : 145, top: compact ? 52 : 28, bottom: 42 },
    xAxis: { type: 'category', boundaryGap: false, data: dates, ...axisStyle(), axisLabel: { color: '#73777b', fontSize: 10, hideOverlap: true, formatter: (value, index) => monthStart(index) ? `${value.slice(5, 7)}月` : '' } },
    yAxis: { type: 'value', name: title, nameTextStyle: { color: '#73777b', fontSize: 10 }, axisLabel: { color: '#73777b', fontSize: 10, formatter: (value) => `${Number(value).toFixed(annualized ? 0 : 1)}%` }, axisLine: { lineStyle: { color: '#999' } }, axisTick: { show: false }, splitLine: { show: true, lineStyle: { color: '#ddd', type: 'dashed' } } },
    dataZoom: [{ type: 'inside' }],
    series: items.map((item) => ({ name: item.name, type: 'line', data: item.history.map((point) => point.value), showSymbol: false, smooth: .14, lineStyle: { width: 2.2 }, emphasis: { focus: 'series', lineStyle: { width: 3.4 } } }))
  });
}

function renderVolume() {
  const { buckets, history, asOf } = state.volume;
  const maxAmount = Math.max(...buckets.map((item) => Number(item.amount)), 1);
  $('#volumeDate').textContent = asOf;
  $('#volumeRows').innerHTML = buckets.map((item) => `<tr>
    <th scope="row"><strong>${item.name}</strong><small>${item.code === 'OTHER' ? '沪深两市其余股票' : item.code}</small></th>
    <td class="amount-cell" style="--amount-bar:${Math.max(Number(item.amount) / maxAmount * 100, 1)}%"><span>${Number(item.amount).toLocaleString('zh-CN', { maximumFractionDigits: 0 })}</span><small>亿元</small></td>
    ${percentileCell(item.amountPercentile)}
    <td class="share-cell" style="--share-bar:${Math.max(Number(item.share), 1)}%"><span>${Number(item.share).toFixed(2)}%</span></td>
    ${percentileCell(item.sharePercentile)}
  </tr>`).join('');
  renderVolumeAmountTrend(buckets, history);
  renderVolumeShareTrend(buckets, history);
}

function percentileCell(value) {
  return `<td class="percentile-cell" style="--percentile-bar:${Math.max(Number(value), 1)}%"><span>${Number(value).toFixed(1)}%</span></td>`;
}

function volumeChartMeta(history) {
  const dates = history.map((row) => row.date);
  const compact = window.innerWidth <= 760;
  const monthStart = (index) => index === 0 || dates[index].slice(0, 7) !== dates[index - 1].slice(0, 7);
  return { dates, compact, monthStart };
}

function volumeLegend(items, compact) {
  return compact
    ? { data: items.map((item) => item.name), type: 'scroll', top: 10, left: 48, right: 18, itemWidth: 15, itemHeight: 3, itemGap: 10, textStyle: { color: '#555', fontSize: 10 } }
    : { data: items.map((item) => item.name), type: 'scroll', orient: 'vertical', right: 14, top: 'center', itemWidth: 15, itemHeight: 3, itemGap: 12, textStyle: { color: '#555', fontSize: 10 } };
}

function renderVolumeAmountTrend(items, history) {
  state.volumeAmountChart?.dispose();
  const chart = echarts.init($('#volumeAmountChart'), null, { renderer: 'canvas' });
  state.volumeAmountChart = chart;
  const { dates, compact, monthStart } = volumeChartMeta(history);
  $('#volumeAmountDate').textContent = `250个交易日 · ${dates[0]} — ${dates.at(-1)} · 数据来源：Tushare Pro`;
  chart.setOption({
    animationDuration: 650, color: volumePalette,
    tooltip: { trigger: 'axis', backgroundColor: '#fff', borderColor: '#ccc', textStyle: { color: '#222', fontSize: 11 }, formatter: (rows) => `${rows[0].axisValue}<br>${rows.map((row) => `${row.marker}${row.seriesName} <b>${Number(row.value).toLocaleString('zh-CN', { maximumFractionDigits: 0 })}</b> 亿元`).join('<br>')}` },
    legend: volumeLegend(items, compact),
    grid: { left: 58, right: compact ? 20 : 145, top: compact ? 52 : 28, bottom: 42 },
    xAxis: { type: 'category', boundaryGap: false, data: dates, ...axisStyle(), axisLabel: { color: '#73777b', fontSize: 10, hideOverlap: true, formatter: (value, index) => monthStart(index) ? `${value.slice(5, 7)}月` : '' } },
    yAxis: { type: 'value', name: '亿元', nameTextStyle: { color: '#73777b', fontSize: 10 }, ...axisStyle() },
    dataZoom: [{ type: 'inside' }],
    series: items.map((item) => ({ name: item.name, type: 'line', stack: '成交额', data: history.map((row) => row.amounts[item.code]), showSymbol: false, smooth: .12, lineStyle: { width: 1.2 }, areaStyle: { opacity: .72 }, emphasis: { focus: 'series' } }))
  });
}

function renderVolumeShareTrend(items, history) {
  state.volumeShareChart?.dispose();
  const chart = echarts.init($('#volumeShareChart'), null, { renderer: 'canvas' });
  state.volumeShareChart = chart;
  const { dates, compact, monthStart } = volumeChartMeta(history);
  $('#volumeShareDate').textContent = `250个交易日 · ${dates[0]} — ${dates.at(-1)} · 数据来源：Tushare Pro`;
  chart.setOption({
    animationDuration: 650, color: volumePalette,
    tooltip: { trigger: 'axis', backgroundColor: '#fff', borderColor: '#ccc', textStyle: { color: '#222', fontSize: 11 }, formatter: (rows) => `${rows[0].axisValue}<br>${rows.map((row) => `${row.marker}${row.seriesName} <b>${Number(row.value).toFixed(2)}%</b>`).join('<br>')}` },
    legend: volumeLegend(items, compact),
    grid: { left: 58, right: compact ? 20 : 145, top: compact ? 52 : 28, bottom: 42 },
    xAxis: { type: 'category', boundaryGap: false, data: dates, ...axisStyle(), axisLabel: { color: '#73777b', fontSize: 10, hideOverlap: true, formatter: (value, index) => monthStart(index) ? `${value.slice(5, 7)}月` : '' } },
    yAxis: { type: 'value', min: 0, max: 50, name: '成交占比', nameTextStyle: { color: '#73777b', fontSize: 10 }, axisLabel: { color: '#73777b', fontSize: 10, formatter: (value) => `${value}%` }, axisLine: { lineStyle: { color: '#999' } }, axisTick: { show: false }, splitLine: { show: true, lineStyle: { color: '#ddd', type: 'dashed' } } },
    dataZoom: [{ type: 'inside' }],
    series: items.map((item) => ({ name: item.name, type: 'line', data: history.map((row) => row.shares[item.code]), showSymbol: false, smooth: .14, lineStyle: { width: 2 }, emphasis: { focus: 'series', lineStyle: { width: 3.2 } } }))
  });
}

function renderEnvironmentTrend() {
  const items = state.environment.indices.filter((item) => item.group === state.environmentGroup);
  if (!items.length) return;
  state.environmentTrendChart?.dispose();
  const chart = echarts.init($('#environmentTrendChart'), null, { renderer: 'canvas' });
  state.environmentTrendChart = chart;
  const dates = [...new Set(items.flatMap((item) => item.history.map((point) => point.date)))].sort();
  const compact = window.innerWidth <= 760;
  const monthStart = (index) => index === 0 || dates[index].slice(0, 7) !== dates[index - 1].slice(0, 7);
  const start = dates[0];
  const end = dates.at(-1);
  $('#environmentTrendDate').textContent = `250个交易日 · ${start} — ${end} · 数据来源：Tushare Pro`;
  chart.setOption({
    animationDuration: 650,
    color: environmentPalette,
    tooltip: {
      trigger: 'axis', backgroundColor: '#fff', borderColor: '#ccc', textStyle: { color: '#222', fontSize: 11 },
      formatter: (rows) => `${rows[0].axisValue}<br>${rows.filter((row) => row.value !== '-').map((row) => `${row.marker}${row.seriesName} <b>${Number(row.value).toFixed(2)}%</b>`).join('<br>')}`
    },
    legend: compact
      ? { type: 'scroll', top: 10, left: 48, right: 18, itemWidth: 16, itemHeight: 3, itemGap: 12, textStyle: { color: '#555', fontSize: 10 } }
      : { type: 'scroll', orient: 'vertical', right: 16, top: 'center', itemWidth: 16, itemHeight: 3, itemGap: 13, textStyle: { color: '#555', fontSize: 10 } },
    grid: { left: 58, right: compact ? 20 : 160, top: compact ? 52 : 28, bottom: 42 },
    xAxis: { type: 'category', boundaryGap: false, data: dates, ...axisStyle(), axisLabel: { color: '#73777b', fontSize: 10, hideOverlap: true, formatter: (value, index) => monthStart(index) ? value.slice(5, 7) + '月' : '' } },
    yAxis: { type: 'value', name: '累计收益率', nameTextStyle: { color: '#73777b', fontSize: 10 }, axisLabel: { color: '#73777b', fontSize: 10, formatter: (value) => `${Number(value).toFixed(0)}%` }, axisLine: { lineStyle: { color: '#999' } }, axisTick: { show: false }, splitLine: { show: true, lineStyle: { color: '#ddd', type: 'dashed' } } },
    dataZoom: [{ type: 'inside' }],
    series: items.map((item) => {
      const baseline = Number(item.history[0].close);
      const values = new Map(item.history.map((point) => [point.date, (Number(point.close) / baseline - 1) * 100]));
      return { name: item.name, type: 'line', data: dates.map((date) => values.has(date) ? values.get(date) : '-'), showSymbol: false, smooth: .13, lineStyle: { width: 2.2 }, emphasis: { focus: 'series', lineStyle: { width: 3.4 } } };
    }).concat([{ name: '0%基准', type: 'line', data: dates.map(() => 0), showSymbol: false, silent: true, tooltip: { show: false }, lineStyle: { color: '#92979b', width: 1, type: 'dashed' }, z: 0 }])
  });
}

function renderFactors() {
  const data = state.factors;
  $('#factorDate').textContent = data.asOf;
  $('#factorDisclaimer').textContent = data.model.disclaimer;
  $('#factorQualityStats').innerHTML = [
    ['股票池', `${data.quality.universeCount}只`], ['价格历史', `${data.quality.priceHistoryDays}日`],
    ['财务记录', `${data.quality.financialReportRows}条`], ['申万行业覆盖', `${data.quality.swIndustryCovered}只`]
  ].map(([label, value]) => `<div><span>${label}</span><strong>${value}</strong></div>`).join('');
  $('#factorWarnings').innerHTML = data.quality.warnings.map((warning) => `<li>${warning}</li>`).join('');
  $('#factorOverview').innerHTML = data.factors.map((factor) => `<article class="factor-item">
    <div><strong>${factor.name}</strong><span class="factor-quality-${factor.quality}">${factor.quality.toUpperCase()}</span></div>
    <p>${factor.proxy}</p><small>${factor.source}</small>
    <footer><span>覆盖 ${factor.count}/${data.quality.universeCount}</span><b>${(factor.coverage * 100).toFixed(1)}%</b></footer>
  </article>`).join('');
  const select = $('#factorDistributionSelect');
  select.innerHTML = data.factors.map((factor) => `<option value="${factor.key}">${factor.name}</option>`).join('');
  renderFactorIndexChart();
  renderFactorDistributionChart(select.value || data.factors[0].key);
  renderFactorIndustryChart();
  renderFactorStockTable();
}

function factorChartBase() {
  return { backgroundColor: '#fff', tooltip: { backgroundColor: '#fff', borderColor: '#ccc', textStyle: { color: '#222', fontSize: 11 } } };
}

function renderFactorIndexChart() {
  state.factorIndexChart?.dispose();
  const chart = echarts.init($('#factorIndexChart'), null, { renderer: 'canvas' });
  state.factorIndexChart = chart;
  const data = state.factors;
  const compact = window.innerWidth <= 760;
  const axisValues = data.indices.flatMap((index) => data.factors.map((factor) => index.exposures[factor.key])).filter(Number.isFinite);
  const axisLimit = Math.max(1.5, Math.min(3, Math.ceil(Math.max(...axisValues.map(Math.abs), 1.5) * 10) / 10));
  chart.setOption({
    ...factorChartBase(), color: ['#1F77B4', '#E15759', '#2C8C6B', '#F28E2B'],
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, backgroundColor: '#fff', borderColor: '#ccc', textStyle: { color: '#222', fontSize: 11 }, valueFormatter: (value) => value == null ? '无数据' : Number(value).toFixed(2) },
    legend: { top: 8, type: 'scroll', textStyle: { fontSize: 10 } },
    grid: { left: compact ? 88 : 105, right: 20, top: 48, bottom: 38 },
    xAxis: { type: 'value', min: -axisLimit, max: axisLimit, ...axisStyle() },
    yAxis: { type: 'category', data: data.factors.map((item) => item.name), axisLabel: { color: '#555', fontSize: 10 }, axisTick: { show: false }, axisLine: { lineStyle: { color: '#999' } } },
    dataZoom: compact ? [{ type: 'inside', yAxisIndex: 0 }] : [],
    series: data.indices.map((index) => ({ name: index.name, type: 'bar', data: data.factors.map((factor) => index.exposures[factor.key]), barMaxWidth: 11 }))
  });
}

function renderFactorDistributionChart(key) {
  state.factorDistributionChart?.dispose();
  const chart = echarts.init($('#factorDistributionChart'), null, { renderer: 'canvas' });
  state.factorDistributionChart = chart;
  const distribution = state.factors.distributions.find((item) => item.key === key);
  chart.setOption({
    ...factorChartBase(), tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, backgroundColor: '#fff', borderColor: '#ccc', textStyle: { color: '#222', fontSize: 11 } },
    grid: { left: 58, right: 24, top: 28, bottom: 48 }, xAxis: { type: 'category', data: distribution.bins.map((bin) => bin.label), ...axisStyle(), name: '标准化暴露' },
    yAxis: { type: 'value', minInterval: 1, ...axisStyle(), name: '股票数' }, series: [{ type: 'bar', data: distribution.bins.map((bin) => bin.count), itemStyle: { color: '#2D75B6' }, barMaxWidth: 72 }]
  });
}

function renderFactorIndustryChart() {
  state.factorIndustryChart?.dispose();
  const element = $('#factorIndustryChart');
  element.style.width = `${Math.max(960, state.factors.factors.length * 70)}px`;
  element.style.height = `${Math.max(420, state.factors.industries.length * 27 + 100)}px`;
  const chart = echarts.init(element, null, { renderer: 'canvas' });
  state.factorIndustryChart = chart;
  const valueMap = new Map(state.factors.heatmap.map((item) => [`${item.factor}|${item.industry}`, item.value]));
  chart.setOption({
    ...factorChartBase(), tooltip: { position: 'top', backgroundColor: '#fff', borderColor: '#ccc', textStyle: { color: '#222', fontSize: 11 }, formatter: ({ value }) => `${state.factors.factors[value[0]].name} · ${state.factors.industries[value[1]]}<br><b>${value[2] == null ? '无数据' : Number(value[2]).toFixed(2)}</b>` },
    grid: { left: 92, right: 28, top: 58, bottom: 30 },
    xAxis: { type: 'category', data: state.factors.factors.map((item) => item.name), axisLabel: { rotate: 45, fontSize: 9, color: '#555' }, splitArea: { show: true } },
    yAxis: { type: 'category', data: state.factors.industries, axisLabel: { fontSize: 9, color: '#555' }, splitArea: { show: true } },
    visualMap: { min: -1, max: 1, calculable: true, orient: 'horizontal', left: 'center', top: 4, itemWidth: 12, itemHeight: 120, inRange: { color: ['#2878B5', '#F2F2F2', '#D94F4B'] }, textStyle: { fontSize: 9 } },
    series: [{ type: 'heatmap', data: state.factors.factors.flatMap((factor, x) => state.factors.industries.map((industry, y) => [x, y, valueMap.get(`${factor.key}|${industry}`) ?? null])), emphasis: { itemStyle: { borderColor: '#222', borderWidth: 1 } } }]
  });
}

function renderFactorStockTable() {
  const data = state.factors;
  const names = new Map(data.factors.map((item) => [item.key, item.name]));
  $('#factorStockHead').innerHTML = `<tr><th>证券</th><th>行业</th><th>总市值(亿元)</th>${data.stockTableFactors.map((key) => `<th>${names.get(key)}</th>`).join('')}</tr>`;
  const query = $('#factorStockSearch').value.trim().toLowerCase();
  const rows = data.stocks.filter((item) => !query || item.code.toLowerCase().includes(query) || item.name.toLowerCase().includes(query)).slice(0, 100);
  $('#factorStockRows').innerHTML = rows.map((item) => `<tr><th><strong>${item.name}</strong><small>${item.code}</small></th><td>${item.industry}</td><td>${item.marketCap?.toLocaleString('zh-CN') ?? '--'}</td>${data.stockTableFactors.map((key) => `<td class="factor-value">${item.exposures[key] == null ? '--' : Number(item.exposures[key]).toFixed(2)}</td>`).join('')}</tr>`).join('');
}

async function switchView(view) {
  $$('.view-tabs button').forEach((button) => button.classList.toggle('active', button.dataset.view === view));
  $('#sentimentView').classList.toggle('hidden', view !== 'sentiment');
  $('#environmentView').classList.toggle('hidden', view !== 'environment');
  $('#styleView').classList.toggle('hidden', view !== 'style');
  $('#industryView').classList.toggle('hidden', view !== 'industry');
  $('#volumeView').classList.toggle('hidden', view !== 'volume');
  $('#volatilityView').classList.toggle('hidden', view !== 'volatility');
  $('#turnoverView').classList.toggle('hidden', view !== 'turnover');
  $('#breadthView').classList.toggle('hidden', view !== 'breadth');
  $('#factorView').classList.toggle('hidden', view !== 'factors');
  if (view === 'environment' && !state.environment) await loadEnvironment();
  if (view === 'style' && !state.style) await loadStyle();
  if (view === 'industry' && !state.industry) await loadIndustry();
  if (view === 'volume' && !state.volume) await loadVolume();
  if (view === 'volatility' && !state.volatility) await loadVolatility();
  if (view === 'turnover' && !state.turnover) await loadTurnover();
  if (view === 'breadth' && !state.breadth) await loadBreadth();
  if (view === 'factors' && !state.factors) await loadFactors();
  if (view === 'environment') setTimeout(() => state.environmentTrendChart?.resize(), 60);
  if (view === 'style') setTimeout(() => state.styleTrendChart?.resize(), 60);
  if (view === 'industry') setTimeout(() => { state.industryTrendChart?.resize(); }, 60);
  if (view === 'volume') setTimeout(() => { state.volumeAmountChart?.resize(); state.volumeShareChart?.resize(); }, 60);
  if (view === 'volatility') setTimeout(() => { state.indexVolatilityChart?.resize(); state.crossVolatilityChart?.resize(); }, 60);
  if (view === 'turnover') setTimeout(() => state.turnoverChart?.resize(), 60);
  if (view === 'breadth') setTimeout(() => state.breadthChart?.resize(), 60);
  if (view === 'factors') setTimeout(() => { state.factorIndexChart?.resize(); state.factorDistributionChart?.resize(); state.factorIndustryChart?.resize(); }, 60);
  if (window.lucide) window.lucide.createIcons();
}

function render() {
  disposeCharts();
  const data = state.data;
  $('#headerDate').textContent = data.asOf;
  $('#indexZone').textContent = data.index.zone;
  $('#indexChange').textContent = `较前一日 ${change(data.index.change)}`;
  $('#indexChange').className = data.index.change >= 0 ? 'positive' : 'negative';
  $('#dateRange').textContent = `${data.series[0].date} — ${data.series.at(-1).date}`;
  renderGauge(data.index.score);
  renderMain(data.series);
  renderIndicators(data.indicators, data.series);
  initIcons();
}

function renderGauge(value) {
  const chart = chartAt($('#gaugeChart'));
  chart.setOption({
    animationDuration: 850,
    series: [{
      type: 'gauge', startAngle: 205, endAngle: -25, min: 0, max: 100, radius: '88%', center: ['50%', '57%'],
      progress: { show: false }, pointer: { length: '60%', width: 4, itemStyle: { color: '#1f2328' } },
      anchor: { show: true, size: 10, itemStyle: { color: '#1f2328' } },
      axisLine: { lineStyle: { width: 15, color: [[.25, '#5AAEF3'], [.4, '#8EC8F5'], [.6, '#B1B4B6'], [.75, '#FF974C'], [1, '#E65A56']] } },
      axisTick: { distance: -21, splitNumber: 5, lineStyle: { color: '#fff', width: 1 }, length: 5 },
      splitLine: { distance: -23, length: 9, lineStyle: { color: '#fff', width: 2 } },
      axisLabel: { distance: 2, color: '#73777b', fontSize: 9, formatter: (v) => [0, 25, 50, 75, 100].includes(v) ? v : '' },
      detail: { valueAnimation: true, offsetCenter: [0, '35%'], color: '#1f2328', fontSize: 50, fontWeight: 800, formatter: (v) => v.toFixed(1) },
      title: { offsetCenter: [0, '56%'], color: '#777', fontSize: 10 },
      data: [{ value, name: '0 = 恐惧  ·  100 = 贪婪' }]
    }]
  });
}

function renderMain(series) {
  const chart = chartAt($('#mainChart'));
  const dates = series.map((row) => row.date);
  const values = series.map((row) => row.index);
  const shanghai = series.map((row) => row.shanghai);
  chart.setOption({
    animationDuration: 650,
    tooltip: {
      trigger: 'axis', backgroundColor: '#fff', borderColor: '#ccc', textStyle: { color: '#222', fontSize: 11 },
      formatter: (items) => `${items[0].axisValue}<br>${items.map((item) => `${item.marker}${item.seriesName} <b>${Number(item.value).toFixed(item.seriesName === '上证指数' ? 2 : 1)}</b>`).join('<br>')}`
    },
    grid: { ...chartGrid(42), right: 68 },
    xAxis: { type: 'category', boundaryGap: false, data: dates, ...axisStyle(), axisLabel: { color: '#73777b', fontSize: 10, hideOverlap: true, formatter: (value) => value.slice(5) } },
    yAxis: [
      { type: 'value', min: 0, max: 100, name: '情绪得分', nameTextStyle: { color: '#73777b', fontSize: 10 }, ...axisStyle() },
      {
        type: 'value', scale: true, position: 'right', name: '上证指数（点）',
        nameTextStyle: { color: '#73777b', fontSize: 10 }, axisTick: { show: false },
        axisLine: { show: true, lineStyle: { color: '#999' } },
        axisLabel: { show: true, color: '#73777b', fontSize: 10, formatter: (value) => Number(value).toFixed(0) },
        splitLine: { show: false }
      }
    ],
    dataZoom: [{ type: 'inside' }],
    series: [{
      name: '恐慌贪婪指数', type: 'line', yAxisIndex: 0, data: values, smooth: .22, showSymbol: false,
      lineStyle: { color: '#5AAEF3', width: 2.5 }, itemStyle: { color: '#5AAEF3' },
      markArea: { silent: true, itemStyle: { opacity: .035 }, data: [[{ yAxis: 0, itemStyle: { color: '#5AAEF3' } }, { yAxis: 25 }], [{ yAxis: 75, itemStyle: { color: '#E65A56' } }, { yAxis: 100 }]] },
      markLine: { silent: true, symbol: 'none', lineStyle: { color: '#999', type: 'dashed', width: 1 }, data: [{ yAxis: 50 }] },
      emphasis: { focus: 'series' }
    }, {
      name: '上证指数', type: 'line', yAxisIndex: 1, data: shanghai, smooth: .15, showSymbol: false,
      lineStyle: { color: '#E65A56', width: 1.8 }, itemStyle: { color: '#E65A56' }, emphasis: { focus: 'series' }
    }]
  });
}

function renderIndicators(indicators, series) {
  $('#indicatorGrid').innerHTML = indicators.map((item, index) => `
    <button class="indicator-card" style="--accent:${item.color}" data-key="${item.key}" aria-label="查看${item.name}详情">
      <div class="card-head"><span class="card-index">0${index + 1} / 05</span><i data-lucide="arrow-up-right"></i></div>
      <h3>${item.name}</h3><span class="short">${item.short} · ${item.direction}</span>
      <div class="score-row"><strong>${indicatorValue(item.value, item)}</strong><small class="${item.change >= 0 ? 'positive' : 'negative'}">${indicatorChange(item.change, item)}</small></div>
      <div class="mini-chart" id="mini-${item.key}"></div>
      <div class="card-foot"><span>原始值</span><span>均值 ${indicatorValue(item.average, item)}</span></div>
    </button>`).join('');
  indicators.forEach((item) => renderMini(item, series));
  $$('.indicator-card').forEach((card) => card.addEventListener('click', () => {
    if (state.user) openDetail(card.dataset.key);
  }));
}

function renderMini(item, series) {
  const chart = chartAt($(`#mini-${item.key}`));
  chart.setOption({
    animation: false,
    grid: { left: 3, right: 3, top: 6, bottom: 6 },
    xAxis: { type: 'category', data: series.map((row) => row.date), show: false },
    yAxis: { type: 'value', scale: true, show: false },
    series: [{ type: 'line', data: series.map((row) => row[item.key]), showSymbol: false, smooth: .2, lineStyle: { color: item.color, width: 2 }, areaStyle: { color: item.color, opacity: .08 } }]
  });
}

function openDetail(key) {
  const item = state.data.indicators.find((indicator) => indicator.key === key);
  $('#detailDirection').textContent = item.direction;
  $('#detailName').textContent = item.name;
  $('#detailDescription').textContent = item.description;
  $('#detailScore').textContent = indicatorValue(item.value, item);
  $('#detailAverage').textContent = indicatorValue(item.average, item);
  $('#detailMin').textContent = indicatorValue(item.min, item);
  $('#detailMax').textContent = indicatorValue(item.max, item);
  $('#detailSource').textContent = `数据来源：${item.source}`;
  $('#detailView').classList.remove('hidden');
  document.body.style.overflow = 'hidden';
  requestAnimationFrame(() => {
    const existing = echarts.getInstanceByDom($('#detailChart'));
    if (existing) existing.dispose();
    const chart = echarts.init($('#detailChart'));
    chart.setOption({
      tooltip: {
        trigger: 'axis', backgroundColor: '#fff', borderColor: '#ccc', textStyle: { color: '#222', fontSize: 11 },
        valueFormatter: (value) => indicatorValue(value, item)
      },
      grid: { left: 68, right: 48, top: 45, bottom: 55 },
      xAxis: { type: 'category', boundaryGap: false, data: state.data.series.map((row) => row.date), name: '日期', nameLocation: 'middle', nameGap: 33, ...axisStyle() },
      yAxis: { type: 'value', scale: true, name: `原始值（${item.unit}）`, ...axisStyle() },
      dataZoom: [{ type: 'inside' }, { type: 'slider', height: 16, bottom: 9, borderColor: '#ccc' }],
      series: [{
        type: 'line', data: state.data.series.map((row) => row[key]), showSymbol: false, smooth: .2,
        lineStyle: { color: item.color, width: 2.5 }, itemStyle: { color: item.color },
        endLabel: { show: true, formatter: ({ value }) => indicatorValue(value, item), color: item.color, fontWeight: 700 }
      }]
    });
    state.detailChart = chart;
  });
}

function closeDetail() {
  $('#detailView').classList.add('hidden');
  document.body.style.overflow = '';
  state.detailChart?.dispose();
}

function openAuth() {
  $('#formError').textContent = '';
  $('#authDialog').showModal();
}

function showAuthResult() {
  const params = new URLSearchParams(window.location.search);
  const result = params.get('auth');
  if (!result) return;
  const messages = {
    'not-configured': '微信登录尚未完成服务端配置。',
    'invalid-state': '登录请求已失效，请重新发起验证。',
    cancelled: '微信验证已取消。'
  };
  if (result !== 'success') {
    openAuth();
    $('#formError').textContent = messages[result] || '微信登录失败，请重试。';
  }
  history.replaceState({}, '', window.location.pathname);
}

function renderUser() {
  const loggedIn = Boolean(state.user);
  $('#authButton').classList.toggle('hidden', loggedIn);
  $('#userMenu').classList.toggle('hidden', !loggedIn);
  $('#indicatorGrid').classList.toggle('blurred', !loggedIn);
  $('#indicatorPreview').classList.toggle('locked', !loggedIn);
  $('#indicatorGate').classList.toggle('hidden', loggedIn);
  if (loggedIn) { $('#userName').textContent = state.user.name; $('#userInitial').textContent = state.user.name.slice(0, 1).toUpperCase(); }
}

async function initAuth() {
  const response = await fetch('/api/me');
  state.user = (await response.json()).user;
  renderUser();
}

$$('.view-tabs button').forEach((button) => button.addEventListener('click', () => switchView(button.dataset.view)));
$$('.environment-group-control button').forEach((button) => button.addEventListener('click', () => {
  state.environmentGroup = button.dataset.environmentGroup;
  $$('.environment-group-control button').forEach((item) => item.classList.toggle('active', item === button));
  renderEnvironmentTrend();
}));
$$('.breadth-group-control button').forEach((button) => button.addEventListener('click', () => {
  state.breadthGroup = button.dataset.breadthGroup;
  $$('.breadth-group-control button').forEach((item) => item.classList.toggle('active', item === button));
  renderBreadth();
}));
$$('.range-control button').forEach((button) => button.addEventListener('click', async () => {
  state.range = button.dataset.range;
  $$('.range-control button').forEach((item) => item.classList.toggle('active', item === button));
  await loadDashboard();
}));
$('#refreshButton').addEventListener('click', loadDashboard);
$('#environmentRefresh').addEventListener('click', loadEnvironment);
$('#styleRefresh').addEventListener('click', loadStyle);
$('#industryRefresh').addEventListener('click', loadIndustry);
$('#volumeRefresh').addEventListener('click', loadVolume);
$('#volatilityRefresh').addEventListener('click', loadVolatility);
$('#turnoverRefresh').addEventListener('click', loadTurnover);
$('#breadthRefresh').addEventListener('click', loadBreadth);
$('#factorRefresh').addEventListener('click', loadFactors);
$('#factorDistributionSelect').addEventListener('change', (event) => renderFactorDistributionChart(event.target.value));
$('#factorStockSearch').addEventListener('input', renderFactorStockTable);
$('#detailBack').addEventListener('click', closeDetail);
$('#authButton').addEventListener('click', openAuth);
$('#indicatorsLogin').addEventListener('click', openAuth);
$('#dialogClose').addEventListener('click', () => $('#authDialog').close());
$('#userTrigger').addEventListener('click', () => $('#userMenu').classList.toggle('open'));
$('#logoutButton').addEventListener('click', async () => { await fetch('/api/logout', { method: 'POST' }); state.user = null; $('#userMenu').classList.remove('open'); renderUser(); });

window.addEventListener('resize', () => { state.charts.forEach((chart) => chart.resize()); if (state.environment && !$('#environmentView').classList.contains('hidden')) renderEnvironmentTrend(); if (state.style && !$('#styleView').classList.contains('hidden')) renderStyleTrend(); if (state.industry && !$('#industryView').classList.contains('hidden')) { renderIndustryTrend([...state.industry.indices].sort((left, right) => Number(right.week) - Number(left.week))); } if (state.volume && !$('#volumeView').classList.contains('hidden')) renderVolume(); if (state.volatility && !$('#volatilityView').classList.contains('hidden')) renderVolatility(); if (state.turnover && !$('#turnoverView').classList.contains('hidden')) renderTurnover(); if (state.breadth && !$('#breadthView').classList.contains('hidden')) renderBreadth(); if (state.factors && !$('#factorView').classList.contains('hidden')) { renderFactorIndexChart(); renderFactorDistributionChart($('#factorDistributionSelect').value); } state.detailChart?.resize(); });
window.addEventListener('keydown', (event) => { if (event.key === 'Escape' && !$('#detailView').classList.contains('hidden')) closeDetail(); });

initIcons();
const yearEl = $('#siteYearYear'); if (yearEl) yearEl.textContent = String(new Date().getFullYear());
await Promise.all([loadDashboard(), initAuth()]);
showAuthResult();
