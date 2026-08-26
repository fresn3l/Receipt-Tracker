/**
 * Compatibility shim: banking UI historically used Eel RPC.
 * Maps eel.fn(...args)() calls onto /api/bank HTTP endpoints.
 */
(function () {
  async function request(path, options = {}) {
    const opts = { ...options };
    opts.headers = opts.headers || {};
    if (opts.body && typeof opts.body === "object" && !(opts.body instanceof FormData)) {
      opts.headers["Content-Type"] = "application/json";
      opts.body = JSON.stringify(opts.body);
    }
    const res = await fetch(path, opts);
    if (!res.ok) {
      let detail = res.statusText;
      try {
        const err = await res.json();
        detail = err.detail || JSON.stringify(err);
      } catch (_) {}
      throw new Error(detail);
    }
    if (res.status === 204) return null;
    const ct = res.headers.get("content-type") || "";
    if (ct.includes("application/json")) return res.json();
    return res.text();
  }

  function wrap(fn) {
    return (...args) => async () => fn(...args);
  }

  window.eel = {
    select_file: wrap(async () => null),

    import_csv_file: wrap(async (filePath, account, autoCategorize, overwrite, checkDuplicates, skipDuplicates) => {
      // Prefer FormData upload from #file-input when available
      const input = document.getElementById("file-input");
      if (!input || !input.files || !input.files[0]) {
        return { success: false, error: "No file selected" };
      }
      const fd = new FormData();
      fd.append("file", input.files[0]);
      if (account) fd.append("account", account);
      fd.append("auto_categorize", String(!!autoCategorize));
      fd.append("overwrite", String(!!overwrite));
      fd.append("check_duplicates", String(checkDuplicates !== false));
      fd.append("skip_duplicates", String(skipDuplicates !== false));
      return request("/api/bank/import", { method: "POST", body: fd });
    }),

    get_transactions: wrap(async (page = 1, perPage = 50) =>
      request(`/api/bank/transactions?page=${page}&per_page=${perPage}`)
    ),

    get_overall_stats: wrap(async () => request("/api/bank/stats")),

    get_monthly_summaries: wrap(async () => request("/api/bank/monthly-summaries")),

    get_category_breakdown: wrap(async () => request("/api/bank/category-breakdown")),

    get_spending_patterns: wrap(async () => request("/api/bank/spending-patterns")),

    export_transactions: wrap(async () => {
      const result = await request("/api/bank/export", { method: "POST" });
      return result.path || result;
    }),

    recategorize_all: wrap(async (overwrite = true) =>
      request(`/api/bank/recategorize?overwrite=${!!overwrite}`, { method: "POST" })
    ),

    edit_transaction: wrap(async (id, description, amount, date, categoryName, categoryParent, notes) =>
      request(`/api/bank/transactions/${encodeURIComponent(id)}`, {
        method: "PATCH",
        body: {
          description,
          amount,
          date,
          category_name: categoryName,
          category_parent: categoryParent,
          notes,
        },
      })
    ),

    delete_transaction: wrap(async (id) =>
      request(`/api/bank/transactions/${encodeURIComponent(id)}`, { method: "DELETE" })
    ),

    delete_transactions: wrap(async (ids) =>
      request("/api/bank/transactions/delete-many", {
        method: "POST",
        body: { transaction_ids: ids },
      })
    ),

    split_transaction: wrap(async (id, splits) =>
      request(`/api/bank/transactions/${encodeURIComponent(id)}/split`, {
        method: "POST",
        body: { splits },
      })
    ),

    merge_transactions: wrap(async (ids, keepFirst = true) =>
      request("/api/bank/transactions/merge", {
        method: "POST",
        body: { transaction_ids: ids, keep_first: keepFirst },
      })
    ),

    bulk_edit_transactions: wrap(async (ids, categoryName, notes) =>
      request("/api/bank/transactions/bulk-edit", {
        method: "POST",
        body: { transaction_ids: ids, category_name: categoryName, notes },
      })
    ),

    search_transactions: wrap(async (query, category, account, dateFrom, dateTo, amountMin, amountMax, transactionType, isRecurring) => {
      const params = new URLSearchParams();
      if (query) params.set("query", query);
      if (category) params.set("category", category);
      if (account) params.set("account", account);
      if (dateFrom) params.set("date_from", dateFrom);
      if (dateTo) params.set("date_to", dateTo);
      if (amountMin) params.set("amount_min", amountMin);
      if (amountMax) params.set("amount_max", amountMax);
      if (transactionType) params.set("transaction_type", transactionType);
      if (isRecurring != null) params.set("is_recurring", String(isRecurring));
      return request(`/api/bank/search?${params}`);
    }),

    get_search_filters: wrap(async () => request("/api/bank/search/filters")),

    set_budget: wrap(async (categoryName, year, month, amount, alertThreshold = "0.8", notes = null) =>
      request("/api/bank/budgets", {
        method: "POST",
        body: {
          category_name: categoryName,
          year,
          month,
          amount,
          alert_threshold: alertThreshold,
          notes,
        },
      })
    ),

    get_all_budget_statuses: wrap(async (year, month) =>
      request(`/api/bank/budgets/status?year=${year}&month=${month}`)
    ),

    get_budget_alerts: wrap(async (year, month) =>
      request(`/api/bank/budgets/alerts?year=${year}&month=${month}`)
    ),

    delete_budget: wrap(async (categoryName, year, month) =>
      request(
        `/api/bank/budgets?category_name=${encodeURIComponent(categoryName)}&year=${year}&month=${month}`,
        { method: "DELETE" }
      )
    ),

    get_budget_templates: wrap(async () => request("/api/bank/budgets/templates")),

    detect_recurring_transactions: wrap(async (minOccurrences = 3) =>
      request(`/api/bank/recurring?min_occurrences=${minOccurrences}`)
    ),

    mark_recurring_transactions: wrap(async () =>
      request("/api/bank/recurring/mark", { method: "POST" })
    ),

    get_category_rules: wrap(async () => request("/api/bank/rules")),

    add_category_rule: wrap(async (pattern, categoryName, parentCategory = null, caseSensitive = false) =>
      request("/api/bank/rules", {
        method: "POST",
        body: {
          pattern,
          category_name: categoryName,
          parent_category: parentCategory,
          case_sensitive: caseSensitive,
        },
      })
    ),

    remove_category_rule: wrap(async (pattern, categoryName) =>
      request(
        `/api/bank/rules?pattern=${encodeURIComponent(pattern)}&category_name=${encodeURIComponent(categoryName)}`,
        { method: "DELETE" }
      )
    ),

    test_category_rule: wrap(async (pattern, testStrings) =>
      request("/api/bank/rules/test", {
        method: "POST",
        body: { pattern, test_strings: testStrings },
      })
    ),
  };
})();
