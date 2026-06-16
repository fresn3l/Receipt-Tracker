const receiptList = document.getElementById("receipt-list");
const productList = document.getElementById("product-list");
const watchlistEl = document.getElementById("watchlist");
const alertsPanel = document.getElementById("alerts-panel");
const mergeSuggestions = document.getElementById("merge-suggestions");
const uploadForm = document.getElementById("upload-form");
const uploadStatus = document.getElementById("upload-status");
const uploadBtn = document.getElementById("upload-btn");
const emptyState = document.getElementById("empty-state");
const emptyTitle = document.getElementById("empty-title");
const emptyText = document.getElementById("empty-text");
const receiptDetail = document.getElementById("receipt-detail");
const productPanel = document.getElementById("product-panel");
const spendingPanel = document.getElementById("spending-panel");
const validationBanner = document.getElementById("validation-banner");
const duplicateBanner = document.getElementById("duplicate-banner");
const reviewBanner = document.getElementById("review-banner");
const detailView = document.getElementById("detail-view");
const receiptEditForm = document.getElementById("receipt-edit-form");
const addItemForm = document.getElementById("add-item-form");
const categoryForm = document.getElementById("category-form");
const budgetForm = document.getElementById("budget-form");
const sidebarReceipts = document.getElementById("sidebar-receipts");
const sidebarPrices = document.getElementById("sidebar-prices");
const sidebarSpending = document.getElementById("sidebar-spending");
const productSearch = document.getElementById("product-search");
const backToReceiptBtn = document.getElementById("back-to-receipt");
const toggleItemsEditBtn = document.getElementById("toggle-items-edit-btn");
const mergeSelectedBtn = document.getElementById("merge-selected-btn");
const toggleWatchBtn = document.getElementById("toggle-watch-btn");
const reviewQueueBtn = document.getElementById("review-queue-btn");
const bulkReparseBtn = document.getElementById("bulk-reparse-btn");
const markReviewedBtn = document.getElementById("mark-reviewed-btn");
const importForm = document.getElementById("import-form");
const unitForm = document.getElementById("unit-form");
const chartRawBtn = document.getElementById("chart-raw-btn");
const chartUnitBtn = document.getElementById("chart-unit-btn");

let priceChart, categoryChart, storeChart, monthlyChart;
let selectedReceiptId = null;
let selectedProductId = null;
let selectedProductIds = new Set();
let currentReceipt = null;
let currentProduct = null;
let editingItemId = null;
let bulkEditMode = false;
let reviewQueueMode = false;
let activeView = "receipts";
let groceryCategories = [];
let chartMode = "raw";

function money(v) { return v == null ? "—" : `$${Number(v).toFixed(2)}`; }
function pct(v) { if (v == null) return "—"; return `${v > 0 ? "+" : ""}${Number(v).toFixed(1)}%`; }
function pctClass(v) { if (v == null || v === 0) return "neutral"; return v > 0 ? "up" : "down"; }
function formatDate(v) { return v ? new Date(v + "T00:00:00").toLocaleDateString() : "Unknown date"; }
function escapeAttr(v) { return String(v).replaceAll('"', "&quot;"); }

async function api(path, options = {}) {
  const response = await fetch(path, options);
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    const detail = Array.isArray(payload.detail) ? payload.detail.map((e) => e.msg).join(", ") : payload.detail;
    throw new Error(detail || "Request failed");
  }
  if (response.status === 204) return null;
  return response.json();
}

function setStatus(msg, type = "") {
  uploadStatus.textContent = msg;
  uploadStatus.className = `status ${type}`.trim();
}

function updateMergeButton() { mergeSelectedBtn.disabled = selectedProductIds.size < 2; }

