/* Au(T+D) 日K线图（ECharts 5）。
   蜡烛图 / MA5~MA30 / 日K→周K·月K聚合 / dataZoom 窗口内最高最低标记等
   逻辑借鉴汇率表 gold_charts.min.js（echarts 4 + jQuery 实现），以 vanilla
   JS 重写并适配本站暗色金融主题（涨红跌绿）。数据源 /api/gold/kline，
   bars 行序 [day, open, close, low, high, change, amplitude, volume]。 */
(function () {
  'use strict';

  var C = {
    up: '#f85149', down: '#3fb950',
    axis: '#8b949e', split: '#21262d', text: '#e6edf3', gold: '#d4a537',
    ma: { MA5: '#d4a537', MA10: '#58a6ff', MA20: '#bc8cff', MA30: '#f0883e' }
  };
  var MA_DEFS = [
    { name: 'MA5', n: 5 }, { name: 'MA10', n: 10 },
    { name: 'MA20', n: 20 }, { name: 'MA30', n: 30 }
  ];
  var WIN = 60; // 初始显示最近 60 根（源站默认窗口）

  var chart = null;
  var rawBars = [];   // 旧→新
  var curBars = [];   // 当前周期聚合后的K线
  var maSeries = {};  // { MA5: [...], ... } 与 curBars 对齐
  var period = 'day';

  // ---------- 聚合（借鉴源站 week/month 分组逻辑，按 key 变化切组） ----------
  function weekKey(dayStr) {
    var p = dayStr.split('-');
    var dt = new Date(+p[0], +p[1] - 1, +p[2]);
    var wd = (dt.getDay() + 6) % 7; // Mon=0
    dt.setDate(dt.getDate() - wd);
    return dt.getFullYear() + '-' + String(dt.getMonth() + 1).padStart(2, '0') + '-' + String(dt.getDate()).padStart(2, '0');
  }
  function monthKey(dayStr) { return dayStr.slice(0, 7); }

  function aggregate(bars, keyFn) {
    var out = [], group = [], gkey = null;
    function flush() {
      if (!group.length) return;
      var o = group[0][1], c = group[group.length - 1][2];
      var l = Math.min.apply(null, group.map(function (b) { return b[3]; }));
      var h = Math.max.apply(null, group.map(function (b) { return b[4]; }));
      var vol = group.reduce(function (s, b) { return s + (b[7] || 0); }, 0);
      var prev = out.length ? out[out.length - 1][2] : null;
      out.push([group[group.length - 1][0], o, c, l, h,
        prev == null ? null : c - prev,
        prev ? (h - l) / prev * 100 : null, vol]);
      group = [];
    }
    bars.forEach(function (b) {
      var k = keyFn(b[0]);
      if (k !== gkey) { flush(); gkey = k; }
      group.push(b);
    });
    flush();
    return out;
  }

  // ---------- MA（收盘价简单移动平均，借鉴源站 u() 函数） ----------
  function calcMA(bars, n) {
    var out = [];
    for (var i = 0; i < bars.length; i++) {
      if (i < n - 1) { out.push('-'); continue; }
      var s = 0;
      for (var j = i - n + 1; j <= i; j++) s += bars[j][2];
      out.push(+(s / n).toFixed(2));
    }
    return out;
  }

  // ---------- 可见窗口内最高/最低标记（dataZoom 防抖 100ms，借鉴源站） ----------
  function markFor(range) {
    var n = curBars.length;
    var s = Math.max(0, Math.floor(range.start / 100 * n));
    var e = Math.min(n - 1, Math.ceil(range.end / 100 * n) - 1);
    if (s > e) { s = 0; e = n - 1; }
    var hi = { v: -Infinity, i: s }, lo = { v: Infinity, i: s };
    for (var i = s; i <= e; i++) {
      if (curBars[i][4] > hi.v) { hi = { v: curBars[i][4], i: i }; }
      if (curBars[i][3] < lo.v) { lo = { v: curBars[i][3], i: i }; }
    }
    return {
      data: [
        { coord: [hi.i, hi.v], symbolSize: 34, itemStyle: { color: C.up },
          label: { formatter: '高 ' + hi.v, position: 'top', color: C.up, fontSize: 10 } },
        { coord: [lo.i, lo.v], symbolSize: 34, itemStyle: { color: C.down },
          label: { formatter: '低 ' + lo.v, position: 'bottom', color: C.down, fontSize: 10 } }
      ]
    };
  }

  // ---------- tooltip / MA 面板 ----------
  function weekday(dayStr) {
    var p = dayStr.split('-');
    return '日一二三四五六'[new Date(+p[0], +p[1] - 1, +p[2]).getDay()];
  }
  function fmtSigned(v) { return v == null ? '—' : (v >= 0 ? '+' : '') + (+v).toFixed(2); }
  function fmtPct(v) { return v == null ? '' : ' (' + fmtSigned(v) + '%)'; }

  function updateMaPanel(idx) {
    var el = document.getElementById('ma-values');
    if (!el) return;
    el.innerHTML = MA_DEFS.map(function (d) {
      return '<span style="color:' + C.ma[d.name] + '">' + d.name + ': ' + maSeries[d.name][idx] + '</span>';
    }).join(' | ');
  }

  function tooltipFormatter(params) {
    var k = params[0], i = k.dataIndex, b = curBars[i];
    if (!b) return '';
    var chg = b[5], amp = b[6], vol = b[7];
    var chgColor = chg > 0 ? C.up : chg < 0 ? C.down : C.axis;
    var prevClose = (chg != null && chg != 0 && b[2] != null) ? b[2] - chg : null;
    var pct = (chg != null && prevClose) ? chg / prevClose * 100 : null;
    updateMaPanel(i);
    return '<b>' + b[0] + ' 周' + weekday(b[0]) + '</b><br>' +
      '开盘: ' + b[1] + '<br>收盘: ' + b[2] + '<br>最低: ' + b[3] + '<br>最高: ' + b[4] + '<br>' +
      '涨跌: <span style="color:' + chgColor + '">' + fmtSigned(chg) + fmtPct(pct) + '</span><br>' +
      '振幅: ' + (amp == null ? '—' : amp.toFixed(2) + '%') +
      (vol ? '<br>成交量: ' + vol + ' 手' : '');
  }

  // ---------- option ----------
  function buildOption() {
    curBars = period === 'day' ? rawBars : aggregate(rawBars, period === 'week' ? weekKey : monthKey);
    maSeries = {};
    MA_DEFS.forEach(function (d) { maSeries[d.name] = calcMA(curBars, d.n); });

    var n = curBars.length;
    var startPct = n > WIN ? (n - WIN) / n * 100 : 0;
    var zm = [{ type: 'inside', start: startPct, end: 100 },
              { type: 'slider', start: startPct, end: 100, bottom: 6, height: 20,
                borderColor: C.split, backgroundColor: '#0d1117',
                fillerColor: 'rgba(212,165,55,.12)', handleStyle: { color: C.gold },
                dataBackground: { lineStyle: { color: C.split }, areaStyle: { color: 'rgba(212,165,55,.08)' } },
                textStyle: { color: C.axis, fontSize: 10 } }];

    return {
      animation: false,
      backgroundColor: 'transparent',
      legend: { show: false },
      tooltip: {
        trigger: 'axis', axisPointer: { type: 'cross', label: { backgroundColor: '#30363d' } },
        backgroundColor: '#161b22', borderColor: '#30363d', borderWidth: 1,
        textStyle: { color: C.text, fontSize: 12 },
        formatter: tooltipFormatter
      },
      grid: { left: 8, right: 60, top: 30, bottom: 70, containLabel: true },
      xAxis: {
        type: 'category', data: curBars.map(function (b) { return b[0]; }),
        boundaryGap: true, axisLine: { lineStyle: { color: C.split } },
        axisLabel: { color: C.axis, fontSize: 11 }, splitLine: { show: false },
        axisPointer: { label: { show: true } }
      },
      yAxis: {
        scale: true, position: 'right',
        axisLabel: { color: C.axis, fontSize: 11 },
        splitLine: { lineStyle: { color: C.split } },
        axisPointer: { label: { show: true } }
      },
      dataZoom: zm,
      series: [
        {
          name: '日K', type: 'candlestick',
          data: curBars.map(function (b) { return [b[1], b[2], b[3], b[4]]; }),
          itemStyle: { color: C.up, color0: C.down, borderColor: C.up, borderColor0: C.down },
          barWidth: '62%',
          markPoint: markFor({ start: startPct, end: 100 })
        }
      ].concat(MA_DEFS.map(function (d) {
        return {
          name: d.name, type: 'line', data: maSeries[d.name], smooth: true,
          showSymbol: false, lineStyle: { opacity: 0.6, color: C.ma[d.name], width: 1 },
          itemStyle: { color: C.ma[d.name] }
        };
      }))
    };
  }

  function applyPeriod(p) {
    period = p;
    document.querySelectorAll('.kline-tab').forEach(function (btn) {
      var active = btn.dataset.period === p;
      btn.style.backgroundColor = active ? C.gold : 'transparent';
      btn.style.color = active ? '#0d1117' : C.axis;
      btn.style.borderColor = active ? C.gold : '#30363d';
    });
    if (chart) chart.setOption(buildOption(), { notMerge: true });
  }

  // ---------- 摘要条 ----------
  function renderSummary() {
    var b = rawBars[rawBars.length - 1];
    if (!b) return;
    var set = function (id, v) { var el = document.getElementById(id); if (el) el.textContent = v; };
    var chg = b[5];
    var prevClose = (chg != null && b[2] != null) ? b[2] - chg : null;
    var pct = (chg != null && prevClose) ? chg / prevClose * 100 : null;
    var cls = chg > 0 ? 'text-up' : chg < 0 ? 'text-down' : 'text-muted';
    set('sum-date', b[0] + ' 周' + weekday(b[0]));
    set('sum-close', b[2] == null ? '—' : b[2].toFixed(2));
    var chgEl = document.getElementById('sum-chg');
    if (chgEl) {
      chgEl.textContent = fmtSigned(chg) + fmtPct(pct);
      chgEl.className = 'num ' + cls;
    }
    set('sum-amp', b[6] == null ? '—' : b[6].toFixed(2) + '%');
    set('sum-vol', b[7] ? b[7].toLocaleString('zh-CN') + ' 手' : '—');
  }

  function showStatus(msg, isError) {
    var el = document.getElementById('kline-status');
    if (!el) return;
    if (!msg) { el.classList.add('hidden'); return; }
    el.classList.remove('hidden');
    el.textContent = msg;
    el.style.color = isError ? C.up : C.axis;
    el.style.borderColor = isError ? 'rgba(248,81,73,.35)' : 'rgba(212,165,55,.3)';
  }

  // ---------- 加载 ----------
  function load() {
    fetch('/api/gold/kline?days=730')
      .then(function (r) { return r.json(); })
      .then(function (env) {
        var bars = env.data && env.data.bars;
        if ((env.code === 1) || !bars || !bars.length) {
          showStatus((env.msg || '数据获取失败，请稍后重试'), true);
          return;
        }
        rawBars = bars;
        renderSummary();
        var dom = document.getElementById('kline-chart');
        chart = echarts.init(dom, null, { renderer: 'canvas' });
        chart.on('dataZoom', debounceMarks);
        applyPeriod('day');
        showStatus(env.code === 2 || env.msg ? env.msg : '');
        window.addEventListener('resize', function () { chart.resize(); });
      })
      .catch(function (err) { showStatus('网络错误：' + err, true); });
  }

  var markTimer = null;
  function debounceMarks(evt) {
    if (markTimer) clearTimeout(markTimer);
    markTimer = setTimeout(function () {
      var opt = chart && chart.getOption();
      if (!opt || !opt.dataZoom || !opt.dataZoom.length) return;
      var dz = opt.dataZoom[0];
      if (dz.start == null || dz.end == null) return;
      chart.setOption({ series: [{ name: '日K', markPoint: markFor({ start: dz.start, end: dz.end }) }] });
    }, 100);
  }

  document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('.kline-tab').forEach(function (btn) {
      btn.addEventListener('click', function () { applyPeriod(btn.dataset.period); });
    });
    load();
  });
})();
