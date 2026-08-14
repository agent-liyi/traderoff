import test from 'node:test';
import assert from 'node:assert/strict';

process.env.NODE_ENV = 'test';
const { zone, buildWechatAuthorizeUrl, dashboard, marketEnvironment, marketStyle, industryPrice, marketVolume, marketVolatility, marketTurnover, marketBreadth, factorExposure } = await import('../server.js');

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

test('market environment returns the exact seven A-share indices and unchanged global references', async () => {
  const result = await marketEnvironment();
  const expected = [
    ['A股', '沪深300', '000300.SH'], ['A股', '中证500', '000905.SH'], ['A股', '中证1000', '000852.SH'], ['A股', '中证2000', '932000.CSI'], ['A股', '中证红利', '000922.CSI'], ['A股', '创业板指', '399006.SZ'], ['A股', '科创50', '000688.SH'],
    ['港股', '恒生指数', 'HSI'], ['港股', '恒生科技', 'HKTECH'], ['美股', '纳斯达克指数', 'IXIC'], ['美股', '标普500', 'SPX']
  ];
  assert.deepEqual(result.indices.map((item) => [item.group, item.name, item.code]), expected);
  assert.ok(result.indices.every((item) => ['week', 'month', 'ytd', 'year', 'close'].every((key) => Number.isFinite(item[key]))));
  assert.ok(result.indices.every((item) => item.sparkline.length === 5 && item.sparkline.every((point) => Number.isFinite(point.close))));
  assert.ok(result.indices.every((item) => item.history.length === 250 && item.history.every((point) => /^\d{4}-\d{2}-\d{2}$/.test(point.date) && Number.isFinite(point.close))));
});

test('market style returns eight complete Tushare style indices', async () => {
  const result = await marketStyle();
  const expectedCodes = ['399370.SZ', '399371.SZ', '399372.SZ', '399373.SZ', '399374.SZ', '399375.SZ', '399376.SZ', '399377.SZ'];
  assert.equal(result.indices.length, 8);
  assert.deepEqual(result.indices.map((item) => item.code), expectedCodes);
  assert.ok(result.indices.every((item) => ['全市场', '大盘', '中盘', '小盘'].includes(item.group)));
  assert.ok(result.indices.every((item) => ['week', 'month', 'ytd', 'year', 'close'].every((key) => Number.isFinite(item[key]))));
  assert.ok(result.indices.every((item) => item.sparkline.length === 5 && item.sparkline.every((point) => Number.isFinite(point.close))));
  assert.ok(result.indices.every((item) => item.history.length === 250 && item.history.every((point) => /^\d{4}-\d{2}-\d{2}$/.test(point.date) && Number.isFinite(point.close))));
});

test('industry price retains all Shenwan Level 1 indices and adds the seven-index market comparison', async () => {
  const result = await industryPrice();
  const expected = [['沪深300', '000300.SH'], ['中证500', '000905.SH'], ['中证1000', '000852.SH'], ['中证2000', '932000.CSI'], ['中证红利', '000922.CSI'], ['创业板指', '399006.SZ'], ['科创50', '000688.SH']];
  assert.equal(result.indices.length, 31);
  assert.ok(result.indices.every((item) => /^801\d{3}\.SI$/.test(item.code)));
  assert.ok(result.indices.every((item) => ['week', 'month', 'ytd', 'year', 'close', 'amount'].every((key) => Number.isFinite(item[key]))));
  assert.ok(result.indices.every((item) => item.sparkline.length === 5 && item.sparkline.every((point) => Number.isFinite(point.close))));
  assert.ok(result.indices.every((item) => item.history.length === 250 && item.history.every((point) => /^\d{4}-\d{2}-\d{2}$/.test(point.date) && Number.isFinite(point.close))));
  assert.deepEqual(result.marketIndices.map((item) => [item.name, item.code]), expected);
  assert.ok(result.marketIndices.every((item) => ['week', 'month', 'ytd', 'year', 'close', 'amount'].every((key) => Number.isFinite(item[key]))));
  assert.ok(result.marketIndices.every((item) => item.history.length === 250));
});

test('market volume returns five reconciled size buckets and 250 complete days', async () => {
  const result = await marketVolume();
  const expected = [['沪深300', '000300.SH'], ['中证500', '000905.SH'], ['中证1000', '000852.SH'], ['中证2000', '932000.CSI'], ['3800以外', 'OTHER']];
  assert.deepEqual(result.buckets.map((item) => [item.name, item.code]), expected);
  assert.equal(result.history.length, 250);
  assert.ok(result.buckets.every((item) => ['amount', 'amountPercentile', 'share', 'sharePercentile'].every((key) => Number.isFinite(item[key]))));
  assert.ok(result.buckets.every((item) => item.share >= 0 && item.share <= 100 && item.amountPercentile > 0 && item.amountPercentile <= 100 && item.sharePercentile > 0 && item.sharePercentile <= 100));
  assert.ok(result.history.every((row) => {
    const amounts = Object.values(row.amounts);
    const shares = Object.values(row.shares);
    return /^\d{4}-\d{2}-\d{2}$/.test(row.date) && Number.isFinite(row.total) && amounts.length === 5 && shares.length === 5 && amounts.every(Number.isFinite) && shares.every((value) => Number.isFinite(value) && value >= 0 && value <= 100) && Math.abs(amounts.reduce((sum, value) => sum + value, 0) - row.total) < 0.02 && Math.abs(shares.reduce((sum, value) => sum + value, 0) - 100) < 0.02;
  }));
});

