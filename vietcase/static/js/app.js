const appState = {
  formStateId: "",
  previewId: "",
  currentPage: 1,
  totalPages: 1,
  currentResults: [],
  currentFilters: {},
  searchInFlight: false,
  previewDirty: false,
};

const documentsState = {
  items: [],
  page: 1,
  pageSize: 10,
  total: 0,
  filterOptions: {},
  selectedIds: new Set(),
  filtersBound: false,
};

const jobsState = {
  items: [],
  actionsBound: false,
  selectedIds: new Set(),
};

let jobsPollTimer = null;
let jobsPollInFlight = false;
let confirmModalBound = false;
let confirmModalResolver = null;
let loadingModalBound = false;

async function requestJson(url, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (options.body && !headers["Content-Type"]) headers["Content-Type"] = "application/json";
  const response = await fetch(url, { ...options, headers });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `HTTP ${response.status}`);
  }
  return response.json();
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function hasDisplayValue(value) {
  return value !== null && value !== undefined && String(value).trim() !== "";
}

function formatDateForDisplay(value) {
  const text = String(value || "").trim();
  if (!text) return "";
  const iso = text.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (iso) return `${iso[3]}/${iso[2]}/${iso[1]}`;
  const dotted = text.match(/^(\d{2})\.(\d{2})\.(\d{4})$/);
  if (dotted) return `${dotted[1]}/${dotted[2]}/${dotted[3]}`;
  return text;
}

function formatDateDots(value) {
  const display = formatDateForDisplay(value);
  return display ? display.replaceAll("/", ".") : "";
}

function formatDateForSource(value) {
  const text = String(value || "").trim();
  if (!text) return "";
  const iso = text.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (iso) return `${iso[1]}-${iso[2]}-${iso[3]}`;
  const vn = text.match(/^(\d{1,2})[\/\-.](\d{1,2})[\/\-.](\d{4})$/);
  if (!vn) return text;
  return `${vn[3]}-${vn[2].padStart(2, "0")}-${vn[1].padStart(2, "0")}`;
}

function normalizeOption(item, fallbackLabel = "") {
  if (typeof item === "string") {
    return { value: item, label: item || fallbackLabel };
  }
  return {
    value: String(item?.value ?? ""),
    label: String(item?.label ?? item?.value ?? fallbackLabel),
  };
}

function fillSelect(select, options, value = "", placeholder = "-----chọn-----") {
  if (!select) return;
  const current = value || select.value || "";
  const normalized = [];
  let sawBlank = false;
  let placeholderLabel = placeholder;

  (options || []).forEach((item) => {
    const option = normalizeOption(item, placeholder);
    if (!option.value) {
      if (!sawBlank) {
        sawBlank = true;
        placeholderLabel = option.label && option.label.trim() ? option.label : placeholder;
      }
      return;
    }
    normalized.push(option);
  });

  select.innerHTML = "";
  const placeholderOption = document.createElement("option");
  placeholderOption.value = "";
  placeholderOption.textContent = placeholderLabel;
  select.appendChild(placeholderOption);

  normalized.forEach((item) => {
    const option = document.createElement("option");
    option.value = item.value;
    option.textContent = item.label;
    select.appendChild(option);
  });

  select.value = [...select.options].some((option) => option.value === current) ? current : "";
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
  badge.className = `badge ${mode === "playwright" ? "badge-playwright" : "badge-requests"}`;
}

function ensureLoadingModal() {
  if (loadingModalBound) return;
  loadingModalBound = true;
  const modal = document.getElementById("loading-modal");
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && appState.searchInFlight && modal) {
      event.preventDefault();
    }
  });
}

function setLoadingModal(visible, message = "Đang xử lý...") {
  ensureLoadingModal();
  const modal = document.getElementById("loading-modal");
  const messageNode = document.getElementById("loading-modal-message");
  if (!modal || !messageNode) return;
  messageNode.textContent = message;
  modal.classList.toggle("hidden", !visible);
  modal.setAttribute("aria-hidden", visible ? "false" : "true");
}

