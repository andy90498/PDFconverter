const state = {
  pageJobId: null,
  pageCount: 0,
  loadedPages: 0,
  pageMode: "keep",
  selectedPages: new Set(),
};

const progressLabel = document.querySelector("#progressLabel");
const progressPercent = document.querySelector("#progressPercent");
const progressBar = document.querySelector("#progressBar");
const resultModal = document.querySelector("#resultModal");
const modalDownloadLink = document.querySelector("#modalDownloadLink");
const modalInfoImageLink = document.querySelector("#modalInfoImageLink");
const resultQrCode = document.querySelector("#resultQrCode");
const resultExpiry = document.querySelector("#resultExpiry");

function setProgress(progress, message) {
  const value = Math.max(0, Math.min(100, Number(progress) || 0));
  progressLabel.textContent = message || "處理中";
  progressPercent.textContent = `${value}%`;
  progressBar.style.width = `${value}%`;
}

function formatExpiry(isoValue) {
  if (!isoValue) return "有效下載時間：";
  const date = new Date(isoValue);
  const formatted = new Intl.DateTimeFormat("zh-TW", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(date);
  return `有效下載時間：${formatted}`;
}

function showDownload(payload) {
  modalDownloadLink.href = payload.download_url || `/download/${payload.token}`;
  modalDownloadLink.download = payload.filename || "";
  modalInfoImageLink.href = payload.info_image_url || `/download/${payload.token}/info-image`;
  resultQrCode.src = payload.qr_url || `/download/${payload.token}/qr`;
  resultExpiry.textContent = formatExpiry(payload.expires_at);
  resultModal.classList.remove("hidden");
  document.body.classList.add("modal-open");
}

function hideDownload() {
  resultModal.classList.add("hidden");
  document.body.classList.remove("modal-open");
  modalDownloadLink.removeAttribute("href");
  modalInfoImageLink.removeAttribute("href");
  resultQrCode.removeAttribute("src");
}

function formatFileSize(bytes) {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function filesToFileList(files) {
  const transfer = new DataTransfer();
  files.forEach((file) => transfer.items.add(file));
  return transfer.files;
}

function createFileManager({ input, list, count, sortable }) {
  let files = [];
  let draggedItem = null;

  function syncInput() {
    input.files = filesToFileList(files);
  }

  function updateCount() {
    if (!count) return;
    const totalSize = files.reduce((sum, file) => sum + file.size, 0);
    count.textContent = files.length
      ? `${files.length} 個檔案，${formatFileSize(totalSize)}`
      : "尚未選擇檔案";
  }

  function render() {
    list.innerHTML = "";
    list.classList.toggle("empty", files.length === 0);
    files.forEach((file, index) => {
      const item = document.createElement("li");
      item.draggable = sortable;
      item.dataset.index = String(index);
      const position = document.createElement("strong");
      const main = document.createElement("span");
      const name = document.createElement("span");
      const size = document.createElement("span");
      const remove = document.createElement("button");

      position.textContent = String(index + 1);
      main.className = "file-main";
      name.className = "file-name";
      name.textContent = file.name;
      size.className = "file-size";
      size.textContent = formatFileSize(file.size);
      remove.type = "button";
      remove.className = "remove-file";
      remove.title = `移除 ${file.name}`;
      remove.setAttribute("aria-label", `移除 ${file.name}`);
      remove.textContent = "×";

      main.append(name, size);
      item.append(position, main, remove);
      remove.addEventListener("click", () => {
        files.splice(index, 1);
        syncInput();
        render();
      });
      list.appendChild(item);
    });
    updateCount();
  }

  function addFiles(nextFiles) {
    const existing = new Set(files.map((file) => `${file.name}:${file.size}:${file.lastModified}`));
    Array.from(nextFiles).forEach((file) => {
      const key = `${file.name}:${file.size}:${file.lastModified}`;
      if (!existing.has(key)) {
        files.push(file);
        existing.add(key);
      }
    });
    syncInput();
    render();
  }

  input.addEventListener("change", () => addFiles(input.files));

  if (sortable) {
    list.addEventListener("dragstart", (event) => {
      draggedItem = event.target.closest("li");
      if (draggedItem) draggedItem.classList.add("dragging");
    });

    list.addEventListener("dragend", () => {
      if (draggedItem) draggedItem.classList.remove("dragging");
      const orderedIndexes = Array.from(list.querySelectorAll("li")).map((item) => Number(item.dataset.index));
      if (orderedIndexes.length === files.length) {
        files = orderedIndexes.map((index) => files[index]);
        syncInput();
        render();
      }
      draggedItem = null;
    });

    list.addEventListener("dragover", (event) => {
      event.preventDefault();
      const after = Array.from(list.querySelectorAll("li:not(.dragging)")).find((item) => {
        const box = item.getBoundingClientRect();
        return event.clientY < box.top + box.height / 2;
      });
      if (!draggedItem) return;
      if (after) list.insertBefore(draggedItem, after);
      else list.appendChild(draggedItem);
    });
  }

  render();
  return {
    getFiles: () => files.slice(),
  };
}

async function postForm(url, formData) {
  hideDownload();
  setProgress(2, "正在上傳");
  const response = await fetch(url, { method: "POST", body: formData });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || "上傳失敗");
  return payload;
}

function pollJob(jobId) {
  const timer = setInterval(async () => {
    try {
      const response = await fetch(`/api/status/${jobId}`);
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error || "查詢狀態失敗");
      setProgress(payload.progress, payload.message || payload.status);
      if (payload.status === "done") {
        clearInterval(timer);
        showDownload(payload);
      }
      if (payload.status === "failed") {
        clearInterval(timer);
        progressLabel.textContent = payload.message || "處理失敗";
      }
    } catch (error) {
      clearInterval(timer);
      progressLabel.textContent = error.message;
    }
  }, 1500);
}

