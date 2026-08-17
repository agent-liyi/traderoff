import { createServer } from 'node:http';
import { readFile, stat, mkdir } from 'node:fs/promises';
import { extname, join, normalize } from 'node:path';
import { fileURLToPath } from 'node:url';
import { DatabaseSync } from 'node:sqlite';
import pg from 'pg';
import { createHash, randomBytes } from 'node:crypto';

const ROOT = fileURLToPath(new URL('.', import.meta.url));
const STATIC_ROOT = join(ROOT, 'static');
const DATA_PATH = process.env.FEAR_GREED_DATA || join(ROOT, '..', 'data', 'fear_greed_runtime.json');
const MARKET_ENVIRONMENT_PATH = process.env.MARKET_ENVIRONMENT_DATA || join(ROOT, '..', 'data', 'market_environment_runtime.json');
const MARKET_STYLE_PATH = process.env.MARKET_STYLE_DATA || join(ROOT, '..', 'data', 'market_style_runtime.json');
const INDUSTRY_PRICE_PATH = process.env.INDUSTRY_PRICE_DATA || join(ROOT, '..', 'data', 'industry_price_runtime.json');
const MARKET_VOLUME_PATH = process.env.MARKET_VOLUME_DATA || join(ROOT, '..', 'data', 'market_volume_runtime.json');
const MARKET_VOLATILITY_PATH = process.env.MARKET_VOLATILITY_DATA || join(ROOT, '..', 'data', 'market_volatility_runtime.json');
const MARKET_TURNOVER_PATH = process.env.MARKET_TURNOVER_DATA || join(ROOT, '..', 'data', 'market_turnover_runtime.json');
const MARKET_BREADTH_PATH = process.env.MARKET_BREADTH_DATA || join(ROOT, '..', 'data', 'market_breadth_runtime.json');
const FACTOR_EXPOSURE_PATH = process.env.FACTOR_EXPOSURE_DATA || join(ROOT, '..', 'data', 'factor_exposure_runtime.json');
const DB_PATH = process.env.USERS_DB || join(ROOT, 'data', 'users.sqlite');
const PORT = Number(process.env.PORT || 8788);
const WECHAT_AUTH_MODE = process.env.WECHAT_AUTH_MODE || 'development';
const WECHAT_APP_ID = process.env.WECHAT_APP_ID || '';
const WECHAT_APP_SECRET = process.env.WECHAT_APP_SECRET || '';
const WECHAT_REDIRECT_URI = process.env.WECHAT_REDIRECT_URI || `http://localhost:${PORT}/api/auth/wechat/callback`;
const WECHAT_STATE_TTL_MS = 10 * 60 * 1000;
const MARKET_DATA_BACKEND = process.env.MARKET_DATA_BACKEND || (process.env.NODE_ENV === 'test' ? 'file' : 'postgres');
const MARKET_DATABASE_URL = process.env.MARKET_DATABASE_URL || process.env.DATABASE_URL || '';
const marketDb = MARKET_DATA_BACKEND === 'postgres' && MARKET_DATABASE_URL
  ? new pg.Pool({ connectionString: MARKET_DATABASE_URL, max: Number(process.env.MARKET_DB_POOL_SIZE || 4) })
  : null;
await mkdir(join(ROOT, 'data'), { recursive: true });

const db = new DatabaseSync(DB_PATH);
db.exec(`
  PRAGMA journal_mode = WAL;
  CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
  );
  CREATE TABLE IF NOT EXISTS sessions (
    token_hash TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires_at INTEGER NOT NULL
  );
  CREATE TABLE IF NOT EXISTS oauth_states (
    state_hash TEXT PRIMARY KEY,
    expires_at INTEGER NOT NULL
  );
`);

