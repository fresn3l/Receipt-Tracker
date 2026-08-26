// Main JavaScript for Finance Tracker Web App

let monthlyChart = null;
let categoryChart = null;
let topCategoriesChart = null;
let currentPage = 1;
const itemsPerPage = 50;

// Initialize app
document.addEventListener('DOMContentLoaded', async () => {
    setupTabs();
    setupFileUpload();
    await loadDashboard();
    await loadTransactions();
    await loadCategories();
    await loadCategoryRules();
});

// Tab Navigation
function setupTabs() {
    const tabButtons = document.querySelectorAll('.tab-btn');
    const tabContents = document.querySelectorAll('.tab-content');

    tabButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            const targetTab = btn.getAttribute('data-tab');
            
            // Update active tab button
            tabButtons.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            
            // Update active tab content
            tabContents.forEach(content => {
                content.classList.remove('active');
                if (content.id === targetTab) {
                    content.classList.add('active');
                }
            });
        });
    });
}

// File Upload Setup
function setupFileUpload() {
    const fileInput = document.getElementById('file-input');
    const uploadArea = document.getElementById('file-upload-area');
    const fileName = document.getElementById('file-name');
    const importBtn = document.getElementById('import-btn');

    uploadArea.addEventListener('click', () => fileInput.click());

    uploadArea.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadArea.classList.add('dragover');
    });

    uploadArea.addEventListener('dragleave', () => {
        uploadArea.classList.remove('dragover');
    });

    uploadArea.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadArea.classList.remove('dragover');
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            fileInput.files = files;
            handleFileSelect();
        }
    });

    fileInput.addEventListener('change', handleFileSelect);

    function handleFileSelect() {
        if (fileInput.files.length > 0) {
            fileName.textContent = fileInput.files[0].name;
            importBtn.disabled = false;
        } else {
            fileName.textContent = '';
            importBtn.disabled = true;
        }
    }
}

// Import CSV
async function importCSV() {
    const fileInput = document.getElementById('file-input');
    const autoCategorize = document.getElementById('auto-categorize').checked;
    const checkDuplicates = document.getElementById('check-duplicates').checked;
    const accountName = document.getElementById('account-name').value || null;
    const statusDiv = document.getElementById('import-status');

    if (!fileInput.files.length) {
        showStatus('Please select a file', 'error');
        return;
    }

    showLoading(true);
    statusDiv.style.display = 'none';

    try {
        // Use Eel's file dialog or get file path
        let filePath;
        try {
            // Try to get file path from Eel file dialog
            filePath = await eel.select_file()();
        } catch (e) {
            // Fallback: use file input
            const file = fileInput.files[0];
            // For Eel, we need the actual file path, not just the name
            // This will work if the file is in a known location
            filePath = file.name;
        }
        
        if (!filePath) {
            // If no file selected via dialog, use the file input
            const file = fileInput.files[0];
            filePath = file.name;
        }
        
        const result = await eel.import_csv_file(
            filePath,
            accountName,
            autoCategorize,
            false, // overwrite
            checkDuplicates,
            true  // skip duplicates
        )();

        if (result.success) {
            showStatus(`Successfully imported ${result.new_transactions} transactions!`, 'success');
            
            // Reset form
            fileInput.value = '';
            document.getElementById('file-name').textContent = '';
            document.getElementById('import-btn').disabled = true;
            
            // Reload data
            await loadDashboard();
            await loadTransactions();
            await loadCategories();
        } else {
            showStatus(`Error: ${result.error || 'Unknown error'}`, 'error');
        }
        
    } catch (error) {
        showStatus(`Error: ${error.message || error}`, 'error');
    } finally {
        showLoading(false);
    }
}

function showStatus(message, type) {
    const statusDiv = document.getElementById('import-status');
    statusDiv.textContent = message;
    statusDiv.className = type;
    statusDiv.style.display = 'block';
}