function setView(view) {
  activeView = view;
  document.querySelectorAll(".nav-btn").forEach((b) => b.classList.toggle("active", b.dataset.view === view));
  sidebarReceipts.classList.toggle("hidden", view !== "receipts");
  sidebarPrices.classList.toggle("hidden", view !== "prices");
  sidebarSpending.classList.toggle("hidden", view !== "spending");
  receiptDetail.classList.add("hidden");
  productPanel.classList.add("hidden");
  spendingPanel.classList.add("hidden");
  emptyState.classList.add("hidden");

  if (view === "receipts") {
    (selectedReceiptId ? receiptDetail : emptyState).classList.remove("hidden");
    if (!selectedReceiptId) {
      emptyTitle.textContent = "Select a receipt";
      emptyText.textContent = "Choose a receipt from the list or upload a new one.";
    }
    loadReceipts().catch((e) => setStatus(e.message, "error"));
  } else if (view === "prices") {
    (selectedProductId ? productPanel : emptyState).classList.remove("hidden");
    if (!selectedProductId) {
      emptyTitle.textContent = "Track grocery prices";
      emptyText.textContent = "Search products, use the watchlist, and review price alerts.";
    }
    loadAlerts().catch(() => {});
    loadWatchlist().catch(() => {});
    loadProducts().catch((e) => setStatus(e.message, "error"));
  } else {
    spendingPanel.classList.remove("hidden");
    loadSpending().catch((e) => setStatus(e.message, "error"));
  }
}

async function loadAlerts() {
  const alerts = await api("/api/insights/alerts");
  if (!alerts.length) { alertsPanel.classList.add("hidden"); return; }
  alertsPanel.classList.remove("hidden");
  alertsPanel.innerHTML = `<strong>Price alerts</strong>${alerts.slice(0, 5).map((a) => `<div class="alert-item"><button type="button" class="item-link" data-id="${a.product_id}">${a.product_name}</button>: ${a.message}</div>`).join("")}`;
  alertsPanel.querySelectorAll("button[data-id]").forEach((btn) => btn.addEventListener("click", () => showProduct(Number(btn.dataset.id), { fromReceipt: false })));
}

async function loadWatchlist() {
  const items = await api("/api/products/watchlist");
  watchlistEl.innerHTML = items.length ? "" : "<li class='meta'>Pin items from product detail.</li>";
  for (const p of items) {
    const li = document.createElement("li");
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = p.id === selectedProductId ? "active" : "";
    btn.innerHTML = `<strong>${p.canonical_name}</strong><span class="meta">${money(p.latest_price)}${p.change_since_previous_pct != null ? ` · ${pct(p.change_since_previous_pct)}` : ""}</span>`;
    btn.addEventListener("click", () => showProduct(p.id, { fromReceipt: false }));
    li.appendChild(btn);
    watchlistEl.appendChild(li);
  }
}

async function loadReceipts() {
  const path = reviewQueueMode ? "/api/receipts?review_only=true" : "/api/receipts";
  const receipts = await api(path);
  const queue = reviewQueueMode ? receipts : await api("/api/receipts/review-queue");
  reviewQueueBtn.textContent = queue.length ? `Needs review (${queue.length})` : "Needs review";
  receiptList.innerHTML = receipts.length ? "" : `<li class='meta'>${reviewQueueMode ? "No receipts need review." : "No receipts yet."}</li>`;
  for (const r of receipts) {
    const li = document.createElement("li");
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = r.id === selectedReceiptId ? "active" : "";
    const flags = [r.has_warning && "⚠ totals", r.possible_duplicate && "⚠ duplicate", r.needs_review && "⚠ review"].filter(Boolean).join(" · ");
    btn.innerHTML = `<strong>${r.store_name || "Unknown store"}</strong><span class="meta">${formatDate(r.purchase_date)} · ${r.item_count} items · ${money(r.total)}${flags ? ` · ${flags}` : ""}</span>`;
    btn.addEventListener("click", () => showReceipt(r.id));
    li.appendChild(btn);
    receiptList.appendChild(li);
  }
  reviewQueueBtn.classList.toggle("active", reviewQueueMode);
}

async function loadProducts() {
  const q = productSearch.value.trim();
  const path = q ? `/api/products?q=${encodeURIComponent(q)}` : "/api/products";
  const products = await api(path);
  productList.innerHTML = products.length ? "" : "<li class='meta'>No products found.</li>";
  for (const p of products) {
    const li = document.createElement("li");
    li.className = "product-row";
    const cb = document.createElement("input");
    cb.type = "checkbox";
    cb.checked = selectedProductIds.has(p.id);
    cb.addEventListener("change", () => { cb.checked ? selectedProductIds.add(p.id) : selectedProductIds.delete(p.id); updateMergeButton(); });
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = p.id === selectedProductId ? "active" : "";
    const unit = p.normalized_unit_price != null ? ` · ${money(p.normalized_unit_price)}/${p.normalized_unit || "unit"}` : "";
    btn.innerHTML = `<strong>${p.is_watched ? "★ " : ""}${p.canonical_name}</strong><span class="meta">${p.purchase_count} buys · ${money(p.latest_price)}${unit}</span>`;
    btn.addEventListener("click", () => showProduct(p.id, { fromReceipt: false }));
    li.append(cb, btn);
    productList.appendChild(li);
  }
  updateMergeButton();
}

