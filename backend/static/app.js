const receiptList = document.getElementById("receipt-list");
const productList = document.getElementById("product-list");
const uploadForm = document.getElementById("upload-form");
const uploadStatus = document.getElementById("upload-status");
const uploadBtn = document.getElementById("upload-btn");
const emptyState = document.getElementById("empty-state");
const emptyTitle = document.getElementById("empty-title");
const emptyText = document.getElementById("empty-text");
const receiptDetail = document.getElementById("receipt-detail");
const productPanel = document.getElementById("product-panel");
const validationBanner = document.getElementById("validation-banner");
const detailView = document.getElementById("detail-view");
const receiptEditForm = document.getElementById("receipt-edit-form");
const addItemForm = document.getElementById("add-item-form");
const sidebarReceipts = document.getElementById("sidebar-receipts");
const sidebarPrices = document.getElementById("sidebar-prices");
const productSearch = document.getElementById("product-search");
const backToReceiptBtn = document.getElementById("back-to-receipt");
const toggleItemsEditBtn = document.getElementById("toggle-items-edit-btn");

let priceChart = null;
let selectedReceiptId = null;
let selectedProductId = null;
let currentReceipt = null;
let editingItemId = null;
let bulkEditMode = false;
let activeView = "receipts";
let openedProductFromReceipt = false;

function money(value) {
  if (value == null) return "—";
  return `$${Number(value).toFixed(2)}`;
}

function pct(value) {
  if (value == null) return "—";
  const sign = value > 0 ? "+" : "";
  return `${sign}${Number(value).toFixed(1)}%`;
}

function pctClass(value) {
  if (value == null || value === 0) return "neutral";
  return value > 0 ? "up" : "down";
}

function formatDate(value) {
  if (!value) return "Unknown date";
  return new Date(value + "T00:00:00").toLocaleDateString();
}

function toInputDate(value) {
  return value || "";
}

async function api(path, options = {}) {
  const response = await fetch(path, options);
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    const detail = Array.isArray(payload.detail)
      ? payload.detail.map((entry) => entry.msg).join(", ")
      : payload.detail;
    throw new Error(detail || "Request failed");
  }
  if (response.status === 204) return null;
  return response.json();
}

function setStatus(message, type = "") {
  uploadStatus.textContent = message;
  uploadStatus.className = `status ${type}`.trim();
}

function escapeAttr(value) {
  return String(value).replaceAll('"', "&quot;");
}

function setView(view) {
  activeView = view;
  document.querySelectorAll(".nav-btn").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.view === view);
  });
  sidebarReceipts.classList.toggle("hidden", view !== "receipts");
  sidebarPrices.classList.toggle("hidden", view !== "prices");

  if (view === "prices") {
    receiptDetail.classList.add("hidden");
    emptyState.classList.add("hidden");
    if (selectedProductId) {
      productPanel.classList.remove("hidden");
    } else {
      productPanel.classList.add("hidden");
      emptyState.classList.remove("hidden");
      emptyTitle.textContent = "Track grocery prices";
      emptyText.textContent = "Search and select a product to see price trends, averages, and rate of change.";
    }
    loadProducts().catch((error) => setStatus(error.message, "error"));
  } else {
    productPanel.classList.add("hidden");
    if (selectedReceiptId) {
      receiptDetail.classList.remove("hidden");
      emptyState.classList.add("hidden");
    } else {
      receiptDetail.classList.add("hidden");
      emptyState.classList.remove("hidden");
      emptyTitle.textContent = "Select a receipt";
      emptyText.textContent = "Choose a receipt from the list or upload a new one.";
    }
  }
}

function renderValidation(validation) {
  if (!validation || validation.is_valid) {
    validationBanner.classList.add("hidden");
    validationBanner.textContent = "";
    return;
  }

  validationBanner.classList.remove("hidden");
  validationBanner.className = "validation-banner warning";
  const parts = [...validation.warnings];
  if (validation.items_sum != null && validation.receipt_total != null) {
    parts.unshift(
      `Items: ${money(validation.items_sum)} · Receipt: ${money(validation.receipt_total)}`
    );
  }
  validationBanner.textContent = parts.join(" ");
}

