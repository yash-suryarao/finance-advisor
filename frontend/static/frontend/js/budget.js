
function initializeDashboard() {
    setCurrentMonth();
    fetchBudgetData();
    fetchTransactions();
    fetchBudgetInsights();
}

async function fetchBudgetInsights() {
    try {
        let response = await fetch('/api/insights/budget-insights/', { headers: authHeaders });
        if (!response.ok) return;
        let data = await response.json();
        let warnings = "";
        let count = 0;

        data.forEach(insight => {
            if (insight.forecasted_spending > insight.average_spending) {
                warnings += `<div class="flex items-center justify-between py-1 border-b border-red-100 last:border-0">
                                         <span>⚠️ High spending detected in <b>${insight.category}</b>. AI suggests: ${insight.savings_recommendation}</span>
                                         <button onclick='showReallocationModal("${insight.category}", ${insight.suggested_limit || insight.forecasted_spending})' class='bg-red-100 text-red-700 px-3 py-1 rounded text-xs font-semibold hover:bg-red-200 transition ml-4 whitespace-nowrap'>Adjust to ₹${insight.suggested_limit || insight.forecasted_spending}</button>
                                     </div>`;
                count++;
            }
        });

        const warningBox = document.getElementById('budgetWarnings');
        if (count > 0) {
            warningBox.innerHTML = warnings;
            warningBox.classList.remove('hidden');
        } else {
            warningBox.innerHTML = `<span class="text-green-600"><i class="ri-check-line mr-1"></i> Your budget is optimized! No AI adjustments needed.</span>`;
            warningBox.classList.replace('text-red-600', 'text-green-600');
            warningBox.classList.replace('bg-red-50', 'bg-green-50');
            warningBox.classList.remove('hidden');
        }
    } catch (e) { console.error("Error fetching AI insights:", e); }
}

function optimizeWithAI() {
    const btn = document.querySelector('button[onclick="optimizeWithAI()"]');
    const originalHTML = btn.innerHTML;
    btn.innerHTML = `<i class="ri-loader-4-line ri-spin mr-2"></i> Analyzing...`;
    btn.disabled = true;

    setTimeout(() => {
        fetchBudgetInsights();
        btn.innerHTML = originalHTML;
        btn.disabled = false;
    }, 800); // Simulate API latency for UX
}

let currentReallocationCategory = "";
let currentReallocationLimit = 0;

function showReallocationModal(category, suggestedLimit) {
    currentReallocationCategory = category;
    currentReallocationLimit = suggestedLimit;
    document.getElementById('aiSuggestionText').innerHTML = `AI suggests reallocating <b>${category}</b> budget to ₹${suggestedLimit}. Do you approve?`;
    document.getElementById('aiReallocateModal').classList.remove('hidden');
}

async function confirmReallocation(approved) {
    if (approved) {
        try {
            const response = await fetch('/api/insights/accept-suggested-budget/', {
                method: 'POST',
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": getCookie('csrftoken'), // Add CSRF token for Django
                    ...authHeaders
                },
                body: JSON.stringify({ category: currentReallocationCategory, new_limit: currentReallocationLimit })
            });

            if (response.ok) {
                alert(`Budget for ${currentReallocationCategory} successfully updated to ₹${currentReallocationLimit} in the database!`);
                // Optionally trigger a re-fetch of the budget table here
                if (typeof fetchBudgetData === 'function') fetchBudgetData();
            } else {
                alert("Failed to update budget in the database.");
            }
        } catch (e) {
            console.error(e);
            alert("Error connecting to server.");
        }
    }
    document.getElementById('aiReallocateModal').classList.add('hidden');
}

// Helper for CSRF token if not already defined globally
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