// Load Dashboard
async function loadDashboard() {
    try {
        const stats = await eel.get_overall_stats()();
        updateStats(stats);
        
        const summaries = await eel.get_monthly_summaries()();
        updateMonthlySummaries(summaries);
        updateMonthlyChart(summaries);
        
        const categoryBreakdown = await eel.get_category_breakdown()();
        updateCategoryChart(categoryBreakdown);
    } catch (error) {
        console.error('Error loading dashboard:', error);
    }
}

function updateStats(stats) {
    document.getElementById('total-income').textContent = formatCurrency(stats.total_income);
    document.getElementById('total-expenses').textContent = formatCurrency(stats.total_expenses);
    
    const netAmount = parseFloat(stats.net_amount);
    const netEl = document.getElementById('net-amount');
    netEl.textContent = formatCurrency(stats.net_amount);
    netEl.className = 'stat-value ' + (netAmount >= 0 ? 'positive' : 'negative');
    
    const savingsRate = stats.savings_rate || 0;
    document.getElementById('savings-rate').textContent = savingsRate.toFixed(1) + '%';
}

function updateMonthlyChart(summaries) {
    const ctx = document.getElementById('monthly-chart').getContext('2d');
    
    if (monthlyChart) {
        monthlyChart.destroy();
    }
    
    const labels = summaries.map(s => `${s.year}-${String(s.month).padStart(2, '0')}`);
    const income = summaries.map(s => parseFloat(s.total_income));
    const expenses = summaries.map(s => parseFloat(s.total_expenses));
    
    monthlyChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: 'Income',
                data: income,
                borderColor: '#10b981',
                backgroundColor: 'rgba(16, 185, 129, 0.1)',
                tension: 0.4
            }, {
                label: 'Expenses',
                data: expenses,
                borderColor: '#ef4444',
                backgroundColor: 'rgba(239, 68, 68, 0.1)',
                tension: 0.4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: {
                    position: 'top',
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        callback: function(value) {
                            return '$' + value.toLocaleString();
                        }
                    }
                }
            }
        }
    });
}

function updateCategoryChart(breakdown) {
    const ctx = document.getElementById('category-chart').getContext('2d');
    
    if (categoryChart) {
        categoryChart.destroy();
    }
    
    const categories = Object.keys(breakdown).slice(0, 10);
    const amounts = categories.map(cat => parseFloat(breakdown[cat]));
    
    categoryChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: categories,
            datasets: [{
                data: amounts,
                backgroundColor: [
                    '#2563eb', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6',
                    '#ec4899', '#06b6d4', '#84cc16', '#f97316', '#6366f1'
                ]
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: {
                    position: 'right',
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            return context.label + ': $' + context.parsed.toLocaleString();
                        }
                    }
                }
            }
        }
    });
}

function updateMonthlySummaries(summaries) {
    const container = document.getElementById('monthly-summaries');
    container.innerHTML = '';
    
    summaries.slice(0, 6).forEach(summary => {
        const item = document.createElement('div');
        item.className = 'monthly-summary-item';
        item.innerHTML = `
            <div>
                <strong>${summary.year}-${String(summary.month).padStart(2, '0')}</strong>
                <div style="font-size: 12px; color: #64748b; margin-top: 5px;">
                    ${summary.transaction_count} transactions
                </div>
            </div>
            <div class="month-summary">
                <div>
                    <div class="month-summary-label">Income</div>
                    <div class="month-summary-value" style="color: #10b981">${formatCurrency(summary.total_income)}</div>
                </div>
                <div>
                    <div class="month-summary-label">Expenses</div>
                    <div class="month-summary-value" style="color: #ef4444">${formatCurrency(summary.total_expenses)}</div>
                </div>
                <div>
                    <div class="month-summary-label">Net</div>
                    <div class="month-summary-value" style="color: ${parseFloat(summary.net_amount) >= 0 ? '#10b981' : '#ef4444'}">
                        ${formatCurrency(summary.net_amount)}
                    </div>
                </div>
            </div>
        `;
        container.appendChild(item);
    });
}

