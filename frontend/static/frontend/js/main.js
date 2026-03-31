// ==========================================
// 1. GLOBAL STATE & SETUP
// ==========================================

const authHeaders = {
    "Authorization": `Bearer ${localStorage.getItem('access_token')}`
};

// Global Fetch Interceptor to catch 401 Unauthorized (Expired Tokens)
const originalFetch = window.fetch;
window.fetch = async function () {
    let response = await originalFetch.apply(this, arguments);
    if (response.status === 401 && typeof arguments[0] === 'string' && !arguments[0].includes('/login/')) {
        console.warn("Session expired. Redirecting to login.");
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        window.location.href = '/frontend/login/';
    }
    return response;
};

// Set Savings Progress Bar Width will be handled by fetchDashboardStats()

// Load User Data handled by nav.js event listener

// ==========================================
// 3. ECHARTS & FINANCIAL HEALTH GAUGE
// ==========================================

// Initialize ECharts instances
const incomeVsExpensesChart = echarts.init(document.getElementById('incomeVsExpensesChart'));
const financialHealthGauge = echarts.init(document.getElementById('financialHealthGauge'));

window.updateHealthGauge = function (score, label) {
    let healthColor = '#F59E0B'; // Yellow warning fallback
    if (label === 'Excellent') healthColor = '#10B981'; // Green
    if (label === 'Poor') healthColor = '#EF4444'; // Red
    if (label === '') healthColor = '#9CA3AF'; // Gray for empty/no-data

    financialHealthGauge.setOption({
        series: [{
            type: 'gauge',
            startAngle: 180,
            endAngle: 0,
            min: 0,
            max: 100,
            splitNumber: 2,
            itemStyle: {
                color: healthColor,
                shadowColor: 'rgba(0,0,0,0.1)',
                shadowBlur: 10,
                shadowOffsetX: 2,
                shadowOffsetY: 2
            },
            progress: { show: true, roundCap: true, width: 14 },
            pointer: { show: false },
            axisLine: { roundCap: true, lineStyle: { width: 14 } },
            axisTick: { show: false },
            splitLine: { show: false },
            axisLabel: { show: false },
            title: { show: false },
            detail: {
                offsetCenter: [0, '25%'],
                valueAnimation: true,
                formatter: function (value) {
                    if (label === '') return '{str|\nNo Data}';
                    return '{value|' + value.toFixed(0) + '}{str|\n' + label + '}';
                },
                rich: {
                    value: { fontSize: 36, fontWeight: '900', color: healthColor, padding: [0, 0, 5, 0] },
                    str: { color: '#666', fontSize: 13, fontWeight: 'bold' }
                }
            },
            data: [{ value: score }]
        }]
    });
};

// ==========================================
// 4. API DASHBOARD DATA FETCHING
// ==========================================

async function fetchDashboardStats() {
    try {
        const response = await fetch('/frontend/financial-summary/', { headers: authHeaders });
        const data = await response.json();

        const onlyExpense = (data.monthly_income === 0 && data.monthly_expenses > 0);

        const formatWidget = (elementId, value, isExpense = false, forceNegative = false) => {
            const num = parseFloat(value) || 0;
            const absoluteVal = Math.abs(num).toFixed(2);

            let isBad = isExpense ? (num > 0) : (num < 0 || forceNegative);
            let arrow = isExpense ? (num > 0 ? 'up' : 'down') : (num < 0 || forceNegative ? 'down' : 'up');

            // Handle true 0.00% (No change)
            if (num === 0 && !forceNegative) {
                arrow = isExpense ? 'down' : 'up';
                isBad = false;
            }

            let color = isBad ? 'text-red-500' : 'text-green-500';
            if (elementId === 'balanceChange' || elementId === 'incomeChange') {
                color = isBad ? 'text-red-600' : 'text-green-600';
            }

            let sign = num > 0 ? '+' : (num < 0 || forceNegative ? '-' : '');
            if (num === 0 && !forceNegative) sign = ''; // Just 0.00% without sign

            document.getElementById(elementId).innerHTML = `<i class="ri-arrow-${arrow}-line"></i> ${sign}${absoluteVal}%`;
            document.getElementById(elementId).className = `text-sm font-medium mt-2 ${color}`;
        };

        // Populate Raw Currency Amounts
        document.getElementById('totalBalance').textContent = `₹${parseFloat(data.total_balance).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
        document.getElementById('monthlyIncome').textContent = `₹${parseFloat(data.monthly_income).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
        document.getElementById('monthlyExpenses').textContent = `₹${parseFloat(Math.abs(data.monthly_expenses)).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
        document.getElementById('savingsAmount').textContent = `₹${parseFloat(data.savings).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

        // Populate Calculated Percentage Changes with Arrow/Color Logic
        formatWidget('balanceChange', data.balance_change, false, onlyExpense);
        formatWidget('incomeChange', data.income_change, false, false);
        formatWidget('expenseChange', data.expense_change, true, false);
        formatWidget('savingsChange', data.savings_change, false, onlyExpense);

        // Financial Health Progress Bars
        document.getElementById('savingsRateLabel').textContent = `${data.savings_rate}%`;
        document.getElementById('savingsRateBar').style.width = `${Math.min(data.savings_rate, 100)}%`;

        document.getElementById('spendingRatioLabel').textContent = `${data.spending_ratio}%`;
        document.getElementById('spendingRatioBar').style.width = `${Math.min(data.spending_ratio, 100)}%`;

        // Update the health gauge globally if initialized
        if (window.updateHealthGauge) {
            window.updateHealthGauge(data.financial_health_score, data.financial_health);
        }
    } catch (error) {
        console.error('Error fetching dashboard stats:', error);
    }
}

async function fetchInitialChartData() {
    try {
        const response = await fetch('/frontend/spending-analysis/?period=month', { headers: authHeaders });
        const data = await response.json();
        updateCharts(data);
    } catch (error) {
        console.error('Error fetching chart data:', error);
    }
}

// ==========================================
// 5. CHART WIDGET RENDERING
// ==========================================

function updateCharts(data) {
    // Bar Chart (Income vs. Expenses for 6 months)
    incomeVsExpensesChart.setOption({
        tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
        legend: { data: ['Income', 'Expenses'], bottom: 0 },
        grid: { left: '3%', right: '4%', bottom: '15%', top: '5%', containLabel: true },
        xAxis: { type: 'category', data: data.bar_months, axisTick: { alignWithLabel: true }, axisLine: { lineStyle: { color: '#E5E7EB' } }, axisLabel: { color: '#6B7280', fontWeight: '500' } },
        yAxis: { type: 'value', splitLine: { lineStyle: { color: '#F3F4F6' } }, axisLabel: { color: '#6B7280', formatter: '₹{value}' } },
        series: [
            { name: 'Income', type: 'bar', barWidth: '15%', itemStyle: { color: '#10B981', borderRadius: [4, 4, 0, 0] }, data: data.bar_income },
            { name: 'Expenses', type: 'bar', barWidth: '15%', barGap: '30%', itemStyle: { color: '#EF4444', borderRadius: [4, 4, 0, 0] }, data: data.bar_expenses }
        ]
    });
}

// Load data on page load
fetchDashboardStats();
fetchInitialChartData();

// Event listeners for filtering
document.querySelectorAll('.filter-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('.filter-btn').forEach(b => b.classList.replace('bg-primary', 'bg-gray-100'));
        btn.classList.replace('bg-gray-100', 'bg-primary');

        fetch(`/frontend/spending-analysis/?period=${btn.getAttribute('data-period')}`, { headers: authHeaders })
            .then(response => response.json())
            .then(data => updateCharts(data));
    });
});