function renderValidation(v) {
  if (!v || v.is_valid) { validationBanner.classList.add("hidden"); return; }
  validationBanner.classList.remove("hidden");
  validationBanner.className = "validation-banner warning";
  validationBanner.textContent = [...(v.items_sum != null ? [`Items: ${money(v.items_sum)} · Receipt: ${money(v.receipt_total)}`] : []), ...v.warnings].join(" ");
}

function renderDuplicateWarning(ids) {
  if (!ids?.length) { duplicateBanner.classList.add("hidden"); return; }
  duplicateBanner.classList.remove("hidden");
  duplicateBanner.className = "validation-banner warning";
  duplicateBanner.textContent = `Possible duplicate of receipt(s): ${ids.map((id) => `#${id}`).join(", ")}`;
}

function renderReviewBanner(receipt) {
  const markBtn = document.getElementById("mark-reviewed-btn");
  if (!receipt.needs_review) {
    reviewBanner.classList.add("hidden");
    markBtn.classList.add("hidden");
    return;
  }
  reviewBanner.classList.remove("hidden");
  reviewBanner.className = "validation-banner warning";
  const conf = receipt.parse_confidence != null ? ` Confidence: ${Math.round(receipt.parse_confidence * 100)}%.` : "";
  reviewBanner.textContent = `Needs review — fix items or totals, then mark reviewed.${conf}`;
  markBtn.classList.remove("hidden");
}

function setReceiptEditMode(on) {
  detailView.classList.toggle("hidden", on);
  receiptEditForm.classList.toggle("hidden", !on);
}

function setBulkEditMode(on) {
  bulkEditMode = on;
  editingItemId = null;
  toggleItemsEditBtn.textContent = on ? "Done editing items" : "Edit all items";
  toggleItemsEditBtn.classList.toggle("active", on);
  if (currentReceipt) renderReceiptItems(currentReceipt.line_items);
}

function wireLineCalc(row) {
  const qty = row.querySelector('[data-field="quantity"]');
  const unit = row.querySelector('[data-field="unit_price"]');
  const total = row.querySelector('[data-field="line_total"]');
  if (!qty || !unit || !total) return;
  const upd = () => {
    const q = Number(qty.value), u = Number(unit.value);
    if (qty.value && unit.value && !Number.isNaN(q) && !Number.isNaN(u)) total.value = (q * u).toFixed(2);
  };
  qty.addEventListener("input", upd);
  unit.addEventListener("input", upd);
}

function renderEditableRow(item) {
  const row = document.createElement("tr");
  row.className = "editing-row";
  row.innerHTML = `<td><input class="cell-input" data-field="raw_name" value="${escapeAttr(item.raw_name)}" /></td><td><input class="cell-input num" data-field="quantity" type="number" value="${item.quantity}" step="0.01" /></td><td><input class="cell-input num" data-field="unit_price" type="number" value="${item.unit_price ?? ""}" step="0.01" /></td><td><input class="cell-input num" data-field="line_total" type="number" value="${item.line_total ?? ""}" step="0.01" /></td><td class="row-actions"><button type="button" class="secondary small save-item-btn">Save</button>${bulkEditMode ? "" : '<button type="button" class="secondary small cancel-item-btn">Cancel</button>'}</td>`;
  wireLineCalc(row);
  row.querySelector(".save-item-btn").addEventListener("click", () => saveLineItem(item.id, row));
  row.querySelector(".cancel-item-btn")?.addEventListener("click", () => { editingItemId = null; renderReceiptItems(currentReceipt.line_items); });
  return row;
}

