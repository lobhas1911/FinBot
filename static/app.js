let currentTicker = null;
let chartInstances = {};

// ── Load Company ─────────────────────────────────────────────────

async function loadCompany() {
  const input = document.getElementById('companyInput');
  const company = input.value.trim();
  if (!company) return;
  await _doLoad(company);
}

async function quickLoad(ticker) {
  document.getElementById('companyInput').value = ticker;
  await _doLoad(ticker);
}

async function refreshCompany() {
  if (!currentTicker) return;
  await fetch(`/api/session/${currentTicker}`, { method: 'DELETE' });
  await _doLoad(currentTicker);
}

async function _doLoad(company) {
  showLoading(true, `Fetching financial data for "${company}"...`);
  hideWelcome();

  try {
    const res = await fetch(`/api/load/${encodeURIComponent(company)}`);
    const data = await res.json();

    if (!res.ok) {
      showLoading(false);
      alert(data.detail || 'Failed to load company data.');
      return;
    }

    currentTicker = data.ticker;
    document.getElementById('companyBadge').textContent = data.ticker;
    document.getElementById('companyInput').value = data.name || data.ticker;

    renderSources(data.sources);
    renderInfo(data.info);
    renderRatios(data.ratios);
    renderCharts(data.charts);
    renderSpecs(data.info, data.ratios);

    showLoading(false);
    showTabs();
    switchTab('analysis');
    enableChat();
    generateAnalysis();

  } catch (e) {
    showLoading(false);
    alert('Network error: ' + e.message);
  }
}


// ── Analysis ─────────────────────────────────────────────────────

async function generateAnalysis() {
  if (!currentTicker) return;
  const btn = document.getElementById('analyzeBtn');
  const content = document.getElementById('analysisContent');

  btn.disabled = true;
  btn.textContent = 'Generating...';
  content.innerHTML = '<p class="muted center">⏳ Analyzing financial data with AI...</p>';

  try {
    const res = await fetch(`/api/analyze/${encodeURIComponent(currentTicker)}`);
    const text = await res.text();
    let data;
    try { data = JSON.parse(text); } catch(e) {
      content.innerHTML = `<p class="muted">Server error. Check terminal for details.</p>`;
      btn.disabled = false; btn.textContent = 'Regenerate';
      return;
    }
    if (!res.ok) {
      content.innerHTML = `<p class="muted">Error: ${data.detail}</p>`;
    } else {
      content.innerHTML = formatAnalysis(data.analysis);
    }
  } catch (e) {
    content.innerHTML = `<p class="muted">Error: ${e.message}</p>`;
  }

  btn.disabled = false;
  btn.textContent = 'Regenerate';
}

function formatAnalysis(text) {
  // Convert markdown-style headers and bold to HTML
  return text
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/^#{1,3}\s+(.+)$/gm, '<h3>$1</h3>')
    .replace(/\n/g, '<br>');
}


// ── Charts ───────────────────────────────────────────────────────

function renderCharts(charts) {
  const grid = document.getElementById('chartsGrid');
  grid.innerHTML = '';

  // Destroy old chart instances
  Object.values(chartInstances).forEach(c => c.destroy());
  chartInstances = {};

  const colorSets = {
    bar: { bg: 'rgba(35, 134, 54, 0.7)', border: '#2ea043' },
    line: { bg: 'rgba(31, 111, 235, 0.15)', border: '#58a6ff' },
  };

  Object.entries(charts).forEach(([key, chart]) => {
    const card = document.createElement('div');
    card.className = 'chart-card';
    card.innerHTML = `<div class="chart-title">${chart.title}</div><canvas id="chart_${key}"></canvas>`;
    grid.appendChild(card);

    const ctx = document.getElementById(`chart_${key}`).getContext('2d');
    const colors = colorSets[chart.type] || colorSets.bar;

    chartInstances[key] = new Chart(ctx, {
      type: chart.type,
      data: {
        labels: chart.labels,
        datasets: [{
          label: chart.title,
          data: chart.values,
          backgroundColor: colors.bg,
          borderColor: colors.border,
          borderWidth: 2,
          fill: chart.type === 'line',
          tension: 0.4,
          pointRadius: chart.type === 'line' ? 3 : 0,
        }]
      },
      options: {
        responsive: true,
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: (ctx) => {
                const v = ctx.parsed.y;
                return ' ' + formatNumber(v);
              }
            }
          }
        },
        scales: {
          x: {
            ticks: { color: '#9ca3af', maxRotation: 45, font: { size: 10 } },
            grid: { color: 'rgba(0,0,0,0.04)' }
          },
          y: {
            ticks: {
              color: '#9ca3af',
              font: { size: 10 },
              callback: (v) => formatNumber(v)
            },
            grid: { color: 'rgba(0,0,0,0.04)' }
          }
        }
      }
    });
  });
}

function formatNumber(v) {
  if (v === null || v === undefined) return 'N/A';
  const abs = Math.abs(v);
  if (abs >= 1e12) return (v / 1e12).toFixed(2) + 'T';
  if (abs >= 1e9)  return (v / 1e9).toFixed(2) + 'B';
  if (abs >= 1e6)  return (v / 1e6).toFixed(2) + 'M';
  if (abs >= 1e3)  return (v / 1e3).toFixed(1) + 'K';
  return v.toFixed(2);
}


