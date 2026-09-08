// 서버가 정적 페이지를 함께 서빙하면 같은 origin을 사용하고,
// file://로 직접 열었을 때만 로컬 기본 포트로 폴백한다.
const API_BASE = location.protocol.startsWith('http')
    ? `${location.origin}/api`
    : 'http://127.0.0.1:8000/api';

let historyChartInstance = null;
let futureChartInstance = null;
let currentHistoryData = null;
let currentForecastData = null;

// DOM Elements
const apiStatus = document.getElementById('api-status');
const partSelect = document.getElementById('part-select');
const horizonSelect = document.getElementById('horizon-select');
const scenarioSlider = document.getElementById('scenario-slider');
const scenarioValue = document.getElementById('scenario-value');
const predictBtn = document.getElementById('predict-btn');

// KPI Elements
const kpiWape = document.getElementById('kpi-wape');
const kpiAvg = document.getElementById('kpi-avg');
const kpiCv = document.getElementById('kpi-cv');
const kpiFutureSum = document.getElementById('kpi-future-sum');
const kpiBaseSum = document.getElementById('kpi-base-sum');
const kpiLeadTime = document.getElementById('kpi-leadtime');
const metricsTableBody = document.getElementById('metrics-table-body');
const statsTableBody = document.getElementById('stats-table-body');
const evalNote = document.getElementById('eval-note');

const tableBody = document.getElementById('forecast-table-body');

// Initialize
async function init() {
    await checkHealth();
    await loadParts();
    
    scenarioSlider.addEventListener('input', (e) => {
        scenarioValue.textContent = `${e.target.value > 0 ? '+' : ''}${e.target.value}%`;
    });

    predictBtn.addEventListener('click', handlePredict);
}

async function checkHealth() {
    try {
        const res = await fetch(`${API_BASE}/health`);
        if (res.ok) {
            apiStatus.textContent = 'API Connected';
            apiStatus.className = 'badge status-badge connected';
        } else {
            throw new Error('Not OK');
        }
    } catch (err) {
        apiStatus.textContent = 'API Error';
        apiStatus.className = 'badge status-badge error';
        console.error(err);
    }
}

async function loadParts() {
    try {
        const res = await fetch(`${API_BASE}/parts`);
        const data = await res.json();
        
        partSelect.innerHTML = '';
        if (data.parts && data.parts.length > 0) {
            data.parts.forEach(p => {
                const opt = document.createElement('option');
                opt.value = p.part_id;
                opt.textContent = `${p.part_id} - ${p.part_name} (LT: ${p.lead_time_days}d)`;
                partSelect.appendChild(opt);
            });
        } else {
            const opt = document.createElement('option');
            opt.textContent = '데이터 없음';
            partSelect.appendChild(opt);
        }
    } catch (err) {
        console.error('Failed to load parts', err);
        partSelect.innerHTML = '<option value="">에러 발생</option>';
    }
}

async function handlePredict() {
    const partId = partSelect.value;
    if (!partId) return;

    const horizon = parseInt(horizonSelect.value);
    const scenario = parseFloat(scenarioSlider.value);

    predictBtn.disabled = true;
    predictBtn.textContent = '예측 중...';

    try {
        // Fetch history
        const histRes = await fetch(`${API_BASE}/history/${partId}`);
        const histData = await histRes.json();
        currentHistoryData = histData.history;

        // Fetch forecast
        const fcastRes = await fetch(`${API_BASE}/forecast`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                part_id: partId,
                horizon_weeks: horizon,
                scenario_adjustment_pct: scenario
            })
        });

        if (!fcastRes.ok) {
            const errData = await fcastRes.json().catch(() => ({}));
            showError(errData.detail || `예측 요청 실패 (HTTP ${fcastRes.status})`);
            return;
        }

        currentForecastData = await fcastRes.json();
        
        renderAll();

    } catch (err) {
        console.error(err);
        showError('예측 실패: ' + err.message);
    } finally {
        predictBtn.disabled = false;
        predictBtn.textContent = '예측 실행 (Predict)';
    }
}

