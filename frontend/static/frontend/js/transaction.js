
const authHeaders = {
    "Authorization": `Bearer ${localStorage.getItem('access_token')}`
};

document.addEventListener("DOMContentLoaded", () => {
    fetchTransactions();
    fetchCategories();
});

document.getElementById("addTransactionBtn").addEventListener("click", () => {
    document.getElementById("addTransactionModal").classList.remove("hidden");
});
document.getElementById("closeModal").addEventListener("click", () => {
    document.getElementById("addTransactionModal").classList.add("hidden");
});

document.getElementById("transactionForm").addEventListener("submit", async function (event) {
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
            headers: {
                "Content-Type": "application/json",
                ...authHeaders
            },
            body: JSON.stringify(newTransaction),
        });
        fetchTransactions();
        document.getElementById("addTransactionModal").classList.add("hidden");
    } catch (error) {
        console.error("Error adding transaction:", error);
    }
});

async function fetchTransactions() {
    try {
        const response = await fetch("/api/transactions/", { headers: authHeaders });
        const data = await response.json();
        const transactions = data.results || data; // Handle DRF Pagination object
        renderTransactions(transactions);
    } catch (error) {
        console.error("Error fetching transactions:", error);
    }
}

async function fetchCategories() {
    try {
        const response = await fetch("/api/transactions/categories/", { headers: authHeaders });
        const categories = await response.json();
        const categorySelect = document.getElementById("transactionCategory");
        categorySelect.innerHTML = categories.map(c => `<option value="${c.id}">${c.name}</option>`).join('');
    } catch (error) {
        console.error("Error fetching categories:", error);
    }
}

function renderTransactions(transactions) {
    const tbody = document.getElementById("transactionsList");
    tbody.innerHTML = transactions.map(t => `
        <tr class="border-b">
            <td class="px-6 py-4 text-center">${t.date}</td>
            <td class="px-6 py-4 text-center">${t.category_name || 'Uncategorized'}</td>
            <td class="px-6 py-4 text-center font-bold">₹${parseFloat(t.amount).toFixed(2)}</td>
            <td class="px-6 py-4 text-center text-gray-500">${t.description || "N/A"}</td>
            <td class="px-6 py-4 text-center">
                <button onclick="deleteTransaction(${t.id})" class="text-red-500 hover:text-red-700 transition" title="Delete">
                    <i class="ri-close-circle-fill text-2xl"></i>
                </button>
            </td>
        </tr>
    `).join('');
}


const voiceEntryBtn = document.getElementById('voiceEntryBtn');
const transactionModal = document.getElementById('transactionModal');
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

    if (voiceEntryBtn) {
        voiceEntryBtn.addEventListener('click', () => {
            recognition.start();
            alert("Listening... Speak your transaction details.");
        });
    }

    recognition.onresult = async (event) => {
        const voiceText = event.results[0][0].transcript;
        console.log("Voice Input:", voiceText);

        if (voiceEntryBtn) {
            voiceEntryBtn.textContent = "Processing...";
            voiceEntryBtn.disabled = true;
        }

        const response = await fetch('/api/transactions/process-voice-entry/', {
            method: 'POST',
            headers: {
                "Content-Type": "application/json",
                ...authHeaders
            },
            body: JSON.stringify({ voice_text: voiceText })
        });

        if (voiceEntryBtn) {
            voiceEntryBtn.textContent = "Voice Entry";
            voiceEntryBtn.disabled = false;
        }

        const data = await response.json();

        if (data.error) {
            alert("Error processing voice input.");
            return;
        }

        editAmount.value = data.amount;
        editCategory.value = data.category;
        editType.value = data.transaction_type;

        if (transactionModal) transactionModal.classList.remove('hidden');
    };

    recognition.onerror = (event) => {
        alert("Voice recognition error: " + event.error);
    };
}

if (saveTransactionBtn) {
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
            if (transactionModal) transactionModal.classList.add('hidden');
            fetchTransactions();
        } else {
            alert("Error saving transaction.");
        }
    });
}

if (cancelTransactionBtn) {
    cancelTransactionBtn.addEventListener('click', () => {
        if (transactionModal) transactionModal.classList.add('hidden');
    });
}

async function deleteTransaction(id) {
    if (!confirm("Are you sure you want to delete this transaction? A backup will be saved.")) return;
    try {
        const response = await fetch(`/api/transactions/${id}/`, {
            method: 'DELETE',
            headers: authHeaders
        });

        if (response.ok) {
            fetchTransactions();
        } else {
            console.error("Failed to delete the transaction on backend.");
            alert("Error deleting transaction.");
        }
    } catch (error) {
        console.error("Error communicating with delete endpoint:", error);
        alert("Server error when deleting transaction.");
    }
}
