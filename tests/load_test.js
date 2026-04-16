import http from 'k6/http';
import { check } from 'k6';
import { Trend, Rate } from 'k6/metrics';

let reqDur = new Trend('req_duration');
// failure = anything other than HTTP 200 (429/400/401/5xx all count as failed)
let failedRate = new Rate('failed_rate');
// success only when status === 200 (explicit for reporting)
let success200 = new Rate('success_200');

function randomHex(len) {
  const chars = '0123456789abcdef';
  let s = '';
  for (let i = 0; i < len; i++) {
    s += chars[Math.floor(Math.random() * 16)];
  }
  return s;
}

export let options = {
  vus: 100,
  duration: '30s',
  summaryTrendStats: ['avg', 'med', 'p(90)', 'p(95)', 'p(99)', 'min', 'max'],
};

const BASE = 'http://127.0.0.1:8000';
const TEST_API_KEY = __ENV.TEST_API_KEY;
if (!TEST_API_KEY) {
  throw new Error('Set TEST_API_KEY for k6 (must match INITIAL_API_KEY / api_keys in DB)');
}
const AUTH_HEADER = { headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${TEST_API_KEY}` } };
const USER_ID = __ENV.USER_ID ? parseInt(__ENV.USER_ID, 10) : 0;
const USER_PHONE = __ENV.USER_PHONE || 'loadtest-user';

export default function () {
  const ref = `lt-${__VU}-${__ITER}-${Date.now()}-${randomHex(16)}`;
  const payload = JSON.stringify({ order_reference: ref, category: 'test', user_id: USER_ID, user_phone: USER_PHONE });
  const res = http.post(`${BASE}/cards/buy`, payload, AUTH_HEADER);

  reqDur.add(res.timings.duration);
  const ok = res.status === 200;
  failedRate.add(!ok);
  success200.add(ok);

  check(res, {
    'status is 200': (r) => r.status === 200,
  });
}
