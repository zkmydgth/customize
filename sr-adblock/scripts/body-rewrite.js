// 自动生成：由上游 [Body Rewrite] 转换，请勿手改 (tools/gen_scripts.py)

var JQRT = (function () {
  function isObj(v) { return v !== null && typeof v === 'object' && !Array.isArray(v); }
  function truthy(v) { return v !== false && v !== null && v !== undefined; }
  function eq(a, b) { return JSON.stringify(a) === JSON.stringify(b); }
  function clone(o) { return o === undefined ? null : JSON.parse(JSON.stringify(o)); }
  function gp(v, p) {
    for (var i = 0; i < p.length; i++) {
      if (v === null || v === undefined) return null;
      v = v[p[i]];
    }
    return v === undefined ? null : v;
  }
  function sp(v, p, x) {
    if (!p.length) return x;
    var k = p[0], base = (v === null || v === undefined) ? (typeof k === 'number' ? [] : {}) : clone(v);
    if (typeof base !== 'object') base = typeof k === 'number' ? [] : {};
    base[k] = sp(base[k] === undefined ? null : base[k], p.slice(1), x);
    return base;
  }
  function dp(v, p) {
    if (!p.length) return null;
    var base = clone(v);
    if (base === null || typeof base !== 'object') return base;
    if (p.length === 1) {
      if (Array.isArray(base)) base.splice(p[0], 1); else delete base[p[0]];
      return base;
    }
    var k = p[0];
    if (base[k] === undefined) return base;
    base[k] = dp(base[k], p.slice(1));
    return base;
  }
  function cmpv(a, b) {
    function rank(x) {
      if (x === null) return 0; if (x === false) return 1; if (x === true) return 2;
      if (typeof x === 'number') return 3; if (typeof x === 'string') return 4;
      if (Array.isArray(x)) return 5; return 6;
    }
    if (rank(a) !== rank(b)) return rank(a) - rank(b);
    if (typeof a === 'number' || typeof a === 'string') return a < b ? -1 : (a > b ? 1 : 0);
    var sa = JSON.stringify(a), sb = JSON.stringify(b);
    return sa < sb ? -1 : (sa > sb ? 1 : 0);
  }

  function make(AST) {
    function pths(n, v, last) {
      switch (n.t) {
        case 'id': return [[]];
        case 'field':
          // 最后一级允许父级为任意类型（= 赋值会覆盖），中间一级必须是对象
          if (v !== null && v !== undefined && !isObj(v)) throw new Error('badpath');
          return [[n.n]];
        case 'index': {
          var ix0 = ev(n.e, v)[0];
          if (v !== null && v !== undefined) {
            if (Array.isArray(v) && typeof ix0 !== 'number') throw new Error('badpath');
            else if (isObj(v) && typeof ix0 === 'number') throw new Error('badpath');
            else if (!Array.isArray(v) && !isObj(v)) throw new Error('badpath');
          }
          return [[ix0]];
        }
        case 'iter': {
          var r = [];
          if (Array.isArray(v)) { for (var i = 0; i < v.length; i++) r.push([i]); }
          else if (isObj(v)) { for (var k in v) r.push([k]); }
          else throw new Error('iter');
          return r;
        }
        case 'opt': try { return pths(n.e, v, last); } catch (e) { return []; }
        case 'pipe': {
          var out = [], lp = pths(n.l, v, false);
          for (var i2 = 0; i2 < lp.length; i2++) {
            var sv = gp(v, lp[i2]), rp = pths(n.r, sv, last);
            for (var j = 0; j < rp.length; j++) out.push(lp[i2].concat(rp[j]));
          }
          return out;
        }
        case 'comma': return pths(n.l, v, last).concat(pths(n.r, v, last));
        default: throw new Error('badpath');
      }
    }

    function bin(n, v) {
      var op = n.op;
      if (op === 'and') return [truthy(ev(n.l, v)[0]) && truthy(ev(n.r, v)[0])];
      if (op === 'or') return [truthy(ev(n.l, v)[0]) || truthy(ev(n.r, v)[0])];
      var a = ev(n.l, v)[0], b = ev(n.r, v)[0];
      switch (op) {
        case '==': return [eq(a, b)];
        case '!=': return [!eq(a, b)];
        case '<': return [cmpv(a, b) < 0];
        case '>': return [cmpv(a, b) > 0];
        case '<=': return [cmpv(a, b) <= 0];
        case '>=': return [cmpv(a, b) >= 0];
        case '+':
          if (a === null) return [b];
          if (b === null) return [a];
          if (typeof a === 'number' && typeof b === 'number') return [a + b];
          if (typeof a === 'string' && typeof b === 'string') return [a + b];
          if (Array.isArray(a) && Array.isArray(b)) return [a.concat(b)];
          if (isObj(a) && isObj(b)) { var c = clone(a); for (var k in b) c[k] = b[k]; return [c]; }
          throw new Error('add');
        case '-': return [a - b];
        case '*': return [a * b];
        case '/': return [a / b];
        case '%': return [a % b];
      }
      throw new Error('op ' + op);
    }

    function call(n, v) {
      var f = n.f, A = n.args;
      var av = function (i) { return ev(A[i], v)[0]; };
      switch (f) {
        case 'length':
          if (v === null) return [0];
          if (typeof v === 'string' || Array.isArray(v)) return [v.length];
          if (isObj(v)) return [Object.keys(v).length];
          return [Math.abs(v)];
        case 'keys': return [Array.isArray(v) ? v.map(function (_, i) { return i; }) : Object.keys(v)];
        case 'empty': return [];
        case 'not': return [!truthy(v)];
        case 'type': return [v === null ? 'null' : Array.isArray(v) ? 'array' : typeof v === 'object' ? 'object' : typeof v];
        case 'tostring': return [typeof v === 'string' ? v : JSON.stringify(v)];
        case 'tonumber': return [typeof v === 'number' ? v : parseFloat(v)];
        case 'tojson': return [JSON.stringify(v)];
        case 'fromjson': return [JSON.parse(v)];
        case 'add': return [Array.isArray(v) ? v.reduce(function (a, b) { return a === null ? b : (typeof a === 'number' ? a + b : Array.isArray(a) ? a.concat(b) : a + b); }, null) : v];
        case 'sort': return [clone(v).sort(cmpv)];
        case 'unique': { var s = clone(v).sort(cmpv), u = []; s.forEach(function (x) { if (!u.length || !eq(u[u.length - 1], x)) u.push(x); }); return [u]; }
        case 'reverse': return [clone(v).reverse()];
        case 'first': return Array.isArray(v) ? (v.length ? [v[0]] : []) : [v];
        case 'last': return Array.isArray(v) ? (v.length ? [v[v.length - 1]] : []) : [v];
        case 'min': return [clone(v).sort(cmpv)[0]];
        case 'max': { var t = clone(v).sort(cmpv); return [t[t.length - 1]]; }
        case 'map': {
          var o = [];
          if (Array.isArray(v)) { v.forEach(function (x) { o = o.concat(ev(A[0], x)); }); }
          else if (isObj(v)) { Object.keys(v).forEach(function (k) { o = o.concat(ev(A[0], v[k])); }); }
          else throw new Error('map');
          return [o];
        }
        case 'select': return ev(A[0], v).some(truthy) ? [v] : [];
        case 'del': {
          var ps = pths(A[0], v, true), out = v;
          ps.sort(function (a, b) { return b.length - a.length; });
          ps.forEach(function (p) { out = dp(out, p); });
          return [out];
        }
        case 'delpaths': {
          var pl = av(0) || [], out2 = v;
          pl.slice().sort(function (a, b) { return b.length - a.length; });
          pl.forEach(function (p) { out2 = dp(out2, p); });
          return [out2];
        }
        case 'has': {
          var hk = av(0);
          if (v === null || v === undefined) return [false];
          if (Array.isArray(v)) { if (typeof hk !== 'number') throw new Error('has'); return [Object.prototype.hasOwnProperty.call(v, hk)]; }
          if (isObj(v)) { if (typeof hk !== 'string') throw new Error('has'); return [Object.prototype.hasOwnProperty.call(v, hk)]; }
          throw new Error('has');
        }
        case 'getpath': return [gp(v, av(0) || [])];
        case 'setpath': return [sp(v, av(0) || [], av(1))];
        case 'with_entries': {
          var ent;
          if (Array.isArray(v)) ent = [];
          else if (isObj(v)) ent = Object.keys(v).map(function (k) { return { key: k, value: v[k] }; });
          else throw new Error('with_entries');
          var m = [];
          ent.forEach(function (e) { m = m.concat(ev(A[0], e)); });
          var r = {};
          m.forEach(function (e) { if (e && e.key !== undefined) r[e.key] = e.value; });
          return [r];
        }
        case 'IN': { var vals = ev(A[0], v); return [vals.some(function (x) { return eq(x, v); })]; }
        case 'test': return [new RegExp(av(0)).test(String(v))];
        case 'startswith': return [String(v).indexOf(String(av(0))) === 0];
        case 'endswith': return [String(v).indexOf(String(av(0)), String(v).length - String(av(0)).length) !== -1];
        case 'contains': return [Array.isArray(v) ? v.some(function (x) { return eq(x, av(0)); }) : String(v).indexOf(String(av(0))) !== -1];
        case 'split': return [String(v).split(String(av(0)))];
        case 'join': return [(v || []).join(av(0))];
        case 'recurse': {
          var acc = [];
          (function walk(x) { acc.push(clone(x)); if (Array.isArray(x)) x.forEach(walk); else if (isObj(x)) Object.keys(x).forEach(function (k) { walk(x[k]); }); })(v);
          return acc;
        }
        case 'error': throw new Error(String(av(0) || 'error'));
        case 'halt': throw new Error('halt');
      }
      throw new Error('fn ' + f);
    }

    function asg(n, v) {
      var ps = pths(n.l, v, true), out = v;
      if (n.op === '=') {
        var val = ev(n.r, v)[0];
        ps.forEach(function (p) { out = sp(out, p, clone(val)); });
        return [out];
      }
      ps.forEach(function (p) {
        var old = gp(out, p), rv = ev(n.r, old);
        if (!rv.length) { out = dp(out, p); return; }
        var nv = rv[0];
        if (n.op === '|=') out = sp(out, p, nv);
        else if (n.op === '+=') out = sp(out, p, (typeof old === 'number' ? old + nv : old === null ? nv : old + nv));
        else if (n.op === '-=') out = sp(out, p, old - nv);
        else if (n.op === '*=') out = sp(out, p, old * nv);
        else if (n.op === '/=') out = sp(out, p, old / nv);
      });
      return [out];
    }

    function ev(n, v) {
      switch (n.t) {
        case 'id': return [v];
        case 'lit': return [n.v];
        case 'field':
          if (v === null || v === undefined) return [null];
          if (!isObj(v)) throw new Error('field');
          return [v[n.n] === undefined ? null : v[n.n]];
        case 'index': {
          if (v === null || v === undefined) return [null];
          var ix = ev(n.e, v)[0];
          return [v[ix] === undefined ? null : v[ix]];
        }
        case 'iter': {
          if (Array.isArray(v)) return v.slice();
          if (isObj(v)) { var a = []; for (var k in v) a.push(v[k]); return a; }
          throw new Error('iter');
        }
        case 'opt': try { return ev(n.e, v); } catch (e) { return []; }
        case 'pipe': {
          var o = [];
          ev(n.l, v).forEach(function (x) { o = o.concat(ev(n.r, x)); });
          return o;
        }
        case 'comma': return ev(n.l, v).concat(ev(n.r, v));
        case 'alt': { var l = ev(n.l, v).filter(truthy); return l.length ? l : ev(n.r, v); }
        case 'un': { var x = ev(n.e, v)[0]; return n.op === 'not' ? [!truthy(x)] : [-x]; }
        case 'bin': return bin(n, v);
        case 'if': { var c = ev(n.c, v)[0]; return truthy(c) ? ev(n.a, v) : (n.b ? ev(n.b, v) : [v]); }
        case 'arr': return n.e ? [ev(n.e, v)] : [[]];
        case 'obj': {
          var res = [{}];
          n.pairs.forEach(function (pr) {
            var ks = ev(pr[0], v), vs = ev(pr[1], v), nr = [];
            res.forEach(function (o) {
              ks.forEach(function (kk) {
                vs.forEach(function (vv) { var c = clone(o); c[kk] = clone(vv); nr.push(c); });
              });
            });
            res = nr;
          });
          return res;
        }
        case 'assign': return asg(n, v);
        case 'try': try { return ev(n.e, v); } catch (e) { return n.c ? ev(n.c, e) : []; }
        case 'call': return call(n, v);
      }
      throw new Error('node ' + n.t);
    }

    return function (input) { return ev(AST, input); };
  }
  return { make: make };
})();
if (typeof module !== 'undefined') module.exports = JQRT;

