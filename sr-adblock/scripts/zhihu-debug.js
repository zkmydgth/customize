// 知乎信息流诊断（临时）：把 data 清空
// 判据：刷新后信息流「空白」= 脚本已执行；「仍有内容」= 脚本没执行
const url = $request.url;
let info = "";
try {
  const b = JSON.parse($response.body);
  const d = (b && b.data) || [];
  const types = {};
  d.forEach(function (i) { const t = (i && i.type) || "?"; types[t] = (types[t] || 0) + 1; });
  info = "共 " + d.length + " 条 | feed_advert=" +
         d.filter(function (i) { return i && i.type === "feed_advert"; }).length +
         " | " + Object.keys(types).slice(0, 4).join(",");
  b.data = [];
  try { $notification.post("知乎诊断", "脚本已执行，信息流已清空", info.slice(0, 200)); } catch (e) {}
  $done({ body: JSON.stringify(b) });
} catch (e) {
  try { $notification.post("知乎诊断", "解析失败", e.message); } catch (e2) {}
  $done({});
}
