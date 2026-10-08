/* 少儿险条款事实对照 —— 前端渲染
 *
 * 硬约束（见 docs/01-合规边界.md）：
 *   - 不排序、不评分、不做优劣判断。产品按备案名称字典序固定排列。 lint:ignore
 *   - 不提供任何投保/报价/核保外链。
 *   - 每个数值都可展开看到条款原文出处。
 */

'use strict';

let DATA = null;
let currentCat = 'accident';
let currentAge = 0;

/* ---------- 字段定义：每行对应一个 fieldTrace 路径 ---------- */

const FORMATS = {
  money: (v) => (typeof v === 'number' ? v.toLocaleString('zh-CN') + ' 元' : '—'),
  num:   (v) => (typeof v === 'number' ? String(v) : '—'),
  bool:  (v) => (v === true ? '是' : v === false ? '否' : '未明确'),
  text:  (v) => (v === null || v === undefined || v === '' ? '未明确' : String(v)),
  renew: (v) => ({ guaranteed_fixed: '保证续保（固定年期）',
                   guaranteed_limited: '保证续保（有条件）',
                   not_guaranteed: '不保证续保' }[v] || '未明确'),
};

const RENEW_LABEL = (y) => (y === 0 ? '不保证续保' : y === null ? '未明确' : `保证续保 ${y} 年`);

const LAYOUT = {
  accident: [
    { group: '保障责任' },
    { label: '意外身故/伤残保额', path: 'coverage.accident.death.limit', fmt: 'money' },
    { label: '未成年人身故监管上限', path: 'coverage.accident.death.regulationCap.applies', fmt: 'bool' },
    { label: '监管上限表述', path: 'coverage.accident.death.regulationCap.rule', fmt: 'text' },
    { label: '意外医疗保额', path: 'coverage.accident.medical.limit', fmt: 'money' },
    { label: '意外医疗免赔额', path: 'coverage.accident.medical.deductible', fmt: 'money' },
    { label: '意外医疗报销比例', path: 'coverage.accident.medical.reimburseRatio', fmt: 'text' },
    { label: '社保外用药', path: 'coverage.accident.medical.outOfCatalogDrug', fmt: 'bool', critical: true },
    { label: '门急诊可报销', path: 'coverage.accident.medical.outpatientCovered', fmt: 'bool' },
    { label: '单次住院天数上限', path: 'coverage.accident.medical.inHospitalDaysLimit', fmt: 'num' },
    { group: '住院津贴' },
    { label: '津贴标准', path: 'coverage.accident.hospitalizationAllowance.perDay', fmt: 'money' },
    { label: '津贴最长天数', path: 'coverage.accident.hospitalizationAllowance.maxDays', fmt: 'num' },
    { group: '其他责任与条款要点' },
    { label: '特定意外额外责任', path: 'coverage.accident.specialAccidents', fmt: 'list' },
    { label: '先天/遗传性疾病除外', path: 'healthDisclosure.hasCongenitalExclusion', fmt: 'bool', critical: true },
  ],
  medical: [
    { group: '保障责任' },
    { label: '一般医疗保额', path: 'coverage.medical.general.limit', fmt: 'money' },
    { label: '重大疾病医疗保额', path: 'coverage.medical.criticalIllness.limit', fmt: 'money' },
    { label: '免赔额', path: 'coverage.medical.deductible.amount', fmt: 'money', critical: true },
    { label: '免赔额口径', path: 'coverage.medical.deductible.scope',
      fmt: (v) => ({ annual: '年度免赔', per_claim: '每次事故免赔', family_shared: '家庭共享免赔' }[v] || '未明确') },
    { label: '赔付比例', path: 'coverage.medical.general.reimburseRatio', fmt: 'text' },
    { label: '等待期', path: 'coverage.medical.waitingPeriodDays', fmt: 'num' },
    { label: '医院范围', path: 'coverage.medical.hospitalScope', fmt: 'text' },
    { group: '续保条件（少儿医疗险最关键）' },
    { label: '续保类型', path: 'coverage.medical.renewal.type', fmt: 'renew', critical: true },
    { label: '条款原文表述', path: 'coverage.medical.renewal.text', fmt: 'text', critical: true },
    { label: '保证续保年数', special: 'renewalYears', critical: true },
    { label: '续保补充说明', path: 'underwriting.renewalNote', fmt: 'text' },
    { group: '外延责任' },
    { label: '社保外用药', path: 'coverage.medical.outOfCatalogDrug', fmt: 'bool' },
    { label: '质子重离子', path: 'coverage.medical.specialtyDrug', fmt: 'bool' },
    { label: '院外购药', path: 'coverage.medical.outpatientDrugPurchase', fmt: 'bool' },
    { label: '住院费用垫付', path: 'coverage.medical.hospitalStayAdvance', fmt: 'bool' },
    { label: '特需/国际部', path: 'coverage.medical.specialWard', fmt: 'bool' },
  ],
};