const fmtPct = (v) => (v === null || v === undefined) ? 'N/A' : `${(v * 100).toFixed(1)}%`;
const fmtNum = (v) => (v === null || v === undefined) ? 'N/A' : Number(v).toLocaleString(undefined, { maximumFractionDigits: 1 });

function updateKPIs() {
    if (!currentForecastData) return;
    const d = currentForecastData;

    kpiWape.textContent = fmtPct(d.metrics.ml.WAPE);
    kpiAvg.textContent = fmtNum(d.statistics.recent_4w_avg);
    kpiCv.textContent = d.statistics.cv === null ? 'N/A' : d.statistics.cv.toFixed(2);
    kpiFutureSum.textContent = fmtNum(d.scenario.scenario_sum);
    kpiBaseSum.textContent = fmtNum(d.scenario.baseline_sum);
    kpiLeadTime.textContent = `${d.scenario.lead_time_days}일 / ${fmtNum(d.scenario.lead_time_cumulative_demand)}`;
}

function renderMetricsTable() {
    const m = currentForecastData.metrics;
    const best = currentForecastData.evaluation.best_model;
    const labels = { naive: 'Baseline · Naive', seasonal_naive: 'Baseline · Seasonal Naive', ml: `ML · ${currentForecastData.model_name}` };
    metricsTableBody.innerHTML = '';
    Object.keys(labels).forEach(key => {
        const tr = document.createElement('tr');
        const mark = key === best ? ' ★' : '';
        tr.innerHTML = `
            <td>${labels[key]}${mark}</td>
            <td>${fmtPct(m[key].WAPE)}</td>
            <td>${fmtNum(m[key].MAE)}</td>
            <td>${fmtNum(m[key].RMSE)}</td>
        `;
        if (key === best) tr.style.fontWeight = '600';
        metricsTableBody.appendChild(tr);
    });
    const e = currentForecastData.evaluation;
    evalNote.textContent = `Holdout ${e.holdout_start}부터 ${e.holdout_weeks}주 / Train ${e.train_weeks}주 / 계절 lag ${e.seasonal_lag_weeks}주 · ${e.note}`;
}

function renderStatsTable() {
    const s = currentForecastData.statistics;
    const rows = [
        ['관측 주 수', `${s.weeks}주`],
        ['평균 수요', fmtNum(s.mean)],
        ['표준편차', fmtNum(s.std)],
        ['변동계수(CV)', s.cv === null ? 'N/A' : s.cv.toFixed(3)],
        ['최근 4주 평균', fmtNum(s.recent_4w_avg)],
        ['최근 8주 평균', fmtNum(s.recent_8w_avg)],
        ['최근 12주 평균', fmtNum(s.recent_12w_avg)],
        ['수요 0인 주', `${s.zero_demand_weeks}주`],
        ['최대 / 최소', `${fmtNum(s.max)} / ${fmtNum(s.min)}`]
    ];
    statsTableBody.innerHTML = rows.map(([k, v]) => `<tr><td>${k}</td><td>${v}</td></tr>`).join('');
}

// 한 파트가 실패해도 나머지 화면은 살린다(예: 차트 라이브러리 로드 실패).
function safeRender(name, fn) {
    try {
        fn();
    } catch (err) {
        console.error(`[${name}] 렌더 실패`, err);
        showError(`${name} 표시 중 문제가 발생했습니다: ${err.message}`);
    }
}

function renderAll() {
    clearError();
    safeRender('KPI', updateKPIs);
    safeRender('예측 상세', renderTable);
    safeRender('모델 성능 비교', renderMetricsTable);
    safeRender('통계 리포트', renderStatsTable);
    if (typeof Chart === 'undefined') {
        showError('차트 라이브러리를 불러오지 못했습니다. frontend/vendor/chart.umd.min.js 파일을 확인하세요. (표와 KPI는 정상 표시됩니다)');
        return;
    }
    safeRender('차트', renderCharts);
}

