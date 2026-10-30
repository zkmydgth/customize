/* jq 子集运行时（内联进每个生成的 SR 脚本）
   用法: var run = JQRT.make(<AST>); var out = run(inputObj);
   ！注意：文件体积直接决定手机端脚本体积，改动后请跑 tools/test_equiv.py */
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