function renderLineItemRow(item) {
  if (bulkEditMode || editingItemId === item.id) return renderEditableRow(item);
  const row = document.createElement("tr");
  if (item.parse_confidence != null && item.parse_confidence < 0.7) row.classList.add("low-confidence");
  const nameCell = document.createElement("td");
  const link = document.createElement("button");
  link.type = "button";
  link.className = "item-link";
  link.textContent = item.raw_name;
  if (item.product_id) link.addEventListener("click", () => showProduct(item.product_id, { fromReceipt: true, name: item.raw_name }));
  nameCell.appendChild(link);
  const actions = document.createElement("td");
  actions.className = "row-actions";
  actions.innerHTML = '<button type="button" class="secondary small edit-item-btn">Edit</button><button type="button" class="danger small delete-item-btn">Del</button>';
  actions.querySelector(".edit-item-btn").addEventListener("click", () => { editingItemId = item.id; renderReceiptItems(currentReceipt.line_items); });
  actions.querySelector(".delete-item-btn").addEventListener("click", () => deleteLineItem(item.id));
  row.append(nameCell);
  row.innerHTML += `<td class="num">${item.quantity}</td><td class="num">${money(item.unit_price)}</td><td class="num">${money(item.line_total)}</td>`;
  row.appendChild(actions);
  row.replaceChild(nameCell, row.firstChild);
  return row;
}

function renderReceiptItems(items) {
  const tbody = document.getElementById("detail-items");
  tbody.innerHTML = "";
  items.forEach((item) => tbody.appendChild(renderLineItemRow(item)));
}

async function showReceipt(id) {
  selectedReceiptId = id;
  reviewQueueMode = false;
  currentReceipt = await api(`/api/receipts/${id}`);
  setView("receipts");
  document.getElementById("detail-store").textContent = currentReceipt.store_name || "Unknown store";
  document.getElementById("detail-meta").textContent = `${formatDate(currentReceipt.purchase_date)} · Total ${money(currentReceipt.total)}`;
  const notesView = document.getElementById("detail-notes-view");
  if (currentReceipt.notes) { notesView.textContent = `Notes: ${currentReceipt.notes}`; notesView.classList.remove("hidden"); }
  else notesView.classList.add("hidden");
  const img = document.getElementById("detail-image");
  if (currentReceipt.image_path === "imported/no-image") {
    img.classList.add("hidden");
  } else {
    img.classList.remove("hidden");
    img.src = `/api/receipts/${id}/image?t=${Date.now()}`;
  }
  document.getElementById("edit-store").value = currentReceipt.store_name || "";
  document.getElementById("edit-date").value = currentReceipt.purchase_date || "";
  document.getElementById("edit-total").value = currentReceipt.total ?? "";
  document.getElementById("edit-notes").value = currentReceipt.notes || "";
  renderValidation(currentReceipt.validation);
  renderDuplicateWarning(currentReceipt.possible_duplicate_ids);
  renderReviewBanner(currentReceipt);
  renderReceiptItems(currentReceipt.line_items);
  await loadReceipts();
}

