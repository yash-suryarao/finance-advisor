const voiceEntryBtn = document.getElementById('voiceEntryBtn');
const transactionModal = document.getElementById('transactionModal');
const authHeaders = {
    "Authorization": `Bearer ${localStorage.getItem('access_token')}`
};
const editAmount = document.getElementById('editAmount');
const editCategory = document.getElementById('editCategory');
const editType = document.getElementById('editType');
const saveTransactionBtn = document.getElementById('saveTransaction');
const cancelTransactionBtn = document.getElementById('cancelTransaction');

if ('SpeechRecognition' in window || 'webkitSpeechRecognition' in window) {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    const recognition = new SpeechRecognition();

    recognition.continuous = false;
    recognition.lang = 'en-US';
    recognition.interimResults = false;
    recognition.maxAlternatives = 1;

    voiceEntryBtn.addEventListener('click', () => {
        recognition.start();
        alert("Listening... Speak your transaction details.");
    });

    recognition.onresult = async (event) => {
        const voiceText = event.results[0][0].transcript;
        console.log("Voice Input:", voiceText);

        // Show loading
        voiceEntryBtn.textContent = "Processing...";
        voiceEntryBtn.disabled = true;

        const response = await fetch('/api/transactions/process-voice-entry/', {
            method: 'POST',
            headers: {
                "Content-Type": "application/json",
                ...authHeaders
            },
            body: JSON.stringify({ voice_text: voiceText })
        });

        voiceEntryBtn.textContent = "Voice Entry";
        voiceEntryBtn.disabled = false;

        const data = await response.json();

        if (data.error) {
            alert("Error processing voice input.");
            return;
        }

        // Populate transaction details in modal
        editAmount.value = data.amount;
        editCategory.value = data.category;
        editType.value = data.transaction_type;

        transactionModal.classList.remove('hidden');
    };

    recognition.onerror = (event) => {
        alert("Voice recognition error: " + event.error);
    };
}

// Handle transaction save
saveTransactionBtn.addEventListener('click', async () => {
    const transactionData = {
        amount: parseFloat(editAmount.value),
        transaction_type: editType.value,
        category: editCategory.value
    };

    const response = await fetch('/api/transactions/confirm-voice-transaction/', {
        method: 'POST',
        headers: {
            "Content-Type": "application/json",
            ...authHeaders
        },
        body: JSON.stringify(transactionData)
    });

    const result = await response.json();

    if (result.message) {
        alert("Transaction saved successfully!");
        transactionModal.classList.add('hidden');
    } else {
        alert("Error saving transaction.");
    }
});

cancelTransactionBtn.addEventListener('click', () => {
    transactionModal.classList.add('hidden');
});

// Fetch User Data from API

async function fetchUserProfile() {
    try {
        const response = await fetch('/users/api/user-profile/', { headers: authHeaders });
        const data = await response.json();
        document.getElementById('userAvatar').src = data.avatar;
        document.getElementById('userName').textContent = data.username;
        document.getElementById('currentDate').textContent = new Date().toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' });
    } catch (error) {
        console.error('Error fetching user profile:', error);
    }
}



// Toggle User Dropdown Menu
document.getElementById('userDropdownBtn').addEventListener('click', () => {
    document.getElementById('userDropdown').classList.toggle('hidden');
});

// Close dropdown when clicking outside
document.addEventListener('click', (event) => {
    const dropdown = document.getElementById('userDropdown');
    if (!document.getElementById('userDropdownBtn').contains(event.target) && !dropdown.contains(event.target)) {
        dropdown.classList.add('hidden');
    }
});



// Set Savings Progress Bar Width will be handled by fetchDashboardStats()

// Load User Data on Page Load
fetchUserProfile();

// Initialize ECharts instances
const incomeVsExpensesChart = echarts.init(document.getElementById('incomeVsExpensesChart'));
const financialHealthGauge = echarts.init(document.getElementById('financialHealthGauge'));

