const appState = {
  formStateId: "",
  previewId: "",
  currentPage: 1,
  totalPages: 1,
  currentResults: [],
  currentFilters: {},
};

async function getJson(url, options = {}) {
  const response = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `HTTP ${response.status}`);
  }
  return response.json();
}

function formatDateForSource(value) {
  if (!value) return "";
  const match = String(value).trim().match(/^(\d{1,2})[\/\-](\d{1,2})[\/\-](\d{4})$/);
  if (match) {
    const [, d, m, y] = match;
    return `${d.padStart(2, "0")}/${m.padStart(2, "0")}/${y}`;
  }
  const iso = String(value).trim().match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (iso) {
    const [, y, m, d] = iso;
    return `${d}/${m}/${y}`;
  }
  return String(value).trim();
}

function fillSelect(select, options, value = "") {
  if (!select) return;
  const current = value || select.value || "";
  select.innerHTML = "";
  const normalizedOptions = options || [];
  const hasEmptyOption = normalizedOptions.some((item) => (item.value || "") === "");
  if (!hasEmptyOption) {
    const placeholder = document.createElement("option");
    placeholder.value = "";
    placeholder.textContent = "-----ch?n-----";
    select.appendChild(placeholder);
  }
  normalizedOptions.forEach((item) => {
    const option = document.createElement("option");
    option.value = item.value || "";
    option.textContent = item.label || item.value || "";
    select.appendChild(option);
  });
  select.value = current;
}

function collectFormPayload(form) {
  const fd = new FormData(form);
  return {
    keyword: fd.get("keyword") || "",
    court_level: fd.get("court_level") || "",
    court: fd.get("court") || "",
    adjudication_level: fd.get("adjudication_level") || "",
    document_type: fd.get("document_type") || "",
    case_style: fd.get("case_style") || "",
    legal_relation: fd.get("legal_relation") || "",
    date_from: formatDateForSource(fd.get("date_from") || ""),
    date_to: formatDateForSource(fd.get("date_to") || ""),
    precedent_applied: fd.get("precedent_applied") === "on",
    precedent_voted: fd.get("precedent_voted") === "on",
  };
}

function updateSourceMode(mode) {
  const badge = document.getElementById("source-mode-badge");
  if (!badge) return;
  badge.textContent = mode || "requests";
  badge.className = `badge ${mode === 'playwright' ? 'badge-playwright' : 'badge-requests'}`;
}

function renderResults(results) {
  const container = document.getElementById("results-list");
  if (!container) return;
  appState.currentResults = results || [];
  if (!results.length) {
    container.innerHTML = '<div class="empty-state">Không có kết quả phù hợp.</div>';
    return;
  }
  container.innerHTML = results.map((item, idx) => `
    <article class="result-card">
      <header>
        <div>
          <div class="card-title">${item.title || item.document_number || item.document_type || `Hồ sơ ${idx + 1}`}</div>
          <div class="muted">${item.court_name || ''} ${item.issued_date ? `• ${item.issued_date}` : ''}</div>
        </div>
        <label><input type="checkbox" class="result-selector" data-index="${idx}"> Chọn tải</label>
      </header>
      <div class="meta-grid">
        <div><strong>Loại:</strong> ${item.document_type || ""}</div>
        <div><strong>Số văn bản:</strong> ${item.document_number || ""}</div>
        <div><strong>Ngày công bố:</strong> ${item.published_date || ""}</div>
        <div><strong>Loại vụ việc:</strong> ${item.case_style || ""}</div>
        <div><strong>Quan hệ pháp luật:</strong> ${item.legal_relation || ""}</div>
        <div><strong>Cấp xét xử:</strong> ${item.adjudication_level || ""}</div>
      </div>
    </article>
  `).join("");
}

function renderPagination(currentPage, totalPages) {
  const wrapper = document.getElementById("pagination");
  if (!wrapper) return;
  appState.currentPage = currentPage;
  appState.totalPages = totalPages;
  document.getElementById("current-page").textContent = currentPage;
  document.getElementById("page-count").textContent = totalPages;
  document.getElementById("page-input").value = currentPage;
  wrapper.classList.toggle("hidden", totalPages <= 1);
  document.getElementById("prev-page").disabled = currentPage <= 1;
  document.getElementById("next-page").disabled = currentPage >= totalPages;
}

async function bootstrapFilters() {
  const payload = await getJson("/api/filters/bootstrap");
  appState.formStateId = payload.form_state_id || "";
  document.querySelectorAll("select[data-dynamic]").forEach((select) => {
    const key = select.getAttribute("name");
    fillSelect(select, payload.selects[key] || []);
  });
}

async function refreshDependent(parentField, parentValue) {
  if (!appState.formStateId) return;
  const payload = await getJson(`/api/filters/dependent?parent_field=${encodeURIComponent(parentField)}&parent_value=${encodeURIComponent(parentValue)}&form_state_id=${encodeURIComponent(appState.formStateId)}`);
  appState.formStateId = payload.form_state_id || appState.formStateId;
  Object.entries(payload.selects || {}).forEach(([key, options]) => {
    fillSelect(document.querySelector(`select[name='${key}']`), options);
  });
}

async function executeSearch(pageIndex = 1) {
  const form = document.getElementById("search-form");
  appState.currentFilters = collectFormPayload(form);
  const endpoint = pageIndex === 1 || !appState.previewId ? "/api/search/preview" : "/api/search/page";
  const body = pageIndex === 1 || !appState.previewId
    ? { filters: appState.currentFilters, page_index: 1 }
    : { preview_id: appState.previewId, page_index: pageIndex };
  const payload = await getJson(endpoint, { method: "POST", body: JSON.stringify(body) });
  appState.previewId = payload.preview_id || appState.previewId;
  document.getElementById("total-results").textContent = payload.total_results || 0;
  document.getElementById("total-pages").textContent = payload.total_pages || 0;
  updateSourceMode(payload.source_mode || "requests");
  renderResults(payload.results || []);
  renderPagination(payload.current_page || 1, payload.total_pages || 1);
}