// ── Chat ─────────────────────────────────────────────────────────

async function sendChat() {
  const input = document.getElementById('chatInput');
  const question = input.value.trim();
  if (!question || !currentTicker) return;

  input.value = '';
  appendMsg('user', question);
  const typing = appendTyping();

  try {
    const res = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ticker: currentTicker, question })
    });
    const text = await res.text();
    typing.remove();
    let data;
    try { data = JSON.parse(text); } catch(e) {
      appendMsg('bot', '⚠ Server error. Check terminal for details.');
      return;
    }
    if (!res.ok) {
      appendMsg('bot', '⚠ ' + (data.detail || 'Error'));
    } else {
      appendMsg('bot', data.answer);
    }
  } catch (e) {
    typing.remove();
    appendMsg('bot', '⚠ Network error: ' + e.message);
  }
}

function askSuggestion(el) {
  document.getElementById('chatInput').value = el.textContent;
  sendChat();
}

function appendMsg(role, text) {
  const msgs = document.getElementById('messages');
  const welcome = msgs.querySelector('.welcome');
  if (welcome) welcome.remove();

  const div = document.createElement('div');
  div.className = `msg ${role}`;
  const formatted = text
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\n/g, '<br>');
  div.innerHTML = `<div class="msg-bubble">${formatted}</div>`;
  msgs.appendChild(div);
  msgs.scrollTop = msgs.scrollHeight;
  return div;
}

function appendTyping() {
  const msgs = document.getElementById('messages');
  const div = document.createElement('div');
  div.className = 'msg bot';
  div.innerHTML = `<div class="msg-bubble"><div class="typing"><span></span><span></span><span></span></div></div>`;
  msgs.appendChild(div);
  msgs.scrollTop = msgs.scrollHeight;
  return div;
}


// ── Sidebar Rendering ─────────────────────────────────────────────

function renderSources(sources) {
  const list = document.getElementById('sourceList');
  list.innerHTML = '';

  // Separate loaded data from external links
  const dataItems = sources.filter(s => s.status === 'loaded');
  const linkItems = sources.filter(s => s.status === 'link');
  const failedItems = sources.filter(s => s.status === 'failed');

  if (dataItems.length) {
    const label = document.createElement('div');
    label.className = 'source-group-label';
    label.textContent = 'FETCHED DATA';
    list.appendChild(label);

    dataItems.forEach(s => {
      const div = document.createElement('div');
      div.className = 'source-item';
      div.innerHTML = `
        <div class="source-dot dot-loaded"></div>
        <div class="source-name">${s.name}</div>`;
      list.appendChild(div);
    });
  }

  if (linkItems.length) {
    const label = document.createElement('div');
    label.className = 'source-group-label';
    label.style.marginTop = '10px';
    label.textContent = 'FINANCIAL DOCUMENTS';
    list.appendChild(label);

    linkItems.forEach(s => {
      const div = document.createElement('div');
      div.className = 'source-item source-link';
      div.innerHTML = `
        <div class="source-dot dot-link"></div>
        <div>
          <a class="source-link-name" href="${s.url}" target="_blank" rel="noopener">${s.name}</a>
          <div class="source-type">${s.type}</div>
        </div>`;
      list.appendChild(div);
    });
  }

  if (failedItems.length) {
    failedItems.forEach(s => {
      const div = document.createElement('div');
      div.className = 'source-item';
      div.innerHTML = `
        <div class="source-dot dot-failed"></div>
        <div class="source-name muted">${s.name}</div>`;
      list.appendChild(div);
    });
  }
}

function renderInfo(info) {
  const panel = document.getElementById('infoPanel');
  const content = document.getElementById('infoContent');
  if (!info || !info.name) return;

  const rows = [
    ['Name', info.name],
    ['Sector', info.sector],
    ['Industry', info.industry],
    ['Country', info.country],
    ['Currency', info.currency],
    ['Exchange', info.exchange],
    ['Employees', info.employees ? info.employees.toLocaleString() : null],
    ['Market Cap', info.market_cap ? formatNumber(info.market_cap) : null],
  ];

  content.innerHTML = rows
    .filter(([, v]) => v && v !== 'N/A')
    .map(([l, v]) => `<div class="info-row"><span class="info-label">${l}</span><span class="info-value">${v}</span></div>`)
    .join('');

  panel.style.display = 'block';
}

