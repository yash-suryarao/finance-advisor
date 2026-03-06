
const authHeaders = {
    "Authorization": `Bearer ${localStorage.getItem('access_token')}`
};

let allTransactions = [];
let currentPeriod = 'month';
let sortKey = 'date';
let sortAsc = false;
let activeCategoryFilter = null;

// ── Boot ──────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
    fetchAllData();
    fetchCategories();
    document.getElementById("addTransactionBtn").addEventListener("click", () =>
        document.getElementById("addTransactionModal").classList.remove("hidden"));
    document.getElementById("closeModal").addEventListener("click", closeAddModal);
    document.getElementById("cancelBtn").addEventListener("click", closeAddModal);
    document.getElementById("transactionForm").addEventListener("submit", submitTransaction);
    document.getElementById("exportCsvBtn").addEventListener("click", exportCsv);
    setPeriod('month');
});

function closeAddModal() {
    document.getElementById("addTransactionModal").classList.add("hidden");
}

// ── Period selector ───────────────────────────────
function setPeriod(p) {
    currentPeriod = p;
    document.querySelectorAll('.period-btn').forEach(btn => {
        btn.classList.toggle('active-period', btn.dataset.period === p);
    });
    updateAll();
}

// ── Fetch ALL transactions (follows DRF pagination) ──
async function fetchAllData() {
    try {
        let url = "/api/transactions/?page_size=100";
        let results = [];

        while (url) {
            const res = await fetch(url, { headers: authHeaders });
            const data = await res.json();

            if (Array.isArray(data)) {
                // Non-paginated response
                results = data;
                url = null;
            } else {
                results = results.concat(data.results || []);
                url = data.next || null;  // follow next page if exists
            }
        }

        allTransactions = results;
        updateAll();
    } catch (e) {
        console.error("Error fetching transactions:", e);
    }
}

// ── Date filtering by period ──────────────────────
function filterByPeriod(transactions, period) {
    const now = new Date();
    return transactions.filter(t => {
        const d = new Date(t.date);
        if (period === 'today') {
            return d.toDateString() === now.toDateString();
        } else if (period === 'week') {
            const weekAgo = new Date(now); weekAgo.setDate(now.getDate() - 7);
            return d >= weekAgo;
        } else if (period === 'month') {
            return d.getMonth() === now.getMonth() && d.getFullYear() === now.getFullYear();
        } else if (period === 'year') {
            return d.getFullYear() === now.getFullYear();
        }
        return true;
    });
}

// ── Update everything when period changes ─────────
function updateAll() {
    const periodTx = filterByPeriod(allTransactions, currentPeriod);
    updateStatCards(periodTx);
    renderDonutChart(periodTx);
    renderTrendChart(allTransactions);
    renderFilteredTable();
}

