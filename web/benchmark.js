/* 保额保费基准 —— 前端
 *
 * 硬约束：输出价格区间与样本出处。不排序、不评分、不评价优劣。 lint:ignore
 * 区间只呈现上下界与中位数，不做任何「谁更好」的视觉暗示（无颜色偏向、无加粗排序）。
 */

'use strict';

let ALL = null;
let CURRENT = null;

const $ = (id) => document.getElementById(id);

function esc(s) {
  return String(s ?? '').replace(/[&<>"']/g, (c) =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

const money = (n) => Number(n).toLocaleString('zh-CN');

/* --- 与后端 Query 一一对应；空值表示不限 --- */
function readQuery() {
  const termYearsWrap = $('term-years-wrap');
  termYearsWrap.hidden = $('q-term').value !== 'term_N_years';
  return {
    age: Number($('q-age').value),
    gender: $('q-gender').value,
    sumInsured: Math.round(Number($('q-sum').value) * 10000),
    term: $('q-term').value,
    termYears: $('q-term').value === 'term_N_years' ? Number($('q-term-years').value) : null,
    pay: Number($('q-pay').value),
    ptype: $('q-type').value,
  };
}

function matches(q, c) {
  if (!(c.ageFrom <= q.age && q.age <= c.ageTo)) return false;
  if (c.gender !== q.gender) return false;
  if (c.sumInsured !== q.sumInsured) return false;
  if (c.coverageTerm !== q.term) return false;
  if (q.term === 'term_N_years' && c.termYears !== q.termYears) return false;
  if (c.payTerm !== q.pay) return false;
  if (c.productType !== q.ptype) return false;
  return true;
}

/* --- 渲染 --- */

function render(groups) {
  const box = $('results');
  box.innerHTML = '';

  if (!groups.length) {
    $('empty').hidden = false;
    $('empty').querySelector('p').innerHTML =
      '没有符合这组条件的基准组。库内现有：' +
      escapeLabels() + '。填写模板见 <code>data/benchmarks/_template.json</code>。';
    return;
  }
  $('empty').hidden = true;

  groups.forEach((g) => box.insertAdjacentHTML('beforeend', card(g)));
}

function escapeLabels() {
  const labels = CURRENT ? CURRENT.map((g) => g.label) : [];
  return labels.length ? labels.map((l) => `<code>${esc(l)}</code>`).join('、') : '（无）';
}

function card(g) {
  const c = g.condition;
  const notes = [];
  if (!g.reliable) {
    notes.push(`<span class="lbl">样本量：</span>仅 ${g.sampleCount} 条，低于 3 条，本区间不足以代表市场。`);
  }
  (g.warnings || []).forEach((w) => notes.push(`<span class="lbl">提示：</span>${esc(w)}`));
  (g.caveats || []).forEach((v) => notes.push(`<span class="lbl">注意：</span>${esc(v)}`));

  const rows = g.samples.map((s, i) =>
    `<tr>
      <td>${money(s.annualPremium)}</td>
      <td>${esc(s.insurerName)}</td>
      <td>${esc(s.productName)}${s.isInLibrary ? '<span class="lib-tag">已收录</span>' : ''}</td>
      <td><span class="premium-cell" data-sample="${i}" tabindex="0" role="button">查看出处</span></td>
    </tr>`).join('');

  return `
    <article class="bm-card${g.reliable ? '' : ' unreliable'}">
      <div class="bm-head">
        <h3>${esc(g.label)}</h3>
        <span class="meta">${g.sampleCount} 个样本 · 核验 ${esc(g.verifiedAt)} · ${esc(g.verifier)}</span>
      </div>

      <div class="bm-stats">
        <div class="stat primary">
          <div class="k">年保费区间</div>
          <div class="v">${money(g.low)} – ${money(g.high)}<small>元</small></div>
        </div>
        <div class="stat">
          <div class="k">中位数</div>
          <div class="v">${money(g.median)}<small>元/年</small></div>
        </div>
        <div class="stat">
          <div class="k">均值</div>
          <div class="v">${money(g.mean)}<small>元/年</small></div>
        </div>
        <div class="stat">
          <div class="k">保额 / 中位保费</div>
          <div class="v">${Math.round(g.leverage)}<small>倍</small></div>
        </div>
        <div class="stat">
          <div class="k">总保费（${c.payTerm}年缴）</div>
          <div class="v">${money(g.median * c.payTerm)}<small>元</small></div>
        </div>
      </div>

      <div class="bm-body">
        <table class="bm-samples">
          <thead><tr><th>年保费（元）</th><th>公司</th><th>产品</th><th>出处</th></tr></thead>
          <tbody>${rows}</tbody>
        </table>
      </div>

      ${notes.length ? `<div class="bm-notes">${notes.map((n) => `<p>${n}</p>`).join('')}</div>` : ''}
      <div class="bm-scope"><span class="lbl">样本来源说明：</span>${esc(g.scopeNote)}</div>
    </article>`;
}

/* --- 样本出处弹层 --- */

let MATCHED = [];   // 当前查询命中的基准组，样本下标以它为基准

function showSample(idx) {
  const g = MATCHED[idx];
  if (!g) return;
  const s = g.samples[idx];
  const doc = s.source.documents[0];
  const tier = { 1: '官网披露', 2: '中保协产品库', 3: '官方App截图' }[doc.tier] || doc.tier;

  $('sample-name').textContent = `${s.insurerName} · ${s.productName}`;
  $('sample-body').innerHTML = `
    <div class="trace-doc">年保费 <strong>${money(s.annualPremium)} 元</strong></div>
    <div class="trace-doc">
      费率表：${esc(doc.title)}
      <span class="trace-tier">${tier}</span>
    </div>
    <blockquote class="trace-quote">${esc(s.source.premiumQuote)}</blockquote>
    <a class="trace-link" href="${esc(doc.url)}" target="_blank" rel="noopener noreferrer">查看原始文件 ↗</a>
    <p class="muted small" style="margin-top:14px">
      核验日期 ${esc(s.source.verifiedAt)} · 核对人 ${esc(s.source.verifier)}
    </p>`;
  $('sample-popover').hidden = false;
}

/* --- 启动 --- */

async function boot() {
  let data;
  try {
    const res = await fetch('data/benchmarks.json');
    if (!res.ok) throw new Error(res.status);
    data = await res.json();
  } catch {
    $('empty').hidden = false;
    $('results').innerHTML = '';
    $('empty').querySelector('p').innerHTML =
      '尚未执行 <code>python -m insurance.benchmark --out web/data/benchmarks.json</code>，或库内没有基准数据。';
    return;
  }

  CURRENT = data.groups || [];
  $('disclaimer-text').textContent = data.disclaimer || '';
  $('footer-disclaimer').textContent = data.disclaimer || '';

  const run = () => {
    const q = readQuery();
    MATCHED = CURRENT.filter((g) => matches(q, g.condition));
    render(MATCHED);
  };

  $('q-run').addEventListener('click', run);
  $('q-term').addEventListener('change', run);
  $('q-clear').addEventListener('click', () => {
    ['q-age', 'q-sum', 'q-pay'].forEach((id) => { $(id).value = ''; });
    $('q-gender').value = ''; $('q-term').value = ''; $('q-type').value = '';
    $('term-years-wrap').hidden = true;
    $('results').innerHTML = '';
    $('empty').hidden = true;
  });

  $('results').addEventListener('click', (e) => {
    const el = e.target.closest('.premium-cell');
    if (el) showSample(Number(el.dataset.sample));
  });
  $('results').addEventListener('keydown', (e) => {
    if (e.key === 'Enter' || e.key === ' ') {
      const el = e.target.closest('.premium-cell');
      if (el) { e.preventDefault(); showSample(Number(el.dataset.sample)); }
    }
  });

  document.querySelector('.popover-close').addEventListener('click', () => {
    $('sample-popover').hidden = true;
  });
  $('sample-popover').addEventListener('click', (e) => {
    if (e.target.id === 'sample-popover') e.currentTarget.hidden = true;
  });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') $('sample-popover').hidden = true;
  });

  // 首屏即按表单当前条件筛选，避免「表单写着 A、结果列着 B」的错觉
  run();
}

boot();