function setReceiptEditMode(enabled) {
  detailView.classList.toggle("hidden", enabled);
  receiptEditForm.classList.toggle("hidden", !enabled);
}

function setBulkEditMode(enabled) {
  bulkEditMode = enabled;
  editingItemId = null;
  toggleItemsEditBtn.textContent = enabled ? "Done editing items" : "Edit all items";
  toggleItemsEditBtn.classList.toggle("active", enabled);
  if (currentReceipt) renderReceiptItems(currentReceipt.line_items);
}

function wireLineCalc(row) {
  const qty = row.querySelector('[data-field="quantity"]');
  const unit = row.querySelector('[data-field="unit_price"]');
  const total = row.querySelector('[data-field="line_total"]');
  if (!qty || !unit || !total) return;

  const updateTotal = () => {
    const q = Number(qty.value);
    const u = Number(unit.value);
    if (qty.value !== "" && unit.value !== "" && !Number.isNaN(q) && !Number.isNaN(u)) {
      total.value = (q * u).toFixed(2);
    }
  };
  qty.addEventListener("input", updateTotal);
  unit.addEventListener("input", updateTotal);
}

async function loadReceipts() {
  const receipts = await api("/api/receipts");
  receiptList.innerHTML = "";

  if (!receipts.length) {
    receiptList.innerHTML = "<li class='meta'>No receipts yet.</li>";
    return;
  }

  for (const receipt of receipts) {
    const li = document.createElement("li");
    const button = document.createElement("button");
    button.type = "button";
    button.className = receipt.id === selectedReceiptId ? "active" : "";
    const warning = receipt.has_warning ? " · ⚠ check totals" : "";
    button.innerHTML = `
      <strong>${receipt.store_name || "Unknown store"}</strong>
      <span class="meta">${formatDate(receipt.purchase_date)} · ${receipt.item_count} items · ${money(receipt.total)}${warning}</span>
    `;
    button.addEventListener("click", () => showReceipt(receipt.id));
    li.appendChild(button);
    receiptList.appendChild(li);
  }
}

async function loadProducts() {
  const query = productSearch.value.trim();
  const path = query ? `/api/products?q=${encodeURIComponent(query)}` : "/api/products";
  const products = await api(path);
  productList.innerHTML = "";

  if (!products.length) {
    productList.innerHTML = "<li class='meta'>No products found.</li>";
    return;
  }

  for (const product of products) {
    const li = document.createElement("li");
    const button = document.createElement("button");
    button.type = "button";
    button.className = product.id === selectedProductId ? "active" : "";
    const change =
      product.change_since_previous_pct != null
        ? ` · <span class="${pctClass(product.change_since_previous_pct)}">${pct(product.change_since_previous_pct)}</span>`
        : "";
    button.innerHTML = `
      <strong>${product.canonical_name}</strong>
      <span class="meta">${product.purchase_count} buys · latest ${money(product.latest_price)} · avg ${money(product.avg_price)}${change}</span>
    `;
    button.addEventListener("click", () => showProduct(product.id, { fromReceipt: false }));
    li.appendChild(button);
    productList.appendChild(li);
  }
}

function renderEditableRow(item) {
  const row = document.createElement("tr");
  row.className = "editing-row";
  row.innerHTML = `
    <td><input type="text" class="cell-input" data-field="raw_name" value="${escapeAttr(item.raw_name)}" /></td>
    <td><input type="number" class="cell-input num" data-field="quantity" value="${item.quantity}" step="0.01" min="0" /></td>
    <td><input type="number" class="cell-input num" data-field="unit_price" value="${item.unit_price ?? ""}" step="0.01" min="0" /></td>
    <td><input type="number" class="cell-input num" data-field="line_total" value="${item.line_total ?? ""}" step="0.01" min="0" /></td>
    <td class="row-actions">
      <button type="button" class="secondary small save-item-btn">Save</button>
      ${bulkEditMode ? "" : '<button type="button" class="secondary small cancel-item-btn">Cancel</button>'}
    </td>
  `;
  wireLineCalc(row);
  row.querySelector(".save-item-btn").addEventListener("click", () => saveLineItem(item.id, row));
  const cancelBtn = row.querySelector(".cancel-item-btn");
  if (cancelBtn) {
    cancelBtn.addEventListener("click", () => {
      editingItemId = null;
      renderReceiptItems(currentReceipt.line_items);
    });
  }
  return row;
}

