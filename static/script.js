const state = {
  pageJobId: null,
  pageCount: 0,
  loadedPages: 0,
  pageMode: "keep",
  selectedPages: new Set(),
  pageOrder: [],
  pageRotations: {},
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

  function moveFile(fromIndex, toIndex) {
    if (toIndex < 0 || toIndex >= files.length || fromIndex === toIndex) return;
    const [file] = files.splice(fromIndex, 1);
    files.splice(toIndex, 0, file);
    syncInput();
    render();
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
      const actions = document.createElement("span");
      const moveUp = document.createElement("button");
      const moveDown = document.createElement("button");
      const remove = document.createElement("button");

      position.textContent = String(index + 1);
      main.className = "file-main";
      name.className = "file-name";
      name.textContent = file.name;
      size.className = "file-size";
      size.textContent = formatFileSize(file.size);
      actions.className = "file-actions";
      moveUp.type = "button";
      moveUp.className = "move-file";
      moveUp.textContent = "↑";
      moveUp.title = `將 ${file.name} 上移`;
      moveUp.setAttribute("aria-label", `將 ${file.name} 上移`);
      moveUp.disabled = index === 0;
      moveDown.type = "button";
      moveDown.className = "move-file";
      moveDown.textContent = "↓";
      moveDown.title = `將 ${file.name} 下移`;
      moveDown.setAttribute("aria-label", `將 ${file.name} 下移`);
      moveDown.disabled = index === files.length - 1;
      remove.type = "button";
      remove.className = "remove-file";
      remove.title = `移除 ${file.name}`;
      remove.setAttribute("aria-label", `移除 ${file.name}`);
      remove.textContent = "×";

      main.append(name, size);
      actions.append(moveUp, moveDown, remove);
      item.append(position, main, actions);
      moveUp.addEventListener("click", () => moveFile(index, index - 1));
      moveDown.addEventListener("click", () => moveFile(index, index + 1));
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
  const passwords = {};
  try {
    while (true) {
      const response = await fetch(url, { method: "POST", body: formData });
      const payload = await response.json();
      if (response.status === 409 && payload.password_required) {
        formData.set('upload_id', payload.upload_id);
        formData.delete('files');
        formData.delete('file');
        for (const file of payload.password_required) {
          passwords[String(file.index)] = await askPdfPassword(file);
        }
        formData.set('passwords', JSON.stringify(passwords));
        continue;
      }
      if (!response.ok) throw new Error(payload.error || "上傳失敗");
      return payload;
    }
  } finally {
    formData.delete('passwords');
    formData.delete('new_password');
  }
}

function askPdfPassword(file) {
  const dialog = document.querySelector('#passwordDialog');
  const input = document.querySelector('#sourcePassword');
  document.querySelector('#passwordFile').textContent = file.filename;
  document.querySelector('#passwordHint').textContent = file.incorrect
    ? '密碼不正確，請重新輸入。' : '這份 PDF 已上鎖，請輸入開啟密碼。';
  input.value = '';
  dialog.showModal();
  input.focus();
  return new Promise((resolve, reject) => {
    dialog.addEventListener('close', () => {
      const password = input.value;
      input.value = '';
      if (dialog.returnValue === 'confirm') resolve(password);
      else reject(new Error('已取消 PDF 密碼輸入'));
    }, { once: true });
  });
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

const imageFormat = document.querySelector("#imageFormat");
const imageCompression = document.querySelector("#imageCompression");
const imageCompressionNumber = document.querySelector("#imageCompressionNumber");
const compressionOutput = document.querySelector("#compressionOutput");
const compressionControl = document.querySelector("#compressionControl");
const compressionHint = document.querySelector("#compressionHint");

function normalizeCompression(value) {
  const numeric = Number.parseInt(value, 10);
  return Math.min(100, Math.max(0, Number.isNaN(numeric) ? 0 : numeric));
}

function setCompression(value) {
  const normalized = normalizeCompression(value);
  imageCompression.value = String(normalized);
  imageCompressionNumber.value = String(normalized);
  compressionOutput.textContent = `${normalized}%`;
}

function syncCompressionAvailability() {
  const isPng = imageFormat.value === "png";
  if (isPng) setCompression(0);
  imageCompression.disabled = isPng;
  imageCompressionNumber.disabled = isPng;
  compressionControl.classList.toggle("is-disabled", isPng);
  compressionHint.textContent = isPng
    ? "PNG 固定為 0%，維持無損輸出"
    : "0% 為最高畫質，100% 為最低品質";
}

imageCompression.addEventListener("input", () => setCompression(imageCompression.value));
imageCompressionNumber.addEventListener("input", () => setCompression(imageCompressionNumber.value));
imageFormat.addEventListener("change", syncCompressionAvailability);
setCompression(0);
syncCompressionAvailability();

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
    state.pageOrder = Array.from({length: payload.page_count}, (_, index) => index + 1);
    state.pageRotations = {};
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
    const card = document.createElement("div");
    card.className = "page-card";
    card.dataset.page = String(page);
    card.draggable = true;
    card.innerHTML = `<button type="button" class="page-select" aria-pressed="false" aria-label="勾選原第 ${page} 頁"><div class="page-preview"><img draggable="false" src="/api/pages/${state.pageJobId}/thumbnail/${page}" alt="原第 ${page} 頁"></div><span>原第 ${page} 頁</span></button><div class="page-rotations"><button type="button" data-angle="-90" aria-label="原第 ${page} 頁向左旋轉 90 度">↶ 左轉 90°</button><button type="button" data-angle="90" aria-label="原第 ${page} 頁向右旋轉 90 度">↷ 右轉 90°</button></div>`;
    const select = card.querySelector('.page-select');
    select.addEventListener("click", () => {
      if (state.selectedPages.has(page)) state.selectedPages.delete(page);
      else state.selectedPages.add(page);
      card.classList.toggle("selected", state.selectedPages.has(page));
      select.setAttribute('aria-pressed', String(state.selectedPages.has(page)));
    });
    card.querySelectorAll('[data-angle]').forEach((button) => {
      button.addEventListener('click', () => {
        const angle = ((state.pageRotations[page] || 0) + Number(button.dataset.angle) + 360) % 360;
        state.pageRotations[page] = angle;
        const img = card.querySelector('img');
        img.style.transform = `rotate(${angle}deg)`;
        img.style.width = angle % 180 ? '75%' : '100%';
      });
    });
    card.addEventListener('dragstart', (event) => {
      event.dataTransfer.setData('text/plain', String(page));
      event.dataTransfer.effectAllowed = 'move';
      card.classList.add('dragging');
    });
    card.addEventListener('dragend', () => {
      card.classList.remove('dragging');
      grid.querySelectorAll('.drop-target').forEach((item) => item.classList.remove('drop-target'));
    });
    card.addEventListener('dragover', (event) => {
      event.preventDefault();
      event.dataTransfer.dropEffect = 'move';
      card.classList.add('drop-target');
    });
    card.addEventListener('dragleave', () => card.classList.remove('drop-target'));
    card.addEventListener('drop', (event) => {
      event.preventDefault();
      card.classList.remove('drop-target');
      const from = state.pageOrder.indexOf(Number(event.dataTransfer.getData('text/plain')));
      const to = state.pageOrder.indexOf(page);
      if (from < 0 || from === to) return;
      const [moved] = state.pageOrder.splice(from, 1);
      state.pageOrder.splice(to, 0, moved);
      const cards = new Map(Array.from(grid.children, (item) => [Number(item.dataset.page), item]));
      state.pageOrder.forEach((number) => { if (cards.has(number)) grid.appendChild(cards.get(number)); });
    });
    grid.appendChild(card);
  }
  state.loadedPages = nextEnd;
  document.querySelector("#loadMorePages").classList.toggle("hidden", state.loadedPages >= state.pageCount);
}