function syncSearchControls() {
  const form = document.getElementById("search-form");
  if (form) {
    form.querySelectorAll("input, select, button").forEach((node) => {
      if (!(node instanceof HTMLInputElement || node instanceof HTMLSelectElement || node instanceof HTMLButtonElement)) return;
      node.disabled = appState.searchInFlight;
    });
  }

  const downloadNow = document.getElementById("download-now");
  const downloadSelected = document.getElementById("download-selected");
  const downloadPage = document.getElementById("download-page");
  const prev = document.getElementById("prev-page");
  const next = document.getElementById("next-page");
  const jump = document.getElementById("jump-page");
  const pageInput = document.getElementById("page-input");
  const paginationLocked = appState.searchInFlight || appState.previewDirty || !appState.previewId;

  if (downloadNow) downloadNow.disabled = appState.searchInFlight;
  if (downloadSelected) downloadSelected.disabled = appState.searchInFlight || appState.previewDirty || !appState.currentResults.length;
  if (downloadPage) downloadPage.disabled = appState.searchInFlight || appState.previewDirty || !appState.currentResults.length;
  if (prev) prev.disabled = paginationLocked || appState.currentPage <= 1;
  if (next) next.disabled = paginationLocked || appState.currentPage >= appState.totalPages;
  if (jump) jump.disabled = paginationLocked || appState.totalPages <= 1;
  if (pageInput) pageInput.disabled = paginationLocked || appState.totalPages <= 1;
}

async function runSearchAction(message, task) {
  if (appState.searchInFlight) return null;
  appState.searchInFlight = true;
  setLoadingModal(true, message);
  syncSearchControls();
  try {
    return await task();
  } finally {
    appState.searchInFlight = false;
    setLoadingModal(false);
    syncSearchControls();
  }
}

function markPreviewDirty() {
  if (!appState.previewId) return;
  appState.previewDirty = true;
  syncSearchControls();
}

function buildSourceCardBody(item) {
  const lines = [];
  if (hasDisplayValue(item.legal_relation)) lines.push(`<div class="source-line"><strong>Quan hệ pháp luật:</strong> ${escapeHtml(item.legal_relation)}</div>`);

  const row1 = [];
  if (hasDisplayValue(item.adjudication_level)) row1.push(`<div class="source-col"><strong>Cấp xét xử:</strong> ${escapeHtml(item.adjudication_level)}</div>`);
  if (hasDisplayValue(item.precedent_applied)) row1.push(`<div class="source-col"><strong>Áp dụng án lệ:</strong> ${escapeHtml(item.precedent_applied)}</div>`);
  if (row1.length) lines.push(`<div class="source-row">${row1.join("")}</div>`);

  const row2 = [];
  if (hasDisplayValue(item.case_style)) row2.push(`<div class="source-col"><strong>Loại vụ/việc:</strong> ${escapeHtml(item.case_style)}</div>`);
  if (hasDisplayValue(item.correction_count)) row2.push(`<div class="source-col"><strong>Đính chính:</strong> ${escapeHtml(item.correction_count)}</div>`);
  if (row2.length) lines.push(`<div class="source-row">${row2.join("")}</div>`);

  if (hasDisplayValue(item.summary_text)) lines.push(`<div class="source-line"><strong>Thông tin về vụ/việc:</strong> ${escapeHtml(item.summary_text)}</div>`);
  if (hasDisplayValue(item.precedent_vote_count)) lines.push(`<div class="source-line"><strong>Tổng số lượt được bình chọn làm nguồn phát triển án lệ:</strong> ${escapeHtml(item.precedent_vote_count)}</div>`);
  return lines.join("");
}