document.querySelector("#closeResultModal").addEventListener("click", hideDownload);
resultModal.addEventListener("click", (event) => {
  if (event.target === resultModal) hideDownload();
});
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && !resultModal.classList.contains("hidden")) hideDownload();
});

document.querySelectorAll(".tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((item) => item.classList.remove("active"));
    document.querySelectorAll(".panel").forEach((item) => item.classList.remove("active"));
    tab.classList.add("active");
    document.querySelector(`#${tab.dataset.panel}`).classList.add("active");
  });
});

document.querySelectorAll(".drop-zone").forEach((zone) => {
  const input = zone.querySelector("input");
  zone.addEventListener("dragover", (event) => {
    event.preventDefault();
    zone.classList.add("dragover");
  });
  zone.addEventListener("dragleave", () => zone.classList.remove("dragover"));
  zone.addEventListener("drop", (event) => {
    event.preventDefault();
    zone.classList.remove("dragover");
    input.files = event.dataTransfer.files;
    input.dispatchEvent(new Event("change", { bubbles: true }));
  });
});

const pdfImagesInput = document.querySelector("#pdfImagesForm input[type=file]");
const pdfImagesManager = createFileManager({
  input: pdfImagesInput,
  list: document.querySelector("#pdfImagesList"),
  count: document.querySelector("#pdfImagesCount"),
  sortable: true,
});

document.querySelector("#pdfImagesForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    if (pdfImagesManager.getFiles().length === 0) throw new Error("請先選擇要轉檔的 PDF");
    const form = event.currentTarget;
    const formData = new FormData(form);
    formData.set("keep_annotations", form.keep_annotations.checked ? "true" : "false");
    const payload = await postForm("/api/jobs/pdf-to-images", formData);
    pollJob(payload.job_id);
  } catch (error) {
    progressLabel.textContent = error.message;
  }
});

const mergeInput = document.querySelector("#mergeForm input[type=file]");
const mergeManager = createFileManager({
  input: mergeInput,
  list: document.querySelector("#mergeList"),
  count: document.querySelector("#mergeCount"),
  sortable: true,
});

document.querySelector("#mergeForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    const files = mergeManager.getFiles();
    if (files.length === 0) throw new Error("請先選擇要合併的檔案");
    const form = event.currentTarget;
    const formData = new FormData(form);
    formData.set("order", JSON.stringify(files.map((_, index) => index)));
    const payload = await postForm("/api/jobs/merge", formData);
    pollJob(payload.job_id);
  } catch (error) {
    progressLabel.textContent = error.message;
  }
});

const pageFileInput = document.querySelector("#pageUploadForm input[type=file]");
const pageFileSummary = document.querySelector("#pageFileSummary");

pageFileInput.addEventListener("change", () => {
  const file = pageFileInput.files[0];
  pageFileSummary.classList.toggle("empty", !file);
  pageFileSummary.textContent = file ? `${file.name}，${formatFileSize(file.size)}` : "尚未選擇檔案";
});

document.querySelector("#pageUploadForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    if (!pageFileInput.files[0]) throw new Error("請先選擇要整理頁面的 PDF");
    const payload = await postForm("/api/pages/upload", new FormData(event.currentTarget));
    state.pageJobId = payload.job_id;
    state.pageCount = payload.page_count;
    state.loadedPages = 0;
    state.selectedPages.clear();
    document.querySelector("#pageGrid").innerHTML = "";
    document.querySelector("#pageWorkspace").classList.remove("hidden");
    setProgress(100, `已載入 ${payload.page_count} 頁`);
    loadMorePages();
  } catch (error) {
    progressLabel.textContent = error.message;
  }
});

function loadMorePages() {
  const grid = document.querySelector("#pageGrid");
  const nextEnd = Math.min(state.loadedPages + 24, state.pageCount);
  for (let page = state.loadedPages + 1; page <= nextEnd; page += 1) {
    const card = document.createElement("button");
    card.type = "button";
    card.className = "page-card";
    card.dataset.page = String(page);
    card.innerHTML = `<img src="/api/pages/${state.pageJobId}/thumbnail/${page}" alt="第 ${page} 頁"><span>第 ${page} 頁</span>`;
    card.addEventListener("click", () => {
      if (state.selectedPages.has(page)) state.selectedPages.delete(page);
      else state.selectedPages.add(page);
      card.classList.toggle("selected", state.selectedPages.has(page));
    });
    grid.appendChild(card);
  }
  state.loadedPages = nextEnd;
  document.querySelector("#loadMorePages").disabled = state.loadedPages >= state.pageCount;
}

document.querySelector("#loadMorePages").addEventListener("click", loadMorePages);

document.querySelectorAll(".segmented button").forEach((button) => {
  button.addEventListener("click", () => {
    document.querySelectorAll(".segmented button").forEach((item) => item.classList.remove("active"));
    button.classList.add("active");
    state.pageMode = button.dataset.mode;
  });
});

document.querySelector("#processPages").addEventListener("click", async () => {
  try {
    if (!state.pageJobId) throw new Error("請先載入 PDF");
    if (state.selectedPages.size === 0) throw new Error("請至少勾選一頁");
    hideDownload();
    setProgress(2, "正在建立頁面整理任務");
    const retention = document.querySelector("#pageRetention").value;
    const response = await fetch("/api/jobs/pages", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        source_job_id: state.pageJobId,
        selected_pages: Array.from(state.selectedPages),
        mode: state.pageMode,
        retention: retention,
      }),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || "建立任務失敗");
    pollJob(payload.job_id);
  } catch (error) {
    progressLabel.textContent = error.message;
  }
});