// Load Transactions
async function loadTransactions(page = 1) {
    try {
        const transactions = await eel.get_transactions(page, itemsPerPage)();
        displayTransactions(transactions);
        updatePagination(transactions.length);
    } catch (error) {
        console.error('Error loading transactions:', error);
    }
}

function displayTransactions(transactions) {
    const tbody = document.getElementById('transactions-tbody');
    tbody.innerHTML = '';
    
    if (transactions.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" class="empty-state">No transactions found.</td></tr>';
        return;
    }
    
    transactions.forEach(txn => {
        const row = document.createElement('tr');
        const amount = parseFloat(txn.amount);
        const isExpense = amount < 0;
        const amountClass = isExpense ? 'expense' : 'income';
        
        row.innerHTML = `
            <td><input type="checkbox" class="transaction-checkbox" value="${txn.id}" onchange="toggleTransactionSelect('${txn.id}')"></td>
            <td>${txn.date}</td>
            <td>${txn.description} ${txn.is_recurring ? '🔄' : ''}</td>
            <td>${txn.category ? txn.category.name : '<span class="uncategorized">Uncategorized</span>'}</td>
            <td class="${amountClass}">${formatCurrency(Math.abs(amount))}</td>
            <td><span class="badge">${txn.transaction_type}</span></td>
            <td>
                <button class="btn btn-small btn-secondary" onclick="editTransaction('${txn.id}')">Edit</button>
                <button class="btn btn-small btn-danger" onclick="deleteTransaction('${txn.id}')">Delete</button>
                <button class="btn btn-small btn-secondary" onclick="splitTransaction('${txn.id}')">Split</button>
            </td>
        `;
        tbody.appendChild(row);
    });
    
    // Load filter options
    eel.get_search_filters()().then(filters => {
        updateFilterOptions(filters);
    }).catch(err => console.error('Error loading filters:', err));
}

// Load Categories
async function loadCategories() {
    try {
        const patterns = await eel.get_spending_patterns()();
        displayTopCategories(patterns);
        displayCategoriesList(patterns);
    } catch (error) {
        console.error('Error loading categories:', error);
    }
}

function displayTopCategories(patterns) {
    const ctx = document.getElementById('top-categories-chart').getContext('2d');
    
    if (topCategoriesChart) {
        topCategoriesChart.destroy();
    }
    
    const top10 = patterns.slice(0, 10);
    const labels = top10.map(p => p.category);
    const amounts = top10.map(p => parseFloat(p.total_amount));
    
    topCategoriesChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Spending',
                data: amounts,
                backgroundColor: '#2563eb'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: {
                    display: false
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        callback: function(value) {
                            return '$' + value.toLocaleString();
                        }
                    }
                }
            }
        }
    });
}

function displayCategoriesList(patterns) {
    const container = document.getElementById('categories-list');
    container.innerHTML = '<h3 style="margin-bottom: 20px;">All Categories</h3>';
    
    patterns.forEach(pattern => {
        const item = document.createElement('div');
        item.className = 'category-item';
        item.innerHTML = `
            <div>
                <strong>${pattern.category}</strong>
                <div style="font-size: 12px; color: #64748b; margin-top: 5px;">
                    ${pattern.transaction_count} transactions • Avg: ${formatCurrency(pattern.average_transaction)}
                </div>
            </div>
            <div style="text-align: right;">
                <div style="font-size: 20px; font-weight: 600">${formatCurrency(pattern.total_amount)}</div>
                <div style="font-size: 12px; color: #64748b">${pattern.percentage_of_total ? pattern.percentage_of_total.toFixed(1) + '%' : 'N/A'}</div>
            </div>
        `;
        container.appendChild(item);
    });
}

// Export Transactions
async function exportTransactions() {
    try {
        const result = await eel.export_transactions()();
        alert(`Transactions exported to: ${result}`);
    } catch (error) {
        alert(`Error exporting: ${error.message || error}`);
    }
}