function buildSearchResultCard(item, idx) {
  const title = item.title || item.document_number || item.document_type || `Hồ sơ ${idx + 1}`;
  const published = formatDateDots(item.published_date || item.published_date_display || "");
  return `
    <article class="result-card source-card">
      <header>
        <div>
          <div class="card-title">${escapeHtml(title)}</div>
          ${published ? `<div class="published-chip">(${escapeHtml(published)})</div>` : ""}
        </div>
        <label><input type="checkbox" class="result-selector" data-index="${idx}"> Chọn tải</label>
      </header>
      <div class="source-card-lines">${buildSourceCardBody(item)}</div>
    </article>
  `;
}

function renderResults(results) {
  const container = document.getElementById("results-list");
  if (!container) return;
  appState.currentResults = results || [];
  container.innerHTML = results.length
    ? results.map((item, idx) => buildSearchResultCard(item, idx)).join("")
    : '<div class="empty-state">Không có kết quả phù hợp.</div>';
  syncSearchControls();
}

function renderPagination(currentPage, totalPages) {
  const wrapper = document.getElementById("pagination");
  if (!wrapper) return;
  appState.currentPage = currentPage;
  appState.totalPages = totalPages;
  document.getElementById("current-page").textContent = String(currentPage);
  document.getElementById("page-count").textContent = String(totalPages);
  document.getElementById("page-input").value = String(currentPage);
  wrapper.classList.toggle("hidden", totalPages <= 1);
  syncSearchControls();
}

async function bootstrapFilters() {
  const payload = await runSearchAction("Đang tải bộ lọc...", () => requestJson("/api/filters/bootstrap"));
  if (!payload) return;
  appState.formStateId = payload.form_state_id || "";
  document.querySelectorAll("select[data-dynamic]").forEach((select) => {
    const key = select.getAttribute("name");
    fillSelect(select, payload.selects[key] || []);
  });
  syncSearchControls();
}

async function refreshDependent(parentField, parentValue) {
  if (!appState.formStateId) return;
  const payload = await runSearchAction(
    "Đang tải bộ lọc...",
    () => requestJson(`/api/filters/dependent?parent_field=${encodeURIComponent(parentField)}&parent_value=${encodeURIComponent(parentValue)}&form_state_id=${encodeURIComponent(appState.formStateId)}`),
  );
  if (!payload) return;
  appState.formStateId = payload.form_state_id || appState.formStateId;
  Object.entries(payload.selects || {}).forEach(([key, options]) => {
    fillSelect(document.querySelector(`select[name='${key}']`), options);
  });
}

async function executeSearch(pageIndex = 1) {
  const form = document.getElementById("search-form");
  if (pageIndex > 1 && (!appState.previewId || appState.previewDirty)) return;
  if (pageIndex === 1 || !appState.previewId) appState.currentFilters = collectFormPayload(form);
  const endpoint = pageIndex === 1 || !appState.previewId ? "/api/search/preview" : "/api/search/page";
  const body = pageIndex === 1 || !appState.previewId
    ? { filters: appState.currentFilters, page_index: 1 }
    : { preview_id: appState.previewId, page_index: pageIndex };
  const payload = await runSearchAction(
    pageIndex === 1 || !appState.previewId ? "Đang tìm kiếm..." : "Đang chuyển trang...",
    () => requestJson(endpoint, { method: "POST", body: JSON.stringify(body) }),
  );
  if (!payload) return;
  appState.previewId = payload.preview_id || appState.previewId;
  appState.previewDirty = false;
  document.getElementById("total-results").textContent = String(payload.total_results || 0);
  document.getElementById("total-pages").textContent = String(payload.total_pages || 0);
  updateSourceMode(payload.source_mode || "requests");
  renderResults(payload.results || []);
  renderPagination(payload.current_page || 1, payload.total_pages || 1);
}

function selectedItems() {
  return [...document.querySelectorAll(".result-selector:checked")]
    .map((node) => appState.currentResults[Number(node.dataset.index || -1)])
    .filter(Boolean);
}