const userColumns = db.prepare('PRAGMA table_info(users)').all().map((column) => column.name);
if (!userColumns.includes('phone')) db.exec('ALTER TABLE users ADD COLUMN phone TEXT');
if (!userColumns.includes('wechat_openid')) db.exec('ALTER TABLE users ADD COLUMN wechat_openid TEXT');
if (!userColumns.includes('avatar_url')) db.exec('ALTER TABLE users ADD COLUMN avatar_url TEXT');
db.exec('CREATE UNIQUE INDEX IF NOT EXISTS users_phone_unique ON users(phone) WHERE phone IS NOT NULL');
db.exec('CREATE UNIQUE INDEX IF NOT EXISTS users_wechat_openid_unique ON users(wechat_openid) WHERE wechat_openid IS NOT NULL');

const INDICATORS = {
  qvix: { rawColumn: 'raw_qvix', factor: 1, precision: 2, unit: '%', name: 'QVIX 波动率', short: '50ETF QVIX', color: '#5AAEF3', direction: '反向指标', source: 'Tushare · 50ETF期权链', description: '按照 QVIX 方差互换口径综合近月、次月和不同行权价的 50ETF 期权，直接显示年化隐含波动率。' },
  strength: { rawColumn: 'raw_strength', factor: 1, precision: 2, unit: '%', name: '股价强度', short: '250日新高占比', color: '#333333', direction: '正向指标', source: 'Tushare · A股日线', description: '直接显示全市场收盘价创 250 日新高的股票数量占当日股票总数的比例。' },
  futures: { rawColumn: 'raw_futures', factor: 1, precision: 2, unit: '%', name: '期货升贴水', short: 'IF 次月', color: '#E65A56', direction: '正向指标', source: 'Tushare · IF期货与沪深300', description: '直接显示 IF 次月合约相对沪深 300 的年化升贴水率，经 10 个交易日移动平均。' },
  volume: { rawColumn: 'raw_volume', factor: 100, precision: 2, unit: '%', name: '成交量偏离', short: '沪深全市场', color: '#6D61E4', direction: '正向指标', source: 'Tushare · 沪深A股日线汇总', description: '直接显示沪深两市 A 股总成交量相对 20 日移动平均成交量的偏离比例。' },
  safety: { rawColumn: 'raw_safety', factor: 100, precision: 2, unit: '%', name: '避险需求', short: '股债收益差', color: '#30CB13', direction: '正向指标', source: 'Tushare · 沪深300与中债综合指数', description: '直接显示沪深 300 的 20 日收益率减去中债综合指数 20 日收益率。' }
};

const A_SHARE_INDEX_UNIVERSE = [
  ['沪深300', '000300.SH'], ['中证500', '000905.SH'], ['中证1000', '000852.SH'], ['中证2000', '932000.CSI'], ['中证红利', '000922.CSI'], ['创业板指', '399006.SZ'], ['科创50', '000688.SH']
];
const MARKET_ENVIRONMENT_INDICES = [
  ...A_SHARE_INDEX_UNIVERSE.map(([name, code]) => ['A股', name, code]),
  ['港股', '恒生指数', 'HSI'], ['港股', '恒生科技', 'HKTECH'], ['美股', '纳斯达克指数', 'IXIC'], ['美股', '标普500', 'SPX']
];

function marketDatabaseUnavailable(message, cause) {
  const unavailable = new Error(message);
  unavailable.statusCode = 503;
  unavailable.cause = cause;
  return unavailable;
}

async function marketSnapshot(dataset, fallbackPath) {
  if (MARKET_DATA_BACKEND === 'file') return JSON.parse(await readFile(fallbackPath, 'utf8'));
  if (!marketDb) throw marketDatabaseUnavailable('行情数据库未配置');
  let result;
  try {
    result = await marketDb.query('SELECT payload FROM market_runtime_snapshots WHERE dataset = $1', [dataset]);
  } catch (error) {
    throw marketDatabaseUnavailable('行情数据库暂时不可用', error);
  }
  if (!result.rowCount) throw marketDatabaseUnavailable(`${dataset} 行情快照尚未入库`);
  return result.rows[0].payload;
}

