function money(value) {
  if (value == null || value === "") return "—";
  const n = Number(value);
  if (Number.isNaN(n)) return String(value);
  return n.toLocaleString(undefined, { style: "currency", currency: "USD" });
}

function showPanel(name) {
  document.querySelectorAll(".panel").forEach((el) => el.classList.remove("active"));
  document.querySelectorAll(".nav-item").forEach((el) => el.classList.remove("active"));
  const panel = document.getElementById(`panel-${name}`);
  const nav = document.querySelector(`.nav-item[data-panel="${name}"]`);
  if (panel) panel.classList.add("active");
  if (nav) nav.classList.add("active");
  if (name === "dashboard") loadDashboard();
  if (name === "settings") loadSettings();
}

async function loadDashboard() {
  try {
    const res = await fetch("/api/app/dashboard");
    const data = await res.json();
    const bank = data.banking || {};
    const grocery = data.grocery || {};
    document.getElementById("dash-income").textContent = money(bank.total_income);
    document.getElementById("dash-expenses").textContent = money(bank.total_expenses);
    document.getElementById("dash-net").textContent = money(bank.net_amount);
    document.getElementById("dash-receipt-count").textContent = grocery.receipt_count ?? "—";
    document.getElementById("dash-grocery-total").textContent = money(grocery.total_spent);
    document.getElementById("dash-grocery-avg").textContent = money(grocery.avg_trip_total);
  } catch (err) {
    console.error(err);
  }
}

async function loadSettings() {
  const res = await fetch("/api/app/settings");
  const data = await res.json();
  document.getElementById("openai-model").value = data.openai_model || "gpt-4o-mini";
  document.getElementById("data-dir").value = data.data_dir || "";
  document.getElementById("key-status").textContent = data.openai_api_key_set
    ? `Key on file: ${data.openai_api_key_masked}`
    : "No API key saved yet.";
  document.getElementById("openai-key").value = "";
  document.getElementById("openai-key").placeholder = data.openai_api_key_set ? "•••• leave blank to keep" : "sk-…";
}

document.querySelectorAll(".nav-item").forEach((btn) => {
  btn.addEventListener("click", () => showPanel(btn.dataset.panel));
});

document.querySelectorAll("[data-goto]").forEach((btn) => {
  btn.addEventListener("click", () => showPanel(btn.dataset.goto));
});

document.getElementById("settings-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const payload = {
    openai_model: document.getElementById("openai-model").value.trim() || "gpt-4o-mini",
  };
  const key = document.getElementById("openai-key").value.trim();
  if (key) payload.openai_api_key = key;
  const res = await fetch("/api/app/settings", {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const msg = document.getElementById("settings-msg");
  if (res.ok) {
    msg.textContent = "Saved.";
    loadSettings();
  } else {
    msg.textContent = "Could not save settings.";
  }
});

loadDashboard();