function renderLineItemRow(item) {
  if (bulkEditMode || editingItemId === item.id) {
    return renderEditableRow(item);
  }

  const row = document.createElement("tr");
  const nameCell = document.createElement("td");
  const link = document.createElement("button");
  link.type = "button";
  link.className = "item-link";
  link.textContent = item.raw_name;
  if (item.product_id) {
    link.addEventListener("click", () => showProduct(item.product_id, { fromReceipt: true, name: item.raw_name }));
  }
  nameCell.appendChild(link);

  const actions = document.createElement("td");
  actions.className = "row-actions";
  actions.innerHTML = `
    <button type="button" class="secondary small edit-item-btn">Edit</button>
    <button type="button" class="danger small delete-item-btn">Del</button>
  `;
  actions.querySelector(".edit-item-btn").addEventListener("click", () => {
    editingItemId = item.id;
    renderReceiptItems(currentReceipt.line_items);
  });
  actions.querySelector(".delete-item-btn").addEventListener("click", () => deleteLineItem(item.id));

  row.appendChild(nameCell);
  row.innerHTML += `
    <td class="num">${item.quantity}</td>
    <td class="num">${money(item.unit_price)}</td>
    <td class="num">${money(item.line_total)}</td>
  `;
  row.appendChild(actions);
  row.replaceChild(nameCell, row.firstChild);
  return row;
}

function renderReceiptItems(items) {
  const tbody = document.getElementById("detail-items");
  tbody.innerHTML = "";
  for (const item of items) {
    tbody.appendChild(renderLineItemRow(item));
  }
}

async function showReceipt(receiptId) {
  selectedReceiptId = receiptId;
  editingItemId = null;
  setReceiptEditMode(false);
  currentReceipt = await api(`/api/receipts/${receiptId}`);

  setView("receipts");
  emptyState.classList.add("hidden");
  productPanel.classList.add("hidden");
  receiptDetail.classList.remove("hidden");

  document.getElementById("detail-store").textContent = currentReceipt.store_name || "Unknown store";
  document.getElementById("detail-meta").textContent = `${formatDate(currentReceipt.purchase_date)} · Total ${money(currentReceipt.total)}`;
  document.getElementById("detail-image").src = `/api/receipts/${receiptId}/image?t=${Date.now()}`;

  document.getElementById("edit-store").value = currentReceipt.store_name || "";
  document.getElementById("edit-date").value = toInputDate(currentReceipt.purchase_date);
  document.getElementById("edit-total").value = currentReceipt.total ?? "";

  renderValidation(currentReceipt.validation);
  renderReceiptItems(currentReceipt.line_items);
  await loadReceipts();
}