// Utility Functions
function formatCurrency(amount) {
    return '$' + parseFloat(amount).toLocaleString('en-US', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    });
}

function showLoading(show) {
    document.getElementById('loading-overlay').style.display = show ? 'flex' : 'none';
}

function updatePagination(totalItems) {
    const totalPages = Math.ceil(totalItems / itemsPerPage);
    const pagination = document.getElementById('pagination');
    
    if (totalPages <= 1) {
        pagination.innerHTML = '';
        return;
    }
    
    let html = '';
    for (let i = 1; i <= totalPages; i++) {
        html += `<button class="${i === currentPage ? 'active' : ''}" onclick="goToPage(${i})">${i}</button>`;
    }
    pagination.innerHTML = html;
}

function goToPage(page) {
    currentPage = page;
    loadTransactions(page);
}

// ========== Transaction Editing Functions ==========

let selectedTransactions = new Set();

function toggleSelectAll() {
    const selectAll = document.getElementById('select-all-transactions').checked;
    const checkboxes = document.querySelectorAll('.transaction-checkbox');
    checkboxes.forEach(cb => {
        cb.checked = selectAll;
        if (selectAll) {
            selectedTransactions.add(cb.value);
        } else {
            selectedTransactions.delete(cb.value);
        }
    });
}

function toggleTransactionSelect(transactionId) {
    if (selectedTransactions.has(transactionId)) {
        selectedTransactions.delete(transactionId);
    } else {
        selectedTransactions.add(transactionId);
    }
}

async function editTransaction(transactionId) {
    try {
        const transactions = await eel.get_transactions(1, 1000)();
        const transaction = transactions.find(t => t.id === transactionId);
        if (!transaction) return;

        document.getElementById('edit-txn-id').value = transaction.id;
        document.getElementById('edit-txn-description').value = transaction.description;
        document.getElementById('edit-txn-amount').value = Math.abs(parseFloat(transaction.amount));
        document.getElementById('edit-txn-date').value = transaction.date;
        document.getElementById('edit-txn-category').value = transaction.category?.name || '';
        document.getElementById('edit-txn-category-parent').value = transaction.category?.parent || '';
        document.getElementById('edit-txn-notes').value = transaction.notes || '';

        showModal('edit-transaction-modal');
    } catch (error) {
        alert(`Error loading transaction: ${error.message || error}`);
    }
}

document.getElementById('edit-transaction-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    try {
        const result = await eel.edit_transaction(
            document.getElementById('edit-txn-id').value,
            document.getElementById('edit-txn-description').value,
            document.getElementById('edit-txn-amount').value,
            document.getElementById('edit-txn-date').value,
            document.getElementById('edit-txn-category').value || null,
            document.getElementById('edit-txn-category-parent').value || null,
            document.getElementById('edit-txn-notes').value || null
        )();
        
        if (result.success) {
            closeModal('edit-transaction-modal');
            await loadTransactions();
            alert('Transaction updated successfully');
        } else {
            alert(`Error: ${result.error || 'Failed to update transaction'}`);
        }
    } catch (error) {
        alert(`Error: ${error.message || error}`);
    }
});

async function deleteTransaction(transactionId) {
    if (!confirm('Are you sure you want to delete this transaction?')) return;
    
    try {
        const result = await eel.delete_transaction(transactionId)();
        if (result.success) {
            await loadTransactions();
            alert('Transaction deleted');
        } else {
            alert('Error deleting transaction');
        }
    } catch (error) {
        alert(`Error: ${error.message || error}`);
    }
}

async function bulkDeleteTransactions() {
    if (selectedTransactions.size === 0) {
        alert('Please select transactions to delete');
        return;
    }
    
    if (!confirm(`Are you sure you want to delete ${selectedTransactions.size} transactions?`)) return;
    
    try {
        const result = await eel.delete_transactions(Array.from(selectedTransactions))();
        if (result.success) {
            selectedTransactions.clear();
            await loadTransactions();
            alert(`Deleted ${result.deleted_count} transactions`);
        }
    } catch (error) {
        alert(`Error: ${error.message || error}`);
    }
}