let dataMtime = 0;
let rows = [];
async function loadRows() {
  if (MARKET_DATA_BACKEND === 'postgres') {
    if (!marketDb) throw marketDatabaseUnavailable('行情数据库未配置');
    let result;
    try {
      result = await marketDb.query(`
        SELECT trade_date::text AS date, score_qvix AS "QVIX", score_strength AS "股价强度",
          score_futures AS "期货升贴水", score_volume AS "成交量", score_safety AS "避险需求",
          our_index, our_zone, shanghai_index, raw_qvix, raw_strength, raw_futures, raw_volume, raw_safety
        FROM market_fear_greed_daily
        ORDER BY trade_date
      `);
    } catch (error) {
      throw marketDatabaseUnavailable('行情数据库暂时不可用', error);
    }
    if (!result.rowCount) throw marketDatabaseUnavailable('恐惧贪婪行情尚未入库');
    return result.rows.map((row) => Object.fromEntries(Object.entries(row).map(([key, value]) => [key, key === 'date' || key === 'our_zone' ? value : Number(value)])));
  }
  const info = await stat(DATA_PATH);
  if (!rows.length || info.mtimeMs !== dataMtime) {
    rows = JSON.parse(await readFile(DATA_PATH, 'utf8')).map((row) => Object.fromEntries(Object.entries(row).map(([key, value]) => [key, key === 'date' || key === 'our_zone' ? value : Number(value)])));
    dataMtime = info.mtimeMs;
  }
  return rows;
}

async function marketEnvironment() {
  const payload = await marketSnapshot('market-environment', MARKET_ENVIRONMENT_PATH);
  if (!Array.isArray(payload.indices) || payload.indices.length !== MARKET_ENVIRONMENT_INDICES.length) throw new Error('市场环境数据不完整');
  if (payload.indices.some((item, index) => item.group !== MARKET_ENVIRONMENT_INDICES[index][0] || item.name !== MARKET_ENVIRONMENT_INDICES[index][1] || item.code !== MARKET_ENVIRONMENT_INDICES[index][2] || item.history?.length !== 250)) throw new Error('市场环境指数定义不正确');
  return payload;
}

async function marketStyle() {
  const payload = await marketSnapshot('market-style', MARKET_STYLE_PATH);
  if (!Array.isArray(payload.indices) || payload.indices.length !== 8) throw new Error('市场风格数据不完整');
  return payload;
}

async function industryPrice() {
  const payload = await marketSnapshot('industry-price', INDUSTRY_PRICE_PATH);
  if (!Array.isArray(payload.indices) || payload.indices.length !== 31) throw new Error('行业价格指数数据不完整');
  return payload;
}

async function marketVolume() {
  const payload = await marketSnapshot('market-volume', MARKET_VOLUME_PATH);
  const expected = [
    ['沪深300', '000300.SH'], ['中证500', '000905.SH'], ['中证1000', '000852.SH'], ['中证2000', '932000.CSI'], ['3800以外', 'OTHER']
  ];
  if (!Array.isArray(payload.buckets) || payload.buckets.length !== expected.length || !Array.isArray(payload.history) || payload.history.length !== 250) throw new Error('市场成交量数据不完整');
  if (payload.buckets.some((item, index) => item.name !== expected[index][0] || item.code !== expected[index][1])) throw new Error('市场成交量桶定义不正确');
  return payload;
}

async function marketVolatility() {
  const payload = await marketSnapshot('market-volatility', MARKET_VOLATILITY_PATH);
  if (!Array.isArray(payload.indexVolatility) || payload.indexVolatility.length !== A_SHARE_INDEX_UNIVERSE.length || !Array.isArray(payload.crossSectionVolatility) || payload.crossSectionVolatility.length !== A_SHARE_INDEX_UNIVERSE.length) throw new Error('市场波动率数据不完整');
  for (const group of [payload.indexVolatility, payload.crossSectionVolatility]) {
    if (group.some((item, index) => item.name !== A_SHARE_INDEX_UNIVERSE[index][0] || item.code !== A_SHARE_INDEX_UNIVERSE[index][1] || item.history?.length !== 250)) throw new Error('市场波动率指数定义不正确');
  }
  return payload;
}