// Resize charts on window resize
window.addEventListener('resize', () => {
    incomeVsExpensesChart.resize();
    financialHealthGauge.resize();
});



async function fetchTransactions() {
    try {
        const response = await fetch('/api/transactions/', { headers: authHeaders });
        const data = await response.json();
        const transactions = data.results || data;
        const transactionList = document.getElementById('transactionList');

        // Clear existing content
        transactionList.innerHTML = '';

        // Sort transactions to ensure the newest are at the top (LIFO/Stack) using precise creation timestamp
        const sortedTransactions = transactions.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));

        // Restrict to max 10 transactions for the dashboard view
        sortedTransactions.slice(0, 10).forEach(transaction => {
            let iconClass = "ri-file-list-line text-gray-600";  // Default icon
            let bgClass = "bg-gray-100";

            // Set Color based purely on category_type
            let amountClass = transaction.category_type === "income" ? "text-green-600" : "text-red-600";

            // Categorizing transactions
            const catName = transaction.category_name || "Other";
            switch (catName.toLowerCase()) {
                case "salary":
                    iconClass = "ri-bank-line text-green-600";
                    bgClass = "bg-green-100";
                    break;
                case "freelance":
                    iconClass = "ri-briefcase-line text-green-600";
                    bgClass = "bg-green-100";
                    break;
                case "investment":
                    iconClass = "ri-stock-line text-green-600";
                    bgClass = "bg-green-100";
                    break;
                case "bonus":
                    iconClass = "ri-gift-line text-green-600";
                    bgClass = "bg-green-100";
                    break;
                case "subscription":
                    iconClass = "ri-netflix-fill text-purple-600";
                    bgClass = "bg-purple-100";
                    break;
                case "netflix":
                    iconClass = "ri-netflix-fill text-red-600";
                    bgClass = "bg-red-100";
                    break;
                case "spotify":
                    iconClass = "ri-spotify-line text-green-600";
                    bgClass = "bg-green-100";
                    break;
                case "amazon prime":
                    iconClass = "ri-amazon-fill text-blue-600";
                    bgClass = "bg-blue-100";
                    break;
                case "hulu":
                    iconClass = "ri-hulu-fill text-green-600";
                    bgClass = "bg-green-100";
                    break;
                case "disney plus":
                    iconClass = "ri-disney-fill text-blue-600";
                    bgClass = "bg-blue-100";
                    break;
                case "shopping":
                    iconClass = "ri-shopping-bag-line text-blue-600";
                    bgClass = "bg-blue-100";
                    break;
                case "groceries":
                    iconClass = "ri-store-line text-blue-600";
                    bgClass = "bg-blue-100";
                    break;
                case "restaurant":
                case "food":
                case "dining":
                    iconClass = "ri-restaurant-line text-orange-600";
                    bgClass = "bg-orange-100";
                    break;
                case "transport":
                case "fuel":
                case "travel":
                    iconClass = "ri-car-line text-orange-600";
                    bgClass = "bg-orange-100";
                    break;
                case "education":
                case "courses":
                case "books":
                    iconClass = "ri-book-line text-indigo-600";
                    bgClass = "bg-indigo-100";
                    break;
                case "entertainment":
                case "movies":
                case "gaming":
                    iconClass = "ri-movie-line text-red-600";
                    bgClass = "bg-red-100";
                    break;
                case "health":
                case "medical":
                case "insurance":
                    iconClass = "ri-hospital-line text-red-600";
                    bgClass = "bg-red-100";
                    break;
                case "utilities":
                case "electricity":
                case "water":
                case "internet":
                case "phone":
                    iconClass = "ri-flashlight-line text-yellow-600";
                    bgClass = "bg-yellow-100";
                    break;
                case "rent":
                case "mortgage":
                case "household":
                    iconClass = "ri-home-line text-teal-600";
                    bgClass = "bg-teal-100";
                    break;
                case "charity":
                case "donation":
                    iconClass = "ri-heart-line text-pink-600";
                    bgClass = "bg-pink-100";
                    break;
                case "debt":
                case "loan":
                case "credit card":
                    iconClass = "ri-money-dollar-box-line text-gray-600";
                    bgClass = "bg-gray-100";
                    break;
                default:
                    iconClass = "ri-file-list-line text-gray-600";  // Default icon
                    bgClass = "bg-gray-100";
                    break;
            }

            // Format amount
            const formattedAmount = `₹${parseFloat(transaction.amount).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;

            // Create transaction item
            const transactionItem = `
                    <div class="relative pl-8 py-3 group">
                        <div class="absolute left-[-2px] top-[1.3rem] w-2.5 h-2.5 rounded-full border-2 border-white ${bgClass.replace('100', '400')} z-20 shadow-sm transition group-hover:scale-125 hidden sm:block"></div>
                        <div class="flex items-center justify-between bg-gray-50 p-4 rounded-xl border border-gray-100 hover:shadow-sm transition cursor-pointer">
                            <div class="flex items-center">
                                <div class="w-10 h-10 ${bgClass} rounded-full flex items-center justify-center mr-4 group-hover:scale-105 transition duration-300">
                                    <i class="${iconClass}"></i>
                                </div>
                                <div>
                                    <p class="font-bold text-gray-900 leading-tight">${transaction.description || transaction.category_name}</p>
                                    <p class="text-xs font-semibold text-gray-500 mt-0.5">${transaction.category_name} &bull; ${new Date(transaction.date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}</p>
                                </div>
                            </div>
                            <div class="text-right">
                                <p class="font-bold ${amountClass}">${transaction.category_type === "income" ? "+" : "-"}${formattedAmount}</p>
                            </div>
                        </div>
                    </div>
                `;

            transactionList.innerHTML += transactionItem;
        });

    } catch (error) {
        console.error('Error fetching transactions:', error);
    }
}

// Fetch transactions on page load
fetchTransactions();


async function fetchAIInsights() {
    // Show loading state immediately to provide visual feedback during the LLM delay
    const insightsBox = document.getElementById('aiInsightsBox');
    if (insightsBox) {
        insightsBox.innerHTML = `
            <div class="col-span-full flex flex-col items-center justify-center p-12 text-blue-600 bg-blue-50 rounded-xl border border-blue-100">
                <i class="ri-loader-4-line animate-spin text-3xl mb-3"></i>
                <p class="text-sm font-semibold">Generating fresh AI Insights...</p>
                <p class="text-xs text-blue-400 mt-1">Analyzing your latest transactions</p>
            </div>
        `;
    }

    try {
        // Add timestamp to bypass browser cache and force a fresh LLM generation
        const response = await fetch(`/api/insights/ai-insights/?t=${new Date().getTime()}`, { headers: authHeaders });
        const data = await response.json();

        document.getElementById('aiInsightsBox').innerHTML = '';

        if (data.length === 0 || (data.length === 1 && data[0].type === "General")) {
            const msg = data.length === 1 ? data[0].description : "No new AI insights available.";
            document.getElementById('aiInsightsBox').innerHTML = `<div class="col-span-full flex items-center justify-center p-8 text-sm text-gray-500 bg-gray-50 rounded-xl border border-dashed border-gray-200">${msg}</div>`;
            return;
        }

        data.forEach(insight => {
            let borderColor = 'border-blue-500';
            let bgColor = 'bg-blue-50';
            let iconColor = 'text-blue-500';
            let titleColor = 'text-blue-700';
            let textColor = 'text-blue-600';
            let subtleTextColor = 'text-blue-400';
            let btnColor = 'text-blue-700 hover:text-blue-800';

            let icon = 'ri-information-line';
            if (insight.type === 'Anomaly') icon = 'ri-error-warning-line';
            else if (insight.type === 'Forecast') icon = 'ri-line-chart-line';
            else if (insight.type === 'Budget') icon = 'ri-scissors-cut-line';

            document.getElementById('aiInsightsBox').innerHTML += `
                <div class="${bgColor} rounded-xl border-l-4 ${borderColor} p-5 flex flex-col justify-between hover:shadow-sm transition">
                    <div>
                        <div class="flex items-start mb-2">
                            <i class="${icon} ${iconColor} text-lg mr-2 mt-0.5"></i>
                            <h4 class="text-sm font-bold ${titleColor} leading-tight">${insight.title}</h4>
                        </div>
                        <p class="text-sm ${textColor} mb-4 ml-6 leading-relaxed line-clamp-3">${insight.description}</p>
                    </div>
                    <div class="ml-6 flex items-center justify-between mt-auto pt-2 border-t border-blue-100">
                        <span class="text-xs font-semibold ${subtleTextColor}">Category: <span class="uppercase tracking-wide">${insight.category}</span></span>
                        <button onclick="showAIModal('${encodeURIComponent(insight.title).replace(/'/g, "%27")}', '${encodeURIComponent(insight.category).replace(/'/g, "%27")}')" class="text-xs font-bold ${btnColor} flex items-center bg-blue-100 px-2 py-1 rounded-md hover:bg-blue-200 transition">View Details <i class="ri-arrow-right-line ml-1"></i></button>
                    </div>
                </div>
            `;
        });
    }
    catch (error) {
        console.error('Error fetching AI insights:', error);
    }
}

async function showAIModal(encodedTitle, encodedCategory) {
    const rawTitle = decodeURIComponent(encodedTitle);
    const category = decodeURIComponent(encodedCategory);

    // Create modal DOM once (reused on subsequent calls)
    let modal = document.getElementById('aiInsightModal');
    if (!modal) {
        modal = document.createElement('div');
        modal.id = 'aiInsightModal';
        modal.className = 'fixed inset-0 bg-black bg-opacity-40 backdrop-blur-sm flex justify-center items-center z-50 transition-opacity';
        modal.innerHTML = `
            <div class="bg-white rounded-2xl shadow-xl w-full max-w-2xl overflow-hidden transform transition-all scale-100 p-6 relative max-h-[85vh] flex flex-col">
                <button onclick="document.getElementById('aiInsightModal').classList.add('hidden')"
                    class="absolute top-4 right-4 text-gray-400 hover:text-gray-600 transition z-10 w-8 h-8 flex items-center justify-center bg-gray-100 rounded-full">
                    <i class="ri-close-line text-xl"></i>
                </button>
                <div class="flex items-center mb-5 shrink-0 pr-8">
                    <div class="w-12 h-12 bg-indigo-100 rounded-full flex items-center justify-center mr-4">
                        <i class="ri-sparkling-fill text-indigo-600 text-2xl"></i>
                    </div>
                    <h3 id="aiModalTitle" class="text-2xl font-bold text-gray-900 leading-tight">AI Insight</h3>
                </div>
                <!-- Scrollable body: LLM details + budget recommendation -->
                <div class="p-5 bg-indigo-50 border border-indigo-100 rounded-xl relative overflow-y-auto custom-scrollbar flex-1">
                    <div id="aiModalDetails" class="text-indigo-950 text-[15px] leading-relaxed"></div>
                    <!-- AI Budget suggestion card injected here after LLM load -->
                    <div id="aiModalBudgetSection" class="mt-6 hidden"></div>
                </div>
                <div class="mt-6 flex justify-end shrink-0">
                    <button onclick="document.getElementById('aiInsightModal').classList.add('hidden')"
                        class="px-5 py-2.5 bg-indigo-600 text-white font-medium rounded-xl hover:bg-indigo-700 transition duration-200">Got it</button>
                </div>
            </div>
        `;
        document.body.appendChild(modal);
    }

    // Show modal immediately with loading spinner
    document.getElementById('aiModalTitle').innerHTML = rawTitle;
    document.getElementById('aiModalDetails').innerHTML = `
        <div class="flex flex-col items-center justify-center py-10 text-indigo-500">
            <i class="ri-loader-4-line animate-spin text-4xl mb-3"></i>
            <p class="text-sm font-semibold">Generating AI analysis for <strong>${category}</strong>...</p>
            <p class="text-xs text-indigo-400 mt-1">This may take a few seconds</p>
        </div>`;
    // Hide budget section while loading
    const budgetSection = document.getElementById('aiModalBudgetSection');
    if (budgetSection) { budgetSection.classList.add('hidden'); budgetSection.innerHTML = ''; }
    modal.classList.remove('hidden');

    // ── 1. Fetch LLM category analysis ───────────────────────────────────────
    try {
        const res = await fetch(`/api/insights/category-detail/?category=${encodeURIComponent(category)}`, { headers: authHeaders });
        const data = await res.json();
        let rawDetails = data.llm_details || 'No analysis available.';

        // Parse Markdown → HTML
        rawDetails = rawDetails
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.*?)\*/g, '<em>$1</em>')
            .replace(/### (.*?)\n/g, '<h4 class="font-bold text-lg mt-4 mb-2 text-indigo-900">$1</h4>\n')
            .replace(/## (.*?)\n/g, '<h3 class="font-bold text-xl mt-5 mb-3 text-indigo-950 border-b border-indigo-200 pb-1">$1</h3>\n')
            .replace(/\n/g, '<br>');

        document.getElementById('aiModalDetails').innerHTML = rawDetails;
    } catch (err) {
        document.getElementById('aiModalDetails').innerHTML = `<p class="text-red-500 text-sm">Failed to load analysis. Please try again.</p>`;
        console.error('Category insight fetch error:', err);
    }

    // ── 2. Fetch AI budget suggestion for this specific category ─────────────
    // Runs in parallel with LLM — appended after LLM content renders
    try {
        const suggestRes = await fetch('/api/insights/ai-budget-suggestions/', { headers: authHeaders });
        const suggestData = await suggestRes.json();
        const suggestions = suggestData.suggestions || [];
        const match = suggestions.find(s => s.category === category);

        const sec = document.getElementById('aiModalBudgetSection');
        if (!sec) return;

        if (!match) {
            // No spending history for this category — show a generic set prompt
            sec.classList.remove('hidden');
            sec.innerHTML = `
                <div class="border border-indigo-200 rounded-xl p-4 bg-white">
                    <div class="flex items-center gap-2 mb-2">
                        <i class="ri-funds-line text-indigo-500 text-lg"></i>
                        <h4 class="font-bold text-indigo-900 text-sm">💡 AI Budget Recommendation</h4>
                    </div>
                    <p class="text-xs text-indigo-600 mb-3">No spending history found for <strong>${category}</strong>. Set a manual budget limit to start tracking.</p>
                    <div class="flex items-center gap-2">
                        <input type="number" id="manualBudgetInput_${category.replace(/\s/g, '_')}"
                            class="flex-1 p-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-400"
                            placeholder="Enter monthly limit ₹" />
                        <button onclick="setManualBudgetFromModal('${category}')"
                            class="px-4 py-2 text-xs font-bold bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition whitespace-nowrap">
                            Set Budget
                        </button>
                    </div>
                </div>`;
            return;
        }

        const isHighRisk = match.reason.includes('XGBoost flagged');
        const existingText = match.current_limit !== null
            ? `Current: <span class="line-through text-gray-400">₹${match.current_limit.toLocaleString('en-IN', { maximumFractionDigits: 0 })}</span> → `
            : '';
        const actionLabel = match.current_limit !== null ? 'Update Budget' : 'Set Budget';
        const riskBadge = isHighRisk
            ? `<span class="text-[10px] font-bold px-1.5 py-0.5 bg-red-50 text-red-600 border border-red-200 rounded-full">🔴 High Spend (XGBoost)</span>`
            : `<span class="text-[10px] font-bold px-1.5 py-0.5 bg-blue-50 text-blue-600 border border-blue-200 rounded-full">✅ Avg Spend Analysis</span>`;

        sec.classList.remove('hidden');
        sec.innerHTML = `
            <div class="border border-indigo-200 rounded-xl p-4 bg-white">
                <div class="flex items-center justify-between mb-3">
                    <div class="flex items-center gap-2">
                        <i class="ri-funds-line text-indigo-500 text-lg"></i>
                        <h4 class="font-bold text-indigo-900 text-sm">💡 AI Budget Recommendation</h4>
                        ${riskBadge}
                    </div>
                </div>
                <p class="text-xs text-gray-600 mb-3 leading-relaxed">${match.reason}</p>
                <div class="flex items-center justify-between bg-indigo-50 rounded-lg px-4 py-3">
                    <div class="text-sm text-gray-600">
                        ${existingText}<span class="font-bold text-indigo-700 text-base">₹${match.suggested_limit.toLocaleString('en-IN', { maximumFractionDigits: 0 })}<span class="text-xs font-medium text-indigo-500">/mo</span></span>
                        <div class="text-xs text-gray-400 mt-0.5">Based on ₹${match.current_avg_spend.toLocaleString('en-IN', { maximumFractionDigits: 0 })}/mo avg · ${isHighRisk ? '15%' : '10%'} savings target</div>
                    </div>
                    <button id="setBudgetBtn_${category.replace(/\W/g, '_')}"
                        onclick="setAIBudgetFromModal('${category}', ${match.suggested_limit})"
                        class="px-4 py-2 text-xs font-bold bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition flex items-center gap-1 shrink-0 ml-3">
                        <i class="ri-check-line"></i> ${actionLabel}
                    </button>
                </div>
            </div>`;
    } catch (e) {
        console.warn('Could not load budget suggestion for modal:', e);
    }
}

// Sets AI-suggested budget directly from the insight modal
async function setAIBudgetFromModal(category, amount) {
    const btnId = `setBudgetBtn_${category.replace(/\W/g, '_')}`;
    const btn = document.getElementById(btnId);
    if (btn) { btn.disabled = true; btn.innerHTML = '<i class="ri-loader-4-line animate-spin"></i> Saving...'; }

    try {
        const res = await fetch('/api/transactions/budget/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCookie('csrftoken'), ...authHeaders },
            body: JSON.stringify({ category, monthly_limit: amount })
        });
        if (res.ok) {
            if (btn) {
                btn.innerHTML = '<i class="ri-check-double-line"></i> Budget Set!';
                btn.className = btn.className.replace('bg-indigo-600 hover:bg-indigo-700', 'bg-green-600 hover:bg-green-700');
            }
            // Refresh budget overview panel in background
            if (typeof fetchBudgets === 'function') fetchBudgets();
        } else {
            if (btn) { btn.disabled = false; btn.innerHTML = 'Retry'; }
        }
    } catch (e) {
        console.error('Set budget from modal error:', e);
        if (btn) { btn.disabled = false; btn.innerHTML = 'Retry'; }
    }
}

// Sets a manually typed budget from the no-history case in the modal
async function setManualBudgetFromModal(category) {
    const inputId = `manualBudgetInput_${category.replace(/\s/g, '_')}`;
    const input = document.getElementById(inputId);
    const amount = input ? parseFloat(input.value) : 0;
    if (!amount || amount <= 0) { alert('Please enter a valid amount.'); return; }
    await setAIBudgetFromModal(category, amount);
}

fetchAIInsights();

// Helper for CSRF token
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}






async function fetchUserNotifications() {
    try {
        const response = await fetch('/users/api/user-notifications/', { headers: authHeaders });
        const data = await response.json();
        const notificationList = document.getElementById('notificationList');
        const notificationBadge = document.getElementById('notificationBadge');

        notificationList.innerHTML = '';
        if (data.length > 0) {
            notificationBadge.classList.remove('hidden'); // Show red dot
            data.forEach(notification => {
                notificationList.innerHTML += `
                                <div class="p-2 bg-gray-50 rounded">
                                    <p class="font-medium text-gray-900">${notification.title}</p>
                                    <p class="text-sm text-gray-600">${notification.message}</p>
                                    <p class="text-xs text-gray-500">${notification.timestamp}</p>
                                </div>
                            `;
            });
        } else {
            notificationList.innerHTML = `<p class="text-sm text-gray-500">No new notifications.</p>`;
        }
    } catch (error) {
        console.error('Error fetching notifications:', error);
    }
}

// Show/Hide Notifications
if (document.getElementById('notificationBtn')) {
    document.getElementById('notificationBtn').addEventListener('click', () => {
        document.getElementById('notificationDropdown').classList.toggle('hidden');
        fetchUserNotifications();
    });
}

fetchUserNotifications(); // Load on page load


// ==========================================
// BUDGET OVERVIEW — Real data from /api/transactions/budget/
// Shows actual spending vs limit per category, delete button, created date.
// ==========================================

async function fetchBudgets() {
    const budgetList = document.getElementById('budgetOverviewList');
    if (!budgetList) return;
    try {
        const response = await fetch('/api/transactions/budget/', { headers: authHeaders });
        if (!response.ok) return;
        const data = await response.json();

        budgetList.innerHTML = '';

        if (!data || data.length === 0) {
            budgetList.innerHTML = `
                <div class="flex flex-col items-center justify-center h-full text-center text-gray-400 py-10">
                    <i class="ri-pie-chart-2-line text-4xl mb-3"></i>
                    <p class="text-sm font-medium">No active budgets.</p>
                    <p class="text-xs text-gray-300 mt-1">Click <strong>+ Add Budget</strong> to set a monthly limit.</p>
                </div>`;
            return;
        }

        data.forEach(budget => {
            const limit = parseFloat(budget.monthly_limit) || 1;
            const spent = parseFloat(budget.actual_spent) || 0;
            const percentage = Math.min((spent / limit) * 100, 100).toFixed(1);
            const remaining = Math.max(limit - spent, 0);

            // Color coding: green → amber → red based on % used
            let barColor = 'bg-green-500';
            let badgeColor = 'bg-green-50 text-green-700';
            let statusText = 'On Track';
            if (percentage >= 100) {
                barColor = 'bg-red-500';
                badgeColor = 'bg-red-50 text-red-700';
                statusText = 'Exceeded';
            } else if (percentage >= 75) {
                barColor = 'bg-amber-500';
                badgeColor = 'bg-amber-50 text-amber-700';
                statusText = 'Near Limit';
            } else if (percentage >= 50) {
                barColor = 'bg-blue-500';
                badgeColor = 'bg-blue-50 text-blue-700';
                statusText = 'Active';
            }

            const fmtINR = (v) => '₹' + parseFloat(v).toLocaleString('en-IN', { minimumFractionDigits: 0 });

            budgetList.innerHTML += `
                <div class="border border-gray-100 rounded-xl p-4 bg-white hover:shadow-sm transition group"
                     data-budget-category="${budget.category}">
                    <!-- Header row: category name, status badge, prediction badge, delete button -->
                    <div class="flex justify-between items-start mb-2">
                        <div class="flex flex-wrap items-center gap-1.5">
                            <span class="font-bold text-gray-800 text-sm leading-tight">${budget.category}</span>
                            <span class="px-1.5 py-0.5 rounded text-[10px] font-semibold ${badgeColor}">${statusText}</span>
                            <!-- Prophet prediction badge injected here by fetchOverspendPredictions() -->
                            <span class="prediction-badge"></span>
                        </div>
                        <button onclick="deleteBudget(${budget.id})" 
                            class="text-gray-300 hover:text-red-500 transition opacity-0 group-hover:opacity-100 shrink-0 ml-2"
                            title="Delete this budget">
                            <i class="ri-close-circle-line text-lg"></i>
                        </button>
                    </div>

                    <!-- Progress bar: actual spending vs monthly limit -->
                    <div class="w-full bg-gray-100 rounded-full h-2 overflow-hidden mb-2">
                        <div class="${barColor} h-full rounded-full transition-all duration-1000 ease-out" 
                             style="width: ${percentage}%"></div>
                    </div>

                    <!-- Amounts row: spent, limit, remaining, created date -->
                    <div class="flex justify-between text-xs font-semibold text-gray-500">
                        <span>Spent: <span class="text-gray-900">${fmtINR(spent)}</span></span>
                        <span>Limit: <span class="text-gray-900">${fmtINR(limit)}</span></span>
                    </div>
                    <div class="flex justify-between text-[11px] text-gray-400 mt-1">
                        <span>Remaining: <span class="font-medium text-gray-600">${fmtINR(remaining)}</span></span>
                        <span>Set on ${budget.created_at}</span>
                    </div>
                </div>`;
        });

        // After all cards are rendered, overlay Prophet overspend prediction badges
        fetchOverspendPredictions();

    } catch (error) {
        console.error('Error fetching budgets:', error);
        if (budgetList) budgetList.innerHTML = `<div class="text-center text-red-400 text-sm py-6">Failed to load budgets.</div>`;
    }
}
fetchBudgets();

// Delete a budget by id
async function deleteBudget(budgetId) {
    if (!confirm('Delete this budget limit? This will not affect your transactions.')) return;
    try {
        const res = await fetch(`/api/transactions/budget/${budgetId}/delete/`, {
            method: 'DELETE',
            headers: { 'X-CSRFToken': getCookie('csrftoken'), ...authHeaders },
        });
        if (res.ok) {
            fetchBudgets();
        } else {
            alert('Could not delete budget. Please try again.');
        }
    } catch (e) {
        console.error('Delete budget error:', e);
    }
}

// Save Budget logic for modal — uses `category` and `monthly_limit` field names
if (document.getElementById('saveBudgetBtn')) {
    document.getElementById('saveBudgetBtn').addEventListener('click', async () => {
        const category = document.getElementById('budgetCategory').value;
        const amount = parseFloat(document.getElementById('budgetAmount').value);

        if (!category || !amount || amount <= 0) {
            alert('Please select a category and enter a valid amount.');
            return;
        }

        // Disable button to prevent double submit
        const btn = document.getElementById('saveBudgetBtn');
        btn.disabled = true;
        btn.textContent = 'Saving...';

        try {
            const res = await fetch('/api/transactions/budget/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCookie('csrftoken'), ...authHeaders },
                body: JSON.stringify({ category: category, monthly_limit: amount })
            });
            if (res.ok) {
                document.getElementById('addBudgetModal').classList.add('hidden');
                document.getElementById('budgetAmount').value = '';
                document.getElementById('budgetCategory').value = '';
                fetchBudgets();
            } else {
                const err = await res.json();
                alert('Error saving budget: ' + JSON.stringify(err));
            }
        } catch (e) {
            console.error(e);
            alert('Failed to communicate with the server.');
        } finally {
            btn.disabled = false;
            btn.textContent = 'Save Budget';
        }
    });
}



// ==========================================
// FEATURE 1: AI SUGGEST ALL BUDGETS
// Opens modal, fetches XGBoost-backed suggestions,
// lets user apply one or all at once.
// ==========================================

// Stores suggestions from last AI fetch (used by Apply All)
let _suggestionsData = [];

async function openAISuggestModal() {
    const modal = document.getElementById('aiSuggestModal');
    const list = document.getElementById('aiSuggestList');
    if (!modal || !list) return;
    modal.classList.remove('hidden');
    list.innerHTML = `
        <div class="flex items-center justify-center py-10 text-indigo-500">
            <i class="ri-loader-4-line animate-spin text-3xl mr-3"></i>
            <span class="text-sm font-semibold">Analysing your spending history with XGBoost...</span>
        </div>`;
    _suggestionsData = [];

    try {
        const res = await fetch('/api/insights/ai-budget-suggestions/', { headers: authHeaders });
        const data = await res.json();

        if (!data.suggestions || data.suggestions.length === 0) {
            list.innerHTML = `<div class="text-center text-gray-400 text-sm py-8">${data.message || 'No suggestions available yet. Add more transactions.'}</div>`;
            return;
        }

        _suggestionsData = data.suggestions;
        list.innerHTML = '';

        data.suggestions.forEach((s, idx) => {
            const hasExisting = s.current_limit !== null;
            const existingText = hasExisting
                ? `<span class="text-gray-400 line-through mr-1">₹${s.current_limit.toLocaleString('en-IN', { maximumFractionDigits: 0 })}</span>`
                : '<span class="text-gray-400 mr-1">No limit set</span>';
            const isHighRisk = s.reason.includes('XGBoost flagged');
            const badgeColor = isHighRisk ? 'bg-red-50 text-red-600 border-red-200' : 'bg-blue-50 text-blue-600 border-blue-200';
            const badgeLabel = isHighRisk ? '🔴 High Risk (XGBoost)' : '✅ Avg Spend';

            list.innerHTML += `
                <div class="border border-gray-100 rounded-xl p-4 hover:bg-gray-50 transition">
                    <div class="flex justify-between items-start mb-2">
                        <div>
                            <span class="font-bold text-gray-800">${s.category}</span>
                            <span class="ml-2 text-xs px-2 py-0.5 rounded-full border font-semibold ${badgeColor}">${badgeLabel}</span>
                        </div>
                        <button onclick="applySingleSuggestion('${s.category}', ${s.suggested_limit})"
                            class="px-3 py-1.5 text-xs font-bold bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition">
                            Set ₹${s.suggested_limit.toLocaleString('en-IN', { maximumFractionDigits: 0 })}
                        </button>
                    </div>
                    <div class="flex items-center gap-2 text-xs text-gray-500 mb-1">
                        ${existingText} → <span class="font-bold text-indigo-700">₹${s.suggested_limit.toLocaleString('en-IN', { maximumFractionDigits: 0 })}/mo</span>
                        <span class="text-gray-300">|</span>
                        <span>Avg: ₹${s.current_avg_spend.toLocaleString('en-IN', { maximumFractionDigits: 0 })}/mo</span>
                    </div>
                    <p class="text-xs text-gray-400 leading-relaxed">${s.reason}</p>
                </div>`;
        });
    } catch (e) {
        list.innerHTML = `<div class="text-center text-red-400 text-sm py-8">Failed to load suggestions. Please try again.</div>`;
        console.error(e);
    }
}

async function applySingleSuggestion(category, amount) {
    try {
        const res = await fetch('/api/transactions/budget/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCookie('csrftoken'), ...authHeaders },
            body: JSON.stringify({ category, monthly_limit: amount })
        });
        if (res.ok) {
            fetchBudgets();
            // Visual feedback: show a tiny toast effect in the button
            alert(`✅ Budget for "${category}" set to ₹${amount.toLocaleString('en-IN', { maximumFractionDigits: 0 })}/mo`);
        }
    } catch (e) { console.error(e); }
}

async function applyAllSuggestions() {
    if (!_suggestionsData.length) return;
    if (!confirm(`Apply all ${_suggestionsData.length} AI-suggested budgets? This will create or update your limits.`)) return;

    const promises = _suggestionsData.map(s =>
        fetch('/api/transactions/budget/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCookie('csrftoken'), ...authHeaders },
            body: JSON.stringify({ category: s.category, monthly_limit: s.suggested_limit })
        })
    );
    await Promise.all(promises);
    document.getElementById('aiSuggestModal').classList.add('hidden');
    fetchBudgets();
    alert(`✅ ${_suggestionsData.length} AI budgets applied successfully!`);
}


// ==========================================
// FEATURE 2: AI BUDGET PLANNER (50/30/20)
// Opens modal, lets user enter income, calls
// Gemini+50/30/20 backend, shows color-coded plan.
// ==========================================

let _plannerData = [];

function openAIPlannerModal() {
    const modal = document.getElementById('aiBudgetPlannerModal');
    if (!modal) return;
    modal.classList.remove('hidden');
    document.getElementById('plannerResults').classList.add('hidden');
    document.getElementById('plannerInputSection').classList.remove('hidden');
    document.getElementById('plannerIncomeInput').value = '';
}

async function generateAIBudgetPlan() {
    const incomeInput = document.getElementById('plannerIncomeInput');
    const income = parseFloat(incomeInput.value);
    if (!income || income <= 0) {
        alert('Please enter your monthly income to generate a plan.');
        return;
    }

    const btn = document.getElementById('generatePlanBtn');
    btn.disabled = true;
    btn.innerHTML = '<i class="ri-loader-4-line animate-spin"></i> Generating...';

    try {
        const res = await fetch('/api/insights/ai-budget-planner/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCookie('csrftoken'), ...authHeaders },
            body: JSON.stringify({ monthly_income: income })
        });
        const data = await res.json();

        if (data.error) {
            alert(data.error);
            return;
        }

        _plannerData = data.allocations;
        document.getElementById('plannerSummary').textContent = data.summary;
        document.getElementById('plannerResults').classList.remove('hidden');

        // Render allocation table
        const table = document.getElementById('plannerTable');
        table.innerHTML = '';

        const colorMap = {
            blue: { bar: 'bg-blue-500', badge: 'bg-blue-50 text-blue-700', text: 'text-blue-700' },
            purple: { bar: 'bg-purple-500', badge: 'bg-purple-50 text-purple-700', text: 'text-purple-700' },
            green: { bar: 'bg-green-500', badge: 'bg-green-50 text-green-700', text: 'text-green-700' },
        };

        data.allocations.forEach(a => {
            const c = colorMap[a.color] || colorMap.blue;
            const fmtINR = (v) => '₹' + parseFloat(v).toLocaleString('en-IN', { maximumFractionDigits: 0 });
            table.innerHTML += `
                <div class="flex items-center gap-3 p-3 bg-gray-50 rounded-xl border border-gray-100">
                    <div class="w-2 h-8 ${c.bar} rounded-full shrink-0"></div>
                    <div class="flex-1 min-w-0">
                        <div class="flex items-center justify-between mb-1">
                            <span class="font-semibold text-gray-800 text-sm truncate">${a.category}</span>
                            <div class="flex items-center gap-2 shrink-0 ml-2">
                                <span class="text-xs px-2 py-0.5 rounded-full font-bold ${c.badge}">${a.bucket}</span>
                                <span class="font-bold ${c.text} text-sm">${fmtINR(a.amount)}</span>
                            </div>
                        </div>
                        <div class="w-full bg-gray-200 rounded-full h-1.5 overflow-hidden">
                            <div class="${c.bar} h-full rounded-full" style="width: ${Math.min(a.pct, 100)}%"></div>
                        </div>
                    </div>
                    <span class="text-xs text-gray-400 font-medium w-9 text-right shrink-0">${a.pct}%</span>
                </div>`;
        });

        // Show total vs income check
        const remaining = income - data.total_allocated;
        if (Math.abs(remaining) > 100) {
            table.innerHTML += `
                <div class="p-3 bg-amber-50 border border-amber-200 rounded-xl text-xs text-amber-700 font-medium">
                    ⚖️ Total allocated: ₹${data.total_allocated.toLocaleString('en-IN', { maximumFractionDigits: 0 })} 
                    | Unallocated: ₹${remaining.toLocaleString('en-IN', { maximumFractionDigits: 0 })}
                    — Consider adding to Investments or Emergency Fund.
                </div>`;
        }
    } catch (e) {
        console.error(e);
        alert('Failed to generate budget plan. Please try again.');
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<i class="ri-sparkling-2-fill"></i> Generate Plan';
    }
}

async function applyAllPlanBudgets() {
    if (!_plannerData.length) return;
    if (!confirm(`Apply all ${_plannerData.length} budget allocations? Existing limits will be updated.`)) return;

    const promises = _plannerData.map(a =>
        fetch('/api/transactions/budget/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCookie('csrftoken'), ...authHeaders },
            body: JSON.stringify({ category: a.category, monthly_limit: a.amount })
        })
    );
    await Promise.all(promises);
    document.getElementById('aiBudgetPlannerModal').classList.add('hidden');
    fetchBudgets();
    alert(`✅ ${_plannerData.length} budget limits applied from your AI plan!`);
}


// ==========================================
// FEATURE 3: OVERSPENDING PREDICTIONS
// Fetches Prophet/linear EOMonth predictions per budget,
// then overlays risk badges on the budget overview cards.
// Called automatically after fetchBudgets() renders cards.
// ==========================================

async function fetchOverspendPredictions() {
    try {
        const res = await fetch('/api/insights/overspend-predictions/', { headers: authHeaders });
        if (!res.ok) return;
        const predictions = await res.json();

        // Map category → prediction
        const predMap = {};
        predictions.forEach(p => { predMap[p.category] = p; });

        // Find all budget cards and inject the prediction badge
        const budgetList = document.getElementById('budgetOverviewList');
        if (!budgetList) return;

        const cards = budgetList.querySelectorAll('[data-budget-category]');
        cards.forEach(card => {
            const cat = card.getAttribute('data-budget-category');
            const pred = predMap[cat];
            if (!pred) return;

            const badgeContainer = card.querySelector('.prediction-badge');
            if (!badgeContainer) return;

            let badge = '';
            // 'exceeded' is skipped — the main status badge already shows "Exceeded" in red
            if (pred.risk_level === 'danger') {
                badge = `<span class="text-[10px] font-bold text-red-600 bg-red-50 border border-red-200 px-1.5 py-0.5 rounded-full" title="Prophet predicts ₹${pred.predicted_eom.toLocaleString('en-IN', { maximumFractionDigits: 0 })} by month-end">⚠️ Will Exceed +₹${pred.overspend_amount.toLocaleString('en-IN', { maximumFractionDigits: 0 })}</span>`;
            } else if (pred.risk_level === 'warning') {
                badge = `<span class="text-[10px] font-bold text-amber-600 bg-amber-50 border border-amber-200 px-1.5 py-0.5 rounded-full" title="On pace to use ${pred.pct_predicted}% of budget">📈 ${pred.pct_predicted}% by EOM</span>`;
            }
            badgeContainer.innerHTML = badge;
        });
    } catch (e) {
        console.error('Overspend predictions error:', e);
    }
}


// Fetch Savings Goals for Dashboard
async function fetchSavingsGoals() {
    try {
        const response = await fetch('/api/insights/goal-progress/', { headers: authHeaders });
        if (!response.ok) return;
        const data = await response.json();
        const goalsList = document.getElementById('savingsGoalsList');
        if (!goalsList) return;

        goalsList.innerHTML = '';

        if (!data.goals || data.goals.length === 0) {
            goalsList.innerHTML = '<div class="col-span-full flex items-center justify-center p-8 text-sm text-gray-500 bg-gray-50 rounded-xl border border-dashed border-gray-200">No savings goals set. Create one to start tracking!</div>';
            return;
        }

        data.goals.forEach(goal => {
            const target = parseFloat(goal.target_amount);
            const saved = parseFloat(goal.saved_amount || 0);
            const percentage = Math.min((saved / target) * 100, 100);

            const today = new Date();
            const deadline = new Date(goal.deadline);
            const timeDiff = deadline.getTime() - today.getTime();
            const daysLeft = Math.ceil(timeDiff / (1000 * 3600 * 24));

            let statusBadge = '';
            let isOverdue = false;
            if (daysLeft < 0 && percentage < 100) {
                isOverdue = true;
                statusBadge = `<span class="text-xs font-bold text-red-600">Overdue</span>`;
            } else if (percentage >= 100) {
                statusBadge = `<span class="text-xs font-bold text-green-600">Completed</span>`;
            } else {
                statusBadge = `<span class="text-xs font-bold text-blue-600">${daysLeft} days left</span>`;
            }

            goalsList.innerHTML += `
                <div class="bg-white border border-gray-100 p-5 rounded-2xl shadow-sm hover:shadow-md transition flex flex-col min-w-0">
                    <div class="flex justify-between items-start mb-4 gap-2">
                        <div class="flex items-center gap-3 min-w-0">
                            <div class="w-11 h-11 shrink-0 bg-blue-50 text-blue-500 rounded-full flex items-center justify-center">
                                <i class="ri-flag-fill text-xl"></i>
                            </div>
                            <div class="min-w-0">
                                <h4 class="font-bold text-gray-900 truncate">${goal.goal_name}</h4>
                                <p class="text-xs font-medium text-gray-500 mt-0.5">Target: ₹${target.toLocaleString('en-IN')} by ${deadline.toLocaleDateString('en-US', { day: 'numeric', month: 'short' })}</p>
                            </div>
                        </div>
                        <div class="flex items-center gap-2 shrink-0">
                           ${statusBadge}
                           <button onclick="deleteSavingsGoal(${goal.id})" class="text-gray-400 hover:text-red-500 transition" title="Delete Goal">
                               <i class="ri-close-line text-lg"></i>
                           </button>
                        </div>
                    </div>
                    
                    <div class="w-full bg-gray-100 rounded-full h-2.5 overflow-hidden mb-3">
                        <div class="${percentage >= 100 ? 'bg-green-500' : (isOverdue ? 'bg-red-500' : 'bg-blue-500')} h-full rounded-full transition-all duration-1000 ease-out" style="width: ${percentage}%"></div>
                    </div>
                    
                    <div class="flex justify-between items-center text-xs font-bold mb-4">
                        <span class="text-gray-500">Saved: <span class="text-gray-900">₹${saved.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span></span>
                        <span class="text-gray-500">Left: <span class="text-gray-900">₹${Math.max(target - saved, 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span></span>
                    </div>
                    
                    <div class="flex flex-wrap gap-2 mt-auto">
                        <button onclick="openDepositModal(${goal.id})" class="text-sm px-4 py-1.5 bg-gray-100 hover:bg-gray-200 text-gray-800 font-semibold rounded-lg transition">
                            Add Deposit
                        </button>
                        ${percentage >= 100 ? `
                        <button onclick="withdrawSavingsGoal(${goal.id})" class="text-sm px-4 py-1.5 bg-green-500 hover:bg-green-600 text-white font-semibold rounded-lg transition shadow-sm">
                            Withdraw
                        </button>` : ''}
                    </div>
                </div>
            `;
        });
    } catch (error) {
        console.error('Error fetching savings goals:', error);
    }
}
if (document.getElementById('savingsGoalsList')) fetchSavingsGoals();

// Save Goal logic for modal
if (document.getElementById('saveGoalBtn')) {
    document.getElementById('saveGoalBtn').addEventListener('click', async () => {
        const goal_name = document.getElementById('goalTitle').value;
        const target_amount = parseFloat(document.getElementById('goalAmount').value);
        const deadline = document.getElementById('goalDeadline').value;

        if (!goal_name || !target_amount || !deadline) {
            alert("Please fill in all goal fields.");
            return;
        }

        try {
            const res = await fetch('/api/insights/add-goal/', {
                method: 'POST',
                headers: { "Content-Type": "application/json", "X-CSRFToken": getCookie('csrftoken'), ...authHeaders },
                body: JSON.stringify({ goal_name, target_amount, deadline })
            });
            if (res.ok) {
                document.getElementById('addGoalModal').classList.add('hidden');
                document.getElementById('goalTitle').value = '';
                document.getElementById('goalAmount').value = '';
                document.getElementById('goalDeadline').value = '';
                fetchSavingsGoals();
            } else {
                alert("Error saving goal.");
            }
        } catch (e) {
            console.error(e);
            alert("Failed to communicate with the server.");
        }
    });
}

// Deposit and Delete Logic
let currentDepositGoalId = null;

function openDepositModal(goalId) {
    currentDepositGoalId = goalId;
    document.getElementById('depositAmount').value = '';
    document.getElementById('addDepositModal').classList.remove('hidden');
}

if (document.getElementById('saveDepositBtn')) {
    document.getElementById('saveDepositBtn').addEventListener('click', async () => {
        const amount = parseFloat(document.getElementById('depositAmount').value);
        if (!amount || amount <= 0) {
            alert("Please enter a valid deposit amount.");
            return;
        }

        try {
            const res = await fetch('/api/insights/update-goal-savings/', {
                method: 'POST',
                headers: { "Content-Type": "application/json", "X-CSRFToken": getCookie('csrftoken'), ...authHeaders },
                body: JSON.stringify({ goal_id: currentDepositGoalId, deposit_amount: amount })
            });
            if (res.ok) {
                document.getElementById('addDepositModal').classList.add('hidden');
                fetchSavingsGoals();
                if (typeof fetchDashboardData === 'function') fetchDashboardData();
                else location.reload();
            } else {
                const data = await res.json();
                alert(data.error || "Error adding deposit.");
            }
        } catch (e) {
            console.error(e);
            alert("Failed to communicate with the server.");
        }
    });
}

async function withdrawSavingsGoal(goalId) {
    if (!confirm('Are you sure you want to withdraw this completed goal? The funds will be securely added back to your main balance.')) return;

    try {
        const res = await fetch(`/api/insights/withdraw-goal-savings/`, {
            method: 'POST',
            headers: { "Content-Type": "application/json", "X-CSRFToken": getCookie('csrftoken'), ...authHeaders },
            body: JSON.stringify({ goal_id: goalId })
        });
        if (res.ok) {
            fetchSavingsGoals();
            if (typeof fetchDashboardData === 'function') fetchDashboardData();
            else location.reload();
        } else {
            const data = await res.json();
            alert(data.error || "Error withdrawing goal funds.");
        }
    } catch (e) {
        console.error(e);
        alert("Failed to communicate with the server.");
    }
}

async function deleteSavingsGoal(goalId) {
    if (!confirm('Are you sure you want to delete this goal?')) return;

    try {
        const res = await fetch(`/api/insights/delete-goal/${goalId}/`, {
            method: 'DELETE',
            headers: { "X-CSRFToken": getCookie('csrftoken'), ...authHeaders }
        });
        if (res.ok) {
            fetchSavingsGoals();
        } else {
            alert("Error deleting goal.");
        }
    } catch (e) {
        console.error(e);
        alert("Failed to communicate with the server.");
    }
}