async function bulkEditTransactions() {
    if (selectedTransactions.size === 0) {
        alert('Please select transactions to edit');
        return;
    }
    
    const category = prompt('Enter category name (or leave empty to skip):');
    const notes = prompt('Enter notes to add (or leave empty to skip):');
    
    if (!category && !notes) return;
    
    try {
        const result = await eel.bulk_edit_transactions(
            Array.from(selectedTransactions),
            category || null,
            notes || null
        )();
        
        if (result.success) {
            selectedTransactions.clear();
            await loadTransactions();
            alert(`Updated ${result.updated_count} transactions`);
        }
    } catch (error) {
        alert(`Error: ${error.message || error}`);
    }
}

async function splitTransaction(transactionId) {
    try {
        const transactions = await eel.get_transactions(1, 1000)();
        const transaction = transactions.find(t => t.id === transactionId);
        if (!transaction) return;

        document.getElementById('split-txn-id').value = transaction.id;
        document.getElementById('split-txn-info').innerHTML = `
            <p><strong>Description:</strong> ${transaction.description}</p>
            <p><strong>Amount:</strong> ${formatCurrency(Math.abs(parseFloat(transaction.amount)))}</p>
        `;
        document.getElementById('split-entries').innerHTML = '';
        addSplitEntry();
        showModal('split-transaction-modal');
    } catch (error) {
        alert(`Error: ${error.message || error}`);
    }
}

function addSplitEntry() {
    const container = document.getElementById('split-entries');
    const entry = document.createElement('div');
    entry.className = 'split-entry';
    entry.innerHTML = `
        <div class="form-group">
            <label>Amount</label>
            <input type="number" step="0.01" class="split-amount" required>
        </div>
        <div class="form-group">
            <label>Category</label>
            <input type="text" class="split-category" required>
        </div>
        <div class="form-group">
            <label>Description</label>
            <input type="text" class="split-description">
        </div>
        <button type="button" class="btn btn-danger btn-small" onclick="this.parentElement.remove()">Remove</button>
    `;
    container.appendChild(entry);
}

document.getElementById('split-transaction-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const entries = document.querySelectorAll('.split-entry');
    const splits = [];
    let total = 0;
    
    entries.forEach(entry => {
        const amount = parseFloat(entry.querySelector('.split-amount').value);
        const category = entry.querySelector('.split-category').value;
        const description = entry.querySelector('.split-description').value;
        splits.push({
            amount: amount,
            category_name: category,
            description: description || null
        });
        total += amount;
    });
    
    try {
        const result = await eel.split_transaction(
            document.getElementById('split-txn-id').value,
            splits
        )();
        
        if (result.success) {
            closeModal('split-transaction-modal');
            await loadTransactions();
            alert('Transaction split successfully');
        } else {
            alert(`Error: ${result.error || 'Failed to split transaction'}`);
        }
    } catch (error) {
        alert(`Error: ${error.message || error}`);
    }
});

// ========== Advanced Search Functions ==========

function toggleAdvancedSearch() {
    const panel = document.getElementById('advanced-search');
    panel.style.display = panel.style.display === 'none' ? 'block' : 'none';
}

async function applyAdvancedSearch() {
    try {
        const results = await eel.search_transactions(
            document.getElementById('search-input').value || null,
            document.getElementById('category-filter').value || null,
            document.getElementById('search-account').value || null,
            document.getElementById('search-date-from').value || null,
            document.getElementById('search-date-to').value || null,
            document.getElementById('search-amount-min').value || null,
            document.getElementById('search-amount-max').value || null,
            document.getElementById('type-filter').value || null,
            document.getElementById('search-recurring').checked || null
        )();
        
        displaySearchResults(results);
    } catch (error) {
        alert(`Error: ${error.message || error}`);
    }
}