async function marketTurnover() {
  const payload = await marketSnapshot('market-turnover', MARKET_TURNOVER_PATH);
  const expected = A_SHARE_INDEX_UNIVERSE;
  if (!Array.isArray(payload.indices) || payload.indices.length !== expected.length) throw new Error('市场换手率数据不完整');
  if (payload.indices.some((item, index) => item.name !== expected[index][0] || item.code !== expected[index][1] || item.history?.length !== 250)) throw new Error('市场换手率指数定义不正确');
  return payload;
}

async function marketBreadth() {
  const payload = await marketSnapshot('market-breadth', MARKET_BREADTH_PATH);
  const expected = A_SHARE_INDEX_UNIVERSE;
  if (!Array.isArray(payload.groups) || payload.groups.length !== expected.length) throw new Error('成分股涨跌分布数据不完整');
  if (payload.groups.some((item, index) => item.name !== expected[index][0] || item.code !== expected[index][1] || item.distribution?.length !== 22)) throw new Error('成分股涨跌分布定义不正确');
  if (payload.groups.some((item) => item.rise + item.flat + item.fall !== item.count || item.distribution.reduce((sum, bin) => sum + Number(bin.count), 0) !== item.count)) throw new Error('成分股涨跌分布统计不完整');
  return payload;
}

const FACTOR_KEYS = ['size', 'nonlinearSize', 'beta', 'momentum', 'residualVolatility', 'liquidity', 'bookToPrice', 'earningsYield', 'growth', 'dividendYield', 'leverage', 'earningsVariability', 'earningsQuality', 'profitability', 'investmentQuality', 'longTermReversal'];
let factorExposureMtime = 0;
let factorExposureCache = null;
async function factorExposure() {
  if (MARKET_DATA_BACKEND === 'postgres') {
    factorExposureCache = await marketSnapshot('factor-exposure', FACTOR_EXPOSURE_PATH);
  } else {
    let info;
    try {
      info = await stat(FACTOR_EXPOSURE_PATH);
    } catch (error) {
      if (error.code === 'ENOENT') {
        const unavailable = new Error('多因子快照尚未生成');
        unavailable.statusCode = 503;
        throw unavailable;
      }
      throw error;
    }
    if (!factorExposureCache || info.mtimeMs !== factorExposureMtime) {
      factorExposureCache = JSON.parse(await readFile(FACTOR_EXPOSURE_PATH, 'utf8'));
      factorExposureMtime = info.mtimeMs;
    }
  }
  const payload = factorExposureCache;
  if (payload.schemaVersion !== 1 || !/^\d{4}-\d{2}-\d{2}$/.test(payload.asOf || '')) throw new Error('多因子数据版本或日期无效');
  if (!Array.isArray(payload.factors) || payload.factors.length !== 16 || payload.factors.some((item, index) => item.key !== FACTOR_KEYS[index] || !Number.isFinite(item.coverage) || item.coverage < 0 || item.coverage > 1)) throw new Error('多因子定义不完整');
  if (!Array.isArray(payload.indices) || payload.indices.length !== 4 || payload.indices.some((item) => !item.exposures || !item.coverages || FACTOR_KEYS.some((key) => item.exposures[key] !== null && !Number.isFinite(item.exposures[key])))) throw new Error('多因子指数数据不完整');
  if (!Array.isArray(payload.distributions) || payload.distributions.length !== 16 || payload.distributions.some((item, index) => item.key !== FACTOR_KEYS[index] || item.bins?.length !== 6 || item.bins.some((bin) => typeof bin.label !== 'string' || !Number.isInteger(bin.count) || bin.count < 0))) throw new Error('多因子分布数据不完整');
  if (!Array.isArray(payload.industries) || !payload.industries.length || !Array.isArray(payload.stockTableFactors) || payload.stockTableFactors.some((key) => !FACTOR_KEYS.includes(key))) throw new Error('多因子行业或明细定义不完整');
  if (!payload.model?.disclaimer?.includes('非 MSCI Barra 官方模型') || !Array.isArray(payload.quality?.warnings)) throw new Error('多因子声明或质量信息不完整');
  if (!Array.isArray(payload.stocks) || payload.stocks.length > 500 || payload.stocks.some((item) => typeof item.code !== 'string' || typeof item.name !== 'string' || !item.exposures) || !Array.isArray(payload.heatmap)) throw new Error('多因子明细数据无效');
  return payload;
}