async function saveLineItem(itemId, row) {
  const payload = {};
  for (const input of row.querySelectorAll(".cell-input")) {
    const field = input.dataset.field;
    if (field === "raw_name") {
      payload.raw_name = input.value.trim();
    } else {
      payload[field] = input.value === "" ? null : Number(input.value);
    }
  }

  if (!payload.raw_name) {
    alert("Item name is required.");
    return;
  }

  await api(`/api/receipts/${selectedReceiptId}/items/${itemId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!bulkEditMode) editingItemId = null;
  currentReceipt = await api(`/api/receipts/${selectedReceiptId}`);
  renderValidation(currentReceipt.validation);
  renderReceiptItems(currentReceipt.line_items);
}

async function deleteLineItem(itemId) {
  if (!confirm("Delete this line item?")) return;
  await api(`/api/receipts/${selectedReceiptId}/items/${itemId}`, { method: "DELETE" });
  await showReceipt(selectedReceiptId);
}

function renderStatCard(label, value, subtext = "", valueClass = "") {
  return `
    <article class="stat-card">
      <span class="stat-label">${label}</span>
      <strong class="stat-value ${valueClass}">${value}</strong>
      ${subtext ? `<span class="stat-sub">${subtext}</span>` : ""}
    </article>
  `;
}

function renderProductAnalytics(product) {
  const { analytics: a, history } = product;

  document.getElementById("product-title").textContent = product.canonical_name;
  document.getElementById("product-subtitle").textContent = product.category
    ? `Category: ${product.category}`
    : `${a.purchase_count} purchases tracked`;

  const statsGrid = document.getElementById("stats-grid");
  statsGrid.innerHTML = [
    renderStatCard("Latest price", money(a.latest_price)),
    renderStatCard("Average", money(a.avg_price)),
    renderStatCard("Low / High", `${money(a.min_price)} / ${money(a.max_price)}`),
    renderStatCard(
      "Since first buy",
      pct(a.change_since_first_pct),
      a.first_price != null ? `from ${money(a.first_price)}` : "",
      pctClass(a.change_since_first_pct)
    ),
    renderStatCard(
      "Since last buy",
      pct(a.change_since_previous_pct),
      "",
      pctClass(a.change_since_previous_pct)
    ),
    renderStatCard(
      "Buy frequency",
      a.avg_days_between_purchases != null ? `~${a.avg_days_between_purchases} days` : "—",
      "average gap between purchases"
    ),
  ].join("");

  const labels = history.map((point) => formatDate(point.purchase_date));
  const prices = history.map((point) => point.effective_price);
  const avgLine = a.avg_price != null ? history.map(() => a.avg_price) : [];

  if (priceChart) priceChart.destroy();
  priceChart = new Chart(document.getElementById("price-chart"), {
    type: "line",
    data: {
      labels,
      datasets: [
        {
          label: "Unit price",
          data: prices,
          borderColor: "#5eead4",
          backgroundColor: "rgba(94, 234, 212, 0.12)",
          tension: 0.2,
          fill: true,
          pointRadius: 4,
        },
        {
          label: "Average",
          data: avgLine,
          borderColor: "#fbbf24",
          borderDash: [6, 4],
          pointRadius: 0,
          fill: false,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { labels: { color: "#e8eef7" } },
        tooltip: {
          callbacks: {
            label(context) {
              return `${context.dataset.label}: ${money(context.parsed.y)}`;
            },
          },
        },
      },
      scales: {
        x: { ticks: { color: "#9fb0c7" }, grid: { color: "#2d3a4d" } },
        y: {
          ticks: {
            color: "#9fb0c7",
            callback: (value) => `$${value}`,
          },
          grid: { color: "#2d3a4d" },
        },
      },
    },
  });

  const changeRows = document.getElementById("change-rows");
  changeRows.innerHTML = "";
  if (!a.changes.length) {
    changeRows.innerHTML = "<tr><td colspan='4' class='meta'>Need at least two purchases to compute changes.</td></tr>";
  } else {
    for (const change of [...a.changes].reverse()) {
      const row = document.createElement("tr");
      row.innerHTML = `
        <td>${formatDate(change.from_date)} → ${formatDate(change.to_date)}</td>
        <td class="num">${money(change.from_price)}</td>
        <td class="num">${money(change.to_price)}</td>
        <td class="num ${pctClass(change.change_pct)}">${pct(change.change_pct)}</td>
      `;
      changeRows.appendChild(row);
    }
  }

  const historyRows = document.getElementById("history-rows");
  historyRows.innerHTML = "";
  for (const point of [...history].reverse()) {
    const row = document.createElement("tr");
    row.innerHTML = `
      <td>${formatDate(point.purchase_date)}</td>
      <td class="num">${money(point.effective_price)}</td>
      <td class="num">${point.quantity}</td>
      <td><button type="button" class="item-link view-receipt-btn" data-receipt-id="${point.receipt_id}">#${point.receipt_id}</button></td>
    `;
    row.querySelector(".view-receipt-btn").addEventListener("click", () => showReceipt(point.receipt_id));
    historyRows.appendChild(row);
  }
}

async function showProduct(productId, options = {}) {
  const { fromReceipt = false, name = null } = options;
  selectedProductId = productId;
  openedProductFromReceipt = fromReceipt;

  const product = await api(`/api/products/${productId}`);
  if (name) product.canonical_name = name;

  emptyState.classList.add("hidden");
  receiptDetail.classList.add("hidden");
  productPanel.classList.remove("hidden");
  backToReceiptBtn.classList.toggle("hidden", !fromReceipt);

  if (!fromReceipt) setView("prices");
  renderProductAnalytics(product);
  await loadProducts();
}

document.querySelectorAll(".nav-btn").forEach((btn) => {
  btn.addEventListener("click", () => setView(btn.dataset.view));
});

document.getElementById("edit-receipt-btn").addEventListener("click", () => setReceiptEditMode(true));
document.getElementById("cancel-receipt-edit").addEventListener("click", () => setReceiptEditMode(false));
toggleItemsEditBtn.addEventListener("click", () => setBulkEditMode(!bulkEditMode));

receiptEditForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const totalValue = document.getElementById("edit-total").value;
  await api(`/api/receipts/${selectedReceiptId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      store_name: document.getElementById("edit-store").value.trim() || null,
      purchase_date: document.getElementById("edit-date").value || null,
      total: totalValue === "" ? null : Number(totalValue),
    }),
  });
  setReceiptEditMode(false);
  await showReceipt(selectedReceiptId);
});

