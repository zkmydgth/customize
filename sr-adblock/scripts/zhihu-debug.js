// 知乎信息流诊断（临时）：只读不写，把卡片类型分布弹通知
// 验证点：1) 脚本是否被执行 2) 广告卡片的真实 type 3) 上游脚本是否已删除广告
const url = $request.url;
let msg = "";
try {
  const body = JSON.parse($response.body);
  const data = (body && body.data) || [];
  const types = {};
  data.forEach(function (i) {
    const t = (i && i.type) || "(no-type)";
    types[t] = (types[t] || 0) + 1;
  });
  const ad = data.filter(function (i) { return i && i.type === "feed_advert"; }).length;
  const keys = Object.keys(types).sort(function (a, b) { return types[b] - types[a]; });
  msg = "共 " + data.length + " 条 | feed_advert=" + ad + "\n" +
        keys.slice(0, 5).map(function (k) { return k + "×" + types[k]; }).join(" ");
  // 抽查第一条，看有哪些字段能用于判定
  if (data[0]) {
    msg += "\n#1 字段: " + Object.keys(data[0]).slice(0, 8).join(",");
  }
} catch (e) {
  msg = "解析失败: " + e.message;
}
try {
  $notification.post("知乎信息流诊断", String(url).slice(8, 60), msg.slice(0, 300));
} catch (e) {}
$done({});