function zone(score) {
  if (score < 25) return '极度恐惧';
  if (score < 40) return '恐惧';
  if (score < 60) return '中性';
  if (score < 75) return '贪婪';
  return '极度贪婪';
}

function rangeRows(allRows, range) {
  const sizes = { '6m': 126, '1y': 250, '3y': 750, all: 1250 };
  return allRows.slice(-Math.min(sizes[range] || 250, allRows.length));
}

function summarize(values) {
  const valid = values.filter(Number.isFinite);
  return { min: Math.min(...valid), max: Math.max(...valid), average: valid.reduce((sum, value) => sum + value, 0) / valid.length };
}

async function dashboard(range = '1y', user = null) {
  const allRows = await loadRows();
  const selected = rangeRows(allRows, range);
  const current = allRows.at(-1);
  const previous = allRows.at(-2);
  const indicators = Object.entries(INDICATORS).map(([key, meta]) => {
    const value = (row) => row[meta.rawColumn] * meta.factor;
    return {
      key, ...meta, value: value(current), change: value(current) - value(previous),
      ...summarize(selected.map(value))
    };
  });
  const indicatorSeries = selected.map((row, index) => ({
    date: row.date,
    index: row.our_index,
    shanghai: row.shanghai_index,
    ...(user ? {
      qvix: row.raw_qvix,
      strength: row.raw_strength,
      futures: row.raw_futures,
      volume: row.raw_volume * 100,
      safety: row.raw_safety * 100,
    } : {
      qvix: 18 + Math.sin(index / 8),
      strength: 1 + Math.sin(index / 10),
      futures: -8 + Math.sin(index / 9),
      volume: Math.sin(index / 7) * 5,
      safety: Math.sin(index / 11) * 4,
    })
  }));
  return {
    asOf: current.date,
    index: { score: current.our_index, change: current.our_index - previous.our_index, zone: zone(current.our_index) },
    indicators: user ? indicators : Object.entries(INDICATORS).map(([key, meta]) => ({
      key, ...meta, value: 0, change: 0, average: 0, min: 0, max: 0
    })),
    series: indicatorSeries
  };
}