document.getElementById("reparse-btn").addEventListener("click", async () => {
  if (!confirm("Re-parse this receipt from the saved image? Current line items will be replaced.")) return;
  try {
    await api(`/api/receipts/${selectedReceiptId}/reparse`, { method: "POST" });
    setBulkEditMode(false);
    await showReceipt(selectedReceiptId);
    setStatus("Receipt re-parsed.", "success");
  } catch (error) {
    setStatus(error.message, "error");
  }
});

document.getElementById("delete-receipt-btn").addEventListener("click", async () => {
  if (!confirm("Delete this receipt and its image permanently?")) return;
  await api(`/api/receipts/${selectedReceiptId}`, { method: "DELETE" });
  selectedReceiptId = null;
  currentReceipt = null;
  setBulkEditMode(false);
  receiptDetail.classList.add("hidden");
  emptyState.classList.remove("hidden");
  await loadReceipts();
  setStatus("Receipt deleted.", "success");
});

backToReceiptBtn.addEventListener("click", async () => {
  productPanel.classList.add("hidden");
  if (selectedReceiptId) await showReceipt(selectedReceiptId);
});

productSearch.addEventListener("input", () => {
  loadProducts().catch((error) => setStatus(error.message, "error"));
});

addItemForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const unitValue = document.getElementById("new-item-unit").value;
  const totalValue = document.getElementById("new-item-total").value;

  await api(`/api/receipts/${selectedReceiptId}/items`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      raw_name: document.getElementById("new-item-name").value.trim(),
      quantity: Number(document.getElementById("new-item-qty").value),
      unit_price: unitValue === "" ? null : Number(unitValue),
      line_total: totalValue === "" ? null : Number(totalValue),
    }),
  });

  addItemForm.reset();
  document.getElementById("new-item-qty").value = "1";
  await showReceipt(selectedReceiptId);
});

document.getElementById("new-item-qty").addEventListener("input", syncNewItemTotal);
document.getElementById("new-item-unit").addEventListener("input", syncNewItemTotal);

function syncNewItemTotal() {
  const qty = Number(document.getElementById("new-item-qty").value);
  const unit = Number(document.getElementById("new-item-unit").value);
  if (!Number.isNaN(qty) && !Number.isNaN(unit) && document.getElementById("new-item-unit").value !== "") {
    document.getElementById("new-item-total").value = (qty * unit).toFixed(2);
  }
}

uploadForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const fileInput = document.getElementById("receipt-file");
  const file = fileInput.files[0];
  if (!file) return;

  const formData = new FormData();
  formData.append("file", file);

  uploadBtn.disabled = true;
  setStatus("Parsing receipt with vision model...");

  try {
    const receipt = await api("/api/receipts/upload", { method: "POST", body: formData });
    setStatus("Receipt saved.", "success");
    fileInput.value = "";
    await loadReceipts();
    await showReceipt(receipt.id);
  } catch (error) {
    setStatus(error.message, "error");
  } finally {
    uploadBtn.disabled = false;
  }
});

loadReceipts().catch((error) => setStatus(error.message, "error"));