window.updateHealthGauge = function (score, label) {
    let healthColor = '#F59E0B'; // Yellow warning fallback
    if (label === 'Excellent') healthColor = '#10B981'; // Green
    if (label === 'Poor') healthColor = '#EF4444'; // Red

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

async function fetchDashboardStats() {
    try {
        const response = await fetch('/frontend/financial-summary/', { headers: authHeaders });
        const data = await response.json();

        document.getElementById('totalBalance').textContent = `₹${parseFloat(data.total_balance).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;
        document.getElementById('balanceChange').innerHTML = `<i class="ri-arrow-${data.balance_change >= 0 ? 'up' : 'down'}-line"></i> ${data.balance_change}%`;
        document.getElementById('balanceChange').className = `text-sm mt-2 ${data.balance_change >= 0 ? 'text-green-600' : 'text-red-600'}`;

        document.getElementById('monthlyIncome').textContent = `₹${parseFloat(data.monthly_income).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;
        document.getElementById('incomeChange').innerHTML = `<i class="ri-arrow-${data.income_change >= 0 ? 'up' : 'down'}-line"></i> ${data.income_change}%`;
        document.getElementById('incomeChange').className = `text-sm mt-2 ${data.income_change >= 0 ? 'text-green-600' : 'text-red-600'}`;

        document.getElementById('monthlyExpenses').textContent = `₹${parseFloat(Math.abs(data.monthly_expenses)).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;
        document.getElementById('expenseChange').innerHTML = `<i class="ri-arrow-${data.expense_change >= 0 ? 'up' : 'down'}-line"></i> ${Math.abs(data.expense_change)}%`;
        document.getElementById('expenseChange').className = `text-sm font-medium ${data.expense_change <= 0 ? 'text-green-500' : 'text-red-500'}`;

        document.getElementById('savingsAmount').textContent = `₹${parseFloat(data.savings).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;
        document.getElementById('savingsChange').innerHTML = `<i class="ri-arrow-${data.savings_change >= 0 ? 'up' : 'down'}-line"></i> ${Math.abs(data.savings_change)}%`;
        document.getElementById('savingsChange').className = `text-sm font-medium ${data.savings_change >= 0 ? 'text-green-500' : 'text-red-500'}`;

        // Financial Health Progress Bars
        document.getElementById('savingsRateLabel').textContent = `${data.savings_rate}%`;
        document.getElementById('savingsRateBar').style.width = `${Math.min(data.savings_rate, 100)}%`;

        document.getElementById('debtRatioLabel').textContent = `${data.debt_ratio}%`;
        document.getElementById('debtRatioBar').style.width = `${Math.min(data.debt_ratio, 100)}%`;

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

        // Restrict to max 6 transactions for the dashboard view
        transactions.slice(0, 6).forEach(transaction => {
            let iconClass = "ri-file-list-line text-gray-600";  // Default icon
            let bgClass = "bg-gray-100";
            let amountClass = "text-red-600"; // Default to expense

            // Categorizing transactions
            switch (transaction.category_name.toLowerCase()) {
                case "salary":
                    iconClass = "ri-bank-line text-green-600";
                    bgClass = "bg-green-100";
                    amountClass = "text-green-600"; // Income
                    break;
                case "freelance":
                    iconClass = "ri-briefcase-line text-green-600";
                    bgClass = "bg-green-100";
                    amountClass = "text-green-600"; // Income
                    break;
                case "investment":
                    iconClass = "ri-stock-line text-green-600";
                    bgClass = "bg-green-100";
                    amountClass = "text-green-600"; // Income
                    break;
                case "bonus":
                    iconClass = "ri-gift-line text-green-600";
                    bgClass = "bg-green-100";
                    amountClass = "text-green-600"; // Income
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
                            <p class="font-bold ${amountClass}">${transaction.category_type === "income" ? "+" : "-"}${formattedAmount}</p>
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
    try {
        const response = await fetch('/api/insights/ai-insights/', { headers: authHeaders });
        const data = await response.json();

        document.getElementById('aiInsightsBox').innerHTML = '';

        if (data.length === 0) {
            document.getElementById('aiInsightsBox').innerHTML = '<div class="col-span-2 flex items-center justify-center p-8 text-sm text-gray-500 bg-gray-50 rounded-xl border border-dashed border-gray-200">No new AI insights specifically for this month.</div>';
        }

        data.forEach(insight => {
            let isWarning = insight.title.toLowerCase().includes('overspending');
            let borderColor = isWarning ? 'border-red-500' : 'border-blue-500';
            let bgColor = isWarning ? 'bg-red-50' : 'bg-blue-50';
            let iconColor = isWarning ? 'text-red-500' : 'text-blue-500';
            let titleColor = isWarning ? 'text-red-700' : 'text-blue-700';
            let textColor = isWarning ? 'text-red-600' : 'text-blue-600';
            let subtleTextColor = isWarning ? 'text-red-400' : 'text-blue-400';
            let btnColor = isWarning ? 'text-red-700 hover:text-red-800' : 'text-blue-700 hover:text-blue-800';
            let icon = isWarning ? 'ri-error-warning-line' : 'ri-information-line';

            document.getElementById('aiInsightsBox').innerHTML += `
                <div class="${bgColor} rounded-xl border-l-4 ${borderColor} p-5 hover:shadow-sm transition">
                    <div class="flex items-start mb-2">
                        <i class="${icon} ${iconColor} text-lg mr-2 mt-0.5"></i>
                        <h4 class="text-sm font-bold ${titleColor} leading-tight">${insight.title}</h4>
                    </div>
                    <p class="text-sm ${textColor} mb-4 ml-6 leading-relaxed">${insight.message}</p>
                    <div class="ml-6 flex items-center justify-between">
                        <span class="text-xs font-semibold ${subtleTextColor}">Category: <span class="uppercase tracking-wide">${insight.category}</span></span>
                        ${insight.suggested_budget ? `
                            <button class="acceptBudgetBtn text-xs font-bold ${btnColor} flex items-center" 
                                data-category="${insight.category}" data-budget="${insight.suggested_budget}">
                                Apply Budget (₹${insight.suggested_budget}) <i class="ri-arrow-right-line ml-1"></i>
                            </button>
                        ` : `
                            <a href="${insight.action_url}" class="text-xs font-bold ${btnColor} flex items-center">View details <i class="ri-arrow-right-line ml-1"></i></a>
                        `}
                    </div>
                </div>
            `;
        });

        // Attach event listeners to "Accept Suggested Budget" buttons
        document.querySelectorAll('.acceptBudgetBtn').forEach(btn => {
            btn.addEventListener('click', function () {
                acceptSuggestedBudget(this.getAttribute('data-category'), this.getAttribute('data-budget'));
            });
        });

    } catch (error) {
        console.error('Error fetching AI insights:', error);
    }
}

fetchAIInsights();

async function acceptSuggestedBudget(category, newLimit) {
    try {
        const response = await fetch('/api/insights/accept-suggested-budget/', {
            method: 'POST',
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": getCookie('csrftoken')
            },
            body: JSON.stringify({ category, new_limit: newLimit })
        });

        const result = await response.json();

        if (response.ok && result.message) {
            alert(result.message);
            fetchAIInsights(); // Refresh insights after updating budget
            if (typeof fetchBudgetData === 'function') fetchBudgetData(); // Refresh budget if on that page
        } else {
            alert(result.error || "Error updating budget.");
        }
    } catch (e) {
        console.error(e);
        alert("Failed to communicate with the server.");
    }
}

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



async function fetchUpcomingBills() {
    try {
        const response = await fetch('/api/transactions/upcoming-bills/', { headers: authHeaders });
        const bills = await response.json();
        const billsList = document.getElementById('billsList');

        billsList.innerHTML = '';

        if (bills.length === 0) {
            billsList.innerHTML = '<div class="flex items-center justify-center h-full text-sm font-medium text-gray-500">No upcoming bills for now.</div>';
            return;
        }

        bills.forEach(bill => {
            let textColor = bill.days_remaining <= 7 ? "text-red-600" : "text-gray-900";
            let formattedAmount = `₹${bill.amount.toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;

            billsList.innerHTML += `
                <div class="flex items-center justify-between p-4 bg-white border border-gray-100 rounded-xl hover:shadow-sm transition">
                    <div class="flex items-center gap-4">
                        <div class="w-10 h-10 bg-blue-50 text-blue-500 rounded-xl flex items-center justify-center">
                            <i class="ri-calendar-line text-lg"></i>
                        </div>
                        <div>
                            <h4 class="font-bold text-gray-900 text-sm">${bill.name}</h4>
                            <p class="text-xs text-gray-500 font-medium">${bill.category}</p>
                        </div>
                    </div>
                    <div class="text-right">
                        <p class="font-bold text-gray-900 text-sm">${formattedAmount}</p>
                        <p class="text-xs font-medium ${textColor}">Due in ${bill.days_remaining}d</p>
                    </div>
                </div>
            `;
        });

    } catch (error) {
        console.error('Error fetching upcoming bills:', error);
    }
}

fetchUpcomingBills();


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
document.getElementById('notificationBtn').addEventListener('click', () => {
    document.getElementById('notificationDropdown').classList.toggle('hidden');
    fetchUserNotifications();
});

fetchUserNotifications(); // Load on page load


// Fetch Budgets for Dashboard
async function fetchBudgets() {
    try {
        const response = await fetch('/api/budget/', { headers: authHeaders });
        if (!response.ok) return;
        const data = await response.json();
        const budgetList = document.getElementById('budgetOverviewList');
        if (!budgetList) return;

        budgetList.innerHTML = '';

        if (!data || data.length === 0) {
            budgetList.innerHTML = '<div class="flex items-center justify-center h-full text-sm font-medium text-gray-500 mt-10">No active budgets.</div>';
            return;
        }

        data.forEach(budget => {
            const utilization = budget.spent_amount !== undefined ? budget.spent_amount : (budget.spent ? budget.spent : 0);
            const limit = parseFloat(budget.limit_amount || budget.amount || 1);
            const percentage = Math.min((utilization / limit) * 100, 100);
            const formattedLimit = `₹${limit.toLocaleString('en-IN', { minimumFractionDigits: 0 })}`;
            const formattedSpent = `₹${utilization.toLocaleString('en-IN', { minimumFractionDigits: 0 })}`;

            let colorClass = "bg-green-500";
            if (percentage > 90) colorClass = "bg-red-500";
            else if (percentage > 75) colorClass = "bg-yellow-500";
            else if (percentage > 50) colorClass = "bg-blue-500";

            budgetList.innerHTML += `
                <div>
                    <div class="flex justify-between items-center mb-2">
                        <span class="text-sm font-bold text-gray-800">${budget.category_name || budget.category}</span>
                        <span class="text-xs font-semibold text-gray-500">${formattedSpent} / ${formattedLimit}</span>
                    </div>
                    <div class="w-full bg-gray-100 rounded-full h-2 overflow-hidden">
                        <div class="${colorClass} h-full rounded-full transition-all duration-1000 ease-out" style="width: ${percentage}%"></div>
                    </div>
                </div>
            `;
        });
    } catch (error) {
        console.error('Error fetching budgets:', error);
    }
}
fetchBudgets();

// Save Budget logic for modal
if (document.getElementById('saveBudgetBtn')) {
    document.getElementById('saveBudgetBtn').addEventListener('click', async () => {
        const category = document.getElementById('budgetCategory').value;
        const amount = parseFloat(document.getElementById('budgetAmount').value);

        if (!category || !amount) {
            alert("Please select a category and enter an amount");
            return;
        }

        try {
            const res = await fetch('/api/budget/create/', {
                method: 'POST',
                headers: { "Content-Type": "application/json", "X-CSRFToken": getCookie('csrftoken'), ...authHeaders },
                body: JSON.stringify({ category, limit_amount: amount })
            });
            if (res.ok) {
                document.getElementById('addBudgetModal').classList.add('hidden');
                document.getElementById('budgetAmount').value = '';
                fetchBudgets();
            } else {
                alert("Error saving budget.");
            }
        } catch (e) {
            console.error(e);
            alert("Failed to communicate with the server.");
        }
    });
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
                <div class="bg-white border border-gray-100 p-5 rounded-2xl shadow-sm hover:shadow-md transition">
                    <div class="flex justify-between items-start mb-4">
                        <div class="flex items-center gap-4">
                            <div class="w-12 h-12 bg-blue-50 text-blue-500 rounded-full flex items-center justify-center">
                                <i class="ri-flag-fill text-xl"></i>
                            </div>
                            <div>
                                <h4 class="font-bold text-gray-900">${goal.goal_name}</h4>
                                <p class="text-xs font-medium text-gray-500 mt-0.5">Target: ₹${target.toLocaleString('en-IN')} by ${deadline.toLocaleDateString('en-US', { day: 'numeric', month: 'short' })}</p>
                            </div>
                        </div>
                        <div class="text-right">
                           ${statusBadge}
                        </div>
                    </div>
                    
                    <div class="w-full bg-gray-100 rounded-full h-2.5 overflow-hidden mb-3">
                        <div class="${percentage >= 100 ? 'bg-green-500' : (isOverdue ? 'bg-red-500' : 'bg-blue-500')} h-full rounded-full transition-all duration-1000 ease-out" style="width: ${percentage}%"></div>
                    </div>
                    
                    <div class="flex justify-between items-center text-xs font-bold">
                        <span class="text-gray-500">Saved: <span class="text-gray-900">₹${saved.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span></span>
                        <span class="text-gray-500">Left: <span class="text-gray-900">₹${Math.max(target - saved, 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span></span>
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