async function createJob(payload) {
  await requestJson("/api/jobs", { method: "POST", body: JSON.stringify(payload) });
}

function initializeSearchPage() {
  const form = document.getElementById("search-form");
  if (!form) return;
  bootstrapFilters().catch(console.error);
  syncSearchControls();

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    appState.previewId = "";
    appState.previewDirty = false;
    await executeSearch(1);
  });
  form.querySelector("select[name='court_level']")?.addEventListener("change", (event) => {
    markPreviewDirty();
    refreshDependent("court_level", event.target.value).catch(console.error);
  });
  form.querySelector("select[name='case_style']")?.addEventListener("change", (event) => {
    markPreviewDirty();
    refreshDependent("case_style", event.target.value).catch(console.error);
  });
  form.querySelectorAll("input, select").forEach((field) => {
    const eventName = field.tagName === "SELECT" || field.getAttribute("type") === "checkbox" ? "change" : "input";
    field.addEventListener(eventName, () => {
      const name = field.getAttribute("name");
      if (name === "court_level" || name === "case_style") return;
      markPreviewDirty();
    });
  });
  form.addEventListener("reset", () => {
    setTimeout(() => {
      appState.previewId = "";
      appState.previewDirty = false;
      appState.currentResults = [];
      document.getElementById("total-results").textContent = "0";
      document.getElementById("total-pages").textContent = "0";
      renderResults([]);
      renderPagination(1, 1);
      syncSearchControls();
    }, 0);
  });

  document.getElementById("download-now")?.addEventListener("click", async () => {
    await createJob({ mode: "download_now", job_name: "Tải toàn bộ theo bộ lọc", filters: collectFormPayload(form), items: [] });
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

function pruneSelection(setRef, items) {
  const validIds = new Set(items.map((item) => Number(item.id)));
  [...setRef].forEach((id) => {
    if (!validIds.has(Number(id))) setRef.delete(Number(id));
  });
}

function ensureConfirmModal() {
  if (confirmModalBound) return;
  confirmModalBound = true;
  const modal = document.getElementById("confirm-modal");
  const submit = document.getElementById("confirm-modal-submit");
  const cancel = document.getElementById("confirm-modal-cancel");

  function closeModal(result) {
    modal.classList.add("hidden");
    modal.setAttribute("aria-hidden", "true");
    if (confirmModalResolver) {
      confirmModalResolver(result);
      confirmModalResolver = null;
    }
  }

  submit?.addEventListener("click", () => closeModal(true));
  cancel?.addEventListener("click", () => closeModal(false));
  modal?.querySelectorAll("[data-modal-close]")?.forEach((node) => node.addEventListener("click", () => closeModal(false)));
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !modal.classList.contains("hidden")) closeModal(false);
  });
}

function confirmAction({ title, message, confirmLabel = "Xác nhận", danger = true }) {
  ensureConfirmModal();
  const modal = document.getElementById("confirm-modal");
  const titleNode = document.getElementById("confirm-modal-title");
  const messageNode = document.getElementById("confirm-modal-message");
  const submit = document.getElementById("confirm-modal-submit");
  titleNode.textContent = title;
  messageNode.textContent = message;
  submit.textContent = confirmLabel;
  submit.classList.toggle("danger", danger);
  modal.classList.remove("hidden");
  modal.setAttribute("aria-hidden", "false");
  return new Promise((resolve) => {
    confirmModalResolver = resolve;
  });
}

function updateJobsSelectionNote() {
  const note = document.getElementById("jobs-selection-note");
  const button = document.getElementById("jobs-delete-selected");
  if (!note || !button) return;
  const count = jobsState.selectedIds.size;
  note.textContent = count ? `Đã chọn ${count} cụm tải.` : "Chưa chọn cụm tải nào.";
  button.disabled = count === 0;
}