/* ---------- 工具 ---------- */

function get(obj, path) {
  return path.split('.').reduce((o, k) => (o === undefined || o === null ? o : o[k]), obj);
}

function fmtValue(row, product) {
  if (row.special === 'renewalYears') {
    const y = get(product, 'underwriting.guaranteedRenewalYears');
    return { display: RENEW_LABEL(y), raw: y };
  }
  const raw = get(product, row.path);
  const fn = FORMATS[row.fmt] || FORMATS.text;
  if (row.fmt === 'bool' && typeof raw === 'boolean') {
    return { display: fn(raw), raw, cls: raw ? 'yes' : 'no' };
  }
  if (row.fmt === 'list') {
    return { display: Array.isArray(raw) && raw.length ? raw.join('、') : '无', raw };
  }
  return { display: fn(raw), raw };
}

function premiumFor(product, age) {
  const m = get(product, 'premium.byInsuredAge') || {};
  return m[String(age)] ?? m[Object.keys(m)[0]] ?? null;
}

/* ---------- 渲染 ---------- */

function render() {
  const items = DATA.products.filter((p) => p.product.category === currentCat);
  const head = document.getElementById('head-row');
  const body = document.getElementById('body-rows');

  head.innerHTML = '<th>对比项</th>';
  items.forEach(({ product, trace }) => {
    const th = document.createElement('th');
    th.className = 'prod-head';
    const fresh = { fresh: '已复核', aging: '待复核', expired: '已过期' }[trace.freshness];
    th.innerHTML =
      `<div class="prod-name">${esc(product.name)}</div>` +
      `<div class="prod-insurer">${esc(product.insurer.name)}</div>` +
      `<div class="prod-meta"><span class="badge ${trace.freshness}">${fresh}</span></div>` +
      (product.status === 'delisted'
        ? `<span class="delisted-mark">已停售 ${esc(product.delistedOn || '')}</span>` : '');
    head.appendChild(th);
  });

  body.innerHTML = '';

  // 保费行：随年龄选择变化
  const prem = document.createElement('tr');
  prem.className = 'field-row';
  prem.innerHTML = `<th>年保费（${currentAge} 岁）</th>`;
  items.forEach(({ product }) => {
    const p = premiumFor(product, currentAge);
    prem.insertAdjacentHTML('beforeend',
      `<td><span class="value" data-path="premium.byInsuredAge">${p === null ? '费率表无此年龄' : p.toLocaleString('zh-CN') + ' 元'}</span></td>`);
  });
  body.appendChild(prem);

  (LAYOUT[currentCat] || []).forEach((row) => {
    if (row.group) {
      const g = document.createElement('tr');
      g.className = 'group-row';
      g.innerHTML = `<th colspan="${items.length + 1}">${esc(row.group)}</th>`;
      body.appendChild(g);
      return;
    }
    const tr = document.createElement('tr');
    tr.className = 'field-row' + (row.critical ? ' critical-row' : '');
    tr.innerHTML = `<th>${esc(row.label)}</th>`;
    items.forEach(({ product }) => {
      const v = fmtValue(row, product);
      const tracePath = row.special === 'renewalYears'
        ? 'underwriting.guaranteedRenewalYears' : row.path;
      // fieldTrace 的键本身就是点号路径，必须整串直查，不能用 get() 拆分
      const hasTrace = Object.prototype.hasOwnProperty.call(product.source.fieldTrace, tracePath);
      const cls = ['value'];
      if (v.cls) cls.push(v.cls);
      if (v.raw === null || v.raw === undefined) cls.push('undefined');
      if (!hasTrace) cls.push('no-trace');
      tr.insertAdjacentHTML('beforeend',
        `<td><span class="${cls.join(' ')}" data-path="${esc(tracePath)}"` +
        (hasTrace ? ' tabindex="0" role="button"' : '') + `>${esc(v.display)}</span></td>`);
    });
    body.appendChild(tr);
  });

  // 停售产品整体置灰
  if (items.some(({ product }) => product.status === 'delisted')) {
    body.classList.add('has-delisted');
  }
}