async function saveLineItem(itemId, row) {
  const payload = {};
  row.querySelectorAll(".cell-input").forEach((input) => {
    const f = input.dataset.field;
    payload[f] = f === "raw_name" ? input.value.trim() : input.value === "" ? null : Number(input.value);
  });
  if (!payload.raw_name) return alert("Item name is required.");
  await api(`/api/receipts/${selectedReceiptId}/items/${itemId}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
  if (!bulkEditMode) editingItemId = null;
  currentReceipt = await api(`/api/receipts/${selectedReceiptId}`);
  renderValidation(currentReceipt.validation);
  renderReviewBanner(currentReceipt);
  renderReceiptItems(currentReceipt.line_items);
}

async function deleteLineItem(itemId) {
  if (!confirm("Delete this line item?")) return;
  await api(`/api/receipts/${selectedReceiptId}/items/${itemId}`, { method: "DELETE" });
  await showReceipt(selectedReceiptId);
}

function statCard(label, value, sub = "", cls = "") {
  return `<article class="stat-card"><span class="stat-label">${label}</span><strong class="stat-value ${cls}">${value}</strong>${sub ? `<span class="stat-sub">${sub}</span>` : ""}</article>`;
}

async function ensureCategories() {
  if (!groceryCategories.length) groceryCategories = await api("/api/products/categories");
  document.getElementById("product-category").innerHTML = `<option value="">Uncategorized</option>${groceryCategories.map((c) => `<option value="${c}">${c}</option>`).join("")}`;
}

function chartOpts(price = false) {
  return { responsive: true, maintainAspectRatio: false, plugins: { legend: { labels: { color: "#e8eef7" } } }, scales: { x: { ticks: { color: "#9fb0c7" }, grid: { color: "#2d3a4d" } }, y: { ticks: { color: "#9fb0c7", callback: (v) => price ? `$${v}` : v }, grid: { color: "#2d3a4d" } } } };
}

function renderProductChart(product) {
  const a = product.analytics;
  const unit = product.normalized_unit || "unit";
  const hasUnit = product.unit_amount && product.history.some((p) => p.normalized_price != null);
  chartUnitBtn.classList.toggle("hidden", !hasUnit);
  const useUnit = chartMode === "unit" && hasUnit;
  const prices = product.history.map((p) => (useUnit ? p.normalized_price : p.effective_price));
  const avg = useUnit && product.normalized_unit_price != null
    ? product.history.map(() => product.normalized_unit_price)
    : product.history.map(() => a.avg_price);
  const label = useUnit ? `Price per ${unit}` : "Shelf price";
  if (priceChart) priceChart.destroy();
  priceChart = new Chart(document.getElementById("price-chart"), {
    type: "line",
    data: {
      labels: product.history.map((p) => formatDate(p.purchase_date)),
      datasets: [
        { label, data: prices, borderColor: "#5eead4", backgroundColor: "rgba(94,234,212,0.12)", fill: true, tension: 0.2 },
        { label: "Average", data: avg, borderColor: "#fbbf24", borderDash: [6, 4], pointRadius: 0 },
      ],
    },
    options: chartOpts(true),
  });
}

function renderProductAnalytics(product) {
  currentProduct = product;
  const a = product.analytics;
  document.getElementById("product-title").textContent = product.canonical_name;
  const unitLabel = product.unit_amount && product.normalized_unit ? `${product.unit_amount} ${product.normalized_unit}` : null;
  document.getElementById("product-subtitle").textContent = [
    product.category || "Uncategorized",
    unitLabel ? `package: ${unitLabel}` : null,
    product.normalized_unit_price != null ? `${money(product.normalized_unit_price)}/${product.normalized_unit}` : null,
  ].filter(Boolean).join(" · ");
  document.getElementById("product-category").value = product.category || "";
  document.getElementById("product-unit-amount").value = product.unit_amount ?? "";
  document.getElementById("product-normalized-unit").value = product.normalized_unit || "";
  toggleWatchBtn.textContent = product.is_watched ? "★ Watching" : "☆ Watch";
  document.getElementById("stats-grid").innerHTML = [
    statCard("Latest", money(a.latest_price)),
    statCard("Per unit", product.normalized_unit_price != null ? money(product.normalized_unit_price) : "—", product.normalized_unit || ""),
    statCard("Average", money(a.avg_price)),
    statCard("Since first", pct(a.change_since_first_pct), "", pctClass(a.change_since_first_pct)),
    statCard("Since last", pct(a.change_since_previous_pct), "", pctClass(a.change_since_previous_pct)),
    statCard("Frequency", a.avg_days_between_purchases != null ? `~${a.avg_days_between_purchases}d` : "—"),
  ].join("");
  renderProductChart(product);
  const storeRows = document.getElementById("store-comparison-rows");
  storeRows.innerHTML = product.store_comparison?.length ? "" : "<tr><td colspan='4' class='meta'>Need purchases at multiple stores.</td></tr>";
  product.store_comparison?.forEach((s) => { const tr = document.createElement("tr"); tr.innerHTML = `<td>${s.store}</td><td class="num">${s.purchase_count}</td><td class="num">${money(s.avg_price)}</td><td class="num">${money(s.latest_price)}</td>`; storeRows.appendChild(tr); });
  const changeRows = document.getElementById("change-rows");
  changeRows.innerHTML = a.changes.length ? "" : "<tr><td colspan='4' class='meta'>Need two+ purchases.</td></tr>";
  [...a.changes].reverse().forEach((c) => { const tr = document.createElement("tr"); tr.innerHTML = `<td>${formatDate(c.from_date)} → ${formatDate(c.to_date)}</td><td class="num">${money(c.from_price)}</td><td class="num">${money(c.to_price)}</td><td class="num ${pctClass(c.change_pct)}">${pct(c.change_pct)}</td>`; changeRows.appendChild(tr); });
  const historyRows = document.getElementById("history-rows");
  historyRows.innerHTML = "";
  [...product.history].reverse().forEach((p) => {
    const tr = document.createElement("tr");
    const price = p.normalized_price != null ? `${money(p.effective_price)} (${money(p.normalized_price)}/${product.normalized_unit || "unit"})` : money(p.effective_price);
    tr.innerHTML = `<td>${formatDate(p.purchase_date)}</td><td class="num">${price}</td><td class="num">${p.quantity}</td><td><button type="button" class="item-link">#${p.receipt_id}</button></td>`;
    tr.querySelector("button").addEventListener("click", () => showReceipt(p.receipt_id));
    historyRows.appendChild(tr);
  });
}