document.querySelector("#loadMorePages").addEventListener("click", loadMorePages);

document.querySelectorAll("#pageWorkspace .segmented button").forEach((button) => {
  button.addEventListener("click", () => {
    document.querySelectorAll(".segmented button").forEach((item) => item.classList.remove("active"));
    button.classList.add("active");
    state.pageMode = button.dataset.mode;
  });
});

const securityForm = document.querySelector('#securityForm');
const securityMode = document.querySelector('#securityMode');
const newPassword = document.querySelector('#newPassword');
function syncSecurityMode() {
  const locking = securityMode.value === 'lock';
  document.querySelector('#newPasswordControl').classList.toggle('hidden', !locking);
  newPassword.required = locking;
  newPassword.disabled = !locking;
  if (!locking) newPassword.value = '';
}
securityMode.addEventListener('change', syncSecurityMode);
syncSecurityMode();
createFileManager({ input: securityForm.querySelector('input[type=file]'),
  list: document.querySelector('#securityList'), count: document.querySelector('#securityCount'), sortable: false });
securityForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  const button = securityForm.querySelector('button[type=submit]');
  button.disabled = true;
  try {
    const data = new FormData(securityForm);
    newPassword.value = '';
    const payload = await postForm('/api/jobs/pdf-security', data);
    pollJob(payload.job_id);
  } catch (error) {
    progressLabel.textContent = error.message;
  } finally {
    button.disabled = false;
  }
});

document.querySelector("#processPages").addEventListener("click", async () => {
  try {
    if (!state.pageJobId) throw new Error("請先載入 PDF");
    const kept = state.pageOrder.filter((page) => state.selectedPages.size === 0 ||
      (state.pageMode === 'keep' ? state.selectedPages.has(page) : !state.selectedPages.has(page)));
    if (kept.length === 0) throw new Error('至少必須保留一頁');
    const changed = kept.length !== state.pageCount || kept.some((page, index) => page !== index + 1 || state.pageRotations[page]);
    if (!changed) throw new Error('請先調整頁面順序、旋轉或刪減頁面');
    hideDownload();
    setProgress(2, "正在建立頁面整理任務");
    const retention = document.querySelector("#pageRetention").value;
    const response = await fetch("/api/jobs/pages", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        source_job_id: state.pageJobId,
        selected_pages: Array.from(state.selectedPages),
        page_order: state.pageOrder,
        rotations: state.pageRotations,
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
