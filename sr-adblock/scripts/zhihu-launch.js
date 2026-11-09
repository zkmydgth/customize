// [sr-adblock] 知乎开屏广告去广告（2026-11-09）
//
// 背景：知乎把开屏配置放在 body.launch 里，launch 本身是一个 JSON 字符串：
//   { "launch": "{\"ads\":[{...}], ...}" }
// 用 Map Local 返回 {} 时，App 判定「响应不完整」→ 继续用本地缓存的开屏配置，
// 广告照弹（2026-11-09 日志实证：commercial_api 全部命中 Map Local，
// 冷启动时零素材下载，但开屏广告仍然显示）。
//
// 方案：保持响应结构合法，只把 launch.ads 清空（app2smile/rules 的做法）。
// 独立成文件而不是塞进上游 zhihu.js，是为了避开 SR 的脚本 URL 缓存
// （同名 URL 可能仍用旧版脚本）。
//
// 命中范围：commercial_api/real_time_launch_v2、commercial_api/launch_v2
// 对应 [Map Local] 已用负向断言把这两个接口排除，二者不冲突。

const url = $request.url || "";
let obj = {};

try {
  obj = JSON.parse($response.body);
} catch (e) {
  obj = {};
}

try {
  const launch = JSON.parse(obj.launch);
  launch.ads = [];
  obj.launch = JSON.stringify(launch);
} catch (e) {
  // launch 缺失或不是合法 JSON 字符串：给出结构合法的空广告配置
  obj = { launch: JSON.stringify({ ads: [] }) };
}

console.log(`[sr-adblock] zhihu launch 去广告: ${url}`);

$done({ body: JSON.stringify(obj) });
