// 模拟 Shadowrocket 脚本环境，验证生成的 body-rewrite.js
const fs = require('fs');
const vm = require('vm');
const code = fs.readFileSync(__dirname + '/../scripts/body-rewrite.js', 'utf8');

function run(url, body) {
  let out = null;
  const ctx = {
    $request: { url }, $response: { body }, $done: (o) => { out = o; },
    console, JSON, RegExp, Object, Array, String, Number, Math, Error, Date
  };
  vm.createContext(ctx);
  vm.runInContext(code, ctx, { timeout: 5000 });
  return out;
}

const cases = [
  ['B站 pgc 去 payment', 'https://api.bilibili.com/pgc/view/v2/app/season?x=1',
    JSON.stringify({ data: { payment: { a: 1 }, keep: 2 } }), { data: { keep: 2 } }],
  ['B站 tracker 改 stun 地址', 'https://api.bilibili.com/x/pd-proxy/tracker?a=1',
    JSON.stringify({ data: [[{ x: 'stun.chat.bilibili.com:3478' }]] }), null],
  ['B站 首页 tab 替换', 'https://app.bilibili.com/x/resource/show/tab/v2?x=1',
    JSON.stringify({ data: { tab: [{ pos: 0, id: 1 }] } }), 'has-3-tabs'],
  ['B站 splash with_entries', 'https://app.bilibili.com/x/v2/splash/list?x=1',
    JSON.stringify({ data: { show: [1], other: [2] } }), { data: { show: [], other: [2] } }],
  ['字符串替换 false->true', 'https://adservice.sigmob.cn/extconfig?x=1',
    '{"enable": false}', { raw: '{"enable": true}' }],
  ['字符串替换（字面量不匹配则原样）', 'https://mobile.yangkeduo.com/proxy/api/api/express/post/waybill/red_packet/goods_list',
    '{"list":[1,2,3]}', { raw: '{"list":[1,2,3]}' }],
  // ---- 审计补充：同一 URL 命中多条规则必须全部生效 ----
  ['重复pattern×14 快递100 全字段', 'https://p.kuaidi100.com/mobile/mobileapi.do',
    JSON.stringify({adsplash:1,adbanner:2,adposition:3,adShowAgainTime:4,index_banner:5,keep:9}),
    {raw: JSON.stringify({keep:9})}],
  ['重复pattern×4 快手 多字段+过滤', 'https://apissl.ksapisrv.com/rest/system/startup?a=1',
    JSON.stringify({reskinConfig:{a:1},sidebarExSquareStyle:{moreList:[1],topList:[2],commonlyUsedList:[{title:"设置"},{title:"广告位"},{title:"历史记录"}]},keep:1}),
    'gifshow'],
  ['重复pattern×2 喜马拉雅 播放页', 'https://mobwsa.ximalaya.com/mobile-playpage/playpage/tabs/v2/x',
    JSON.stringify({data:{playpage:{resourceMap:{defaultResource:1,playPageTip:2,keep:3}}}}),
    {raw: JSON.stringify({data:{playpage:{resourceMap:{keep:3}}}})}],
  ['内联标志 (?i) 规则必须生效', 'https://lzmh.lz-qs.com:6025/lzmh_app_api/api/v2/user/getUserBaseInfoAndConfig?x=1',
    JSON.stringify({value:{config:{a:1},x:2}}),
    {raw: JSON.stringify({value:{x:2}})}],
  ['协议笔误修正：https 也能命中（上游只写 http）', 'https://dili.sqcosmos.com/jiekou/mains/p1.html',
    JSON.stringify({album:[{id:"4154"},{id:"4155"},{id:"4165"}]}),
    {raw: JSON.stringify({album:[{id:"4155"}]})}],
  ['未匹配 URL 应原样返回', 'https://example.com/nothing',
    '{"a":1}', 'noop']
];

let pass = 0, fail = 0;
for (const [name, url, body, expect] of cases) {
  const out = run(url, body);
  let ok, got = out && out.body !== undefined ? out.body : JSON.stringify(out);
  if (expect === 'noop') ok = out && out.body === undefined;
  else if (expect === 'gifshow') {
    const o = JSON.parse(got);
    ok = !('reskinConfig' in o) && o.sidebarExSquareStyle &&
         !('moreList' in o.sidebarExSquareStyle) && !('topList' in o.sidebarExSquareStyle) &&
         o.sidebarExSquareStyle.commonlyUsedList.length === 2 && o.keep === 1;
  }
  else if (expect === 'has-3-tabs') ok = got && JSON.parse(got).data.tab[0].id === 731;
  else if (expect && expect.raw) ok = got === expect.raw;
  else if (expect) ok = JSON.stringify(JSON.parse(got)) === JSON.stringify(expect);
  else ok = got && got !== body;   // 只要求“发生了改写且未崩溃”
  console.log((ok ? 'PASS ' : 'FAIL ') + name + '  -> ' + String(got).slice(0, 90));
  ok ? pass++ : fail++;
}
console.log(`\n${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
