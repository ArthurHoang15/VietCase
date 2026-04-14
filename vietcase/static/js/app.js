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

function fillSelect(select, options) {
  if (!select) return;
  select.innerHTML = "";
  const placeholder = document.createElement("option");
  placeholder.value = "";
  placeholder.textContent = "-----chọn-----";
  select.appendChild(placeholder);
  (options || []).forEach((item) => {
    const option = document.createElement("option");
    option.value = item.value || "";
    option.textContent = item.label || item.value || "";
    select.appendChild(option);
  });
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
    date_from: fd.get("date_from") || "",
    date_to: fd.get("date_to") || "",
    precedent_applied: fd.get("precedent_applied") === "on",
    precedent_voted: fd.get("precedent_voted") === "on",
  };
}

function renderResults(results) {
  const container = document.getElementById("results-list");
  if (!container) return;
  if (!results.length) {
    container.innerHTML = '<div class="empty-state">Không có kết quả phù hợp.</div>';
    return;
  }
  container.innerHTML = results.map((item, idx) => `
    <article class="result-card">
      <header>
        <div>
          <div class="card-title">${item.title || item.document_number || item.document_type || `Hồ sơ ${idx + 1}`}</div>
          <div class="muted">${item.source_url || ""}</div>
        </div>
        <label><input type="checkbox" class="result-selector" data-index="${idx}"> Chọn tải</label>
      </header>
      <div class="meta-grid">
        <div><strong>Loại:</strong> ${item.document_type || ""}</div>
        <div><strong>Số văn bản:</strong> ${item.document_number || ""}</div>
        <div><strong>Ngày ban hành:</strong> ${item.issued_date || ""}</div>
        <div><strong>Tòa án:</strong> ${item.court_name || ""}</div>
        <div><strong>Loại vụ việc:</strong> ${item.case_style || ""}</div>
        <div><strong>Quan hệ pháp luật:</strong> ${item.legal_relation || ""}</div>
      </div>
    </article>
  `).join("");
  container.dataset.results = JSON.stringify(results);
}

async function bootstrapFilters() {
  const payload = await getJson("/api/filters/bootstrap");
  document.querySelectorAll("select[data-dynamic]").forEach((select) => {
    const key = select.getAttribute("name");
    fillSelect(select, payload.selects[key] || payload.selects[`ctl00$Content$home$Public$ctl00$drp_${key}`] || []);
  });
}

async function createJob(payload) {
  await getJson("/api/jobs", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  window.location.href = "/jobs";
}

function selectedItems() {
  const container = document.getElementById("results-list");
  const results = JSON.parse(container?.dataset.results || "[]");
  const chosen = [];
  document.querySelectorAll(".result-selector:checked").forEach((checkbox) => {
    const index = Number(checkbox.dataset.index || -1);
    if (index >= 0 && results[index]) chosen.push(results[index]);
  });
  return chosen;
}

function bindSearch() {
  const form = document.getElementById("search-form");
  if (!form) return;
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const filters = collectFormPayload(form);
    const payload = await getJson("/api/search/preview", {
      method: "POST",
      body: JSON.stringify({ filters }),
    });
    document.getElementById("total-results").textContent = payload.total_results || 0;
    document.getElementById("total-pages").textContent = payload.total_pages || 0;
    document.getElementById("source-mode").textContent = payload.source_mode || "requests";
    renderResults(payload.results || []);
  });

  document.getElementById("download-now")?.addEventListener("click", async () => {
    const filters = collectFormPayload(form);
    await createJob({
      mode: "download_now",
      job_name: "Đợt tải từ giao diện",
      filters,
      items: [],
    });
  });

  document.getElementById("download-selected")?.addEventListener("click", async () => {
    const items = selectedItems();
    if (!items.length) return;
    await createJob({
      mode: "preview_then_download",
      job_name: "Tải các mục đã chọn",
      filters: {},
      items,
    });
  });

  document.getElementById("download-page")?.addEventListener("click", async () => {
    const container = document.getElementById("results-list");
    const items = JSON.parse(container?.dataset.results || "[]");
    if (!items.length) return;
    await createJob({
      mode: "preview_then_download",
      job_name: "Tải toàn bộ trang hiện tại",
      filters: {},
      items,
    });
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
      <div class="card-title">${job.job_name || `Đợt tải #${job.id}`}</div>
      <div class="meta-grid">
        <div><strong>Trạng thái:</strong> ${job.status}</div>
        <div><strong>Chế độ:</strong> ${job.source_mode}</div>
        <div><strong>Hoàn tất:</strong> ${job.items_completed}/${job.items_total}</div>
        <div><strong>Lỗi:</strong> ${job.items_failed}</div>
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
  if (!documents.length) {
    container.innerHTML = '<div class="empty-state">Chưa có tài liệu nào được tải.</div>';
    return;
  }
  container.innerHTML = documents.map((document) => `
    <article class="result-card">
      <div class="card-title">${document.document_number || document.document_type || 'Tài liệu'}</div>
      <div class="meta-grid">
        <div><strong>Tòa án:</strong> ${document.court_name || ''}</div>
        <div><strong>Loại:</strong> ${document.document_type || ''}</div>
        <div><strong>Trạng thái:</strong> ${document.download_status || ''}</div>
        <div><a href="/api/documents/${document.id}/download-file">Mở PDF</a></div>
      </div>
    </article>
  `).join("");
}

bootstrapFilters().catch(console.error).finally(bindSearch);
loadJobs().catch(console.error);
loadDocuments().catch(console.error);