function publicUser(user) { return { id: user.id, name: user.name, avatarUrl: user.avatar_url || null }; }
function parseCookies(header = '') {
  return Object.fromEntries(header.split(';').map((part) => part.trim().split('=').map(decodeURIComponent)).filter((pair) => pair.length === 2));
}
function currentUser(req) {
  const token = parseCookies(req.headers.cookie).session;
  if (!token) return null;
  const tokenHash = createHash('sha256').update(token).digest('hex');
  return db.prepare(`SELECT users.id, users.name, users.avatar_url FROM sessions JOIN users ON users.id = sessions.user_id WHERE sessions.token_hash = ? AND sessions.expires_at > ?`).get(tokenHash, Date.now()) || null;
}
function createSession(userId) {
  const token = randomBytes(32).toString('base64url');
  db.prepare('INSERT INTO sessions (token_hash, user_id, expires_at) VALUES (?, ?, ?)').run(createHash('sha256').update(token).digest('hex'), userId, Date.now() + 7 * 86400000);
  return token;
}
async function jsonBody(req) {
  let body = '';
  for await (const chunk of req) {
    body += chunk;
    if (body.length > 100000) throw new Error('请求内容过大');
  }
  return JSON.parse(body || '{}');
}
function sendJson(res, status, payload, headers = {}) {
  res.writeHead(status, { 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store', ...headers });
  res.end(JSON.stringify(payload));
}
function sessionCookie(token) { return `session=${encodeURIComponent(token)}; HttpOnly; SameSite=Lax; Path=/; Max-Age=${7 * 86400}`; }

function createWechatState() {
  const state = randomBytes(24).toString('base64url');
  db.prepare('DELETE FROM oauth_states WHERE expires_at <= ?').run(Date.now());
  db.prepare('INSERT INTO oauth_states (state_hash, expires_at) VALUES (?, ?)').run(createHash('sha256').update(state).digest('hex'), Date.now() + WECHAT_STATE_TTL_MS);
  return state;
}
function consumeWechatState(state) {
  if (!state) return false;
  const stateHash = createHash('sha256').update(state).digest('hex');
  const record = db.prepare('SELECT expires_at FROM oauth_states WHERE state_hash = ?').get(stateHash);
  db.prepare('DELETE FROM oauth_states WHERE state_hash = ?').run(stateHash);
  return Boolean(record && record.expires_at > Date.now());
}
function buildWechatAuthorizeUrl(state) {
  const params = new URLSearchParams({ appid: WECHAT_APP_ID, redirect_uri: WECHAT_REDIRECT_URI, response_type: 'code', scope: 'snsapi_login', state });
  return `https://open.weixin.qq.com/connect/qrconnect?${params.toString()}#wechat_redirect`;
}
async function fetchWechatJson(url) {
  const response = await fetch(url, { headers: { Accept: 'application/json' } });
  if (!response.ok) throw new Error(`微信接口请求失败: ${response.status}`);
  const result = await response.json();
  if (result.errcode) throw new Error(`微信接口错误: ${result.errcode}`);
  return result;
}
async function exchangeWechatCode(code) {
  const tokenParams = new URLSearchParams({ appid: WECHAT_APP_ID, secret: WECHAT_APP_SECRET, code, grant_type: 'authorization_code' });
  const token = await fetchWechatJson(`https://api.weixin.qq.com/sns/oauth2/access_token?${tokenParams}`);
  const userParams = new URLSearchParams({ access_token: token.access_token, openid: token.openid, lang: 'zh_CN' });
  return fetchWechatJson(`https://api.weixin.qq.com/sns/userinfo?${userParams}`);
}
function findOrCreateWechatUser(profile) {
  let user = db.prepare('SELECT id, name, avatar_url FROM users WHERE wechat_openid = ?').get(profile.openid);
  if (user) {
    db.prepare('UPDATE users SET name = ?, avatar_url = ? WHERE id = ?').run(profile.nickname || user.name, profile.headimgurl || null, user.id);
    return { ...user, name: profile.nickname || user.name, avatar_url: profile.headimgurl || null };
  }
  const identity = createHash('sha256').update(profile.openid).digest('hex').slice(0, 24);
  const name = String(profile.nickname || '微信用户').slice(0, 40);
  const result = db.prepare('INSERT INTO users (name, email, password_hash, wechat_openid, avatar_url) VALUES (?, ?, ?, ?, ?)').run(name, `${identity}@wechat.local`, 'wechat-oauth', profile.openid, profile.headimgurl || null);
  return { id: Number(result.lastInsertRowid), name, avatar_url: profile.headimgurl || null };
}
function redirect(res, location, headers = {}) {
  res.writeHead(302, { Location: location, 'Cache-Control': 'no-store', ...headers });
  res.end();
}

const mime = { '.html': 'text/html; charset=utf-8', '.css': 'text/css; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.svg': 'image/svg+xml', '.png': 'image/png' };
async function serveStatic(urlPath, res) {
  const requested = urlPath === '/' ? 'index.html' : urlPath.slice(1);
  const filePath = normalize(join(STATIC_ROOT, requested));
  if (!filePath.startsWith(STATIC_ROOT)) return false;
  try {
    const content = await readFile(filePath);
    res.writeHead(200, { 'Content-Type': mime[extname(filePath)] || 'application/octet-stream', 'Cache-Control': extname(filePath) === '.html' ? 'no-cache' : 'public, max-age=86400' });
    res.end(content);
    return true;
  } catch { return false; }
}

const server = createServer(async (req, res) => {
  const url = new URL(req.url, `http://${req.headers.host}`);
  try {
    if (req.method === 'GET' && url.pathname === '/api/dashboard') return sendJson(res, 200, await dashboard(url.searchParams.get('range') || '1y', currentUser(req)));
    if (req.method === 'GET' && url.pathname === '/api/market-environment') return sendJson(res, 200, await marketEnvironment());
    if (req.method === 'GET' && url.pathname === '/api/market-style') return sendJson(res, 200, await marketStyle());
    if (req.method === 'GET' && url.pathname === '/api/industry-price') return sendJson(res, 200, await industryPrice());
    if (req.method === 'GET' && url.pathname === '/api/market-volume') return sendJson(res, 200, await marketVolume());
    if (req.method === 'GET' && url.pathname === '/api/market-volatility') return sendJson(res, 200, await marketVolatility());
    if (req.method === 'GET' && url.pathname === '/api/market-turnover') return sendJson(res, 200, await marketTurnover());
    if (req.method === 'GET' && url.pathname === '/api/market-breadth') return sendJson(res, 200, await marketBreadth());
    if (req.method === 'GET' && url.pathname === '/api/factor-exposure') return sendJson(res, 200, await factorExposure());
    if (req.method === 'GET' && url.pathname === '/api/me') return sendJson(res, 200, { user: currentUser(req) });
    if (req.method === 'GET' && url.pathname === '/api/auth/wechat') {
      const state = createWechatState();
      if (WECHAT_AUTH_MODE === 'development') return redirect(res, `/api/auth/wechat/callback?code=development&state=${encodeURIComponent(state)}`);
      if (!WECHAT_APP_ID || !WECHAT_APP_SECRET || !WECHAT_REDIRECT_URI) return redirect(res, '/?auth=not-configured');
      return redirect(res, buildWechatAuthorizeUrl(state));
    }
    if (req.method === 'GET' && url.pathname === '/api/auth/wechat/callback') {
      if (!consumeWechatState(url.searchParams.get('state'))) return redirect(res, '/?auth=invalid-state');
      if (url.searchParams.get('error') || !url.searchParams.get('code')) return redirect(res, '/?auth=cancelled');
      const profile = WECHAT_AUTH_MODE === 'development'
        ? { openid: 'development-user', nickname: '微信测试用户', headimgurl: '' }
        : await exchangeWechatCode(url.searchParams.get('code'));
      const user = findOrCreateWechatUser(profile);
      return redirect(res, '/?auth=success', { 'Set-Cookie': sessionCookie(createSession(user.id)) });
    }
    if (req.method === 'POST' && url.pathname === '/api/logout') {
      const token = parseCookies(req.headers.cookie).session;
      if (token) db.prepare('DELETE FROM sessions WHERE token_hash = ?').run(createHash('sha256').update(token).digest('hex'));
      return sendJson(res, 200, { ok: true }, { 'Set-Cookie': 'session=; HttpOnly; SameSite=Lax; Path=/; Max-Age=0' });
    }
    if (req.method === 'GET' && await serveStatic(url.pathname, res)) return;
    if (req.method === 'GET') return serveStatic('/', res);
    sendJson(res, 404, { error: '未找到资源' });
  } catch (error) {
    console.error(error);
    sendJson(res, error.statusCode || 500, { error: error.statusCode === 503 ? error.message : '服务暂时不可用' });
  }
});

if (process.env.NODE_ENV !== 'test') server.listen(PORT, '0.0.0.0', () => console.log(`A股恐慌贪婪指数: http://localhost:${PORT}`));
export { dashboard, marketEnvironment, marketStyle, industryPrice, marketVolume, marketVolatility, marketTurnover, marketBreadth, factorExposure, zone, buildWechatAuthorizeUrl, server };