function clearAdvancedSearch() {
    document.getElementById('search-date-from').value = '';
    document.getElementById('search-date-to').value = '';
    document.getElementById('search-amount-min').value = '';
    document.getElementById('search-amount-max').value = '';
    document.getElementById('search-account').value = '';
    document.getElementById('search-recurring').checked = false;
    loadTransactions();
}

function displaySearchResults(results) {
    const tbody = document.getElementById('transactions-tbody');
    if (results.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" class="empty-state">No transactions found</td></tr>';
        return;
    }
    
    tbody.innerHTML = results.map(txn => createTransactionRow(txn)).join('');
}

function createTransactionRow(txn) {
    const amount = parseFloat(txn.amount);
    const amountClass = amount < 0 ? 'expense' : 'income';
    return `
        <tr>
            <td><input type="checkbox" class="transaction-checkbox" value="${txn.id}" onchange="toggleTransactionSelect('${txn.id}')"></td>
            <td>${txn.date}</td>
            <td>${txn.description} ${txn.is_recurring ? '🔄' : ''}</td>
            <td>${txn.category ? txn.category.name : '<span class="uncategorized">Uncategorized</span>'}</td>
            <td class="${amountClass}">${formatCurrency(Math.abs(amount))}</td>
            <td>${txn.transaction_type}</td>
            <td>
                <button class="btn btn-small btn-secondary" onclick="editTransaction('${txn.id}')">Edit</button>
                <button class="btn btn-small btn-danger" onclick="deleteTransaction('${txn.id}')">Delete</button>
                <button class="btn btn-small btn-secondary" onclick="splitTransaction('${txn.id}')">Split</button>
            </td>
        </tr>
    `;
}


function updateFilterOptions(filters) {
    const categoryFilter = document.getElementById('category-filter');
    const accountFilter = document.getElementById('search-account');
    
    // Update category filter
    const currentCategory = categoryFilter.value;
    categoryFilter.innerHTML = '<option value="">All Categories</option>' +
        filters.categories.map(cat => `<option value="${cat}">${cat}</option>`).join('');
    categoryFilter.value = currentCategory;
    
    // Update account filter
    const currentAccount = accountFilter.value;
    accountFilter.innerHTML = '<option value="">All Accounts</option>' +
        filters.accounts.map(acc => `<option value="${acc}">${acc}</option>`).join('');
    accountFilter.value = currentAccount;
}

// ========== Budget Management Functions ==========

async function loadBudgets() {
    const month = parseInt(document.getElementById('budget-month-select').value);
    const year = parseInt(document.getElementById('budget-year-input').value);
    
    try {
        const statuses = await eel.get_all_budget_statuses(year, month)();
        displayBudgets(statuses);
        
        const alerts = await eel.get_budget_alerts(year, month)();
        displayBudgetAlerts(alerts);
    } catch (error) {
        alert(`Error loading budgets: ${error.message || error}`);
    }
}

function displayBudgets(statuses) {
    const container = document.getElementById('budgets-list');
    if (statuses.length === 0) {
        container.innerHTML = '<p class="empty-state">No budgets set for this month</p>';
        return;
    }
    
    container.innerHTML = statuses.map(status => {
        const percentage = status.percentage_spent || 0;
        const progressColor = percentage > 100 ? 'var(--danger-color)' : 
                              percentage > 80 ? 'var(--warning-color)' : 'var(--success-color)';
        
        return `
            <div class="budget-item">
                <div class="budget-header">
                    <h4>${status.category_name}</h4>
                    <button class="btn btn-small btn-danger" onclick="deleteBudget('${status.category_name}')">Delete</button>
                </div>
                <div class="budget-progress">
                    <div class="progress-bar">
                        <div class="progress-fill" style="width: ${Math.min(percentage, 100)}%; background-color: ${progressColor}"></div>
                    </div>
                    <div class="budget-stats">
                        <span>Spent: ${formatCurrency(status.spent)}</span>
                        <span>Budget: ${formatCurrency(status.budget)}</span>
                        <span>Remaining: ${formatCurrency(status.remaining)}</span>
                        <span>${percentage.toFixed(1)}%</span>
                    </div>
                </div>
            </div>
        `;
    }).join('');
}

