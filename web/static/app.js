const state = { range: '1y', data: null, environment: null, environmentGroup: 'A股', charts: [], environmentTrendChart: null, user: null };
const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];
const palette = { qvix: '#5AAEF3', strength: '#333333', futures: '#E65A56', volume: '#6D61E4', safety: '#30CB13' };
const environmentPalette = ['#1F77B4', '#E15759', '#2C8C6B', '#F28E2B', '#6B5FB5', '#A05D3A', '#C6A016', '#40484F'];
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

async function switchView(view) {
  $$('.view-tabs button').forEach((button) => button.classList.toggle('active', button.dataset.view === view));
  $('#sentimentView').classList.toggle('hidden', view !== 'sentiment');
  $('#environmentView').classList.toggle('hidden', view !== 'environment');
  if (view === 'environment' && !state.environment) await loadEnvironment();
  if (view === 'environment') requestAnimationFrame(() => state.environmentTrendChart?.resize());
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
$$('.range-control button').forEach((button) => button.addEventListener('click', async () => {
  state.range = button.dataset.range;
  $$('.range-control button').forEach((item) => item.classList.toggle('active', item === button));
  await loadDashboard();
}));
$('#refreshButton').addEventListener('click', loadDashboard);
$('#environmentRefresh').addEventListener('click', loadEnvironment);
$('#detailBack').addEventListener('click', closeDetail);
$('#authButton').addEventListener('click', openAuth);
$('#indicatorsLogin').addEventListener('click', openAuth);
$('#dialogClose').addEventListener('click', () => $('#authDialog').close());
$('#userTrigger').addEventListener('click', () => $('#userMenu').classList.toggle('open'));
$('#logoutButton').addEventListener('click', async () => { await fetch('/api/logout', { method: 'POST' }); state.user = null; $('#userMenu').classList.remove('open'); renderUser(); });

window.addEventListener('resize', () => { state.charts.forEach((chart) => chart.resize()); if (state.environment && !$('#environmentView').classList.contains('hidden')) renderEnvironmentTrend(); state.detailChart?.resize(); });
window.addEventListener('keydown', (event) => { if (event.key === 'Escape' && !$('#detailView').classList.contains('hidden')) closeDetail(); });

initIcons();
await Promise.all([loadDashboard(), initAuth()]);
showAuthResult();
