import test from 'node:test';
import assert from 'node:assert/strict';

process.env.NODE_ENV = 'test';
const { zone, buildWechatAuthorizeUrl, dashboard, marketEnvironment } = await import('../server.js');

test('zone boundaries follow notebook definitions', () => {
  assert.equal(zone(24.9), '极度恐惧');
  assert.equal(zone(25), '恐惧');
  assert.equal(zone(40), '中性');
  assert.equal(zone(60), '贪婪');
  assert.equal(zone(75), '极度贪婪');
});

test('WeChat authorize URL uses website QR login and callback state', () => {
  const url = new URL(buildWechatAuthorizeUrl('test-state'));
  assert.equal(url.hostname, 'open.weixin.qq.com');
  assert.equal(url.pathname, '/connect/qrconnect');
  assert.equal(url.searchParams.get('scope'), 'snsapi_login');
  assert.equal(url.searchParams.get('state'), 'test-state');
});

test('market environment returns 12 complete Tushare indices', async () => {
  const result = await marketEnvironment();
  assert.equal(result.indices.length, 12);
  assert.ok(result.indices.every((item) => ['A股', '港股', '美股'].includes(item.group)));
  assert.ok(result.indices.every((item) => ['week', 'month', 'ytd', 'year', 'close'].every((key) => Number.isFinite(item[key]))));
  assert.ok(result.indices.every((item) => item.sparkline.length === 5 && item.sparkline.every((point) => Number.isFinite(point.close))));
  assert.ok(result.indices.every((item) => item.history.length === 250 && item.history.every((point) => /^\d{4}-\d{2}-\d{2}$/.test(point.date) && Number.isFinite(point.close))));
});

test('dashboard hides raw indicator values for anonymous visitors', async () => {
  const result = await dashboard('1m');
  assert.equal(result.indicators.length, 5);
  assert.ok(result.indicators.every((indicator) => indicator.value === 0 && indicator.average === 0));
  assert.equal(result.series.length, 250);
  assert.ok(result.index.score >= 0 && result.index.score <= 100);
  assert.ok(result.series.every((point) => Number.isFinite(point.shanghai)));
  assert.ok(result.series.every((point) => ['qvix', 'strength', 'futures', 'volume', 'safety'].every((key) => Number.isFinite(point[key]))));
});