function showError(message) {
    let box = document.getElementById('error-banner');
    if (!box) {
        box = document.createElement('div');
        box.id = 'error-banner';
        box.className = 'error-banner';
        document.querySelector('.dashboard').prepend(box);
    }
    box.textContent = message;
    box.hidden = false;
}

function clearError() {
    const box = document.getElementById('error-banner');
    if (box) box.hidden = true;
}

function renderCharts() {
    // 1. History Chart
    const histDates = currentHistoryData.map(d => d.week_start);
    const histDemand = currentHistoryData.map(d => d.demand_qty);
    
    // For holdout overlay, we need to match dates.
    // The model returns holdout dates, actual, baseline, ml_pred
    const holdout = currentForecastData.holdout;
    
    // We can create a unified dataset for history chart
    const ctxHist = document.getElementById('historyChart').getContext('2d');
    if (historyChartInstance) historyChartInstance.destroy();
    
    // We only plot last 52 weeks or so to make it readable
    const sliceLen = -52;
    const slicedDates = histDates.slice(sliceLen);
    const slicedDemand = histDemand.slice(sliceLen);
    
    // Create arrays for holdout predictions that align with slicedDates
    const mlPredAligned = slicedDates.map(date => {
        const idx = holdout.dates.indexOf(date);
        return idx !== -1 ? holdout.ml_pred[idx] : null;
    });
    const seasonalAligned = slicedDates.map(date => {
        const idx = holdout.dates.indexOf(date);
        return idx !== -1 ? holdout.seasonal[idx] : null;
    });

    historyChartInstance = new Chart(ctxHist, {
        type: 'line',
        data: {
            labels: slicedDates,
            datasets: [
                {
                    label: 'Actual Demand',
                    data: slicedDemand,
                    borderColor: '#94a3b8',
                    backgroundColor: 'transparent',
                    borderWidth: 2,
                    pointRadius: 2
                },
                {
                    label: 'ML Predicted (Holdout)',
                    data: mlPredAligned,
                    borderColor: '#3b82f6',
                    backgroundColor: 'transparent',
                    borderWidth: 2,
                    borderDash: [5, 5],
                    pointRadius: 3
                },
                {
                    label: 'Seasonal Naive (Holdout)',
                    data: seasonalAligned,
                    borderColor: '#f59e0b',
                    backgroundColor: 'transparent',
                    borderWidth: 2,
                    borderDash: [2, 3],
                    pointRadius: 2
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                intersect: false,
                mode: 'index',
            }
        }
    });

    // 2. Future Chart
    const futDates = currentForecastData.future.map(d => d.week_start);
    const futBaseline = currentForecastData.future.map(d => d.baseline);
    const futML = currentForecastData.future.map(d => d.forecast);
    const futScenario = currentForecastData.future.map(d => d.scenario);

    const ctxFut = document.getElementById('futureChart').getContext('2d');
    if (futureChartInstance) futureChartInstance.destroy();

    futureChartInstance = new Chart(ctxFut, {
        type: 'bar',
        data: {
            labels: futDates,
            datasets: [
                {
                    label: 'ML Forecast',
                    data: futML,
                    backgroundColor: 'rgba(59, 130, 246, 0.5)',
                    borderColor: 'rgba(59, 130, 246, 1)',
                    borderWidth: 1
                },
                {
                    label: 'Scenario Adjusted',
                    data: futScenario,
                    backgroundColor: 'rgba(16, 185, 129, 0.5)',
                    borderColor: 'rgba(16, 185, 129, 1)',
                    borderWidth: 1
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    beginAtZero: true
                }
            }
        }
    });
}

function renderTable() {
    tableBody.innerHTML = '';
    currentForecastData.future.forEach(f => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td>${f.week_start}</td>
            <td>${Math.round(f.baseline)}</td>
            <td>${Math.round(f.forecast)}</td>
            <td style="font-weight: 600; color: var(--success);">${Math.round(f.scenario)}</td>
        `;
        tableBody.appendChild(tr);
    });
}

// Start
init();