function renderAgeOptions() {
  const sel = document.getElementById('age-select');
  const items = DATA.products.filter((p) => p.product.category === currentCat);
  const ages = new Set();
  items.forEach(({ product }) => {
    Object.keys(get(product, 'premium.byInsuredAge') || {})
      .forEach((a) => ages.add(Number(a)));
  });
  const list = [...ages].sort((a, b) => a - b);
  if (!list.length) { sel.innerHTML = ''; return; }
  sel.innerHTML = list.map((a) => `<option value="${a}">${a} 岁</option>`).join('');
  if (currentAge > Math.max(...list)) currentAge = Math.min(...list);
  sel.value = currentAge;
  const hint = document.getElementById('age-hint');
  hint.textContent = list.length > 1 ? '切换年龄查看费率表对应值' : '该产品在费率表中仅此一个年龄区间';
}

/* ---------- 溯源弹层 ---------- */

function showTrace(path) {
  const items = DATA.products.filter((p) => p.product.category === currentCat);
  const pop = document.getElementById('trace-popover');
  document.getElementById('popover-path').textContent = path;
  const ft = items[0]?.product.source.fieldTrace || {};
  const t = Object.prototype.hasOwnProperty.call(ft, path) ? ft[path] : null;

  if (!t) {
    document.getElementById('popover-body').innerHTML =
      '<p class="muted">本字段无溯源记录。若在正式库中看到此提示，说明数据录入有误，请反馈。</p>';
    pop.hidden = false;
    return;
  }

  // 同一字段在不同产品里可能指向不同文档，全部列出。
  const rows = items.map(({ product }) => {
    const map = product.source.fieldTrace || {};
    if (!Object.prototype.hasOwnProperty.call(map, path)) return '';
    const tr = map[path];
    const doc = product.source.documents[tr.docIndex];
    if (!doc) return '';
    const tier = { 1: '官网披露', 2: '中保协产品库', 3: '官方App截图' }[tr.tier] || tr.tier;
    return (
      `<div style="margin-bottom:16px">` +
      `<div class="prod-name" style="margin-bottom:6px">${esc(product.name)}</div>` +
      `<div class="trace-doc">${esc(doc.title)}` +
        (tr.page ? ` · 第 ${tr.page} 页` : '') +
        `<span class="trace-tier">${tier}</span></div>` +
      `<blockquote class="trace-quote">${esc(tr.quote)}</blockquote>` +
      `<a class="trace-link" href="${esc(doc.url)}" target="_blank" rel="noopener noreferrer">查看原始文件 ↗</a>` +
      `</div>`
    );
  }).join('');

  document.getElementById('popover-body').innerHTML = rows;
  pop.hidden = false;
}

/* ---------- 转义 ---------- */
function esc(s) {
  return String(s ?? '').replace(/[&<>"']/g, (c) =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

/* ---------- 启动 ---------- */

async function boot() {
  let data;
  try {
    const res = await fetch('data/products.json');
    if (!res.ok) throw new Error(res.status);
    data = await res.json();
  } catch {
    document.getElementById('empty-state').hidden = false;
    document.getElementById('empty-state').querySelector('p')
      .innerHTML = '尚未执行 <code>python -m insurance.build</code>，或库内没有通过校验的数据。';
    return;
  }

  DATA = data;
  document.getElementById('disclaimer-text').textContent = data.disclaimer;
  document.getElementById('footer-disclaimer').textContent = data.disclaimer;
  document.getElementById('snapshot').textContent =
    `数据快照：${data.snapshotDate} · 库内 ${data.count} 个产品 · 每字段均标注条款出处`;

  const cats = [...new Set(data.products.map((p) => p.product.category))];
  if (!cats.length) {
    document.getElementById('empty-state').hidden = false;
    return;
  }

  ['tabs', 'filter-bar', 'table-wrap', 'legend'].forEach((id) => {
    document.getElementById(id).hidden = false;
  });

  document.querySelectorAll('.tab').forEach((btn) => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.tab').forEach((b) => b.classList.remove('active'));
      btn.classList.add('active');
      currentCat = btn.dataset.cat;
      renderAgeOptions();
      render();
    });
  });

  document.getElementById('age-select').addEventListener('change', (e) => {
    currentAge = Number(e.target.value);
    render();
  });

  document.getElementById('body-rows').addEventListener('click', (e) => {
    const el = e.target.closest('.value[tabindex]');
    if (el) showTrace(el.dataset.path);
  });
  document.getElementById('body-rows').addEventListener('keydown', (e) => {
    if (e.key === 'Enter' || e.key === ' ') {
      const el = e.target.closest('.value[tabindex]');
      if (el) { e.preventDefault(); showTrace(el.dataset.path); }
    }
  });

  document.querySelector('.popover-close').addEventListener('click', () => {
    document.getElementById('trace-popover').hidden = true;
  });
  document.getElementById('trace-popover').addEventListener('click', (e) => {
    if (e.target.id === 'trace-popover') e.currentTarget.hidden = true;
  });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') document.getElementById('trace-popover').hidden = true;
  });

  renderAgeOptions();
  render();
}

boot();