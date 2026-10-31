import http from 'k6/http';
import { check, sleep } from 'k6';
import { Counter } from 'k6/metrics';
const BASE = __ENV.BASE_URL || 'http://frontend';
const type = __ENV.TYPE || 'carga';
const stages = {
  carga: [{duration:'20s',target:5},{duration:'60s',target:5},{duration:'20s',target:0}],
  estres: [{duration:'20s',target:10},{duration:'30s',target:30},{duration:'30s',target:60},{duration:'20s',target:0}],
  pico: [{duration:'20s',target:2},{duration:'5s',target:40},{duration:'20s',target:40},{duration:'5s',target:2},{duration:'20s',target:2}],
  resistencia: [{duration:'20s',target:5},{duration:'5m',target:5},{duration:'20s',target:0}]
};
if (!stages[type]) throw new Error('TYPE debe ser carga, estres, pico o resistencia');
const semanticErrors = new Counter('semantic_errors');
export const options = {
  stages: stages[type],
  thresholds: {http_req_failed:['rate<0.01'], http_req_duration:['p(95)<500'], checks:['rate>0.99'],semantic_errors:['count==0']}
};
export default function() {
  const r=http.get(`${BASE}/api/boards/board-1`,{tags:{name:'leer_tablero'}});
  let data; try {data=r.json();} catch {data=null;}
  const valid=!!data && data.id==='board-1' && Number.isInteger(data.version) && data.version>=1;
  check(r, {'HTTP 200':x=>x.status===200,'estructura y version validas':()=>valid});
  semanticErrors.add(valid ? 0 : 1);
  sleep(0.2);
}
export function handleSummary(data) {
  return {
    [`/results/k6-${type}-summary.json`]:JSON.stringify(data,null,2),
    stdout:JSON.stringify({prueba:type,P95_ms:data.metrics.http_req_duration.values['p(95)'],fallos:data.metrics.http_req_failed.values.rate,nota:'Umbrales didácticos; justificar resultados según recursos.'},null,2)+'\n'
  };
}