async function showProduct(id, { fromReceipt = false, name = null } = {}) {
  selectedProductId = id;
  await ensureCategories();
  const product = await api(`/api/products/${id}`);
  if (name) product.canonical_name = name;
  backToReceiptBtn.classList.toggle("hidden", !fromReceipt);
  if (!fromReceipt) setView("prices");
  else { receiptDetail.classList.add("hidden"); productPanel.classList.remove("hidden"); }
  renderProductAnalytics(product);
  await loadProducts();
  await loadWatchlist();
}

async function loadSpending() {
  const [data, inflation] = await Promise.all([api("/api/spending/overview"), api("/api/insights/inflation-basket")]);
  document.getElementById("monthly-budget").value = data.monthly_budget ?? "";
  const s = data.summary;
  document.getElementById("spending-stats").innerHTML = [statCard("Total spent", money(s.total_spent)), statCard("This month", money(data.current_month_spend), data.monthly_budget != null ? `budget ${money(data.monthly_budget)}` : ""), statCard("Budget left", money(data.budget_remaining), "", data.budget_remaining != null && data.budget_remaining < 0 ? "up" : "down"), statCard("Inflation basket", inflation.basket_change_pct != null ? pct(inflation.basket_change_pct) : "—", `${inflation.product_count} products`, pctClass(inflation.basket_change_pct)), statCard("Trips", String(s.receipt_count)), statCard("Avg trip", money(s.avg_trip_total))].join("");
  if (categoryChart) categoryChart.destroy();
  categoryChart = new Chart(document.getElementById("category-chart"), { type: "doughnut", data: { labels: data.by_category.map((e) => e.category), datasets: [{ data: data.by_category.map((e) => e.total), backgroundColor: ["#5eead4", "#60a5fa", "#fbbf24", "#f472b6", "#a78bfa", "#fb923c"] }] }, options: { plugins: { legend: { position: "bottom", labels: { color: "#e8eef7" } } } } });
  if (storeChart) storeChart.destroy();
  storeChart = new Chart(document.getElementById("store-chart"), { type: "bar", data: { labels: data.by_store.map((e) => e.store), datasets: [{ data: data.by_store.map((e) => e.total), backgroundColor: "#5eead4" }] }, options: chartOpts(true) });
  if (monthlyChart) monthlyChart.destroy();
  monthlyChart = new Chart(document.getElementById("monthly-chart"), { type: "line", data: { labels: data.monthly.map((e) => e.month), datasets: [{ label: "Monthly spend", data: data.monthly.map((e) => e.total), borderColor: "#60a5fa", fill: true, tension: 0.2 }] }, options: chartOpts(true) });
}

async function mergeProducts(targetId, sourceIds) {
  if (!confirm(`Merge ${sourceIds.length} product(s)?`)) return;
  const product = await api("/api/products/merge", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ target_id: targetId, source_ids: sourceIds }) });
  selectedProductIds.clear();
  selectedProductId = product.id;
  await showProduct(product.id, { fromReceipt: false });
  setStatus("Products merged.", "success");
}