var __RULES__ = [{"n":"body-rewrite-000","p":"^https:\\/\\/api\\.bilibili\\.com\\/x\\/pd-proxy\\/tracker\\?","j":{"t":"assign","op":"=","l":{"t":"pipe","l":{"t":"pipe","l":{"t":"field","n":"data"},"r":{"t":"iter"}},"r":{"t":"opt","e":{"t":"iter"}}},"r":{"t":"lit","v":"stun.chat.bilibili.com:3478"}},"r":null},{"n":"body-rewrite-001","p":"^https:\\/\\/api\\.bilibili\\.com\\/pgc\\/view\\/v2\\/app\\/season\\?","j":{"t":"call","f":"del","args":[{"t":"pipe","l":{"t":"field","n":"data"},"r":{"t":"field","n":"payment"}}]},"r":null},{"n":"body-rewrite-002","p":"^https:\\/\\/api\\.bilibili\\.com\\/pgc\\/page\\/channel\\?","j":{"t":"assign","op":"|=","l":{"t":"pipe","l":{"t":"field","n":"data"},"r":{"t":"field","n":"modules"}},"r":{"t":"call","f":"map","args":[{"t":"pipe","l":{"t":"call","f":"select","args":[{"t":"bin","op":"!=","l":{"t":"field","n":"type"},"r":{"t":"lit","v":"TIP"}}]},"r":{"t":"if","c":{"t":"bin","op":"==","l":{"t":"field","n":"type"},"r":{"t":"lit","v":"BANNER"}},"a":{"t":"assign","op":"|=","l":{"t":"pipe","l":{"t":"field","n":"module_data"},"r":{"t":"field","n":"items"}},"r":{"t":"call","f":"map","args":[{"t":"call","f":"select","args":[{"t":"pipe","l":{"t":"pipe","l":{"t":"field","n":"url"},"r":{"t":"call","f":"startswith","args":[{"t":"lit","v":"https://www.bilibili.com/blackboard/era/"}]}},"r":{"t":"call","f":"not","args":[]}}]}]}},"b":{"t":"id"}}}]}},"r":null},{"n":"body-rewrite-003","p":"^https:\\/\\/app\\.bilibili\\.com\\/x\\/resource\\/show\\/skin\\?","j":{"t":"call","f":"delpaths","args":[{"t":"arr","e":{"t":"arr","e":{"t":"comma","l":{"t":"lit","v":"data"},"r":{"t":"lit","v":"common_equip"}}}}]},"r":null},{"n":"body-rewrite-004","p":"^https:\\/\\/app\\.bilibili\\.com\\/x\\/resource\\/show\\/tab\\/v2\\?","j":{"t":"pipe","l":{"t":"pipe","l":{"t":"assign","op":"=","l":{"t":"pipe","l":{"t":"field","n":"data"},"r":{"t":"field","n":"tab"}},"r":{"t":"arr","e":{"t":"comma","l":{"t":"comma","l":{"t":"comma","l":{"t":"comma","l":{"t":"obj","pairs":[[{"t":"lit","v":"pos"},{"t":"lit","v":1}],[{"t":"lit","v":"id"},{"t":"lit","v":731}],[{"t":"lit","v":"name"},{"t":"lit","v":"直播"}],[{"t":"lit","v":"tab_id"},{"t":"lit","v":"直播tab"}],[{"t":"lit","v":"uri"},{"t":"lit","v":"bilibili://live/home"}]]},"r":{"t":"obj","pairs":[[{"t":"lit","v":"pos"},{"t":"lit","v":2}],[{"t":"lit","v":"id"},{"t":"lit","v":477}],[{"t":"lit","v":"name"},{"t":"lit","v":"推荐"}],[{"t":"lit","v":"tab_id"},{"t":"lit","v":"推荐tab"}],[{"t":"lit","v":"uri"},{"t":"lit","v":"bilibili://pegasus/promo"}],[{"t":"lit","v":"default_selected"},{"t":"lit","v":1}]]}},"r":{"t":"obj","pairs":[[{"t":"lit","v":"pos"},{"t":"lit","v":3}],[{"t":"lit","v":"id"},{"t":"lit","v":478}],[{"t":"lit","v":"name"},{"t":"lit","v":"热门"}],[{"t":"lit","v":"tab_id"},{"t":"lit","v":"热门tab"}],[{"t":"lit","v":"uri"},{"t":"lit","v":"bilibili://pegasus/hottopic"}]]}},"r":{"t":"obj","pairs":[[{"t":"lit","v":"pos"},{"t":"lit","v":4}],[{"t":"lit","v":"id"},{"t":"lit","v":3502}],[{"t":"lit","v":"name"},{"t":"lit","v":"动画"}],[{"t":"lit","v":"tab_id"},{"t":"lit","v":"bangumi"}],[{"t":"lit","v":"uri"},{"t":"lit","v":"bilibili://pgc/bangumi_v2"}]]}},"r":{"t":"obj","pairs":[[{"t":"lit","v":"pos"},{"t":"lit","v":5}],[{"t":"lit","v":"id"},{"t":"lit","v":3503}],[{"t":"lit","v":"name"},{"t":"lit","v":"影视"}],[{"t":"lit","v":"tab_id"},{"t":"lit","v":"film"}],[{"t":"lit","v":"uri"},{"t":"lit","v":"bilibili://pgc/cinema_v2"}]]}}}},"r":{"t":"assign","op":"=","l":{"t":"pipe","l":{"t":"field","n":"data"},"r":{"t":"field","n":"top"}},"r":{"t":"arr","e":{"t":"obj","pairs":[[{"t":"lit","v":"pos"},{"t":"lit","v":1}],[{"t":"lit","v":"id"},{"t":"lit","v":176}],[{"t":"lit","v":"name"},{"t":"lit","v":"消息"}],[{"t":"lit","v":"tab_id"},{"t":"lit","v":"消息Top"}],[{"t":"lit","v":"uri"},{"t":"lit","v":"bilibili://link/im_home"}],[{"t":"lit","v":"icon"},{"t":"lit","v":"http://i0.hdslb.com/bfs/archive/d43047538e72c9ed8fd8e4e34415fbe3a4f632cb.png"}]]}}}},"r":{"t":"assign","op":"=","l":{"t":"pipe","l":{"t":"field","n":"data"},"r":{"t":"field","n":"bottom"}},"r":{"t":"arr","e":{"t":"comma","l":{"t":"comma","l":{"t":"obj","pairs":[[{"t":"lit","v":"pos"},{"t":"lit","v":1}],[{"t":"lit","v":"id"},{"t":"lit","v":177}],[{"t":"lit","v":"name"},{"t":"lit","v":"首页"}],[{"t":"lit","v":"tab_id"},{"t":"lit","v":"home"}],[{"t":"lit","v":"uri"},{"t":"lit","v":"bilibili://main/home/"}],[{"t":"lit","v":"icon"},{"t":"lit","v":"http://i0.hdslb.com/bfs/archive/63d7ee88d471786c1af45af86e8cb7f607edf91b.png"}],[{"t":"lit","v":"icon_selected"},{"t":"lit","v":"http://i0.hdslb.com/bfs/archive/e5106aa688dc729e7f0eafcbb80317feb54a43bd.png"}]]},"r":{"t":"obj","pairs":[[{"t":"lit","v":"pos"},{"t":"lit","v":2}],[{"t":"lit","v":"id"},{"t":"lit","v":179}],[{"t":"lit","v":"name"},{"t":"lit","v":"动态"}],[{"t":"lit","v":"tab_id"},{"t":"lit","v":"dynamic"}],[{"t":"lit","v":"uri"},{"t":"lit","v":"bilibili://following/home/"}],[{"t":"lit","v":"icon"},{"t":"lit","v":"http://i0.hdslb.com/bfs/archive/86dfbe5fa32f11a8588b9ae0fccb77d3c27cedf6.png"}],[{"t":"lit","v":"icon_selected"},{"t":"lit","v":"http://i0.hdslb.com/bfs/archive/25b658e1f6b6da57eecba328556101dbdcb4b53f.png"}]]}},"r":{"t":"obj","pairs":[[{"t":"lit","v":"pos"},{"t":"lit","v":5}],[{"t":"lit","v":"id"},{"t":"lit","v":181}],[{"t":"lit","v":"name"},{"t":"lit","v":"我的"}],[{"t":"lit","v":"tab_id"},{"t":"lit","v":"我的Bottom"}],[{"t":"lit","v":"uri"},{"t":"lit","v":"bilibili://user_center/"}],[{"t":"lit","v":"icon"},{"t":"lit","v":"http://i0.hdslb.com/bfs/archive/4b0b2c49ffeb4f0c2e6a4cceebeef0aab1c53fe1.png"}],[{"t":"lit","v":"icon_selected"},{"t":"lit","v":"http://i0.hdslb.com/bfs/archive/a54a8009116cb896e64ef14dcf50e5cade401e00.png"}]]}}}}},"r":null},{"n":"body-rewrite-005","p":"^https:\\/\\/app\\.bilibili\\.com\\/x\\/v2\\/splash\\/(list|show|event\\/list2)\\?","j":{"t":"assign","op":"|=","l":{"t":"field","n":"data"},"r":{"t":"call","f":"with_entries","args":[{"t":"if","c":{"t":"pipe","l":{"t":"field","n":"key"},"r":{"t":"call","f":"IN","args":[{"t":"comma","l":{"t":"lit","v":"show"},"r":{"t":"lit","v":"event_list"}}]}},"a":{"t":"assign","op":"=","l":{"t":"field","n":"value"},"r":{"t":"arr","e":null}},"b":{"t":"id"}}]}},"r":null},{"n":"body-rewrite-006","p":"^https:\\/\\/app\\.bilibili\\.com\\/x\\/v2\\/feed\\/index\\?","j":{"t":"if","c":{"t":"pipe","l":{"t":"field","n":"data"},"r":{"t":"field","n":"items"}},"a":{"t":"assign","op":"|=","l":{"t":"pipe","l":{"t":"field","n":"data"},"r":{"t":"field","n":"items"}},"r":{"t":"call","f":"map","args":[{"t":"call","f":"select","args":[{"t":"bin","op":"and","l":{"t":"bin","op":"and","l":{"t":"bin","op":"and","l":{"t":"bin","op":"==","l":{"t":"field","n":"banner_item"},"r":{"t":"lit","v":null}},"r":{"t":"bin","op":"==","l":{"t":"field","n":"ad_info"},"r":{"t":"lit","v":null}}},"r":{"t":"bin","op":"==","l":{"t":"field","n":"card_goto"},"r":{"t":"lit","v":"av"}}},"r":{"t":"pipe","l":{"t":"field","n":"card_type"},"r":{"t":"call","f":"IN","args":[{"t":"comma","l":{"t":"comma","l":{"t":"lit","v":"small_cover_v2"},"r":{"t":"lit","v":"large_cover_single_v9"}},"r":{"t":"lit","v":"large_cover_v1"}}]}}}]}]}},"b":null},"r":null},{"n":"body-rewrite-007","p":"^https:\\/\\/app\\.bilibili\\.com\\/x\\/v2\\/feed\\/index\\/story\\?","j":{"t":"if","c":{"t":"pipe","l":{"t":"field","n":"data"},"r":{"t":"field","n":"items"}},"a":{"t":"assign","op":"|=","l":{"t":"pipe","l":{"t":"field","n":"data"},"r":{"t":"field","n":"items"}},"r":{"t":"call","f":"map","args":[{"t":"pipe","l":{"t":"call","f":"select","args":[{"t":"bin","op":"and","l":{"t":"bin","op":"==","l":{"t":"field","n":"ad_info"},"r":{"t":"lit","v":null}},"r":{"t":"pipe","l":{"t":"pipe","l":{"t":"field","n":"card_goto"},"r":{"t":"call","f":"IN","args":[{"t":"comma","l":{"t":"comma","l":{"t":"lit","v":"vertical_ad_av"},"r":{"t":"lit","v":"vertical_ad_live"}},"r":{"t":"lit","v":"vertical_ad_picture"}}]}},"r":{"t":"call","f":"not","args":[]}}}]},"r":{"t":"call","f":"del","args":[{"t":"comma","l":{"t":"comma","l":{"t":"comma","l":{"t":"comma","l":{"t":"field","n":"story_cart_icon"},"r":{"t":"field","n":"free_flow_toast"}},"r":{"t":"field","n":"image_infos"}},"r":{"t":"field","n":"course_info"}},"r":{"t":"field","n":"game_info"}}]}}]}},"b":null},"r":null},{"n":"body-rewrite-008","p":"^https:\\/\\/app\\.bilibili\\.com\\/x\\/v2\\/account\\/mine(\\/ipad)?\\?","j":{"t":"assign","op":"|=","l":{"t":"field","n":"data"},"r":{"t":"pipe","l":{"t":"pipe","l":{"t":"pipe","l":{"t":"pipe","l":{"t":"pipe","l":{"t":"pipe","l":{"t":"pipe","l":{"t":"call","f":"del","args":[{"t":"comma","l":{"t":"comma","l":{"t":"comma","l":{"t":"comma","l":{"t":"field","n":"answer"},"r":{"t":"field","n":"live_tip"}},"r":{"t":"field","n":"vip_section"}},"r":{"t":"field","n":"vip_section_v2"}},"r":{"t":"field","n":"modular_vip_section"}}]},"r":{"t":"assign","op":"=","l":{"t":"field","n":"vip_type"},"r":{"t":"lit","v":2}}},"r":{"t":"assign","op":"|=","l":{"t":"field","n":"vip"},"r":{"t":"if","c":{"t":"bin","op":"and","l":{"t":"bin","op":"!=","l":{"t":"id"},"r":{"t":"lit","v":null}},"r":{"t":"bin","op":"==","l":{"t":"field","n":"status"},"r":{"t":"lit","v":0}}},"a":{"t":"bin","op":"+","l":{"t":"id"},"r":{"t":"obj","pairs":[[{"t":"lit","v":"status"},{"t":"lit","v":1}],[{"t":"lit","v":"type"},{"t":"lit","v":2}],[{"t":"lit","v":"due_date"},{"t":"lit","v":9005270400000}],[{"t":"lit","v":"role"},{"t":"lit","v":15}]]}},"b":{"t":"id"}}}},"r":{"t":"if","c":{"t":"field","n":"sections_v2"},"a":{"t":"assign","op":"=","l":{"t":"field","n":"sections_v2"},"r":{"t":"arr","e":{"t":"comma","l":{"t":"comma","l":{"t":"obj","pairs":[[{"t":"lit","v":"items"},{"t":"arr","e":{"t":"comma","l":{"t":"comma","l":{"t":"comma","l":{"t":"obj","pairs":[[{"t":"lit","v":"id"},{"t":"lit","v":396}],[{"t":"lit","v":"title"},{"t":"lit","v":"离线缓存"}],[{"t":"lit","v":"uri"},{"t":"lit","v":"bilibili://user_center/download"}],[{"t":"lit","v":"icon"},{"t":"lit","v":"http://i0.hdslb.com/bfs/archive/5fc84565ab73e716d20cd2f65e0e1de9495d56f8.png"}],[{"t":"lit","v":"common_op_item"},{"t":"obj","pairs":[]}]]},"r":{"t":"obj","pairs":[[{"t":"lit","v":"id"},{"t":"lit","v":397}],[{"t":"lit","v":"title"},{"t":"lit","v":"历史记录"}],[{"t":"lit","v":"uri"},{"t":"lit","v":"bilibili://user_center/history"}],[{"t":"lit","v":"icon"},{"t":"lit","v":"http://i0.hdslb.com/bfs/archive/8385323c6acde52e9cd52514ae13c8b9481c1a16.png"}],[{"t":"lit","v":"common_op_item"},{"t":"obj","pairs":[]}]]}},"r":{"t":"obj","pairs":[[{"t":"lit","v":"id"},{"t":"lit","v":3072}],[{"t":"lit","v":"title"},{"t":"lit","v":"我的收藏"}],[{"t":"lit","v":"uri"},{"t":"lit","v":"bilibili://user_center/favourite?version=2"}],[{"t":"lit","v":"icon"},{"t":"lit","v":"http://i0.hdslb.com/bfs/archive/d79b19d983067a1b91614e830a7100c05204a821.png"}],[{"t":"lit","v":"common_op_item"},{"t":"obj","pairs":[]}]]}},"r":{"t":"obj","pairs":[[{"t":"lit","v":"id"},{"t":"lit","v":2830}],[{"t":"lit","v":"title"},{"t":"lit","v":"稍后再看"}],[{"t":"lit","v":"uri"},{"t":"lit","v":"bilibili://user_center/watch_later_v2"}],[{"t":"lit","v":"icon"},{"t":"lit","v":"http://i0.hdslb.com/bfs/archive/63bb768caa02a68cb566a838f6f2415f0d1d02d6.png"}],[{"t":"lit","v":"need_login"},{"t":"lit","v":1}],[{"t":"lit","v":"common_op_item"},{"t":"obj","pairs":[]}]]}}}],[{"t":"lit","v":"style"},{"t":"lit","v":1}],[{"t":"lit","v":"button"},{"t":"obj","pairs":[]}]]},"r":{"t":"obj","pairs":[[{"t":"lit","v":"title"},{"t":"lit","v":"推荐服务"}],[{"t":"lit","v":"items"},{"t":"arr","e":{"t":"comma","l":{"t":"comma","l":{"t":"comma","l":{"t":"obj","pairs":[[{"t":"lit","v":"id"},{"t":"lit","v":402}],[{"t":"lit","v":"title"},{"t":"lit","v":"个性装扮"}],[{"t":"lit","v":"uri"},{"t":"lit","v":"https://www.bilibili.com/h5/mall/home?navhide=1&f_source=shop&from=myservice"}],[{"t":"lit","v":"icon"},{"t":"lit","v":"http://i0.hdslb.com/bfs/archive/0bcad10661b50f583969b5a188c12e5f0731628c.png"}],[{"t":"lit","v":"common_op_item"},{"t":"obj","pairs":[]}]]},"r":{"t":"obj","pairs":[[{"t":"lit","v":"id"},{"t":"lit","v":622}],[{"t":"lit","v":"title"},{"t":"lit","v":"会员购"}],[{"t":"lit","v":"uri"},{"t":"lit","v":"bilibili://mall/home"}],[{"t":"lit","v":"icon"},{"t":"lit","v":"http://i0.hdslb.com/bfs/archive/19c794f01def1a267b894be84427d6a8f67081a9.png"}],[{"t":"lit","v":"common_op_item"},{"t":"obj","pairs":[]}]]}},"r":{"t":"obj","pairs":[[{"t":"lit","v":"id"},{"t":"lit","v":404}],[{"t":"lit","v":"title"},{"t":"lit","v":"我的钱包"}],[{"t":"lit","v":"uri"},{"t":"lit","v":"bilibili://bilipay/mine_wallet"}],[{"t":"lit","v":"icon"},{"t":"lit","v":"http://i0.hdslb.com/bfs/archive/f416634e361824e74a855332b6ff14e2e7c2e082.png"}],[{"t":"lit","v":"common_op_item"},{"t":"obj","pairs":[]}]]}},"r":{"t":"obj","pairs":[[{"t":"lit","v":"id"},{"t":"lit","v":406}],[{"t":"lit","v":"title"},{"t":"lit","v":"我的直播"}],[{"t":"lit","v":"uri"},{"t":"lit","v":"bilibili://user_center/live_center"}],[{"t":"lit","v":"icon"},{"t":"lit","v":"http://i0.hdslb.com/bfs/archive/1db5791746a0112890b77a0236baf263d71ecb27.png"}],[{"t":"lit","v":"common_op_item"},{"t":"obj","pairs":[]}]]}}}],[{"t":"lit","v":"style"},{"t":"lit","v":1}],[{"t":"lit","v":"button"},{"t":"obj","pairs":[]}]]}},"r":{"t":"obj","pairs":[[{"t":"lit","v":"title"},{"t":"lit","v":"更多服务"}],[{"t":"lit","v":"items"},{"t":"arr","e":{"t":"comma","l":{"t":"obj","pairs":[[{"t":"lit","v":"id"},{"t":"lit","v":407}],[{"t":"lit","v":"title"},{"t":"lit","v":"联系客服"}],[{"t":"lit","v":"uri"},{"t":"lit","v":"bilibili://user_center/feedback"}],[{"t":"lit","v":"icon"},{"t":"lit","v":"http://i0.hdslb.com/bfs/archive/7ca840cf1d887a45ee1ef441ab57845bf26ef5fa.png"}],[{"t":"lit","v":"common_op_item"},{"t":"obj","pairs":[]}]]},"r":{"t":"obj","pairs":[[{"t":"lit","v":"id"},{"t":"lit","v":410}],[{"t":"lit","v":"title"},{"t":"lit","v":"设置"}],[{"t":"lit","v":"uri"},{"t":"lit","v":"bilibili://user_center/setting"}],[{"t":"lit","v":"icon"},{"t":"lit","v":"http://i0.hdslb.com/bfs/archive/e932404f2ee62e075a772920019e9fbdb4b5656a.png"}],[{"t":"lit","v":"common_op_item"},{"t":"obj","pairs":[]}]]}}}],[{"t":"lit","v":"style"},{"t":"lit","v":2}],[{"t":"lit","v":"button"},{"t":"obj","pairs":[]}]]}}}},"b":null}},"r":{"t":"if","c":{"t":"field","n":"ipad_sections"},"a":{"t":"assign","op":"=","l":{"t":"field","n":"ipad_sections"},"r":{"t":"arr","e":{"t":"comma","l":{"t":"comma","l":{"t":"comma","l":{"t":"obj","pairs":[[{"t":"lit","v":"id"},{"t":"lit","v":747}],[{"t":"lit","v":"title"},{"t":"lit","v":"离线缓存"}],[{"t":"lit","v":"uri"},{"t":"lit","v":"bilibili://user_center/download"}],[{"t":"lit","v":"icon"},{"t":"lit","v":"http://i0.hdslb.com/bfs/feed-admin/9bd72251f7366c491cfe78818d453455473a9678.png"}],[{"t":"lit","v":"mng_resource"},{"t":"obj","pairs":[[{"t":"lit","v":"icon_id"},{"t":"lit","v":0}],[{"t":"lit","v":"icon"},{"t":"lit","v":""}]]}]]},"r":{"t":"obj","pairs":[[{"t":"lit","v":"id"},{"t":"lit","v":748}],[{"t":"lit","v":"title"},{"t":"lit","v":"历史记录"}],[{"t":"lit","v":"uri"},{"t":"lit","v":"bilibili://user_center/history"}],[{"t":"lit","v":"icon"},{"t":"lit","v":"http://i0.hdslb.com/bfs/feed-admin/83862e10685f34e16a10cfe1f89dbd7b2884d272.png"}],[{"t":"lit","v":"mng_resource"},{"t":"obj","pairs":[[{"t":"lit","v":"icon_id"},{"t":"lit","v":0}],[{"t":"lit","v":"icon"},{"t":"lit","v":""}]]}]]}},"r":{"t":"obj","pairs":[[{"t":"lit","v":"id"},{"t":"lit","v":749}],[{"t":"lit","v":"title"},{"t":"lit","v":"我的收藏"}],[{"t":"lit","v":"uri"},{"t":"lit","v":"bilibili://user_center/favourite"}],[{"t":"lit","v":"icon"},{"t":"lit","v":"http://i0.hdslb.com/bfs/feed-admin/6ae7eff6af627590fc4ed80c905e9e0a6f0e8188.png"}],[{"t":"lit","v":"mng_resource"},{"t":"obj","pairs":[[{"t":"lit","v":"icon_id"},{"t":"lit","v":0}],[{"t":"lit","v":"icon"},{"t":"lit","v":""}]]}]]}},"r":{"t":"obj","pairs":[[{"t":"lit","v":"id"},{"t":"lit","v":750}],[{"t":"lit","v":"title"},{"t":"lit","v":"稍后再看"}],[{"t":"lit","v":"uri"},{"t":"lit","v":"bilibili://user_center/watch_later"}],[{"t":"lit","v":"icon"},{"t":"lit","v":"http://i0.hdslb.com/bfs/feed-admin/928ba9f559b02129e51993efc8afe95014edec94.png"}],[{"t":"lit","v":"mng_resource"},{"t":"obj","pairs":[[{"t":"lit","v":"icon_id"},{"t":"lit","v":0}],[{"t":"lit","v":"icon"},{"t":"lit","v":""}]]}]]}}}},"b":null}},"r":{"t":"if","c":{"t":"field","n":"ipad_upper_sections"},"a":{"t":"assign","op":"=","l":{"t":"field","n":"ipad_upper_sections"},"r":{"t":"arr","e":{"t":"obj","pairs":[[{"t":"lit","v":"id"},{"t":"lit","v":752}],[{"t":"lit","v":"title"},{"t":"lit","v":"创作首页"}],[{"t":"lit","v":"uri"},{"t":"lit","v":"/uper/homevc"}],[{"t":"lit","v":"icon"},{"t":"lit","v":"http://i0.hdslb.com/bfs/feed-admin/d20dfed3b403c895506b1c92ecd5874abb700c01.png"}],[{"t":"lit","v":"mng_resource"},{"t":"obj","pairs":[[{"t":"lit","v":"icon_id"},{"t":"lit","v":0}],[{"t":"lit","v":"icon"},{"t":"lit","v":""}]]}]]}}},"b":null}},"r":{"t":"if","c":{"t":"field","n":"ipad_recommend_sections"},"a":{"t":"assign","op":"=","l":{"t":"field","n":"ipad_recommend_sections"},"r":{"t":"arr","e":{"t":"comma","l":{"t":"obj","pairs":[[{"t":"lit","v":"id"},{"t":"lit","v":755}],[{"t":"lit","v":"title"},{"t":"lit","v":"我的关注"}],[{"t":"lit","v":"uri"},{"t":"lit","v":"bilibili://user_center/myfollows"}],[{"t":"lit","v":"icon"},{"t":"lit","v":"http://i0.hdslb.com/bfs/feed-admin/fdd7f676030c6996d36763a078442a210fc5a8c0.png"}],[{"t":"lit","v":"mng_resource"},{"t":"obj","pairs":[[{"t":"lit","v":"icon_id"},{"t":"lit","v":0}],[{"t":"lit","v":"icon"},{"t":"lit","v":""}]]}]]},"r":{"t":"obj","pairs":[[{"t":"lit","v":"id"},{"t":"lit","v":756}],[{"t":"lit","v":"title"},{"t":"lit","v":"我的消息"}],[{"t":"lit","v":"uri"},{"t":"lit","v":"bilibili://link/im_home"}],[{"t":"lit","v":"icon"},{"t":"lit","v":"http://i0.hdslb.com/bfs/feed-admin/e1471740130a08a48b02a4ab29ed9d5f2281e3bf.png"}],[{"t":"lit","v":"mng_resource"},{"t":"obj","pairs":[[{"t":"lit","v":"icon_id"},{"t":"lit","v":0}],[{"t":"lit","v":"icon"},{"t":"lit","v":""}]]}]]}}}},"b":null}},"r":{"t":"if","c":{"t":"field","n":"ipad_more_sections"},"a":{"t":"assign","op":"=","l":{"t":"field","n":"ipad_more_sections"},"r":{"t":"arr","e":{"t":"comma","l":{"t":"obj","pairs":[[{"t":"lit","v":"id"},{"t":"lit","v":763}],[{"t":"lit","v":"title"},{"t":"lit","v":"我的客服"}],[{"t":"lit","v":"uri"},{"t":"lit","v":"bilibili://user_center/feedback"}],[{"t":"lit","v":"icon"},{"t":"lit","v":"http://i0.hdslb.com/bfs/feed-admin/7801a6180fb67cf5f8ee05a66a4668e49fb38788.png"}],[{"t":"lit","v":"mng_resource"},{"t":"obj","pairs":[[{"t":"lit","v":"icon_id"},{"t":"lit","v":0}],[{"t":"lit","v":"icon"},{"t":"lit","v":""}]]}]]},"r":{"t":"obj","pairs":[[{"t":"lit","v":"id"},{"t":"lit","v":764}],[{"t":"lit","v":"title"},{"t":"lit","v":"设置"}],[{"t":"lit","v":"uri"},{"t":"lit","v":"bilibili://user_center/setting"}],[{"t":"lit","v":"icon"},{"t":"lit","v":"http://i0.hdslb.com/bfs/feed-admin/34e8faea00b3dd78977266b58d77398b0ac9410b.png"}],[{"t":"lit","v":"mng_resource"},{"t":"obj","pairs":[[{"t":"lit","v":"icon_id"},{"t":"lit","v":0}],[{"t":"lit","v":"icon"},{"t":"lit","v":""}]]}]]}}}},"b":null}}},"r":null},{"n":"body-rewrite-009","p":"^https:\\/\\/app\\.bilibili\\.com\\/x\\/v2\\/account\\/myinfo\\?","j":{"t":"assign","op":"|=","l":{"t":"pipe","l":{"t":"field","n":"data"},"r":{"t":"field","n":"vip"}},"r":{"t":"if","c":{"t":"bin","op":"and","l":{"t":"bin","op":"!=","l":{"t":"id"},"r":{"t":"lit","v":null}},"r":{"t":"bin","op":"==","l":{"t":"field","n":"status"},"r":{"t":"lit","v":0}}},"a":{"t":"bin","op":"+","l":{"t":"id"},"r":{"t":"obj","pairs":[[{"t":"lit","v":"status"},{"t":"lit","v":1}],[{"t":"lit","v":"type"},{"t":"lit","v":2}],[{"t":"lit","v":"due_date"},{"t":"lit","v":9005270400000}],[{"t":"lit","v":"role"},{"t":"lit","v":15}]]}},"b":{"t":"id"}}},"r":null},{"n":"body-rewrite-010","p":"^https?:\\/\\/beta-api\\.crunchyroll\\.com\\/cms","j":null,"r":["offset_ms\":\\d+","offset_ms\":99999999999999"]},{"n":"body-rewrite-011","p":"^https?:\\/\\/adservice\\.sigmob\\.cn\\/extconfig","j":null,"r":["false","true"]},{"n":"body-rewrite-012","p":"^https?:\\/\\/maicai\\.api\\.ddxq\\.mobi\\/homeApi\\/newDetails","j":null,"r":["suspension","fmz200"]},{"n":"body-rewrite-013","p":"^https?:\\/\\/47\\.100\\.65\\.202\\/api\\/mobile\\/index\\.php\\?version=\\d&mobile=yes&module=basicdata&type=forumlist","j":null,"r":["adv","fmz200"]},{"n":"body-rewrite-014","p":"^https?:\\/\\/www\\.i3zh\\.com","j":null,"r":["cm-pop-up-banners","fmz200"]},{"n":"body-rewrite-015","p":"^https?:\\/\\/yunbusiness\\.ccb\\.com\\/basic_service\\/txCtrl\\?","j":null,"r":["\"TAG_AD_INFO\"","\"fmz200\""]},{"n":"body-rewrite-016","p":"^https?:\\/\\/waimai-guide\\.ele\\.me\\/\\w+\\/mtop\\.venus\\.shopresourceservice\\.getshopresource","j":null,"r":["posterList","fmz200"]},{"n":"body-rewrite-017","p":"^https?:\\/\\/api\\.m\\.jd\\.com\\/client\\.action\\?functionId=lite_advertising","j":null,"r":["jdLiteAdvertisingVO","fmz200"]},{"n":"body-rewrite-018","p":"^https?:\\/\\/api\\.m\\.jd\\.com\\/client\\.action\\?functionId=lite_SmartPush","j":null,"r":["pushData","fmz200"]},{"n":"body-rewrite-019","p":"^https:\\/\\/bp-api\\.bestv\\.cn\\/cms\\/api\\/free\\/open\\/advertisingV2","j":{"t":"assign","op":"=","l":{"t":"field","n":"dt"},"r":{"t":"arr","e":null}},"r":null},{"n":"body-rewrite-020","p":"^https:\\/\\/bp-api\\.bestv\\.cn\\/cms\\/api\\/c\\/search\\/hot\\/v(2|4)","j":{"t":"pipe","l":{"t":"pipe","l":{"t":"assign","op":"=","l":{"t":"pipe","l":{"t":"field","n":"dt"},"r":{"t":"field","n":"hot"}},"r":{"t":"arr","e":null}},"r":{"t":"assign","op":"=","l":{"t":"pipe","l":{"t":"field","n":"dt"},"r":{"t":"field","n":"recommand"}},"r":{"t":"arr","e":null}}},"r":{"t":"assign","op":"=","l":{"t":"pipe","l":{"t":"field","n":"dt"},"r":{"t":"field","n":"bannerList"}},"r":{"t":"arr","e":null}}},"r":null},{"n":"body-rewrite-021","p":"^https?:\\/\\/p\\.kuaidi100\\.com\\/mobile\\/mobileapi\\.do$","j":{"t":"call","f":"delpaths","args":[{"t":"arr","e":{"t":"arr","e":{"t":"lit","v":"adsplash"}}}]},"r":null},{"n":"body-rewrite-022","p":"^https?:\\/\\/p\\.kuaidi100\\.com\\/mobile\\/mobileapi\\.do$","j":{"t":"call","f":"delpaths","args":[{"t":"arr","e":{"t":"arr","e":{"t":"lit","v":"adIsConsumable"}}}]},"r":null},{"n":"body-rewrite-023","p":"^https?:\\/\\/p\\.kuaidi100\\.com\\/mobile\\/mobileapi\\.do$","j":{"t":"call","f":"delpaths","args":[{"t":"arr","e":{"t":"arr","e":{"t":"lit","v":"adProductId"}}}]},"r":null},{"n":"body-rewrite-024","p":"^https?:\\/\\/p\\.kuaidi100\\.com\\/mobile\\/mobileapi\\.do$","j":{"t":"call","f":"delpaths","args":[{"t":"arr","e":{"t":"arr","e":{"t":"lit","v":"nologin_tips"}}}]},"r":null},{"n":"body-rewrite-025","p":"^https?:\\/\\/p\\.kuaidi100\\.com\\/mobile\\/mobileapi\\.do$","j":{"t":"call","f":"delpaths","args":[{"t":"arr","e":{"t":"arr","e":{"t":"lit","v":"index_banner"}}}]},"r":null},{"n":"body-rewrite-026","p":"^https?:\\/\\/p\\.kuaidi100\\.com\\/mobile\\/mobileapi\\.do$","j":{"t":"call","f":"delpaths","args":[{"t":"arr","e":{"t":"arr","e":{"t":"lit","v":"me_banner"}}}]},"r":null},{"n":"body-rewrite-027","p":"^https?:\\/\\/p\\.kuaidi100\\.com\\/mobile\\/mobileapi\\.do$","j":{"t":"call","f":"delpaths","args":[{"t":"arr","e":{"t":"arr","e":{"t":"lit","v":"index_banner_shadow"}}}]},"r":null},{"n":"body-rewrite-028","p":"^https?:\\/\\/p\\.kuaidi100\\.com\\/mobile\\/mobileapi\\.do$","j":{"t":"call","f":"delpaths","args":[{"t":"arr","e":{"t":"arr","e":{"t":"lit","v":"adshongbao"}}}]},"r":null},{"n":"body-rewrite-029","p":"^https?:\\/\\/p\\.kuaidi100\\.com\\/mobile\\/mobileapi\\.do$","j":{"t":"call","f":"delpaths","args":[{"t":"arr","e":{"t":"arr","e":{"t":"lit","v":"adsapp_homepage_ticket_pop"}}}]},"r":null},{"n":"body-rewrite-030","p":"^https?:\\/\\/p\\.kuaidi100\\.com\\/mobile\\/mobileapi\\.do$","j":{"t":"call","f":"delpaths","args":[{"t":"arr","e":{"t":"arr","e":{"t":"lit","v":"adsoptimizationsend"}}}]},"r":null},{"n":"body-rewrite-031","p":"^https?:\\/\\/p\\.kuaidi100\\.com\\/mobile\\/mobileapi\\.do$","j":{"t":"call","f":"delpaths","args":[{"t":"arr","e":{"t":"arr","e":{"t":"lit","v":"adsapp_activity_ad_array"}}}]},"r":null},{"n":"body-rewrite-032","p":"^https?:\\/\\/p\\.kuaidi100\\.com\\/mobile\\/mobileapi\\.do$","j":{"t":"call","f":"delpaths","args":[{"t":"arr","e":{"t":"arr","e":{"t":"lit","v":"adbanner"}}}]},"r":null},{"n":"body-rewrite-033","p":"^https?:\\/\\/p\\.kuaidi100\\.com\\/mobile\\/mobileapi\\.do$","j":{"t":"call","f":"delpaths","args":[{"t":"arr","e":{"t":"arr","e":{"t":"lit","v":"adposition"}}}]},"r":null},{"n":"body-rewrite-034","p":"^https?:\\/\\/p\\.kuaidi100\\.com\\/mobile\\/mobileapi\\.do$","j":{"t":"call","f":"delpaths","args":[{"t":"arr","e":{"t":"arr","e":{"t":"lit","v":"adShowAgainTime"}}}]},"r":null},{"n":"body-rewrite-035","p":"^https?:\\/\\/p\\.kuaidi100\\.com\\/apicenter\\/xcx\\.dox","j":{"t":"call","f":"delpaths","args":[{"t":"arr","e":{"t":"arr","e":{"t":"comma","l":{"t":"lit","v":"data"},"r":{"t":"lit","v":"secondMenuList"}}}}]},"r":null},{"n":"body-rewrite-036","p":"^https:\\/\\/(apissl|az2-api(-js|-idc)?)\\.(gifshow|ksapisrv)\\.com\\/rest\\/system\\/startup\\?","j":{"t":"call","f":"delpaths","args":[{"t":"arr","e":{"t":"arr","e":{"t":"lit","v":"reskinConfig"}}}]},"r":null},{"n":"body-rewrite-037","p":"^https:\\/\\/(apissl|az2-api(-js|-idc)?)\\.(gifshow|ksapisrv)\\.com\\/rest\\/system\\/startup\\?","j":{"t":"call","f":"delpaths","args":[{"t":"arr","e":{"t":"arr","e":{"t":"comma","l":{"t":"lit","v":"sidebarExSquareStyle"},"r":{"t":"lit","v":"moreList"}}}}]},"r":null},{"n":"body-rewrite-038","p":"^https:\\/\\/(apissl|az2-api(-js|-idc)?)\\.(gifshow|ksapisrv)\\.com\\/rest\\/system\\/startup\\?","j":{"t":"call","f":"delpaths","args":[{"t":"arr","e":{"t":"arr","e":{"t":"comma","l":{"t":"lit","v":"sidebarExSquareStyle"},"r":{"t":"lit","v":"topList"}}}}]},"r":null},{"n":"body-rewrite-039","p":"^https:\\/\\/(apissl|az2-api(-js|-idc)?)\\.(gifshow|ksapisrv)\\.com\\/rest\\/system\\/startup\\?","j":{"t":"assign","op":"|=","l":{"t":"pipe","l":{"t":"field","n":"sidebarExSquareStyle"},"r":{"t":"field","n":"commonlyUsedList"}},"r":{"t":"call","f":"map","args":[{"t":"call","f":"select","args":[{"t":"bin","op":"or","l":{"t":"bin","op":"or","l":{"t":"bin","op":"or","l":{"t":"bin","op":"or","l":{"t":"bin","op":"or","l":{"t":"bin","op":"or","l":{"t":"bin","op":"or","l":{"t":"bin","op":"or","l":{"t":"bin","op":"or","l":{"t":"bin","op":"or","l":{"t":"bin","op":"or","l":{"t":"bin","op":"==","l":{"t":"field","n":"title"},"r":{"t":"lit","v":"设置"}},"r":{"t":"bin","op":"==","l":{"t":"field","n":"title"},"r":{"t":"lit","v":"历史记录"}}},"r":{"t":"bin","op":"==","l":{"t":"field","n":"title"},"r":{"t":"lit","v":"草稿箱"}}},"r":{"t":"bin","op":"==","l":{"t":"field","n":"title"},"r":{"t":"lit","v":"我的钱包"}}},"r":{"t":"bin","op":"==","l":{"t":"field","n":"title"},"r":{"t":"lit","v":"小程序"}}},"r":{"t":"bin","op":"==","l":{"t":"field","n":"title"},"r":{"t":"lit","v":"未成年人模式"}}},"r":{"t":"bin","op":"==","l":{"t":"field","n":"title"},"r":{"t":"lit","v":"官方客服"}}},"r":{"t":"bin","op":"==","l":{"t":"field","n":"title"},"r":{"t":"lit","v":"内容偏好"}}},"r":{"t":"bin","op":"==","l":{"t":"field","n":"title"},"r":{"t":"lit","v":"离线模式"}}},"r":{"t":"bin","op":"==","l":{"t":"field","n":"title"},"r":{"t":"lit","v":"稍后再看"}}},"r":{"t":"bin","op":"==","l":{"t":"field","n":"title"},"r":{"t":"lit","v":"举报中心"}}},"r":{"t":"bin","op":"==","l":{"t":"field","n":"title"},"r":{"t":"lit","v":"挂件"}}}]}]}},"r":null},{"n":"body-rewrite-040","p":"^https:\\/\\/az2-live\\.ksapisrv\\.com\\/rest\\/n\\/live\\/feed\\/square\\/refresh\\?","j":{"t":"call","f":"delpaths","args":[{"t":"arr","e":{"t":"arr","e":{"t":"comma","l":{"t":"lit","v":"data"},"r":{"t":"lit","v":"banners"}}}}]},"r":null},{"n":"body-rewrite-041","p":"^https:\\/\\/az4-api(-idc)?\\.ksapisrv\\.com\\/rest\\/n\\/feed\\/selectionFast\\?","j":{"t":"if","c":{"t":"bin","op":"==","l":{"t":"pipe","l":{"t":"field","n":"feeds"},"r":{"t":"call","f":"type","args":[]}},"r":{"t":"lit","v":"array"}},"a":{"t":"assign","op":"|=","l":{"t":"field","n":"feeds"},"r":{"t":"call","f":"map","args":[{"t":"call","f":"select","args":[{"t":"pipe","l":{"t":"field","n":"ad"},"r":{"t":"call","f":"not","args":[]}}]}]}},"b":{"t":"id"}},"r":null},{"n":"body-rewrite-042","p":"^https:\\/\\/az2-api-js\\.gifshow\\.com\\/rest\\/n\\/user\\/profile\\/v2\\?","j":{"t":"call","f":"delpaths","args":[{"t":"arr","e":{"t":"arr","e":{"t":"lit","v":"postRecommends"}}}]},"r":null},{"n":"body-rewrite-043","p":"(?i)^https://lzmh\\.lz-qs\\.com:6025/lzmh_app_api/api/v2/user/getUserBaseInfoAndConfig\\?","j":{"t":"call","f":"del","args":[{"t":"pipe","l":{"t":"field","n":"value"},"r":{"t":"field","n":"config"}}]},"r":null},{"n":"body-rewrite-044","p":"https?:\\/\\/dili.sqcosmos.com\\/jiekou\\/mains\\/p\\d+.html","j":{"t":"assign","op":"|=","l":{"t":"field","n":"album"},"r":{"t":"call","f":"map","args":[{"t":"call","f":"select","args":[{"t":"bin","op":"and","l":{"t":"bin","op":"!=","l":{"t":"field","n":"id"},"r":{"t":"lit","v":"4154"}},"r":{"t":"bin","op":"!=","l":{"t":"field","n":"id"},"r":{"t":"lit","v":"4165"}}}]}]}},"r":null},{"n":"body-rewrite-045","p":"^https?:\\/\\/mobile\\.yangkeduo\\.com\\/proxy\\/api\\/api\\/express\\/post\\/waybill\\/red_packet\\/goods_list$","j":null,"r":["\"list\":\\[.+\\]","\"list\":[]"]},{"n":"body-rewrite-046","p":"^https:\\/\\/j1\\.pupuapi\\.com\\/client\\/notification\\/message_center\\/unread_number","j":{"t":"assign","op":"=","l":{"t":"field","n":"data"},"r":{"t":"arr","e":null}},"r":null},{"n":"body-rewrite-047","p":"^https:\\/\\/beta-luna\\.douyin\\.com\\/luna\\/card\\?","j":{"t":"if","c":{"t":"pipe","l":{"t":"call","f":"getpath","args":[{"t":"arr","e":{"t":"comma","l":{"t":"lit","v":"card_items"},"r":{"t":"lit","v":0}}}]},"r":{"t":"call","f":"has","args":[{"t":"lit","v":"priority_display"}]}},"a":{"t":"call","f":"setpath","args":[{"t":"arr","e":{"t":"comma","l":{"t":"comma","l":{"t":"lit","v":"card_items"},"r":{"t":"lit","v":0}},"r":{"t":"lit","v":"priority_display"}}},{"t":"lit","v":false}]},"b":{"t":"id"}},"r":null},{"n":"body-rewrite-048","p":"^https:\\/\\/beta-luna\\.douyin\\.com\\/luna\\/card\\?","j":{"t":"if","c":{"t":"pipe","l":{"t":"call","f":"getpath","args":[{"t":"arr","e":{"t":"comma","l":{"t":"lit","v":"card_items"},"r":{"t":"lit","v":0}}}]},"r":{"t":"call","f":"has","args":[{"t":"lit","v":"is_show"}]}},"a":{"t":"call","f":"setpath","args":[{"t":"arr","e":{"t":"comma","l":{"t":"comma","l":{"t":"lit","v":"card_items"},"r":{"t":"lit","v":0}},"r":{"t":"lit","v":"is_show"}}},{"t":"lit","v":false}]},"b":{"t":"id"}},"r":null},{"n":"body-rewrite-049","p":"^https:\\/\\/beta-luna\\.douyin\\.com\\/luna\\/card\\?","j":{"t":"if","c":{"t":"pipe","l":{"t":"call","f":"getpath","args":[{"t":"arr","e":null}]},"r":{"t":"call","f":"has","args":[{"t":"lit","v":"preview_guide"}]}},"a":{"t":"call","f":"setpath","args":[{"t":"arr","e":{"t":"lit","v":"preview_guide"}},{"t":"lit","v":null}]},"b":{"t":"id"}},"r":null},{"n":"body-rewrite-050","p":"^https:\\/\\/beta-luna\\.douyin\\.com\\/luna\\/more-panel\\?","j":{"t":"call","f":"delpaths","args":[{"t":"arr","e":{"t":"arr","e":{"t":"comma","l":{"t":"lit","v":"blocks"},"r":{"t":"lit","v":1}}}}]},"r":null},{"n":"body-rewrite-051","p":"^https?:\\/\\/capi\\.lkcoffee\\.com\\/resource\\/m\\/sys\\/app\\/adposNew","j":null,"r":["\\{.+\\}","{\"status\":\"SUCCESS\"}"]},{"n":"body-rewrite-052","p":"^https?:\\/\\/m\\.lkcoffee\\.com\\/ecapi\\/resource\\/m\\/member\\/exchange\\/page","j":null,"r":["\\{.+\\}","{\"status\":\"SUCCESS\"}"]},{"n":"body-rewrite-053","p":"^https?:\\/\\/m\\.lkcoffee\\.com\\/capi\\/resource\\/m\\/growUp\\/main","j":null,"r":["\"popTitle\":\".+?\"","\"popTitle\":\"\""]},{"n":"body-rewrite-054","p":"^https?:\\/\\/dyncdn\\.me\\/static\\/(?:\\d)?(?:\\d)?\\/js\\/showads\\.js$","j":null,"r":["true","false"]},{"n":"body-rewrite-055","p":"^https://www\\.tailgdd\\.com/v8/smart/app/config/get$","j":{"t":"if","c":{"t":"pipe","l":{"t":"call","f":"getpath","args":[{"t":"arr","e":null}]},"r":{"t":"call","f":"has","args":[{"t":"lit","v":"data"}]}},"a":{"t":"call","f":"setpath","args":[{"t":"arr","e":{"t":"lit","v":"data"}},{"t":"obj","pairs":[]}]},"b":{"t":"id"}},"r":null},{"n":"body-rewrite-056","p":"^https?:\\/\\/tft-app\\.cdtft\\.cn\\/gateway-customer\\/tftapp\\/tft-ams\\/api\\/appAd","j":null,"r":["officialAdvertResultVo","fmz200"]},{"n":"body-rewrite-057","p":"^https?:\\/\\/chl\\.tf\\.cn\\/channelmg\\/sys\\/socso\\/order\\/queryOrderInfo","j":null,"r":["\"imgUrl\"","response-body"]},{"n":"body-rewrite-058","p":"^https?:\\/\\/client\\.tujia\\.com\\/bnbapp-node\\/app\\/portal\\/getportalconfig\\/bnb\\/v2","j":null,"r":["\"banners\":\\[.+\\],","\"banners\":[],"]},{"n":"body-rewrite-059","p":"^https:\\/\\/misc-api-prd-mx\\.wandafilm\\.com\\/commend\\/common_banner_batch\\.api","j":{"t":"pipe","l":{"t":"assign","op":"=","l":{"t":"pipe","l":{"t":"pipe","l":{"t":"field","n":"data"},"r":{"t":"field","n":"objects"}},"r":{"t":"index","e":{"t":"lit","v":"OpenAPP-&-FlashAD"}}},"r":{"t":"arr","e":null}},"r":{"t":"assign","op":"=","l":{"t":"pipe","l":{"t":"pipe","l":{"t":"field","n":"data"},"r":{"t":"field","n":"objects"}},"r":{"t":"index","e":{"t":"lit","v":"InTheaters-&-BoxAD"}}},"r":{"t":"arr","e":null}}},"r":null},{"n":"body-rewrite-060","p":"^https?:\\/\\/misc-api-prd-mx\\.wandafilm\\.com\\/commend\\/common_banner_batch\\.api\\?bannerInfos=%5B%7B%22cinemaI","j":null,"r":["\"WX_index_mp-&-boxAD\"","\"fmz200\""]},{"n":"body-rewrite-061","p":"^https:\\/\\/app-conf\\.ds\\.163\\.com\\/v\\d\\/app\\/base\\/conf\\/static\\/start-config\\?","j":{"t":"call","f":"delpaths","args":[{"t":"arr","e":{"t":"arr","e":{"t":"comma","l":{"t":"comma","l":{"t":"comma","l":{"t":"comma","l":{"t":"comma","l":{"t":"comma","l":{"t":"lit","v":"result"},"r":{"t":"lit","v":"updateConfig"}},"r":{"t":"lit","v":2}},"r":{"t":"lit","v":"itemList"}},"r":{"t":"lit","v":94}},"r":{"t":"lit","v":"itemList"}},"r":{"t":"lit","v":2}}}}]},"r":null},{"n":"body-rewrite-062","p":"^https?:\\/\\/mp\\.weixin\\.qq\\.com\\/mp\\/getappmsgad","j":null,"r":["advertisement","fmz200"]},{"n":"body-rewrite-063","p":"^https:\\/\\/(mobile|mobilehera|mobwsa)\\.ximalaya\\.com\\/discovery-feed\\/v\\d\\/mix\\/","j":{"t":"assign","op":"|=","l":{"t":"field","n":"heData"},"r":{"t":"call","f":"map","args":[{"t":"call","f":"select","args":[{"t":"bin","op":"!=","l":{"t":"pipe","l":{"t":"pipe","l":{"t":"pipe","l":{"t":"field","n":"item"},"r":{"t":"field","n":"list"}},"r":{"t":"iter"}},"r":{"t":"field","n":"bizType"}},"r":{"t":"lit","v":"SceneListenCard"}}]}]}},"r":null},{"n":"body-rewrite-064","p":"^https:\\/\\/(mobile|mobilehera|mobwsa)\\.ximalaya\\.com\\/discovery-category\\/customCategories\\/","j":{"t":"pipe","l":{"t":"assign","op":"|=","l":{"t":"field","n":"categoryList"},"r":{"t":"call","f":"map","args":[{"t":"assign","op":"|=","l":{"t":"field","n":"itemList"},"r":{"t":"call","f":"map","args":[{"t":"call","f":"select","args":[{"t":"pipe","l":{"t":"pipe","l":{"t":"field","n":"title"},"r":{"t":"call","f":"test","args":[{"t":"lit","v":"直播|123狂欢节|SVIP"},{"t":"lit","v":"i"}]}},"r":{"t":"call","f":"not","args":[]}}]}]}}]}},"r":{"t":"assign","op":"|=","l":{"t":"field","n":"customCategoryList"},"r":{"t":"call","f":"map","args":[{"t":"call","f":"select","args":[{"t":"pipe","l":{"t":"pipe","l":{"t":"field","n":"title"},"r":{"t":"call","f":"test","args":[{"t":"lit","v":"直播|123狂欢节|SVIP"},{"t":"lit","v":"i"}]}},"r":{"t":"call","f":"not","args":[]}}]}]}}},"r":null},{"n":"body-rewrite-065","p":"^https:\\/\\/(mobile|mobilehera|mobwsa)\\.ximalaya\\.com\\/football-portal\\/diff2\\/batch\\?","j":{"t":"call","f":"delpaths","args":[{"t":"arr","e":{"t":"arr","e":{"t":"comma","l":{"t":"lit","v":"json"},"r":{"t":"lit","v":"ad"}}}}]},"r":null},{"n":"body-rewrite-066","p":"^https:\\/\\/(mobile|mobilehera|mobwsa)\\.ximalaya\\.com\\/football-portal\\/diff2\\/batch\\?","j":{"t":"call","f":"delpaths","args":[{"t":"arr","e":{"t":"arr","e":{"t":"comma","l":{"t":"lit","v":"json"},"r":{"t":"lit","v":"toc"}}}}]},"r":null},{"n":"body-rewrite-067","p":"^https:\\/\\/(mobile|mobilehera|mobwsa)\\.ximalaya\\.com\\/nexus-web\\/v\\d\\/tabs\\/customTabs\\?","j":{"t":"assign","op":"|=","l":{"t":"pipe","l":{"t":"field","n":"data"},"r":{"t":"field","n":"feedTabs"}},"r":{"t":"call","f":"map","args":[{"t":"call","f":"select","args":[{"t":"bin","op":"!=","l":{"t":"field","n":"name"},"r":{"t":"lit","v":"大赛"}}]}]}},"r":null},{"n":"body-rewrite-068","p":"^https:\\/\\/mobwsa\\.ximalaya\\.com\\/mobile-playpage\\/playpage\\/tabs\\/v2\\/","j":{"t":"call","f":"delpaths","args":[{"t":"arr","e":{"t":"arr","e":{"t":"comma","l":{"t":"comma","l":{"t":"comma","l":{"t":"lit","v":"data"},"r":{"t":"lit","v":"playpage"}},"r":{"t":"lit","v":"resourceMap"}},"r":{"t":"lit","v":"defaultResource"}}}}]},"r":null},{"n":"body-rewrite-069","p":"^https:\\/\\/mobwsa\\.ximalaya\\.com\\/mobile-playpage\\/playpage\\/tabs\\/v2\\/","j":{"t":"call","f":"delpaths","args":[{"t":"arr","e":{"t":"arr","e":{"t":"comma","l":{"t":"comma","l":{"t":"comma","l":{"t":"lit","v":"data"},"r":{"t":"lit","v":"playpage"}},"r":{"t":"lit","v":"resourceMap"}},"r":{"t":"lit","v":"playPageTip"}}}}]},"r":null},{"n":"body-rewrite-070","p":"^https:\\/\\/(mobile|mobilehera|mobwsa)\\.ximalaya\\.com\\/mobile-user\\/v\\d\\/homePage\\/","j":{"t":"call","f":"delpaths","args":[{"t":"arr","e":{"t":"arr","e":{"t":"comma","l":{"t":"lit","v":"data"},"r":{"t":"lit","v":"freeListenV2"}}}}]},"r":null},{"n":"body-rewrite-071","p":"^https:\\/\\/(mobile|mobilehera|mobwsa)\\.ximalaya\\.com\\/mobile-user\\/v\\d\\/homePage\\/","j":{"t":"assign","op":"|=","l":{"t":"pipe","l":{"t":"pipe","l":{"t":"field","n":"data"},"r":{"t":"field","n":"serviceModule"}},"r":{"t":"field","n":"entrances"}},"r":{"t":"call","f":"map","args":[{"t":"call","f":"select","args":[{"t":"bin","op":"==","l":{"t":"field","n":"name"},"r":{"t":"lit","v":"全部服务"}}]}]}},"r":null},{"n":"body-rewrite-072","p":"^https:\\/\\/acs\\.m\\.goofish\\.com\\/gw\\/mtop\\.taobao\\.idlemtopsearch\\.search\\.shade\\/","j":{"t":"call","f":"del","args":[{"t":"field","n":"data"}]},"r":null},{"n":"body-rewrite-073","p":"^https:\\/\\/acs\\.m\\.goofish\\.com\\/gw\\/mtop\\.taobao\\.idle\\.user\\.strategy\\.list\\/","j":{"t":"call","f":"del","args":[{"t":"field","n":"data"}]},"r":null},{"n":"body-rewrite-074","p":"^https:\\/\\/acs\\.m\\.goofish\\.com\\/gw\\/mtop\\.taobao\\.idle\\.group\\.myself\\.banner\\/","j":{"t":"assign","op":"=","l":{"t":"pipe","l":{"t":"field","n":"data"},"r":{"t":"field","n":"bannerList"}},"r":{"t":"arr","e":null}},"r":null},{"n":"body-rewrite-075","p":"^https:\\/\\/acs\\.m\\.goofish\\.com\\/gw\\/mtop\\.taobao\\.idle\\.playboy\\.recommend\\/2\\.0","j":{"t":"pipe","l":{"t":"pipe","l":{"t":"assign","op":"=","l":{"t":"pipe","l":{"t":"field","n":"data"},"r":{"t":"field","n":"recommends"}},"r":{"t":"arr","e":null}},"r":{"t":"assign","op":"=","l":{"t":"pipe","l":{"t":"field","n":"data"},"r":{"t":"field","n":"items"}},"r":{"t":"arr","e":null}}},"r":{"t":"assign","op":"=","l":{"t":"pipe","l":{"t":"field","n":"data"},"r":{"t":"field","n":"next"}},"r":{"t":"lit","v":false}}},"r":null},{"n":"body-rewrite-076","p":"^https:\\/\\/acs\\.m\\.goofish\\.com\\/gw\\/mtop\\.taobao\\.idle\\.item\\.recommend\\.list\\/","j":{"t":"assign","op":"=","l":{"t":"pipe","l":{"t":"field","n":"data"},"r":{"t":"field","n":"cardList"}},"r":{"t":"arr","e":null}},"r":null},{"n":"body-rewrite-077","p":"^https:\\/\\/acs\\.m\\.goofish\\.com\\/gw\\/mtop\\.taobao\\.idle\\.fun\\.follow\\.often\\.visit","j":{"t":"assign","op":"=","l":{"t":"pipe","l":{"t":"field","n":"data"},"r":{"t":"field","n":"sections"}},"r":{"t":"arr","e":null}},"r":null},{"n":"body-rewrite-078","p":"^https:\\/\\/acs\\.m\\.goofish\\.com\\/gw\\/mtop\\.taobao\\.idle\\.circle\\.myself\\.banner\\/1\\.0","j":{"t":"assign","op":"=","l":{"t":"pipe","l":{"t":"field","n":"data"},"r":{"t":"field","n":"bannerList"}},"r":{"t":"arr","e":null}},"r":null},{"n":"body-rewrite-079","p":"^https:\\/\\/acs\\.m\\.goofish\\.com\\/gw\\/mtop\\.taobao\\.idle\\.circle\\.visited\\/1\\.0","j":{"t":"assign","op":"=","l":{"t":"pipe","l":{"t":"field","n":"data"},"r":{"t":"field","n":"visitedCircleList"}},"r":{"t":"arr","e":null}},"r":null},{"n":"body-rewrite-080","p":"^https?:\\/\\/lcen\\.xiaote\\.net\\/api\\/graphql","j":null,"r":["screenSplashAd","fmz200"]},{"n":"body-rewrite-081","p":"^https?:\\/\\/api\\.xiaoyuzhoufm\\.com\\/v1\\/discovery-feed\\/list","j":{"t":"assign","op":"|=","l":{"t":"field","n":"data"},"r":{"t":"call","f":"map","args":[{"t":"call","f":"select","args":[{"t":"bin","op":"and","l":{"t":"bin","op":"!=","l":{"t":"field","n":"type"},"r":{"t":"lit","v":"DISCOVERY_HEADER"}},"r":{"t":"bin","op":"!=","l":{"t":"field","n":"type"},"r":{"t":"lit","v":"DISCOVERY_BANNER"}}}]}]}},"r":null},{"n":"body-rewrite-082","p":"^https?:\\/\\/api\\.xiaoyuzhoufm\\.com\\/v1\\/(related-episode|operation-resource)\\/list","j":{"t":"assign","op":"=","l":{"t":"field","n":"data"},"r":{"t":"arr","e":null}},"r":null},{"n":"body-rewrite-083","p":"^https?:\\/\\/oneapp-api\\.faw-vw\\.com\\/search\\/firstPage\\/getPromptList\\/v1\\?.*","j":{"t":"assign","op":"=","l":{"t":"id"},"r":{"t":"obj","pairs":[[{"t":"lit","v":"returnStatus"},{"t":"lit","v":"SUCCEED"}],[{"t":"lit","v":"hasMore"},{"t":"lit","v":false}],[{"t":"lit","v":"data"},{"t":"arr","e":null}]]}},"r":null},{"n":"body-rewrite-084","p":"^https?:\\/\\/oneapp-api\\.faw-vw\\.com\\/benefits\\/benefitsCard\\/getInfo\\/v1\\?.*","j":{"t":"assign","op":"=","l":{"t":"id"},"r":{"t":"obj","pairs":[[{"t":"lit","v":"returnStatus"},{"t":"lit","v":"SUCCEED"}],[{"t":"lit","v":"hasMore"},{"t":"lit","v":false}],[{"t":"lit","v":"data"},{"t":"arr","e":null}]]}},"r":null},{"n":"body-rewrite-085","p":"^https?:\\/\\/oneapp-api\\.faw-vw\\.com\\/content\\/booth\\/getBoothList\\/v1\\?.*showPositionCode=VWAPP_HOME_BUOY","j":{"t":"assign","op":"=","l":{"t":"id"},"r":{"t":"obj","pairs":[[{"t":"lit","v":"returnStatus"},{"t":"lit","v":"SUCCEED"}],[{"t":"lit","v":"hasMore"},{"t":"lit","v":false}],[{"t":"lit","v":"data"},{"t":"arr","e":null}]]}},"r":null},{"n":"body-rewrite-086","p":"^https?:\\/\\/oneapp-api\\.faw-vw\\.com\\/content\\/booth\\/getBoothList\\/v1\\?.*showPositionCode=VWAPP_(ICE|MEB)_(OPEN_SCREEN_ADS|CAR_ZHIHU_COLLEGE)","j":{"t":"assign","op":"=","l":{"t":"id"},"r":{"t":"obj","pairs":[[{"t":"lit","v":"returnStatus"},{"t":"lit","v":"SUCCEED"}],[{"t":"lit","v":"hasMore"},{"t":"lit","v":false}],[{"t":"lit","v":"data"},{"t":"arr","e":null}]]}},"r":null},{"n":"body-rewrite-087","p":"^https?:\\/\\/oneapp-api\\.faw-vw\\.com\\/content\\/booth\\/getBoothList\\/v1\\?.*showPositionCode=VWAPP_(ICE|MEB)_HOME_(OWNER_BANNER|PROSPECTS_BANNER|CUSTOM_BANNER|KONGO|CUSTOM_KONGO)","j":{"t":"assign","op":"=","l":{"t":"id"},"r":{"t":"obj","pairs":[[{"t":"lit","v":"returnStatus"},{"t":"lit","v":"SUCCEED"}],[{"t":"lit","v":"hasMore"},{"t":"lit","v":false}],[{"t":"lit","v":"data"},{"t":"arr","e":null}]]}},"r":null},{"n":"body-rewrite-088","p":"^https?:\\/\\/oneapp-api\\.faw-vw\\.com\\/content\\/(customize\\/getCustomizePageName|recommend\\/getRecommendInfoFlows|activity\\/getSquareActivityList|theme\\/getThemeList|post\\/getPostsByTags|evaluate\\/getEvaluateCards)\\/v1\\?.*","j":{"t":"assign","op":"=","l":{"t":"id"},"r":{"t":"obj","pairs":[[{"t":"lit","v":"returnStatus"},{"t":"lit","v":"SUCCEED"}],[{"t":"lit","v":"hasMore"},{"t":"lit","v":false}],[{"t":"lit","v":"data"},{"t":"arr","e":null}]]}},"r":null},{"n":"body-rewrite-089","p":"^https?:\\/\\/oneapp-api\\.faw-vw\\.com\\/content\\/(collection\\/getCollectionList)\\/v1\\?.*","j":{"t":"assign","op":"=","l":{"t":"id"},"r":{"t":"obj","pairs":[[{"t":"lit","v":"returnStatus"},{"t":"lit","v":"SUCCEED"}],[{"t":"lit","v":"hasMore"},{"t":"lit","v":false}],[{"t":"lit","v":"data"},{"t":"obj","pairs":[]}]]}},"r":null},{"n":"body-rewrite-090","p":"https?:\\/\\/.+\\.gamersky.com/.+/lists/getListElements","j":{"t":"assign","op":"|=","l":{"t":"field","n":"listElements"},"r":{"t":"call","f":"map","args":[{"t":"call","f":"select","args":[{"t":"pipe","l":{"t":"call","f":"has","args":[{"t":"lit","v":"adCategory"}]},"r":{"t":"call","f":"not","args":[]}}]}]}},"r":null},{"n":"body-rewrite-091","p":"^https?:\\/\\/portal\\.zjzwfw\\.gov\\.cn\\/app_api\\/appHome\\/selectStartPic","j":{"t":"if","c":{"t":"pipe","l":{"t":"call","f":"getpath","args":[{"t":"arr","e":null}]},"r":{"t":"call","f":"has","args":[{"t":"lit","v":"data"}]}},"a":{"t":"call","f":"setpath","args":[{"t":"arr","e":{"t":"lit","v":"data"}},{"t":"obj","pairs":[]}]},"b":{"t":"id"}},"r":null},{"n":"body-rewrite-092","p":"^https?:\\/\\/app-izz\\.zhengzhou\\.gov\\.cn:10019\\/bizgw\\/gateway\\.do","j":null,"r":["\"imgUrl19_5x9\":\".+?\"","\"imgUrl19_5x9\":\"\""]},{"n":"body-rewrite-093","p":"^https:\\/\\/api\\.zhihu\\.com\\/search\\/recommend_query\\/v2\\?","j":null,"r":["\"recommend_queries\":\\{.+\\}","\"recommend_queries\":{}"]},{"n":"body-rewrite-094","p":"^https?:\\/\\/app\\.zhuanzhuan\\.com\\/zz\\/v2\\/zzinfoshow\\/getfeedflowinfo\\?","j":null,"r":["userRed","fmz200"]},{"n":"body-rewrite-095","p":"^https?:\\/\\/app\\.zhuanzhuan\\.com\\/zz\\/v2\\/zzinfoshow\\/getchoicegoodsinfos","j":null,"r":["infoData","fmz200"]}];