async function createJob(payload) {
  await getJson("/api/jobs", { method: "POST", body: JSON.stringify(payload) });
  window.location.href = "/jobs";
}

function selectedItems() {
  const chosen = [];
  document.querySelectorAll(".result-selector:checked").forEach((checkbox) => {
    const index = Number(checkbox.dataset.index || -1);
    if (index >= 0 && appState.currentResults[index]) chosen.push(appState.currentResults[index]);
  });
  return chosen;
}

function bindSearch() {
  const form = document.getElementById("search-form");
  if (!form) return;
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    appState.previewId = "";
    await executeSearch(1);
  });
  form.querySelector("select[name='court_level']")?.addEventListener("change", (event) => refreshDependent("court_level", event.target.value));
  form.querySelector("select[name='case_style']")?.addEventListener("change", (event) => refreshDependent("case_style", event.target.value));
  form.addEventListener("reset", () => {
    setTimeout(() => {
      appState.previewId = "";
      appState.currentResults = [];
      renderResults([]);
      renderPagination(1, 1);
    }, 0);
  });

  document.getElementById("download-now")?.addEventListener("click", async () => {
    const filters = collectFormPayload(form);
    await createJob({ mode: "download_now", job_name: "Tải toàn bộ theo bộ lọc", filters, items: [] });
  });
  document.getElementById("download-selected")?.addEventListener("click", async () => {
    const items = selectedItems();
    if (!items.length) return;
    await createJob({ mode: "preview_then_download", job_name: "Tải các mục đã chọn", filters: {}, items });
  });
  document.getElementById("download-page")?.addEventListener("click", async () => {
    if (!appState.currentResults.length) return;
    await createJob({ mode: "preview_then_download", job_name: `Tải trang ${appState.currentPage}`, filters: {}, items: appState.currentResults });
  });
  document.getElementById("prev-page")?.addEventListener("click", async () => executeSearch(Math.max(1, appState.currentPage - 1)));
  document.getElementById("next-page")?.addEventListener("click", async () => executeSearch(Math.min(appState.totalPages, appState.currentPage + 1)));
  document.getElementById("jump-page")?.addEventListener("click", async () => {
    const page = Number(document.getElementById("page-input").value || 1);
    if (page >= 1 && page <= appState.totalPages) await executeSearch(page);
  });
}

async function loadJobs() {
  const container = document.getElementById("jobs-list");
  if (!container) return;
  const jobs = await getJson("/api/jobs");
  if (!jobs.length) {
    container.innerHTML = '<div class="empty-state">Chưa có đợt tải nào.</div>';
    return;
  }
  container.innerHTML = jobs.map((job) => `
    <article class="result-card">
      <header>
        <div>
          <div class="card-title">${job.job_name || `Đợt tải #${job.id}`}</div>
          <div class="muted">${job.created_at || ''}</div>
        </div>
        <span class="badge ${job.source_mode === 'playwright' ? 'badge-playwright' : 'badge-requests'}">${job.source_mode}</span>
      </header>
      <div class="meta-grid jobs-grid">
        <div><strong>Trạng thái:</strong> ${job.status}</div>
        <div><strong>Tiến độ:</strong> ${job.items_completed}/${job.items_total}</div>
        <div><strong>Lỗi:</strong> ${job.items_failed}</div>
        <div><strong>Trang đã xử lý:</strong> ${job.last_processed_page || 0}</div>
      </div>
      <div class="button-row tight">
        <button class="ghost" data-action="resume" data-id="${job.id}">Tiếp tục</button>
        <button class="ghost" data-action="pause" data-id="${job.id}">Tạm dừng</button>
        <button class="ghost" data-action="cancel" data-id="${job.id}">Hủy</button>
      </div>
    </article>
  `).join("");
  container.querySelectorAll("button[data-action]").forEach((button) => {
    button.addEventListener("click", async () => {
      await getJson(`/api/jobs/${button.dataset.id}/${button.dataset.action}`, { method: "POST" });
      await loadJobs();
    });
  });
}

async function loadDocuments() {
  const container = document.getElementById("documents-list");
  if (!container) return;
  const documents = await getJson("/api/documents");
  const render = (items) => {
    if (!items.length) {
      container.innerHTML = '<div class="empty-state">Chưa có tài liệu nào được tải.</div>';
      return;
    }
    container.innerHTML = items.map((document) => `
      <article class="result-card" data-search="${[document.document_number, document.court_name, document.document_type].join(' ').toLowerCase()}">
        <div class="card-title">${document.document_number || document.document_type || 'Tài liệu'}</div>
        <div class="meta-grid">
          <div><strong>Tòa án:</strong> ${document.court_name || ''}</div>
          <div><strong>Loại:</strong> ${document.document_type || ''}</div>
          <div><strong>Ngày ban hành:</strong> ${document.issued_date || ''}</div>
          <div><a href="/api/documents/${document.id}/download-file">Mở PDF</a></div>
        </div>
      </article>
    `).join("");
  };
  render(documents);
  document.getElementById("document-filter")?.addEventListener("input", (event) => {
    const query = String(event.target.value || "").toLowerCase();
    render(documents.filter((item) => [item.document_number, item.court_name, item.document_type].join(' ').toLowerCase().includes(query)));
  });
}

bootstrapFilters().catch(console.error).finally(bindSearch);
loadJobs().catch(console.error);
loadDocuments().catch(console.error);