async function loadMergeSuggestions(llm = false) {
  mergeSuggestions.innerHTML = "<li class='meta'>Loading...</li>";
  const suggestions = await api(`/api/products/merge-suggestions${llm ? "?use_llm=true" : ""}`);
  mergeSuggestions.innerHTML = suggestions.length ? "" : "<li class='meta'>No suggestions.</li>";
  suggestions.forEach((s) => {
    const li = document.createElement("li");
    li.className = "suggestion-item";
    li.innerHTML = `<span>${s.names.join(" + ")}</span><button type="button" class="secondary small">Merge</button>`;
    li.querySelector("button").addEventListener("click", () => mergeProducts(s.product_ids[0], s.product_ids.slice(1)));
    mergeSuggestions.appendChild(li);
  });
}

document.querySelectorAll(".nav-btn").forEach((b) => b.addEventListener("click", () => setView(b.dataset.view)));
document.getElementById("edit-receipt-btn").addEventListener("click", () => setReceiptEditMode(true));
document.getElementById("cancel-receipt-edit").addEventListener("click", () => setReceiptEditMode(false));
toggleItemsEditBtn.addEventListener("click", () => setBulkEditMode(!bulkEditMode));
mergeSelectedBtn.addEventListener("click", () => { const ids = [...selectedProductIds]; mergeProducts(ids[0], ids.slice(1)); });
document.getElementById("load-suggestions-btn").addEventListener("click", () => loadMergeSuggestions(false).catch((e) => setStatus(e.message, "error")));
document.getElementById("ai-suggestions-btn").addEventListener("click", () => loadMergeSuggestions(true).catch((e) => setStatus(e.message, "error")));
reviewQueueBtn.addEventListener("click", () => { reviewQueueMode = !reviewQueueMode; loadReceipts(); });

bulkReparseBtn.addEventListener("click", async () => {
  const candidates = await api("/api/receipts/reparse-candidates");
  const missing = candidates.filter((c) => c.missing_categories).length;
  const choice = confirm(
    `Re-parse receipts using OpenAI (uses API credits).\n\n` +
    `OK = only receipts missing categories (${missing})\n` +
    `Cancel, then OK on next prompt = re-parse ALL ${candidates.length} with images`
  );
  let payload = { missing_categories_only: true };
  if (!choice) {
    if (!confirm(`Re-parse all ${candidates.length} receipts? This may take a while.`)) return;
    payload = { missing_categories_only: false };
  }
  bulkReparseBtn.disabled = true;
  setStatus("Bulk re-parsing...");
  try {
    const result = await api("/api/receipts/reparse/batch", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    setStatus(`Re-parsed ${result.succeeded.length}/${result.total}. Failed: ${result.failed.length}.`, result.failed.length ? "error" : "success");
    await loadReceipts();
    if (selectedReceiptId) await showReceipt(selectedReceiptId);
  } catch (err) {
    setStatus(err.message, "error");
  } finally {
    bulkReparseBtn.disabled = false;
  }
});

markReviewedBtn.addEventListener("click", async () => {
  if (!selectedReceiptId) return;
  await api(`/api/receipts/${selectedReceiptId}/mark-reviewed`, { method: "POST" });
  await showReceipt(selectedReceiptId);
  setStatus("Marked as reviewed.", "success");
});

importForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const file = document.getElementById("import-file").files[0];
  if (!file) return;
  const replace = document.getElementById("import-replace").checked;
  if (replace && !confirm("Replace ALL existing data with this backup?")) return;
  const fd = new FormData();
  fd.append("file", file);
  try {
    const result = await api(`/api/import/json/file?replace=${replace}`, { method: "POST", body: fd });
    setStatus(`Imported ${result.imported_receipts} receipts, ${result.imported_items} items.`, "success");
    document.getElementById("import-file").value = "";
    selectedReceiptId = null;
    setView("receipts");
    await loadReceipts();
  } catch (err) {
    setStatus(err.message, "error");
  }
});

unitForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  if (!selectedProductId) return;
  const amountVal = document.getElementById("product-unit-amount").value;
  await api(`/api/products/${selectedProductId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      unit_amount: amountVal === "" ? null : Number(amountVal),
      normalized_unit: document.getElementById("product-normalized-unit").value || null,
    }),
  });
  await showProduct(selectedProductId, { fromReceipt: false });
  setStatus("Unit size saved.", "success");
});

chartRawBtn.addEventListener("click", () => {
  chartMode = "raw";
  chartRawBtn.classList.add("active");
  chartUnitBtn.classList.remove("active");
  if (currentProduct) renderProductChart(currentProduct);
});

chartUnitBtn.addEventListener("click", () => {
  chartMode = "unit";
  chartUnitBtn.classList.add("active");
  chartRawBtn.classList.remove("active");
  if (currentProduct) renderProductChart(currentProduct);
});

toggleWatchBtn.addEventListener("click", async () => {
  if (!selectedProductId) return;
  await api(`/api/products/${selectedProductId}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ is_watched: !currentProduct?.is_watched }) });
  await showProduct(selectedProductId, { fromReceipt: false });
});

receiptEditForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  await api(`/api/receipts/${selectedReceiptId}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({
    store_name: document.getElementById("edit-store").value.trim() || null,
    purchase_date: document.getElementById("edit-date").value || null,
    total: document.getElementById("edit-total").value === "" ? null : Number(document.getElementById("edit-total").value),
    notes: document.getElementById("edit-notes").value.trim() || null,
  }) });
  setReceiptEditMode(false);
  await showReceipt(selectedReceiptId);
});

categoryForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  await api(`/api/products/${selectedProductId}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ category: document.getElementById("product-category").value || null }) });
  await showProduct(selectedProductId, { fromReceipt: false });
});

budgetForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const val = document.getElementById("monthly-budget").value;
  await api("/api/settings/budget", { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ monthly_budget: val === "" ? null : Number(val) }) });
  await loadSpending();
  setStatus("Budget saved.", "success");
});

document.getElementById("reparse-btn").addEventListener("click", async () => {
  if (!confirm("Re-parse from saved image?")) return;
  await api(`/api/receipts/${selectedReceiptId}/reparse`, { method: "POST" });
  setBulkEditMode(false);
  await showReceipt(selectedReceiptId);
});

document.getElementById("delete-receipt-btn").addEventListener("click", async () => {
  if (!confirm("Delete receipt permanently?")) return;
  await api(`/api/receipts/${selectedReceiptId}`, { method: "DELETE" });
  selectedReceiptId = null;
  setView("receipts");
  setStatus("Receipt deleted.", "success");
});

backToReceiptBtn.addEventListener("click", () => showReceipt(selectedReceiptId));
productSearch.addEventListener("input", () => loadProducts().catch((e) => setStatus(e.message, "error")));

addItemForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  await api(`/api/receipts/${selectedReceiptId}/items`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({
    raw_name: document.getElementById("new-item-name").value.trim(),
    quantity: Number(document.getElementById("new-item-qty").value),
    unit_price: document.getElementById("new-item-unit").value === "" ? null : Number(document.getElementById("new-item-unit").value),
    line_total: document.getElementById("new-item-total").value === "" ? null : Number(document.getElementById("new-item-total").value),
  }) });
  addItemForm.reset();
  document.getElementById("new-item-qty").value = "1";
  await showReceipt(selectedReceiptId);
});

uploadForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const files = [...document.getElementById("receipt-file").files];
  if (!files.length) return;
  uploadBtn.disabled = true;
  setStatus(files.length > 1 ? `Parsing ${files.length} receipts...` : "Parsing receipt...");
  try {
    if (files.length === 1) {
      const fd = new FormData();
      fd.append("file", files[0]);
      const receipt = await api("/api/receipts/upload", { method: "POST", body: fd });
      await showReceipt(receipt.id);
      setStatus("Receipt saved.", "success");
    } else {
      const fd = new FormData();
      files.forEach((f) => fd.append("files", f));
      const result = await api("/api/receipts/upload/batch", { method: "POST", body: fd });
      setStatus(`Saved ${result.saved.length}, failed ${result.failed.length}.`, result.failed.length ? "error" : "success");
      if (result.saved[0]) await showReceipt(result.saved[0].id);
    }
    document.getElementById("receipt-file").value = "";
    await loadReceipts();
  } catch (err) {
    setStatus(err.message, "error");
  } finally {
    uploadBtn.disabled = false;
  }
});

if ("serviceWorker" in navigator) navigator.serviceWorker.register("/sw.js").catch(() => {});
loadReceipts().catch((e) => setStatus(e.message, "error"));
loadMergeSuggestions().catch(() => {});