function displayBudgetAlerts(alerts) {
    const container = document.getElementById('budget-alerts');
    if (alerts.length === 0) {
        container.innerHTML = '<p class="empty-state">No budget alerts</p>';
        return;
    }
    
    container.innerHTML = alerts.map(alert => `
        <div class="alert-item ${alert.message.includes('Over budget') ? 'alert-danger' : 'alert-warning'}">
            <strong>${alert.category}</strong>
            <p>${alert.message}</p>
        </div>
    `).join('');
}

function showAddBudgetModal() {
    const month = parseInt(document.getElementById('budget-month-select').value);
    const year = parseInt(document.getElementById('budget-year-input').value);
    document.getElementById('add-budget-form').dataset.month = month;
    document.getElementById('add-budget-form').dataset.year = year;
    showModal('add-budget-modal');
}

document.getElementById('add-budget-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const form = e.target;
    const month = parseInt(form.dataset.month);
    const year = parseInt(form.dataset.year);
    
    try {
        const result = await eel.set_budget(
            document.getElementById('budget-category').value,
            year,
            month,
            document.getElementById('budget-amount').value,
            (parseInt(document.getElementById('budget-alert-threshold').value) / 100).toString(),
            document.getElementById('budget-notes').value || null
        )();
        
        if (result.success) {
            closeModal('add-budget-modal');
            form.reset();
            await loadBudgets();
            alert('Budget added successfully');
        } else {
            alert(`Error: ${result.error || 'Failed to add budget'}`);
        }
    } catch (error) {
        alert(`Error: ${error.message || error}`);
    }
});

async function deleteBudget(categoryName) {
    if (!confirm(`Delete budget for ${categoryName}?`)) return;
    
    const month = parseInt(document.getElementById('budget-month-select').value);
    const year = parseInt(document.getElementById('budget-year-input').value);
    
    try {
        const result = await eel.delete_budget(categoryName, year, month)();
        if (result.success) {
            await loadBudgets();
        }
    } catch (error) {
        alert(`Error: ${error.message || error}`);
    }
}

// ========== Recurring Transactions Functions ==========

async function detectRecurring() {
    showLoading(true);
    try {
        const recurring = await eel.detect_recurring_transactions(3)();
        displayRecurringTransactions(recurring);
    } catch (error) {
        alert(`Error: ${error.message || error}`);
    } finally {
        showLoading(false);
    }
}

function displayRecurringTransactions(recurring) {
    const container = document.getElementById('recurring-list');
    if (recurring.length === 0) {
        container.innerHTML = '<p class="empty-state">No recurring transactions detected</p>';
        return;
    }
    
    container.innerHTML = recurring.map(r => `
        <div class="recurring-item">
            <div class="recurring-header">
                <h4>${r.description_pattern}</h4>
                <span class="confidence-badge" style="background-color: ${getConfidenceColor(r.confidence)}">
                    ${(r.confidence * 100).toFixed(0)}% confidence
                </span>
            </div>
            <div class="recurring-details">
                <p><strong>Amount:</strong> ${formatCurrency(r.amount)}</p>
                <p><strong>Frequency:</strong> ${r.frequency}</p>
                <p><strong>Last Seen:</strong> ${r.last_seen}</p>
                <p><strong>Next Expected:</strong> ${r.next_expected || 'N/A'}</p>
                <p><strong>Occurrences:</strong> ${r.transaction_count}</p>
            </div>
        </div>
    `).join('');
}

function getConfidenceColor(confidence) {
    if (confidence >= 0.8) return 'var(--success-color)';
    if (confidence >= 0.6) return 'var(--warning-color)';
    return 'var(--danger-color)';
}