async function deleteJobHistory(jobId) {
  const ok = await confirmAction({ title: "Xóa lịch sử tải", message: "Xóa cụm lịch sử tải này khỏi VietCase? Thao tác này không xóa các file PDF đã tải." });
  if (!ok) return;
  await requestJson(`/api/jobs/${jobId}`, { method: "DELETE" });
  jobsState.selectedIds.delete(Number(jobId));
  await loadJobs();
}

async function deleteSelectedJobs() {
  const ids = [...jobsState.selectedIds];
  if (!ids.length) return;
  const ok = await confirmAction({ title: "Xóa các cụm tải đã chọn", message: `Xóa ${ids.length} cụm lịch sử tải đã chọn? Thao tác này không xóa các file PDF đã tải.` });
  if (!ok) return;
  await requestJson("/api/jobs/delete-selected", { method: "POST", body: JSON.stringify({ ids }) });
  jobsState.selectedIds.clear();
  await loadJobs();
}

async function deleteAllJobs() {
  if (!jobsState.items.length) return;
  const ok = await confirmAction({ title: "Xóa toàn bộ lịch sử tải", message: "Xóa toàn bộ lịch sử tải? Thao tác này không xóa các file PDF đã tải." });
  if (!ok) return;
  await requestJson("/api/jobs/delete-all", { method: "POST" });
  jobsState.selectedIds.clear();
  await loadJobs();
}

function bindJobsActions() {
  if (jobsState.actionsBound) return;
  jobsState.actionsBound = true;
  document.getElementById("jobs-delete-selected")?.addEventListener("click", () => deleteSelectedJobs().catch(console.error));
  document.getElementById("jobs-delete-all")?.addEventListener("click", () => deleteAllJobs().catch(console.error));
}