// ── Stat Cards ────────────────────────────────────
function updateStatCards(transactions) {
    // Previous period for % change
    const now = new Date();
    let prevTransactions = [];
    if (currentPeriod === 'today') {
        const yesterday = new Date(now); yesterday.setDate(now.getDate() - 1);
        prevTransactions = allTransactions.filter(t => new Date(t.date).toDateString() === yesterday.toDateString());
    } else if (currentPeriod === 'week') {
        prevTransactions = allTransactions.filter(t => {
            const d = new Date(t.date);
            const ago14 = new Date(now); ago14.setDate(now.getDate() - 14);
            const ago7 = new Date(now); ago7.setDate(now.getDate() - 7);
            return d >= ago14 && d < ago7;
        });
    } else if (currentPeriod === 'month') {
        const prevMonth = new Date(now.getFullYear(), now.getMonth() - 1, 1);
        prevTransactions = allTransactions.filter(t => {
            const d = new Date(t.date);
            return d.getMonth() === prevMonth.getMonth() && d.getFullYear() === prevMonth.getFullYear();
        });
    } else if (currentPeriod === 'year') {
        prevTransactions = allTransactions.filter(t => new Date(t.date).getFullYear() === now.getFullYear() - 1);
    }

    const calc = (txs) => {
        const inc = txs.filter(t => t.category_type === 'income').reduce((s, t) => s + parseFloat(t.amount), 0);
        const exp = txs.filter(t => t.category_type === 'expense').reduce((s, t) => s + parseFloat(t.amount), 0);
        return { inc, exp, bal: inc - exp };
    };

    const curr = calc(transactions);
    const prev = calc(prevTransactions);

    const fmt = (n) => `₹${Math.abs(n).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;
    const pct = (c, p) => p === 0 ? (c > 0 ? '+100%' : '0%') : `${c >= p ? '+' : ''}${(((c - p) / p) * 100).toFixed(2)}%`;
    const periodLabel = { today: 'yesterday', week: 'last week', month: 'last month', year: 'last year' }[currentPeriod];

    document.getElementById('statBalance').textContent = (curr.bal < 0 ? '-' : '') + fmt(curr.bal);
    document.getElementById('statBalance').className = `text-3xl font-bold mb-1 ${curr.bal < 0 ? 'text-red-500' : 'text-violet-600'}`;
    document.getElementById('statBalanceChange').textContent = `${pct(curr.bal, prev.bal)} from ${periodLabel}`;

    document.getElementById('statIncome').textContent = fmt(curr.inc);
    document.getElementById('statIncomeChange').textContent = `${pct(curr.inc, prev.inc)} from ${periodLabel}`;

    document.getElementById('statExpenses').textContent = fmt(curr.exp);
    document.getElementById('statExpensesChange').textContent = `${pct(curr.exp, prev.exp)} from ${periodLabel}`;
}

// ── Donut Chart ───────────────────────────────────
let donutChart = null;
function renderDonutChart(transactions) {
    const expenses = transactions.filter(t => t.category_type === 'expense');
    const catMap = {};
    expenses.forEach(t => {
        const name = t.category_name || 'Other';
        catMap[name] = (catMap[name] || 0) + parseFloat(t.amount);
    });
    const data = Object.entries(catMap).map(([name, value]) => ({ name, value: parseFloat(value.toFixed(2)) }));

    if (!donutChart) donutChart = echarts.init(document.getElementById('donutChart'));

    const option = {
        tooltip: { trigger: 'item', formatter: (p) => `${p.name}: ₹${p.value.toLocaleString('en-IN')} (${p.percent}%)` },
        legend: { orient: 'vertical', right: '5%', top: 'center', textStyle: { fontSize: 12 } },
        series: [{
            name: 'Spending',
            type: 'pie',
            radius: ['40%', '70%'],
            center: ['38%', '50%'],
            avoidLabelOverlap: true,
            label: { show: false },
            emphasis: { label: { show: true, fontSize: 13, fontWeight: 'bold' } },
            data: data.length ? data : [{ name: 'No Data', value: 1, itemStyle: { color: '#e5e7eb' } }]
        }]
    };
    donutChart.setOption(option, true);

    // Click on slice → filter table by category
    donutChart.off('click');
    donutChart.on('click', (params) => {
        if (params.name === 'No Data') return;
        activeCategoryFilter = params.name;
        document.getElementById('activeCategoryFilter').classList.remove('hidden');
        document.getElementById('activeCategoryLabel').textContent = params.name;
        renderFilteredTable();
    });
    window.addEventListener('resize', () => donutChart.resize());
}

// ── Monthly Trend Chart ───────────────────────────
let trendChart = null;
function renderTrendChart(transactions) {
    // Build last 6 months
    const now = new Date();
    const months = [];
    for (let i = 5; i >= 0; i--) {
        const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
        months.push({ label: d.toLocaleString('default', { month: 'short' }) + ' ' + d.getFullYear(), month: d.getMonth(), year: d.getFullYear() });
    }

    const incomeArr = [], expenseArr = [], savingsArr = [];
    months.forEach(m => {
        const mtx = transactions.filter(t => {
            const d = new Date(t.date);
            return d.getMonth() === m.month && d.getFullYear() === m.year;
        });
        const inc = mtx.filter(t => t.category_type === 'income').reduce((s, t) => s + parseFloat(t.amount), 0);
        const exp = mtx.filter(t => t.category_type === 'expense').reduce((s, t) => s + parseFloat(t.amount), 0);
        incomeArr.push(parseFloat(inc.toFixed(2)));
        expenseArr.push(parseFloat(exp.toFixed(2)));
        savingsArr.push(parseFloat(Math.max(inc - exp, 0).toFixed(2)));
    });

    if (!trendChart) trendChart = echarts.init(document.getElementById('trendChart'));

    const option = {
        tooltip: {
            trigger: 'axis', axisPointer: { type: 'shadow' },
            formatter: (params) =>
                params.map(p => `${p.marker} ${p.seriesName}: ₹${(p.value || 0).toLocaleString('en-IN')}`).join('<br>')
        },
        legend: {
            top: 4,
            data: [
                { name: 'Income', icon: 'circle', itemStyle: { color: '#22c55e' } },
                { name: 'Expenses', icon: 'circle', itemStyle: { color: '#ef4444' } },
                { name: 'Savings', icon: 'rect', itemStyle: { color: '#3b82f6' } }
            ],
            textStyle: { fontSize: 12 }
        },
        grid: { top: 48, bottom: 8, left: 10, right: 20, containLabel: true },
        xAxis: {
            type: 'category',
            data: months.map(m => m.label),
            axisLabel: { fontSize: 11 },
            axisTick: { show: false },
            axisLine: { show: false }
        },
        yAxis: {
            type: 'value',
            splitLine: { lineStyle: { color: '#f1f5f9' } },
            axisLine: { show: false },
            axisTick: { show: false },
            axisLabel: {
                fontSize: 11,
                formatter: v => '₹' + (v >= 1000 ? (v / 1000).toFixed(0) + ',000' : v)
            }
        },
        series: [
            {
                // Savings — blue bars when positive, red when deficit
                name: 'Savings',
                type: 'bar',
                barMaxWidth: 60,
                data: savingsArr.map(v => ({
                    value: v,
                    itemStyle: {
                        color: v >= 0 ? '#3b82f6' : '#f87171',
                        borderRadius: v >= 0 ? [3, 3, 0, 0] : [0, 0, 3, 3]
                    }
                })),
                z: 1
            },
            {
                // Income — dashed green line with circle dots
                name: 'Income',
                type: 'line',
                data: incomeArr,
                symbol: 'circle',
                symbolSize: 9,
                lineStyle: { color: '#22c55e', width: 1.5, type: 'dashed' },
                itemStyle: { color: '#22c55e', borderWidth: 2, borderColor: '#fff' },
                z: 3
            },
            {
                // Expenses — dashed red line with circle dots
                name: 'Expenses',
                type: 'line',
                data: expenseArr,
                symbol: 'circle',
                symbolSize: 9,
                lineStyle: { color: '#ef4444', width: 1.5, type: 'dashed' },
                itemStyle: { color: '#ef4444', borderWidth: 2, borderColor: '#fff' },
                z: 3
            }
        ]
    };
    trendChart.setOption(option, true);
    window.addEventListener('resize', () => trendChart.resize());
}

// ── Table rendering with filters (NOT period-aware) ──
function renderFilteredTable() {
    let txs = [...allTransactions];

    // Category click filter from chart
    if (activeCategoryFilter) {
        txs = txs.filter(t => (t.category_name || 'Other') === activeCategoryFilter);
    }

    // Manual filters only
    const dateVal = document.getElementById('filterDate').value;
    const catVal = document.getElementById('filterCategory').value;
    const amtVal = parseFloat(document.getElementById('filterAmount').value);
    const searchVal = document.getElementById('searchText').value.toLowerCase();

    if (dateVal) txs = txs.filter(t => t.date === dateVal);
    if (catVal) txs = txs.filter(t => (t.category_name || '') === catVal);
    if (!isNaN(amtVal)) txs = txs.filter(t => parseFloat(t.amount) >= amtVal);
    if (searchVal) txs = txs.filter(t => (t.description || '').toLowerCase().includes(searchVal));

    // Sort
    txs.sort((a, b) => {
        let va = a[sortKey], vb = b[sortKey];
        if (sortKey === 'amount') { va = parseFloat(va); vb = parseFloat(vb); }
        return sortAsc ? (va > vb ? 1 : -1) : (va < vb ? 1 : -1);
    });

    renderTransactions(txs);
}

function applyFilters() { renderFilteredTable(); }

function clearFilters() {
    document.getElementById('filterDate').value = '';
    document.getElementById('filterCategory').value = '';
    document.getElementById('filterAmount').value = '';
    document.getElementById('searchText').value = '';
    renderFilteredTable();
}

function clearCategoryFilter() {
    activeCategoryFilter = null;
    document.getElementById('activeCategoryFilter').classList.add('hidden');
    renderFilteredTable();
}

function sortTransactions(key) {
    if (sortKey === key) sortAsc = !sortAsc;
    else { sortKey = key; sortAsc = true; }
    renderFilteredTable();
}

// ── Table render ──────────────────────────────────
function renderTransactions(transactions) {
    const tbody = document.getElementById("transactionsList");
    if (!transactions.length) {
        tbody.innerHTML = `<tr><td colspan="6" class="py-12 text-center text-sm text-gray-400">No transactions found for this period.</td></tr>`;
        return;
    }
    tbody.innerHTML = transactions.map(t => `
        <tr class="border-b">
            <td class="px-6 py-4 text-left">${t.date}</td>
            <td class="px-6 py-4 text-left">${t.category_name || 'Uncategorized'}</td>
            <td class="px-6 py-4 text-center">
                <span class="px-3 py-1 text-xs font-semibold rounded-full ${t.category_type === 'income' ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'} capitalize">
                    ${t.category_type || 'expense'}
                </span>
            </td>
            <td class="px-6 py-4 text-right font-bold">₹${parseFloat(t.amount).toFixed(2)}</td>
            <td class="px-6 py-4 text-left text-gray-500">${t.description || "N/A"}</td>
            <td class="px-6 py-4 text-center">
                <button onclick="deleteTransaction(${t.id})" class="text-red-500 hover:text-red-700 transition" title="Delete">
                    <i class="ri-close-circle-fill text-2xl"></i>
                </button>
            </td>
        </tr>
    `).join('');
}

// ── Fetch categories for filter + modal ──────────
async function fetchCategories() {
    try {
        const res = await fetch("/api/transactions/categories/", { headers: authHeaders });
        const categories = await res.json();
        const modalSel = document.getElementById("transactionCategory");
        const filterSel = document.getElementById("filterCategory");
        const opts = categories.map(c => `<option value="${c.name}">${c.name}</option>`).join('');
        modalSel.innerHTML = opts;
        filterSel.innerHTML = '<option value="">All Categories</option>' + opts;
    } catch (e) {
        console.error("Error fetching categories:", e);
    }
}

// ── Add Transaction ───────────────────────────────
async function submitTransaction(event) {
    event.preventDefault();
    const newTransaction = {
        date: document.getElementById("transactionDate").value,
        category_type: document.getElementById("transactionType").value,
        category: document.getElementById("transactionCategory").value,
        amount: parseFloat(document.getElementById("transactionAmount").value),
        description: document.getElementById("transactionDescription").value,
    };
    try {
        await fetch("/api/transactions/", {
            method: "POST",
            headers: { "Content-Type": "application/json", ...authHeaders },
            body: JSON.stringify(newTransaction),
        });
        closeAddModal();
        await fetchAllData();
    } catch (e) {
        console.error("Error adding transaction:", e);
    }
}

// ── Delete Transaction ────────────────────────────
async function deleteTransaction(id) {
    if (!confirm("Delete this transaction?")) return;
    try {
        const res = await fetch(`/api/transactions/${id}/`, { method: 'DELETE', headers: authHeaders });
        if (res.ok) await fetchAllData();
        else alert("Error deleting transaction.");
    } catch (e) {
        console.error("Error deleting:", e);
    }
}

// ── Export CSV ────────────────────────────────────
function exportCsv() {
    const txs = filterByPeriod(allTransactions, currentPeriod);
    const header = ['Date', 'Category', 'Type', 'Amount', 'Description'];
    const rows = txs.map(t => [t.date, t.category_name || '', t.category_type || '', t.amount, `"${(t.description || '').replace(/"/g, '""')}"`]);
    const csv = [header, ...rows].map(r => r.join(',')).join('\n');
    const a = document.createElement('a');
    a.href = 'data:text/csv;charset=utf-8,' + encodeURIComponent(csv);
    a.download = `transactions_${currentPeriod}_${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
}

// ── Voice entry (kept from original) ─────────────
const voiceEntryBtn = document.getElementById('voiceEntryBtn');
const transactionModal = document.getElementById('transactionModal');
const editAmount = document.getElementById('editAmount');
const editCategory = document.getElementById('editCategory');
const editType = document.getElementById('editType');
const saveTransactionBtn = document.getElementById('saveTransaction');
const cancelTransactionBtn = document.getElementById('cancelTransaction');

if ('SpeechRecognition' in window || 'webkitSpeechRecognition' in window) {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    const recognition = new SR();
    recognition.continuous = false; recognition.lang = 'en-US'; recognition.interimResults = false;

    if (voiceEntryBtn) {
        voiceEntryBtn.addEventListener('click', () => { recognition.start(); alert("Listening..."); });
    }
    recognition.onresult = async (event) => {
        const voiceText = event.results[0][0].transcript;
        if (voiceEntryBtn) { voiceEntryBtn.textContent = "Processing..."; voiceEntryBtn.disabled = true; }
        const res = await fetch('/api/transactions/process-voice-entry/', {
            method: 'POST', headers: { "Content-Type": "application/json", ...authHeaders },
            body: JSON.stringify({ voice_text: voiceText })
        });
        if (voiceEntryBtn) { voiceEntryBtn.textContent = "Voice Entry"; voiceEntryBtn.disabled = false; }
        const data = await res.json();
        if (!data.error) {
            editAmount.value = data.amount; editCategory.value = data.category; editType.value = data.transaction_type;
            if (transactionModal) transactionModal.classList.remove('hidden');
        }
    };
    recognition.onerror = (e) => alert("Voice error: " + e.error);
}

if (saveTransactionBtn) {
    saveTransactionBtn.addEventListener('click', async () => {
        const res = await fetch('/api/transactions/confirm-voice-transaction/', {
            method: 'POST', headers: { "Content-Type": "application/json", ...authHeaders },
            body: JSON.stringify({ amount: parseFloat(editAmount.value), transaction_type: editType.value, category: editCategory.value })
        });
        const result = await res.json();
        if (result.message) { if (transactionModal) transactionModal.classList.add('hidden'); fetchAllData(); }
        else alert("Error saving.");
    });
}
if (cancelTransactionBtn) cancelTransactionBtn.addEventListener('click', () => transactionModal?.classList.add('hidden'));