function renderRatios(ratios) {
  const panel = document.getElementById('ratioPanel');
  const content = document.getElementById('ratioContent');
  if (!ratios) return;

  const rows = [
    ['Price', ratios.current_price],
    ['P/E Ratio', ratios.pe_ratio],
    ['Fwd P/E', ratios.forward_pe],
    ['P/B Ratio', ratios.pb_ratio],
    ['Debt/Equity', ratios.debt_to_equity],
    ['Current Ratio', ratios.current_ratio],
    ['ROE', ratios.roe != null ? (ratios.roe * 100).toFixed(2) + '%' : null],
    ['Profit Margin', ratios.profit_margin != null ? (ratios.profit_margin * 100).toFixed(2) + '%' : null],
    ['Rev Growth', ratios.revenue_growth != null ? (ratios.revenue_growth * 100).toFixed(2) + '%' : null],
    ['Div Yield', ratios.dividend_yield != null ? (ratios.dividend_yield * 100).toFixed(2) + '%' : null],
    ['Beta', ratios.beta],
    ['52W High', ratios['52w_high']],
    ['52W Low', ratios['52w_low']],
  ];

  content.innerHTML = rows
    .filter(([, v]) => v != null)
    .map(([l, v]) => `<div class="ratio-row"><span class="ratio-label">${l}</span><span class="ratio-value">${v}</span></div>`)
    .join('');

  panel.style.display = 'block';
}


function renderSpecs(info, ratios) {
  const content = document.getElementById('specsContent');
  if (!info || !info.name) return;

  const infoRows = [
    ['Company Name', info.name],
    ['Sector', info.sector],
    ['Industry', info.industry],
    ['Country', info.country],
    ['Currency', info.currency],
    ['Exchange', info.exchange],
    ['Employees', info.employees ? info.employees.toLocaleString() : null],
    ['Market Cap', info.market_cap ? formatNumber(info.market_cap) : null],
    ['Website', info.website ? `<a href="${info.website}" target="_blank" rel="noopener">${info.website}</a>` : null],
  ].filter(([, v]) => v && v !== 'N/A');

  const ratioRows = [
    ['Current Price', ratios.current_price],
    ['P/E Ratio (Trailing)', ratios.pe_ratio],
    ['P/E Ratio (Forward)', ratios.forward_pe],
    ['Price / Book', ratios.pb_ratio],
    ['Price / Sales', ratios.ps_ratio],
    ['Debt / Equity', ratios.debt_to_equity],
    ['Current Ratio', ratios.current_ratio],
    ['Quick Ratio', ratios.quick_ratio],
    ['Return on Equity', ratios.roe != null ? (ratios.roe * 100).toFixed(2) + '%' : null],
    ['Return on Assets', ratios.roa != null ? (ratios.roa * 100).toFixed(2) + '%' : null],
    ['Net Profit Margin', ratios.profit_margin != null ? (ratios.profit_margin * 100).toFixed(2) + '%' : null],
    ['Operating Margin', ratios.operating_margin != null ? (ratios.operating_margin * 100).toFixed(2) + '%' : null],
    ['Gross Margin', ratios.gross_margin != null ? (ratios.gross_margin * 100).toFixed(2) + '%' : null],
    ['Revenue Growth (YoY)', ratios.revenue_growth != null ? (ratios.revenue_growth * 100).toFixed(2) + '%' : null],
    ['Earnings Growth (YoY)', ratios.earnings_growth != null ? (ratios.earnings_growth * 100).toFixed(2) + '%' : null],
    ['Dividend Yield', ratios.dividend_yield != null ? (ratios.dividend_yield * 100).toFixed(2) + '%' : null],
    ['Beta', ratios.beta],
    ['52-Week High', ratios['52w_high']],
    ['52-Week Low', ratios['52w_low']],
  ].filter(([, v]) => v != null);

  const descHtml = info.description
    ? `<div class="specs-desc">${info.description}</div>` : '';

  content.innerHTML = `
    ${descHtml}
    <div class="specs-grid">
      <div class="specs-card">
        <div class="specs-card-title">Company Profile</div>
        ${infoRows.map(([l, v]) => `
          <div class="specs-row">
            <span class="specs-label">${l}</span>
            <span class="specs-value">${v}</span>
          </div>`).join('')}
      </div>
      <div class="specs-card">
        <div class="specs-card-title">Valuation & Ratios</div>
        ${ratioRows.map(([l, v]) => `
          <div class="specs-row">
            <span class="specs-label">${l}</span>
            <span class="specs-value specs-value-highlight">${v}</span>
          </div>`).join('')}
      </div>
    </div>`;
}


// ── UI Helpers ────────────────────────────────────────────────────

function showLoading(show, msg = '') {
  const bar = document.getElementById('loadingBar');
  bar.style.display = show ? 'flex' : 'none';
  if (msg) document.getElementById('loadingMsg').textContent = msg;
}

function hideWelcome() {
  const ws = document.getElementById('welcomeScreen');
  if (ws) ws.style.display = 'none';
}

function showTabs() {
  document.getElementById('tabs').style.display = 'flex';
}

function switchTab(name) {
  document.querySelectorAll('.tab-content').forEach(el => el.style.display = 'none');
  document.querySelectorAll('.tab').forEach(el => el.classList.remove('active'));

  document.getElementById(`tab-${name}`).style.display = 'flex';
  document.getElementById(`tab-${name}`).style.flexDirection = 'column';

  const tabs = document.querySelectorAll('.tab');
  const names = ['analysis', 'charts', 'specs', 'chat'];
  tabs[names.indexOf(name)]?.classList.add('active');
}

function enableChat() {
  document.getElementById('chatInput').disabled = false;
  document.getElementById('sendBtn').disabled = false;
}