function renderJobs(jobs) {
  const container = document.getElementById("jobs-list");
  if (!container) return;
  jobsState.items = jobs || [];
  pruneSelection(jobsState.selectedIds, jobsState.items);
  if (!jobs.length) {
    container.innerHTML = '<div class="empty-state">Chưa có đợt tải nào.</div>';
    updateJobsSelectionNote();
    return;
  }
  container.innerHTML = jobs.map((job) => {
    const jobId = Number(job.id);
    const checked = jobsState.selectedIds.has(jobId) ? "checked" : "";
    const status = String(job.status || "").toLowerCase();
    const canResume = Boolean(job.can_resume ?? ["paused", "interrupted"].includes(status));
    const canPause = Boolean(job.can_pause ?? ["queued", "running"].includes(status));
    const canCancel = Boolean(job.can_cancel ?? ["queued", "running", "paused", "interrupted"].includes(status));
    return `
      <article class="result-card job-card">
        <header>
          <div>
            <div class="card-title">${escapeHtml(job.job_name || `Đợt tải #${jobId}`)}</div>
            <div class="result-subtitle">Tạo lúc ${escapeHtml(job.created_at_display || job.created_at || "")}</div>
          </div>
          <div class="button-row tight align-start">
            <span class="badge ${job.source_mode === "playwright" ? "badge-playwright" : "badge-requests"}">${escapeHtml(job.source_mode || "requests")}</span>
            <label><input type="checkbox" class="job-selector" data-id="${jobId}" ${checked}> Chọn</label>
          </div>
        </header>
        <div class="meta-grid jobs-grid">
          <div><strong>Trạng thái:</strong> ${escapeHtml(job.status_display || job.status || "")}</div>
          <div><strong>Tiến độ:</strong> ${escapeHtml(`${job.items_completed || 0}/${job.items_total || 0}`)}</div>
          <div><strong>Lỗi:</strong> ${escapeHtml(job.items_failed || 0)}</div>
          <div><strong>Trang đã xử lý:</strong> ${escapeHtml(job.last_processed_page || 0)}</div>
        </div>
        <div class="button-row tight">
          ${canResume ? `<button class="ghost" data-job-action="resume" data-id="${jobId}">Tiếp tục</button>` : ""}
          ${canPause ? `<button class="ghost" data-job-action="pause" data-id="${jobId}">Tạm dừng</button>` : ""}
          ${canCancel ? `<button class="ghost" data-job-action="cancel" data-id="${jobId}">Hủy</button>` : ""}
          <button class="ghost" data-job-action="delete" data-id="${jobId}">Xóa</button>
        </div>
      </article>
    `;
  }).join("");

  container.querySelectorAll("button[data-job-action]").forEach((button) => {
    button.addEventListener("click", async () => {
      const action = button.dataset.jobAction;
      const jobId = Number(button.dataset.id || 0);
      if (!jobId) return;
      if (action === "delete") return deleteJobHistory(jobId);
      if (action === "cancel") {
        const ok = await confirmAction({ title: "Hủy đợt tải", message: "Hủy đợt tải đang chọn? Các file đã tải trước đó sẽ được giữ nguyên.", confirmLabel: "Hủy đợt tải" });
        if (!ok) return;
      }
      await requestJson(`/api/jobs/${jobId}/${action}`, { method: "POST" });
      await loadJobs();
    });
  });

  container.querySelectorAll(".job-selector").forEach((checkbox) => {
    checkbox.addEventListener("change", () => {
      const jobId = Number(checkbox.dataset.id || 0);
      if (!jobId) return;
      checkbox.checked ? jobsState.selectedIds.add(jobId) : jobsState.selectedIds.delete(jobId);
      updateJobsSelectionNote();
    });
  });
  updateJobsSelectionNote();
}

async function loadJobs() {
  const container = document.getElementById("jobs-list");
  if (!container) return;
  bindJobsActions();
  jobsPollInFlight = true;
  try {
    renderJobs(await requestJson("/api/jobs"));
  } finally {
    jobsPollInFlight = false;
  }
}

function startJobsPolling() {
  if (jobsPollTimer) return;
  jobsPollTimer = window.setInterval(() => {
    if (!jobsPollInFlight) loadJobs().catch(console.error);
  }, 2000);
}

function stopJobsPolling() {
  if (!jobsPollTimer) return;
  window.clearInterval(jobsPollTimer);
  jobsPollTimer = null;
}

function readDocumentFilters() {
  return {
    q: document.getElementById("documents-keyword")?.value?.trim() || "",
    document_type: document.getElementById("documents-document-type")?.value || "",
    court_name: document.getElementById("documents-court-name")?.value || "",
    case_style: document.getElementById("documents-case-style")?.value || "",
    legal_relation: document.getElementById("documents-legal-relation")?.value || "",
    date_from: formatDateForSource(document.getElementById("documents-date-from")?.value || ""),
    date_to: formatDateForSource(document.getElementById("documents-date-to")?.value || ""),
  };
}

function updateDocumentsSelectionNote() {
  const note = document.getElementById("documents-selection-note");
  const button = document.getElementById("documents-delete-selected");
  if (!note || !button) return;
  const count = documentsState.selectedIds.size;
  note.textContent = count ? `Đã chọn ${count} tài liệu.` : "Chưa chọn tài liệu nào.";
  button.disabled = count === 0;
}

function renderDocumentOptions(filterOptions) {
  documentsState.filterOptions = filterOptions || documentsState.filterOptions;
  const currentValues = readDocumentFilters();
  fillSelect(document.getElementById("documents-document-type"), documentsState.filterOptions.document_type || [], currentValues.document_type);
  fillSelect(document.getElementById("documents-court-name"), documentsState.filterOptions.court_name || [], currentValues.court_name);
  fillSelect(document.getElementById("documents-case-style"), documentsState.filterOptions.case_style || [], currentValues.case_style);
  fillSelect(document.getElementById("documents-legal-relation"), documentsState.filterOptions.legal_relation || [], currentValues.legal_relation);
}

function renderDocumentsPagination(totalItems) {
  const wrapper = document.getElementById("documents-pagination");
  if (!wrapper) return;
  const totalPages = Math.max(1, Math.ceil(totalItems / documentsState.pageSize));
  if (documentsState.page > totalPages) documentsState.page = totalPages;
  document.getElementById("documents-current-page").textContent = String(documentsState.page);
  document.getElementById("documents-page-count").textContent = String(totalPages);
  document.getElementById("documents-page-input").value = String(documentsState.page);
  document.getElementById("documents-prev-page").disabled = documentsState.page <= 1;
  document.getElementById("documents-next-page").disabled = documentsState.page >= totalPages;
  wrapper.classList.toggle("hidden", totalItems <= documentsState.pageSize);
}

async function deleteDocumentRecord(documentId) {
  const ok = await confirmAction({ title: "Xóa tài liệu đã tải", message: "Xóa file PDF đã chọn khỏi VietCase và khỏi thư mục downloads nếu file còn tồn tại?" });
  if (!ok) return;
  await requestJson(`/api/documents/${documentId}`, { method: "DELETE" });
  documentsState.selectedIds.delete(Number(documentId));
  await loadDocuments(documentsState.page);
}

async function deleteSelectedDocuments() {
  const ids = [...documentsState.selectedIds];
  if (!ids.length) return;
  const ok = await confirmAction({ title: "Xóa các tài liệu đã chọn", message: `Xóa ${ids.length} file PDF đã chọn khỏi VietCase và khỏi thư mục downloads nếu file còn tồn tại?` });
  if (!ok) return;
  await requestJson("/api/documents/delete-selected", { method: "POST", body: JSON.stringify({ ids }) });
  documentsState.selectedIds.clear();
  await loadDocuments(documentsState.page);
}

async function deleteAllDocuments() {
  if (!documentsState.total) return;
  const ok = await confirmAction({ title: "Xóa toàn bộ tài liệu đã tải", message: "Xóa toàn bộ file PDF đã tải khỏi VietCase và khỏi thư mục downloads nếu file còn tồn tại?" });
  if (!ok) return;
  await requestJson("/api/documents/delete-all", { method: "POST" });
  documentsState.selectedIds.clear();
  await loadDocuments(1);
}

function buildDocumentCard(item) {
  const title = item.display_title || item.title || "Tài liệu đã tải";
  const published = formatDateDots(item.published_date || item.published_date_display || "");
  const openAction = item.file_exists
    ? `<a href="/api/documents/${item.id}/open-file" target="_blank" rel="noopener noreferrer">Mở tài liệu</a>`
    : '<span class="muted">File không còn trên máy</span>';
  const checked = documentsState.selectedIds.has(Number(item.id)) ? "checked" : "";
  return `
    <article class="result-card source-card">
      <header>
        <div>
          <div class="card-title">${escapeHtml(title)}</div>
          ${published ? `<div class="published-chip">(${escapeHtml(published)})</div>` : ""}
        </div>
        <label><input type="checkbox" class="document-selector" data-id="${Number(item.id)}" ${checked}> Chọn</label>
      </header>
      <div class="source-card-lines">${buildSourceCardBody(item)}</div>
      <div class="button-row tight top-space">
        ${openAction}
        <button type="button" class="ghost" data-document-action="delete" data-id="${Number(item.id)}">Xóa</button>
      </div>
    </article>
  `;
}

function renderDocuments(items, total) {
  const container = document.getElementById("documents-list");
  const count = document.getElementById("documents-filter-count");
  if (!container) return;
  documentsState.items = items || [];
  documentsState.total = total || 0;
  pruneSelection(documentsState.selectedIds, documentsState.items);
  renderDocumentsPagination(total || 0);

  if (!items.length) {
    container.innerHTML = '<div class="empty-state">Không có tài liệu phù hợp với bộ lọc hiện tại.</div>';
    if (count) count.textContent = "Không có tài liệu phù hợp với bộ lọc hiện tại.";
    updateDocumentsSelectionNote();
    return;
  }

  const from = (documentsState.page - 1) * documentsState.pageSize + 1;
  const to = from + items.length - 1;
  if (count) count.textContent = `Đang hiển thị ${from}-${to} trên tổng ${total} tài liệu phù hợp.`;

  container.innerHTML = items.map((item) => buildDocumentCard(item)).join("");
  container.querySelectorAll(".document-selector").forEach((checkbox) => {
    checkbox.addEventListener("change", () => {
      const id = Number(checkbox.dataset.id || 0);
      if (!id) return;
      checkbox.checked ? documentsState.selectedIds.add(id) : documentsState.selectedIds.delete(id);
      updateDocumentsSelectionNote();
    });
  });
  container.querySelectorAll("button[data-document-action='delete']").forEach((button) => {
    button.addEventListener("click", async () => {
      const id = Number(button.dataset.id || 0);
      if (!id) return;
      await deleteDocumentRecord(id);
    });
  });
  updateDocumentsSelectionNote();
}

async function loadDocuments(page = 1) {
  const container = document.getElementById("documents-list");
  if (!container) return;
  documentsState.page = Math.max(1, Number(page || 1));
  const filters = readDocumentFilters();
  const params = new URLSearchParams({ page: String(documentsState.page), page_size: String(documentsState.pageSize) });
  Object.entries(filters).forEach(([key, value]) => {
    if (value) params.set(key, value);
  });
  const payload = await requestJson(`/api/documents?${params.toString()}`);
  renderDocumentOptions(payload.filter_options || {});
  renderDocuments(payload.items || [], Number(payload.total || 0));
}

function initializeDocumentsPage() {
  const form = document.getElementById("documents-filter-form");
  if (!form) return;
  document.getElementById("documents-delete-selected")?.addEventListener("click", () => deleteSelectedDocuments().catch(console.error));
  document.getElementById("documents-delete-all")?.addEventListener("click", () => deleteAllDocuments().catch(console.error));
  document.getElementById("documents-prev-page")?.addEventListener("click", () => loadDocuments(Math.max(1, documentsState.page - 1)).catch(console.error));
  document.getElementById("documents-next-page")?.addEventListener("click", () => {
    const totalPages = Math.max(1, Math.ceil(documentsState.total / documentsState.pageSize));
    loadDocuments(Math.min(totalPages, documentsState.page + 1)).catch(console.error);
  });
  document.getElementById("documents-jump-page")?.addEventListener("click", () => {
    const requested = Number(document.getElementById("documents-page-input")?.value || 1);
    if (requested >= 1) loadDocuments(requested).catch(console.error);
  });

  if (!documentsState.filtersBound) {
    documentsState.filtersBound = true;
    [
      document.getElementById("documents-keyword"),
      document.getElementById("documents-document-type"),
      document.getElementById("documents-court-name"),
      document.getElementById("documents-case-style"),
      document.getElementById("documents-legal-relation"),
      document.getElementById("documents-date-from"),
      document.getElementById("documents-date-to"),
    ].forEach((field) => {
      if (!field) return;
      const eventName = field.tagName === "SELECT" ? "change" : "input";
      field.addEventListener(eventName, () => loadDocuments(1).catch(console.error));
    });
    form.addEventListener("reset", () => setTimeout(() => {
      documentsState.selectedIds.clear();
      loadDocuments(1).catch(console.error);
    }, 0));
  }
  loadDocuments(1).catch(console.error);
}

document.addEventListener("DOMContentLoaded", () => {
  ensureConfirmModal();
  ensureLoadingModal();
  initializeSearchPage();
  if (document.getElementById("jobs-list")) {
    loadJobs().catch(console.error);
    startJobsPolling();
  } else {
    stopJobsPolling();
  }
  initializeDocumentsPage();
});