function __rx(p){
  var flags = "";
  while (p.indexOf("(?i)") === 0) { flags += "i"; p = p.slice(4); }
  try { return new RegExp(p, flags); } catch (e) { return null; }
}
var __RE__ = [];
for (var __i = 0; __i < __RULES__.length; __i++) __RE__.push(__rx(__RULES__[__i].p));

(function () {
  var url = ($request && $request.url) || "";
  var body = $response && $response.body;
  if (typeof body !== "string") { $done({}); return; }

  // 同一 URL 可能命中多条规则（上游大量重复 pattern），必须全部依次应用
  var matched = [];
  for (var i = 0; i < __RULES__.length; i++) {
    if (__RE__[i] && __RE__[i].test(url)) matched.push(__RULES__[i]);
  }
  if (!matched.length) { $done({}); return; }

  var obj = undefined;   // undefined=未解析 / null=解析失败
  for (var k = 0; k < matched.length; k++) {
    var r = matched[k];
    if (r.r) {                                  // 字符串替换（上游 http-response 的 search 是正则）
      if (r.r[0]) {
        try {
          body = body.replace(new RegExp(r.r[0], 'g'), function () { return r.r[1]; });
        } catch (e) {
          body = body.split(r.r[0]).join(r.r[1]);   // 正则非法时退回字面量
        }
      }
      obj = undefined;                          // 字符串已变，需重新解析
      continue;
    }
    if (!r.j) continue;
    if (obj === undefined) {
      try { obj = JSON.parse(body); } catch (e) { obj = null; }
    }
    if (obj === null) continue;
    try {
      var out = JQRT.make(r.j)(obj);
      if (out.length && out[0] !== undefined) obj = out[0];
    } catch (e) { /* 单条失败不影响其他规则 */ }
  }
  if (obj !== undefined && obj !== null) body = JSON.stringify(obj);
  $done({ body: body });
})();