test('market volatility returns the exact seven Tushare index and component histories', async () => {
  const result = await marketVolatility();
  const expected = [['沪深300', '000300.SH'], ['中证500', '000905.SH'], ['中证1000', '000852.SH'], ['中证2000', '932000.CSI'], ['中证红利', '000922.CSI'], ['创业板指', '399006.SZ'], ['科创50', '000688.SH']];
  assert.deepEqual(result.indexVolatility.map((item) => [item.name, item.code]), expected);
  assert.deepEqual(result.crossSectionVolatility.map((item) => [item.name, item.code]), expected);
  for (const group of [result.indexVolatility, result.crossSectionVolatility]) {
    assert.ok(group.every((item) => item.history.length === 250));
    assert.ok(group.every((item) => item.history.every((point) => /^\d{4}-\d{2}-\d{2}$/.test(point.date) && Number.isFinite(point.value) && point.value >= 0)));
  }
});

test('market turnover returns seven complete free-float turnover histories', async () => {
  const result = await marketTurnover();
  const expected = [['沪深300', '000300.SH'], ['中证500', '000905.SH'], ['中证1000', '000852.SH'], ['中证2000', '932000.CSI'], ['中证红利', '000922.CSI'], ['创业板指', '399006.SZ'], ['科创50', '000688.SH']];
  assert.deepEqual(result.indices.map((item) => [item.name, item.code]), expected);
  assert.ok(result.indices.every((item) => ['current', 'weekAverage', 'monthAverage', 'percentile'].every((key) => Number.isFinite(item[key]))));
  assert.ok(result.indices.every((item) => item.current >= 0 && item.percentile > 0 && item.percentile <= 100));
  assert.ok(result.indices.every((item) => item.sparkline.length === 5 && item.history.length === 250));
  assert.ok(result.indices.every((item) => item.history.every((point) => /^\d{4}-\d{2}-\d{2}$/.test(point.date) && Number.isFinite(point.value) && point.value >= 0)));
});

test('market breadth returns seven reconciled target-index advance-decline distributions', async () => {
  const result = await marketBreadth();
  const expected = [['沪深300', '000300.SH'], ['中证500', '000905.SH'], ['中证1000', '000852.SH'], ['中证2000', '932000.CSI'], ['中证红利', '000922.CSI'], ['创业板指', '399006.SZ'], ['科创50', '000688.SH']];
  assert.deepEqual(result.groups.map((item) => [item.name, item.code]), expected);
  assert.ok(result.groups.every((item) => Number.isInteger(item.count) && item.count > 0 && item.rise + item.flat + item.fall === item.count));
  assert.ok(result.groups.every((item) => item.distribution.length === 22 && item.distribution.every((bin) => typeof bin.label === 'string' && Number.isInteger(bin.count) && bin.count >= 0)));
  assert.ok(result.groups.every((item) => item.distribution.reduce((sum, bin) => sum + bin.count, 0) === item.count));
});

test('factor exposure returns the exact CNLT reference factor set and transparent quality metadata', async () => {
  const result = await factorExposure();
  const expected = ['size', 'nonlinearSize', 'beta', 'momentum', 'residualVolatility', 'liquidity', 'bookToPrice', 'earningsYield', 'growth', 'dividendYield', 'leverage', 'earningsVariability', 'earningsQuality', 'profitability', 'investmentQuality', 'longTermReversal'];
  assert.deepEqual(result.factors.map((item) => item.key), expected);
  assert.equal(result.indices.length, 4);
  assert.equal(result.distributions.length, 16);
  assert.ok(result.model.disclaimer.includes('非 MSCI Barra 官方模型'));
  assert.ok(result.quality.universeCount >= 1500 && result.quality.universeCount <= 1900);
  assert.ok(result.indices.slice(0, 3).every((item) => item.count >= 250));
  assert.equal(result.indices.at(-1).count, result.quality.universeCount);
  assert.ok(result.quality.priceHistoryDays >= 1250);
  assert.ok(result.factors.every((item) => Number.isFinite(item.coverage) && item.coverage >= 0 && item.coverage <= 1));
  assert.ok(result.factors.filter((item) => item.coverage === 0).every((item) => result.indices.every((index) => index.exposures[item.key] === null)));
  assert.ok(result.stocks.length <= 500);
});

test('dashboard hides raw indicator values for anonymous visitors', async () => {
  const result = await dashboard('1y');
  assert.equal(result.indicators.length, 5);
  assert.ok(result.indicators.every((indicator) => indicator.value === 0 && indicator.average === 0));
  assert.equal(result.series.length, 250);
  assert.ok(result.index.score >= 0 && result.index.score <= 100);
  assert.ok(result.series.every((point) => Number.isFinite(point.shanghai)));
  assert.ok(result.series.every((point) => ['qvix', 'strength', 'futures', 'volume', 'safety'].every((key) => Number.isFinite(point[key]))));
});