async function markRecurring() {
    showLoading(true);
    try {
        const result = await eel.mark_recurring_transactions()();
        if (result.success) {
            alert(`Marked ${result.marked_count} transactions as recurring`);
            await loadTransactions();
        }
    } catch (error) {
        alert(`Error: ${error.message || error}`);
    } finally {
        showLoading(false);
    }
}

// ========== Category Rules Functions ==========

async function loadCategoryRules() {
    try {
        const rules = await eel.get_category_rules()();
        displayCategoryRules(rules);
    } catch (error) {
        alert(`Error loading rules: ${error.message || error}`);
    }
}

function displayCategoryRules(rules) {
    const container = document.getElementById('rules-list');
    if (rules.length === 0) {
        container.innerHTML = '<p class="empty-state">No rules defined</p>';
        return;
    }
    
    container.innerHTML = rules.map((rule, index) => `
        <div class="rule-item">
            <div class="rule-header">
                <h4>Rule ${index + 1}</h4>
                <button class="btn btn-small btn-danger" onclick="removeRule('${rule.pattern}', '${rule.category_name}')">Remove</button>
            </div>
            <div class="rule-details">
                <p><strong>Pattern:</strong> <code>${rule.pattern}</code></p>
                <p><strong>Category:</strong> ${rule.category_name}${rule.parent_category ? ` (${rule.parent_category})` : ''}</p>
                <p><strong>Case Sensitive:</strong> ${rule.case_sensitive ? 'Yes' : 'No'}</p>
            </div>
        </div>
    `).join('');
}

function showAddRuleModal() {
    showModal('add-rule-modal');
}

document.getElementById('add-rule-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    try {
        const result = await eel.add_category_rule(
            document.getElementById('rule-pattern').value,
            document.getElementById('rule-category').value,
            document.getElementById('rule-parent').value || null,
            document.getElementById('rule-case-sensitive').checked
        )();
        
        if (result.success) {
            closeModal('add-rule-modal');
            document.getElementById('add-rule-form').reset();
            await loadCategoryRules();
            alert('Rule added successfully');
        } else {
            alert(`Error: ${result.error || 'Failed to add rule'}`);
        }
    } catch (error) {
        alert(`Error: ${error.message || error}`);
    }
});

async function testRulePattern() {
    const pattern = document.getElementById('rule-pattern').value;
    const testStrings = document.getElementById('rule-test-strings').value.split('\n').filter(s => s.trim());
    
    if (!pattern || testStrings.length === 0) {
        alert('Please enter a pattern and test strings');
        return;
    }
    
    try {
        const result = await eel.test_category_rule(pattern, testStrings)();
        const resultsDiv = document.getElementById('rule-test-results');
        
        if (!result.valid) {
            resultsDiv.innerHTML = `<p class="error">Invalid pattern: ${result.error}</p>`;
            return;
        }
        
        resultsDiv.innerHTML = result.results.map(r => `
            <div class="test-result ${r.matches ? 'match' : 'no-match'}">
                <strong>${r.string}</strong> - ${r.matches ? `✓ Matches: "${r.matched_text}"` : '✗ No match'}
            </div>
        `).join('');
    } catch (error) {
        alert(`Error: ${error.message || error}`);
    }
}

async function removeRule(pattern, categoryName) {
    if (!confirm('Remove this rule?')) return;
    
    try {
        const result = await eel.remove_category_rule(pattern, categoryName)();
        if (result.success) {
            await loadCategoryRules();
        }
    } catch (error) {
        alert(`Error: ${error.message || error}`);
    }
}

// ========== Modal Functions ==========

function showModal(modalId) {
    document.getElementById(modalId).style.display = 'block';
}

function closeModal(modalId) {
    document.getElementById(modalId).style.display = 'none';
}

// Close modal when clicking outside
window.onclick = function(event) {
    if (event.target.classList.contains('modal')) {
        event.target.style.display = 'none';
    }
}


