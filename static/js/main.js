const activeCards = document.querySelectorAll(".card--active");

const ENDPOINTS = {
  image: "/api/convert/image",
  video: "/api/convert/video",
  audio: "/api/convert/audio",
  process: "/api/process/image",
  "video-to-gif": "/api/convert/gif-from-video",
  "gif-to-video": "/api/convert/video-from-gif",
  "pdf-to-images": "/api/document/pdf-to-images",
  "pdf-split": "/api/document/split-pdf",
  "pdf-extract-images": "/api/document/extract-images",
  "video-thumbnail": "/api/document/video-thumbnail",
  "pdf-compress": "/api/compress/pdf",
  "office-compress": "/api/compress/office",
  "universal-compress": "/api/compress/universal",
  "remove-bg": "/api/process/remove-background",
  subtitles: "/api/extract/subtitles",
};

const FFMPEG_REQUIRED_CATEGORIES = ["video", "audio", "video-to-gif", "gif-to-video", "video-thumbnail", "subtitles"];
const DEFAULT_AUDIO_BITRATE = "192k";
const DEFAULT_IMAGE_QUALITY = "85";
const DEFAULT_VIDEO_CODEC = "h264";
const DEFAULT_VIDEO_CRF = "23";
const DEFAULT_GIF_WIDTH = "480";
const DEFAULT_GIF_FPS = "10";
const DEFAULT_COMPRESSION_PRESET = "ebook";
const DEFAULT_TARGET_MB = "8";
const DEFAULT_PDF_DPI = "150";

const JOB_BADGE_LABELS = {
  waiting: "대기 중",
  processing: "처리 중",
  done: "완료",
  error: "실패",
  unsupported: "지원 안 됨",
};

function createJobRow(file, status = "processing") {
  const job = document.createElement("div");
  job.className = `job job--${status}`;
  job.innerHTML = `
    <div class="job__row">
      <span class="job__name">${file.name}</span>
      <span class="job__badge job__badge--${status}">${JOB_BADGE_LABELS[status]}</span>
      <button type="button" class="job__close" title="목록에서 지우기">✕</button>
    </div>
    <div class="job__progress"><div class="job__progress-fill"></div></div>
    <span class="job__error" hidden></span>
  `;
  job.querySelector(".job__close").addEventListener("click", () => job.remove());
  return job;
}

function setJobProgress(job, percent) {
  job.querySelector(".job__progress-fill").style.width = `${percent}%`;
}

function setJobProcessing(job) {
  job.className = "job job--processing";
  job.querySelector(".job__badge").className = "job__badge job__badge--processing";
  job.querySelector(".job__badge").textContent = JOB_BADGE_LABELS.processing;
}

// 원본의 상대 경로(폴더째 드롭한 경우)에서 디렉터리 부분만 뽑아, 변환된 파일명 앞에 그대로 붙인다.
// 이렇게 하면 압축할 때 원본 폴더 구조를 유지할 수 있다.
function buildZipPath(sourceRelativePath, downloadName) {
  const lastSlash = sourceRelativePath.lastIndexOf("/");
  const dir = lastSlash >= 0 ? sourceRelativePath.substring(0, lastSlash + 1) : "";
  return dir + downloadName;
}

// 같은 와이파이의 다른 기기가 내려받을 수 있도록, 결과 파일을 서버에 잠깐 올려두고 QR코드를 보여준다.
function createQrShareButton(getBlob, getFilename) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "job__qr-btn";
  button.textContent = "QR 공유";

  button.addEventListener("click", async () => {
    const existingPanel = button.parentElement.querySelector(".job__qr-panel");
    if (existingPanel) {
      existingPanel.remove();
      return;
    }

    button.disabled = true;
    button.textContent = "생성 중...";

    try {
      const formData = new FormData();
      const filename = getFilename();
      formData.append("file", getBlob(), filename);
      formData.append("filename", filename);

      const response = await fetch("/api/share", { method: "POST", body: formData });
      const data = await response.json();

      if (!response.ok) {
        alert(data.error || "공유 링크 생성에 실패했습니다.");
        return;
      }

      const panel = document.createElement("div");
      panel.className = "job__qr-panel";

      const qrImg = document.createElement("img");
      qrImg.className = "job__qr-image";
      qrImg.src = data.qr_data_uri;
      qrImg.alt = "QR 코드";

      const info = document.createElement("div");
      info.className = "job__qr-info";

      const linkEl = document.createElement("a");
      linkEl.className = "job__qr-link";
      linkEl.href = data.url;
      linkEl.target = "_blank";
      linkEl.rel = "noopener";
      linkEl.textContent = data.url;

      const expiryEl = document.createElement("span");
      expiryEl.className = "job__qr-expiry";
      expiryEl.textContent = `${data.expires_in_minutes}분 후 자동 만료 · 같은 와이파이에서만 접속 가능`;

      info.appendChild(linkEl);
      info.appendChild(expiryEl);
      panel.appendChild(qrImg);
      panel.appendChild(info);
      button.parentElement.appendChild(panel);
    } catch (error) {
      alert("공유 링크 생성 중 오류가 발생했습니다.");
    } finally {
      button.disabled = false;
      button.textContent = "QR 공유";
    }
  });

  return button;
}

function setJobDone(job, blob, downloadName, sourceRelativePath) {
  job.className = "job job--done";
  job.querySelector(".job__badge").className = "job__badge job__badge--done";
  job.querySelector(".job__badge").textContent = JOB_BADGE_LABELS.done;

  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.className = "job__download";
  link.href = url;
  link.download = downloadName;
  link.textContent = "다운로드";
  job.appendChild(link);

  const qrButton = createQrShareButton(
    () => job._downloadBlob,
    () => job._downloadPath.split("/").pop()
  );
  job.appendChild(qrButton);

  // "전체 다운로드"가 이 job을 zip에 담을 수 있도록 결과를 DOM 노드에 그대로 들고 있는다.
  job._downloadBlob = blob;
  job._downloadPath = buildZipPath(sourceRelativePath || "", downloadName);
}

function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes}B`;
  const units = ["KB", "MB", "GB"];
  let value = bytes;
  let unitIndex = -1;
  do {
    value /= 1024;
    unitIndex += 1;
  } while (value >= 1024 && unitIndex < units.length - 1);
  return `${value.toFixed(1)}${units[unitIndex]}`;
}

// 압축 계열 API가 응답 헤더로 원본/압축 후 용량을 실어 보내면, job 옆에 "이전 → 이후" 표시를 붙인다.
function appendSizeComparison(job, xhr) {
  const originalSizeHeader = xhr.getResponseHeader("X-Original-Size");
  const compressedSizeHeader = xhr.getResponseHeader("X-Compressed-Size");
  if (!originalSizeHeader || !compressedSizeHeader) return;

  const originalSize = parseInt(originalSizeHeader, 10);
  const compressedSize = parseInt(compressedSizeHeader, 10);
  const percent = Math.round((1 - compressedSize / originalSize) * 100);

  const meta = document.createElement("span");
  meta.className = "job__meta";
  meta.textContent = `${formatBytes(originalSize)} → ${formatBytes(compressedSize)} (${percent}% 감소)`;
  job.appendChild(meta);

  const targetAchievedHeader = xhr.getResponseHeader("X-Target-Achieved");
  if (targetAchievedHeader === "false") {
    const warning = document.createElement("span");
    warning.className = "job__meta job__meta--warning";
    warning.textContent = "목표 용량까지는 못 줄였어요 (더 줄이면 품질이 너무 나빠져서 최선의 결과를 담았어요)";
    job.appendChild(warning);
  }
}

// 원본 파일과 결과 blob으로 "원본 → 결과" 미리보기 썸네일을 나란히 붙인다 (누끼따기 결과 확인용).
function appendImageComparison(job, originalFile, resultBlob) {
  const wrapper = document.createElement("div");
  wrapper.className = "job__compare";

  const originalUrl = URL.createObjectURL(originalFile);
  const resultUrl = URL.createObjectURL(resultBlob);

  const originalItem = document.createElement("div");
  originalItem.className = "job__compare-item";
  originalItem.innerHTML = `<span class="job__compare-label">원본</span>`;
  const originalImg = document.createElement("img");
  originalImg.src = originalUrl;
  originalImg.alt = "원본 이미지";
  originalItem.appendChild(originalImg);

  const arrow = document.createElement("span");
  arrow.className = "job__compare-arrow";
  arrow.textContent = "→";

  const resultItem = document.createElement("div");
  resultItem.className = "job__compare-item job__compare-item--transparent";
  resultItem.innerHTML = `<span class="job__compare-label">결과</span>`;
  const resultImg = document.createElement("img");
  resultImg.src = resultUrl;
  resultImg.alt = "배경 제거 결과";
  resultItem.appendChild(resultImg);

  wrapper.appendChild(originalItem);
  wrapper.appendChild(arrow);
  wrapper.appendChild(resultItem);
  job.appendChild(wrapper);
}

const LANGUAGE_LABELS = { ko: "한국어", en: "영어" };

// 자막 추출 API가 응답 헤더로 감지된 언어를 실어 보내면 job 옆에 표시한다.
function appendDetectedLanguage(job, xhr) {
  const languageCode = xhr.getResponseHeader("X-Detected-Language");
  if (!languageCode) return;

  const meta = document.createElement("span");
  meta.className = "job__meta";
  meta.textContent = `감지된 언어: ${LANGUAGE_LABELS[languageCode] || languageCode}`;
  job.appendChild(meta);
}

function setJobError(job, message) {
  job.className = "job job--error";
  job.querySelector(".job__badge").className = "job__badge job__badge--error";
  job.querySelector(".job__badge").textContent = JOB_BADGE_LABELS.error;
  const errorEl = job.querySelector(".job__error");
  errorEl.textContent = message;
  errorEl.hidden = false;
}

// job 요소에 진행 상황을 표시하면서 파일 하나를 변환한다. 완료/실패 여부와 상관없이 resolve된다.
// item: { file, relativePath }. options.bitrate/maxDimension/quality/resolution/codec/crf는 카테고리별 옵션.
function convertJob(job, item, format, category = "image", options = {}) {
  return new Promise((resolve) => {
    setJobProcessing(job);

    const formData = new FormData();
    formData.append("file", item.file);
    formData.append("format", format);

    if (category === "audio") {
      formData.append("bitrate", options.bitrate || DEFAULT_AUDIO_BITRATE);
    } else if (category === "image") {
      formData.append("max_dimension", options.maxDimension || "original");
      formData.append("quality", options.quality || DEFAULT_IMAGE_QUALITY);
      formData.append("strip_metadata", options.stripMetadata === false ? "false" : "true");
    } else if (category === "video") {
      formData.append("resolution", options.resolution || "original");
      formData.append("codec", options.codec || DEFAULT_VIDEO_CODEC);
      formData.append("crf", options.crf || DEFAULT_VIDEO_CRF);
      formData.append("strip_metadata", options.stripMetadata === false ? "false" : "true");
    } else if (category === "process") {
      formData.append("width", options.width || "original");
      formData.append("quality", options.quality || DEFAULT_IMAGE_QUALITY);
      if (options.watermarkFile) {
        formData.append("watermark", options.watermarkFile);
      }
      formData.append("position", options.watermarkPosition || "bottom-right");
      formData.append("opacity", options.watermarkOpacity || "50");
      formData.append("strip_metadata", options.stripMetadata === false ? "false" : "true");
    } else if (category === "video-to-gif") {
      formData.append("start", options.start || "0");
      formData.append("duration", options.duration || "3");
      formData.append("width", options.width || DEFAULT_GIF_WIDTH);
      formData.append("fps", options.fps || DEFAULT_GIF_FPS);
    } else if (category === "pdf-to-images") {
      formData.append("dpi", options.dpi || DEFAULT_PDF_DPI);
    } else if (category === "video-thumbnail") {
      formData.append("timestamp", options.timestamp || "0");
    } else if (category === "pdf-compress" || category === "office-compress") {
      formData.append("preset", options.preset || DEFAULT_COMPRESSION_PRESET);
    } else if (category === "universal-compress") {
      formData.append("target_mb", options.targetMb || DEFAULT_TARGET_MB);
    }

    const xhr = new XMLHttpRequest();
    xhr.open("POST", ENDPOINTS[category] || ENDPOINTS.image);
    xhr.responseType = "blob";

    xhr.upload.addEventListener("progress", (event) => {
      if (event.lengthComputable) {
        // 업로드는 전체 작업의 절반으로 취급하고, 나머지 절반은 서버 처리 시간으로 남겨둔다.
        const uploadPercent = (event.loaded / event.total) * 50;
        setJobProgress(job, uploadPercent);
      }
    });

    xhr.addEventListener("load", () => {
      setJobProgress(job, 100);
      if (xhr.status >= 200 && xhr.status < 300) {
        const disposition = xhr.getResponseHeader("Content-Disposition") || "";
        const match = disposition.match(/filename="?([^"]+)"?/);
        const downloadName = match ? match[1] : `converted.${format}`;
        setJobDone(job, xhr.response, downloadName, item.relativePath);
        appendSizeComparison(job, xhr);
        if (category === "remove-bg") {
          appendImageComparison(job, item.file, xhr.response);
        }
        if (category === "subtitles") {
          appendDetectedLanguage(job, xhr);
        }
        refreshHistory();
        refreshStats();
        resolve();
      } else {
        const reader = new FileReader();
        reader.onload = () => {
          try {
            const payload = JSON.parse(reader.result);
            setJobError(job, payload.error || "변환에 실패했습니다.");
          } catch {
            setJobError(job, "변환에 실패했습니다.");
          }
          resolve();
        };
        reader.readAsText(xhr.response);
      }
    });

    xhr.addEventListener("error", () => {
      setJobProgress(job, 100);
      setJobError(job, "서버와 통신 중 오류가 발생했습니다.");
      resolve();
    });

    setJobProgress(job, 5);
    xhr.send(formData);
  });
}

// 카드 드롭존에서 쓰는 진입점: job을 새로 만들고 바로 변환을 시작한다.
function convertFile(jobsContainer, format, item, category = "image", options = {}) {
  const job = createJobRow(item.file, "processing");
  jobsContainer.prepend(job);
  return convertJob(job, item, format, category, options);
}

// 동시에 최대 limit개까지만 실행되도록 작업을 실행한다 (파일이 많을 때 속도를 높이되 서버 과부하는 막는다).
async function runWithConcurrencyLimit(taskFns, limit) {
  const executing = new Set();
  const results = [];

  for (const taskFn of taskFns) {
    const promise = taskFn().finally(() => executing.delete(promise));
    executing.add(promise);
    results.push(promise);

    if (executing.size >= limit) {
      await Promise.race(executing);
    }
  }

  return Promise.all(results);
}

// ---- 드래그앤드롭으로 폴더가 통째로 들어온 경우, 내부를 순회해서 상대 경로를 함께 뽑아낸다 ----

function readEntryAsFile(entry) {
  return new Promise((resolve, reject) => entry.file(resolve, reject));
}

function readAllDirectoryEntries(directoryEntry) {
  const reader = directoryEntry.createReader();
  const collected = [];

  return new Promise((resolve, reject) => {
    function readBatch() {
      reader.readEntries((batch) => {
        if (batch.length === 0) {
          resolve(collected);
          return;
        }
        collected.push(...batch);
        readBatch();
      }, reject);
    }
    readBatch();
  });
}

async function collectFilesFromEntry(entry, items) {
  if (entry.isFile) {
    const file = await readEntryAsFile(entry);
    items.push({ file, relativePath: entry.fullPath.replace(/^\//, "") });
  } else if (entry.isDirectory) {
    const children = await readAllDirectoryEntries(entry);
    for (const child of children) {
      await collectFilesFromEntry(child, items);
    }
  }
}

// dataTransfer에서 {file, relativePath} 목록을 뽑는다. 폴더를 놓았으면 내부까지 순회해 경로를 보존한다.
async function getItemsFromDataTransfer(dataTransfer) {
  const dtItems = dataTransfer.items;

  if (dtItems && dtItems.length > 0 && typeof dtItems[0].webkitGetAsEntry === "function") {
    const entries = Array.from(dtItems)
      .map((dtItem) => dtItem.webkitGetAsEntry())
      .filter(Boolean);

    if (entries.length > 0) {
      const items = [];
      for (const entry of entries) {
        await collectFilesFromEntry(entry, items);
      }
      return items;
    }
  }

  return Array.from(dataTransfer.files).map((file) => ({ file, relativePath: file.name }));
}

function getItemsFromFileList(fileList) {
  return Array.from(fileList).map((file) => ({ file, relativePath: file.webkitRelativePath || file.name }));
}

// ---- ZIP 압축: 외부 라이브러리 없이 STORE(무압축) 방식으로 직접 만든다 ----

const CRC_TABLE = (() => {
  const table = new Uint32Array(256);
  for (let n = 0; n < 256; n++) {
    let c = n;
    for (let k = 0; k < 8; k++) {
      c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    }
    table[n] = c >>> 0;
  }
  return table;
})();

function crc32(bytes) {
  let crc = 0xffffffff;
  for (let i = 0; i < bytes.length; i++) {
    crc = CRC_TABLE[(crc ^ bytes[i]) & 0xff] ^ (crc >>> 8);
  }
  return (crc ^ 0xffffffff) >>> 0;
}

function toDosDateTime(date) {
  const dosTime =
    ((date.getHours() & 0x1f) << 11) | ((date.getMinutes() & 0x3f) << 5) | (Math.floor(date.getSeconds() / 2) & 0x1f);
  const dosDate =
    (((date.getFullYear() - 1980) & 0x7f) << 9) | (((date.getMonth() + 1) & 0xf) << 5) | (date.getDate() & 0x1f);
  return { dosTime, dosDate };
}

// entries: [{ path, blob }] -> zip Blob. UTF-8 파일명 플래그(0x0800)를 켜서 한글 경로도 깨지지 않게 한다.
async function createZipBlob(entries) {
  const textEncoder = new TextEncoder();
  const { dosTime, dosDate } = toDosDateTime(new Date());

  const fileParts = [];
  const centralParts = [];
  let offset = 0;

  for (const entry of entries) {
    const nameBytes = textEncoder.encode(entry.path);
    const content = new Uint8Array(await entry.blob.arrayBuffer());
    const crc = crc32(content);
    const size = content.length;

    const localHeader = new DataView(new ArrayBuffer(30));
    localHeader.setUint32(0, 0x04034b50, true);
    localHeader.setUint16(4, 20, true);
    localHeader.setUint16(6, 0x0800, true);
    localHeader.setUint16(8, 0, true);
    localHeader.setUint16(10, dosTime, true);
    localHeader.setUint16(12, dosDate, true);
    localHeader.setUint32(14, crc, true);
    localHeader.setUint32(18, size, true);
    localHeader.setUint32(22, size, true);
    localHeader.setUint16(26, nameBytes.length, true);
    localHeader.setUint16(28, 0, true);

    fileParts.push(new Uint8Array(localHeader.buffer), nameBytes, content);

    const centralHeader = new DataView(new ArrayBuffer(46));
    centralHeader.setUint32(0, 0x02014b50, true);
    centralHeader.setUint16(4, 20, true);
    centralHeader.setUint16(6, 20, true);
    centralHeader.setUint16(8, 0x0800, true);
    centralHeader.setUint16(10, 0, true);
    centralHeader.setUint16(12, dosTime, true);
    centralHeader.setUint16(14, dosDate, true);
    centralHeader.setUint32(16, crc, true);
    centralHeader.setUint32(20, size, true);
    centralHeader.setUint32(24, size, true);
    centralHeader.setUint16(28, nameBytes.length, true);
    centralHeader.setUint16(30, 0, true);
    centralHeader.setUint16(32, 0, true);
    centralHeader.setUint16(34, 0, true);
    centralHeader.setUint16(36, 0, true);
    centralHeader.setUint32(38, 0, true);
    centralHeader.setUint32(42, offset, true);

    centralParts.push(new Uint8Array(centralHeader.buffer), nameBytes);

    offset += 30 + nameBytes.length + size;
  }

  const centralDirOffset = offset;
  const centralDirSize = centralParts.reduce((sum, part) => sum + part.length, 0);

  const endRecord = new DataView(new ArrayBuffer(22));
  endRecord.setUint32(0, 0x06054b50, true);
  endRecord.setUint16(4, 0, true);
  endRecord.setUint16(6, 0, true);
  endRecord.setUint16(8, entries.length, true);
  endRecord.setUint16(10, entries.length, true);
  endRecord.setUint32(12, centralDirSize, true);
  endRecord.setUint32(16, centralDirOffset, true);
  endRecord.setUint16(20, 0, true);

  return new Blob([...fileParts, ...centralParts, new Uint8Array(endRecord.buffer)], {
    type: "application/zip",
  });
}

// 같은 zip 경로가 여러 번 나오면 "이름 (1).ext", "이름 (2).ext" 식으로 안 겹치게 바꾼다.
function dedupeZipPaths(entries) {
  const usedPaths = new Set();

  return entries.map((entry) => {
    const dotIndex = entry.path.lastIndexOf(".");
    const withoutExt = dotIndex >= 0 ? entry.path.substring(0, dotIndex) : entry.path;
    const ext = dotIndex >= 0 ? entry.path.substring(dotIndex) : "";

    let finalPath = entry.path;
    let counter = 1;
    while (usedPaths.has(finalPath)) {
      finalPath = `${withoutExt} (${counter})${ext}`;
      counter += 1;
    }
    usedPaths.add(finalPath);

    return { ...entry, path: finalPath };
  });
}

function collectCompletedDownloads(jobsContainer) {
  return Array.from(jobsContainer.querySelectorAll(".job--done"))
    .filter((job) => job._downloadBlob)
    .map((job) => ({ path: job._downloadPath, blob: job._downloadBlob }));
}

async function downloadAllAsZip(jobsContainer, zipFileName, triggerButton) {
  const entries = dedupeZipPaths(collectCompletedDownloads(jobsContainer));

  if (entries.length === 0) {
    alert("아직 완료된 파일이 없습니다. 변환이 끝난 뒤 다시 눌러주세요.");
    return;
  }

  if (triggerButton) {
    triggerButton.disabled = true;
    triggerButton.textContent = "압축하는 중...";
  }

  try {
    const zipBlob = await createZipBlob(entries);
    const url = URL.createObjectURL(zipBlob);
    const link = document.createElement("a");
    link.href = url;
    link.download = zipFileName;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  } finally {
    if (triggerButton) {
      triggerButton.disabled = false;
      triggerButton.textContent = "전체 다운로드 (ZIP)";
    }
  }
}

// ---- FFmpeg 설치 상태 확인 및 자동 설치 ----

let ffmpegAvailable = null;
const ffmpegStatusPromise = fetch("/api/ffmpeg/status")
  .then((res) => res.json())
  .then((data) => {
    ffmpegAvailable = data.available;
    return ffmpegAvailable;
  })
  .catch(() => {
    ffmpegAvailable = false;
    return false;
  });

async function ensureFfmpegChecked() {
  if (ffmpegAvailable === null) {
    await ffmpegStatusPromise;
  }
  return ffmpegAvailable;
}

// container 안에 "FFmpeg 설치 필요" 안내와 설치 버튼을 그린다. 설치 성공 시 onReady를 호출한다.
function renderFfmpegPrompt(container, onReady) {
  container.innerHTML = "";

  const notice = document.createElement("div");
  notice.className = "smart-drop__warning";
  notice.textContent = "영상·오디오 변환에는 FFmpeg가 필요합니다. 자동으로 설치할까요? (인터넷 연결 필요, 몇 분 걸릴 수 있어요)";

  const installBtn = document.createElement("button");
  installBtn.type = "button";
  installBtn.className = "smart-drop__convert-all";
  installBtn.textContent = "FFmpeg 설치하기";

  installBtn.addEventListener("click", async () => {
    installBtn.disabled = true;
    installBtn.textContent = "설치 중... (몇 분 걸릴 수 있어요)";

    try {
      const response = await fetch("/api/ffmpeg/install", { method: "POST" });
      const data = await response.json();

      if (data.success) {
        ffmpegAvailable = true;
        onReady();
      } else {
        notice.textContent = `설치에 실패했습니다: ${data.message}`;
        installBtn.disabled = false;
        installBtn.textContent = "다시 시도";
      }
    } catch (error) {
      notice.textContent = "설치 중 서버와 통신하지 못했습니다.";
      installBtn.disabled = false;
      installBtn.textContent = "다시 시도";
    }
  });

  container.appendChild(notice);
  container.appendChild(installBtn);
}

activeCards.forEach((card) => {
  // 이미지->PDF 묶기 카드는 여러 파일을 모았다가 한 번에 보내는 별도 로직으로 처리한다 (아래 참고).
  if (card.id === "imagesToPdfCard") return;
  // PDF 병합 카드도 여러 파일을 모았다가 순서대로 한 번에 보내는 별도 로직으로 처리한다 (아래 참고).
  if (card.id === "pdfMergeCard") return;
  // 유튜브 음원 추출 카드는 파일 드롭이 아니라 링크 입력 + 버튼으로 동작하는 별도 로직이다 (아래 참고).
  if (card.id === "youtubeAudioCard") return;
  // 핫폴더 카드는 파일 드롭이 아니라 폴더 경로 입력 + 감시 시작/중지 버튼으로 동작하는 별도 로직이다 (아래 참고).
  if (card.id === "hotfolderCard") return;

  const input = card.querySelector(".card__input");
  const format = card.dataset.format;
  const category = card.dataset.category || "image";
  const jobsContainer = card.querySelector(".card__jobs");
  const downloadAllBtn = card.querySelector(".card__download-all");

  const bitrateSelect = card.querySelector(".card__bitrate");
  const sizeSelect = card.querySelector(".card__size");
  const qualitySelect = card.querySelector(".card__quality");
  const resolutionSelect = card.querySelector(".card__resolution");
  const codecSelect = card.querySelector(".card__codec");
  const crfSelect = card.querySelector(".card__crf");
  const widthSelect = card.querySelector(".card__width");
  const watermarkInput = card.querySelector(".card__watermark");
  const watermarkPositionSelect = card.querySelector(".card__watermark-position");
  const watermarkOpacitySelect = card.querySelector(".card__watermark-opacity");
  const gifStartInput = card.querySelector(".card__gif-start");
  const gifDurationInput = card.querySelector(".card__gif-duration");
  const gifWidthSelect = card.querySelector(".card__gif-width");
  const gifFpsSelect = card.querySelector(".card__gif-fps");
  const pdfDpiSelect = card.querySelector(".card__pdf-dpi");
  const thumbTimestampInput = card.querySelector(".card__thumb-timestamp");
  const compressPresetSelect = card.querySelector(".card__compress-preset");
  const targetMbInput = card.querySelector(".card__target-mb");
  const stripMetadataCheckbox = card.querySelector(".card__strip-metadata");
  const presetSelect = card.querySelector(".card__preset-select");
  const presetSaveBtn = card.querySelector(".card__preset-save");
  const presetKey = `${category}:${format}`;

  if (card.dataset.accept) {
    input.accept = card.dataset.accept;
  }

  if (downloadAllBtn) {
    downloadAllBtn.addEventListener("click", () => {
      downloadAllAsZip(jobsContainer, `${format}_변환결과.zip`, downloadAllBtn);
    });
  }

  function collectOptions() {
    if (category === "audio") {
      return { bitrate: bitrateSelect ? bitrateSelect.value : DEFAULT_AUDIO_BITRATE };
    }
    if (category === "video") {
      return {
        resolution: resolutionSelect ? resolutionSelect.value : "original",
        codec: codecSelect ? codecSelect.value : DEFAULT_VIDEO_CODEC,
        crf: crfSelect ? crfSelect.value : DEFAULT_VIDEO_CRF,
        stripMetadata: stripMetadataCheckbox ? stripMetadataCheckbox.checked : true,
      };
    }
    if (category === "process") {
      return {
        width: widthSelect ? widthSelect.value : "original",
        quality: qualitySelect ? qualitySelect.value : DEFAULT_IMAGE_QUALITY,
        watermarkFile: watermarkInput && watermarkInput.files[0] ? watermarkInput.files[0] : null,
        watermarkPosition: watermarkPositionSelect ? watermarkPositionSelect.value : "bottom-right",
        watermarkOpacity: watermarkOpacitySelect ? watermarkOpacitySelect.value : "50",
        stripMetadata: stripMetadataCheckbox ? stripMetadataCheckbox.checked : true,
      };
    }
    if (category === "video-to-gif") {
      return {
        start: gifStartInput ? gifStartInput.value : "0",
        duration: gifDurationInput ? gifDurationInput.value : "3",
        width: gifWidthSelect ? gifWidthSelect.value : DEFAULT_GIF_WIDTH,
        fps: gifFpsSelect ? gifFpsSelect.value : DEFAULT_GIF_FPS,
      };
    }
    if (category === "pdf-to-images") {
      return { dpi: pdfDpiSelect ? pdfDpiSelect.value : DEFAULT_PDF_DPI };
    }
    if (category === "video-thumbnail") {
      return { timestamp: thumbTimestampInput ? thumbTimestampInput.value : "0" };
    }
    if (category === "pdf-compress" || category === "office-compress") {
      return { preset: compressPresetSelect ? compressPresetSelect.value : DEFAULT_COMPRESSION_PRESET };
    }
    if (category === "universal-compress") {
      return { targetMb: targetMbInput ? targetMbInput.value : DEFAULT_TARGET_MB };
    }
    return {
      maxDimension: sizeSelect ? sizeSelect.value : "original",
      quality: qualitySelect ? qualitySelect.value : DEFAULT_IMAGE_QUALITY,
      stripMetadata: stripMetadataCheckbox ? stripMetadataCheckbox.checked : true,
    };
  }

  // 프리셋으로 저장할 때는 워터마크 파일(File 객체)처럼 JSON으로 옮길 수 없는 값은 뺀다.
  function getSerializableOptions() {
    const { watermarkFile, ...rest } = collectOptions();
    return rest;
  }

  // 저장된 프리셋 값을 이 카드에 있는 선택지들에 그대로 되돌려놓는다.
  function applyPresetOptions(saved) {
    if (!saved) return;
    if (bitrateSelect && saved.bitrate !== undefined) bitrateSelect.value = saved.bitrate;
    if (sizeSelect && saved.maxDimension !== undefined) sizeSelect.value = saved.maxDimension;
    if (qualitySelect && saved.quality !== undefined) qualitySelect.value = saved.quality;
    if (resolutionSelect && saved.resolution !== undefined) resolutionSelect.value = saved.resolution;
    if (codecSelect && saved.codec !== undefined) codecSelect.value = saved.codec;
    if (crfSelect && saved.crf !== undefined) crfSelect.value = saved.crf;
    if (widthSelect && saved.width !== undefined) widthSelect.value = saved.width;
    if (watermarkPositionSelect && saved.watermarkPosition !== undefined) {
      watermarkPositionSelect.value = saved.watermarkPosition;
    }
    if (watermarkOpacitySelect && saved.watermarkOpacity !== undefined) {
      watermarkOpacitySelect.value = saved.watermarkOpacity;
    }
    if (gifStartInput && saved.start !== undefined) gifStartInput.value = saved.start;
    if (gifDurationInput && saved.duration !== undefined) gifDurationInput.value = saved.duration;
    if (gifWidthSelect && saved.width !== undefined) gifWidthSelect.value = saved.width;
    if (gifFpsSelect && saved.fps !== undefined) gifFpsSelect.value = saved.fps;
    if (pdfDpiSelect && saved.dpi !== undefined) pdfDpiSelect.value = saved.dpi;
    if (thumbTimestampInput && saved.timestamp !== undefined) thumbTimestampInput.value = saved.timestamp;
    if (compressPresetSelect && saved.preset !== undefined) compressPresetSelect.value = saved.preset;
    if (stripMetadataCheckbox && saved.stripMetadata !== undefined) stripMetadataCheckbox.checked = saved.stripMetadata;
  }

  async function loadPresetOptions() {
    if (!presetSelect) return;
    try {
      const response = await fetch(`/api/presets?key=${encodeURIComponent(presetKey)}`);
      const data = await response.json();
      presetSelect.innerHTML = '<option value="">프리셋 불러오기</option>';
      (data.presets || []).forEach((preset) => {
        const option = document.createElement("option");
        option.value = String(preset.id);
        option.textContent = preset.name;
        option.dataset.options = JSON.stringify(preset.options);
        presetSelect.appendChild(option);
      });
    } catch (error) {
      // 프리셋 목록을 못 불러와도 변환 기능 자체에는 영향이 없다.
    }
  }

  if (presetSelect) {
    presetSelect.addEventListener("change", () => {
      const selected = presetSelect.selectedOptions[0];
      if (selected && selected.dataset.options) {
        applyPresetOptions(JSON.parse(selected.dataset.options));
      }
    });
    loadPresetOptions();
  }

  if (presetSaveBtn) {
    presetSaveBtn.addEventListener("click", async () => {
      const name = window.prompt("프리셋 이름을 입력하세요 (예: 유튜브 썸네일 1280 JPG)");
      if (!name) return;

      try {
        await fetch("/api/presets", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ key: presetKey, name, options: getSerializableOptions() }),
        });
        loadPresetOptions();
      } catch (error) {
        alert("프리셋 저장에 실패했습니다.");
      }
    });
  }

  async function handleItems(items) {
    if (FFMPEG_REQUIRED_CATEGORIES.includes(category) && !(await ensureFfmpegChecked())) {
      renderFfmpegPrompt(jobsContainer, () => handleItems(items));
      return;
    }
    const options = collectOptions();
    items.forEach((item) => convertFile(jobsContainer, format, item, category, options));
  }

  input.addEventListener("change", () => {
    handleItems(getItemsFromFileList(input.files));
    input.value = "";
  });

  ["dragenter", "dragover"].forEach((eventName) => {
    card.addEventListener(eventName, (event) => {
      event.preventDefault();
      event.stopPropagation();
      card.classList.add("card--dragover");
    });
  });

  ["dragleave", "drop"].forEach((eventName) => {
    card.addEventListener(eventName, (event) => {
      event.preventDefault();
      event.stopPropagation();
      card.classList.remove("card--dragover");
    });
  });

  card.addEventListener("drop", async (event) => {
    const items = await getItemsFromDataTransfer(event.dataTransfer);
    handleItems(items);
  });
});

document.querySelectorAll(".card--soon").forEach((card) => {
  card.addEventListener("click", () => {
    alert("이 기능은 아직 준비 중입니다. 곧 추가될 예정이에요.");
  });
});

// ---- 스마트 업로드: 파일 종류를 자동 인식하고, 여러 파일을 한 번에 변환한다 ----

const BATCH_CONCURRENCY = 4;

const CATEGORY_LABELS = {
  image: "이미지",
  document: "문서(PDF)",
  video: "영상",
  audio: "오디오",
  unknown: "알 수 없는 형식",
};

const FORMAT_LABELS = {
  jpg: "JPG",
  png: "PNG",
  webp: "WEBP",
  bmp: "BMP",
  gif: "GIF",
  tiff: "TIFF",
  mp4: "MP4",
  mov: "MOV",
  mp3: "MP3",
  wav: "WAV",
  m4a: "M4A",
};

const smartDropZone = document.getElementById("smartDropZone");
const smartDropInput = document.getElementById("smartDropInput");
const smartDropResult = document.getElementById("smartDropResult");

async function detectFile(file) {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch("/api/detect", { method: "POST", body: formData });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.error || "파일을 분석하지 못했습니다.");
  }
  return response.json();
}

function describeDetection(detection) {
  if (!detection.supported) {
    const categoryLabel = CATEGORY_LABELS[detection.category] || "알 수 없는 형식";
    return detection.category === "unknown" ? "알 수 없는 형식" : `${categoryLabel} · 지원 안 됨`;
  }
  const detectedLabel = FORMAT_LABELS[detection.detected_format] || detection.detected_format.toUpperCase();
  const categoryLabel = CATEGORY_LABELS[detection.category] || "";
  return detection.extension_mismatch
    ? `${detectedLabel} ${categoryLabel} (확장자 다름)`
    : `${detectedLabel} ${categoryLabel}`;
}

// 지원되는 파일들의 recommended_formats 교집합을 구한다 (카테고리가 섞여 있으면 자연히 빈 목록이 된다).
function commonRecommendedFormats(entries) {
  const supportedEntries = entries.filter((entry) => entry.detection.supported);
  if (supportedEntries.length === 0) return [];

  const [first, ...rest] = supportedEntries;
  return first.detection.recommended_formats.filter((format) =>
    rest.every((entry) => entry.detection.recommended_formats.includes(format))
  );
}

function renderBatchUI(entries) {
  smartDropResult.hidden = false;
  smartDropResult.innerHTML = "";

  const supportedEntries = entries.filter((entry) => entry.detection.supported);
  const batchCategory = supportedEntries[0]?.detection.category || "image";

  const header = document.createElement("div");
  header.className = "smart-drop__result-header";
  header.textContent = `파일 ${entries.length}개 중 ${supportedEntries.length}개 변환 가능`;
  smartDropResult.appendChild(header);

  const formats = commonRecommendedFormats(entries);
  const controls = document.createElement("div");
  controls.className = "smart-drop__batch-controls";
  const ffmpegPromptBox = document.createElement("div");

  const jobsList = document.createElement("div");
  jobsList.className = "card__jobs";

  if (supportedEntries.length === 0) {
    const desc = document.createElement("div");
    desc.className = "smart-drop__warning";
    desc.textContent = "변환 가능한 파일이 없습니다. PDF는 아직 준비 중이에요.";
    smartDropResult.appendChild(desc);
  } else if (formats.length === 0) {
    const desc = document.createElement("div");
    desc.className = "smart-drop__warning";
    desc.textContent = "선택한 파일들에 공통으로 적용할 수 있는 목표 포맷이 없습니다.";
    smartDropResult.appendChild(desc);
  } else {
    const select = document.createElement("select");
    select.className = "smart-drop__format-select";
    formats.forEach((format) => {
      const option = document.createElement("option");
      option.value = format;
      option.textContent = `${FORMAT_LABELS[format] || format.toUpperCase()}로 변환`;
      select.appendChild(option);
    });

    const convertAllBtn = document.createElement("button");
    convertAllBtn.type = "button";
    convertAllBtn.className = "smart-drop__convert-all";
    convertAllBtn.textContent = "모두 변환";

    const downloadAllBtn = document.createElement("button");
    downloadAllBtn.type = "button";
    downloadAllBtn.className = "smart-drop__convert-all";
    downloadAllBtn.textContent = "전체 다운로드 (ZIP)";
    downloadAllBtn.addEventListener("click", () => {
      downloadAllAsZip(jobsList, "변환결과.zip", downloadAllBtn);
    });

    async function startBatchConvert() {
      convertAllBtn.disabled = true;

      if (FFMPEG_REQUIRED_CATEGORIES.includes(batchCategory) && !(await ensureFfmpegChecked())) {
        renderFfmpegPrompt(ffmpegPromptBox, () => {
          ffmpegPromptBox.innerHTML = "";
          startBatchConvert();
        });
        convertAllBtn.disabled = false;
        return;
      }

      ffmpegPromptBox.innerHTML = "";
      const chosenFormat = select.value;
      const options = batchCategory === "audio" ? { bitrate: DEFAULT_AUDIO_BITRATE } : {};
      const tasks = supportedEntries.map(
        (entry) => () => convertJob(entry.job, entry.item, chosenFormat, entry.detection.category, options)
      );
      runWithConcurrencyLimit(tasks, BATCH_CONCURRENCY).finally(() => {
        convertAllBtn.disabled = false;
      });
    }

    convertAllBtn.addEventListener("click", startBatchConvert);

    controls.appendChild(select);
    controls.appendChild(convertAllBtn);
    controls.appendChild(downloadAllBtn);
    smartDropResult.appendChild(controls);
    smartDropResult.appendChild(ffmpegPromptBox);
  }

  entries.forEach((entry) => {
    const status = entry.detection.supported ? "waiting" : "unsupported";
    const job = createJobRow(entry.item.file, status);
    if (!entry.detection.supported) {
      job.querySelector(".job__progress").hidden = true;
      const errorEl = job.querySelector(".job__error");
      errorEl.textContent = describeDetection(entry.detection);
      errorEl.hidden = false;
    } else {
      const typeNote = document.createElement("span");
      typeNote.className = "job__type";
      typeNote.textContent = describeDetection(entry.detection);
      job.insertBefore(typeNote, job.querySelector(".job__progress"));
    }
    entry.job = job;
    jobsList.appendChild(job);
  });

  smartDropResult.appendChild(jobsList);
}

async function handleSmartDropItems(items) {
  smartDropResult.hidden = false;
  smartDropResult.innerHTML = `<div class="smart-drop__result-desc">파일 ${items.length}개 분석 중...</div>`;

  try {
    const entries = await Promise.all(
      items.map(async (item) => ({ item, detection: await detectFile(item.file) }))
    );
    renderBatchUI(entries);
  } catch (error) {
    smartDropResult.innerHTML = `<div class="smart-drop__warning">${error.message}</div>`;
  }
}

smartDropInput.addEventListener("change", () => {
  if (smartDropInput.files.length > 0) {
    handleSmartDropItems(getItemsFromFileList(smartDropInput.files));
    smartDropInput.value = "";
  }
});

["dragenter", "dragover"].forEach((eventName) => {
  smartDropZone.addEventListener(eventName, (event) => {
    event.preventDefault();
    event.stopPropagation();
    smartDropZone.classList.add("smart-drop__zone--dragover");
  });
});

["dragleave", "drop"].forEach((eventName) => {
  smartDropZone.addEventListener(eventName, (event) => {
    event.preventDefault();
    event.stopPropagation();
    smartDropZone.classList.remove("smart-drop__zone--dragover");
  });
});

smartDropZone.addEventListener("drop", async (event) => {
  const items = await getItemsFromDataTransfer(event.dataTransfer);
  if (items.length > 0) {
    handleSmartDropItems(items);
  }
});

// ---- 변환 히스토리: DB에 남은 기록을 불러와 화면 아래에 표시한다 ----

const historyBody = document.getElementById("historyBody");

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

function formatHistoryTime(isoString) {
  return isoString.replace("T", " ").slice(0, 16);
}

function renderHistory(records) {
  if (!records || records.length === 0) {
    historyBody.innerHTML = `
      <tr class="history__empty-row">
        <td colspan="3">아직 변환 기록이 없습니다.</td>
      </tr>
    `;
    return;
  }

  historyBody.innerHTML = records
    .map((record) => {
      const source = escapeHtml(record.source_format.toUpperCase());
      const target = escapeHtml(record.target_format.toUpperCase());
      return `
        <tr>
          <td>${escapeHtml(record.filename)}</td>
          <td>${source}<span class="history__arrow">→</span>${target}</td>
          <td>${escapeHtml(formatHistoryTime(record.converted_at))}</td>
        </tr>
      `;
    })
    .join("");
}

async function refreshHistory() {
  try {
    const response = await fetch("/api/history");
    const data = await response.json();
    renderHistory(data.records);
  } catch (error) {
    // 히스토리 로딩 실패는 조용히 무시한다 (핵심 변환 기능에는 영향 없음).
  }
}

refreshHistory();

// ---- 변환 통계 대시보드 ----

const statsTotalConversions = document.getElementById("statsTotalConversions");
const statsTodayCount = document.getElementById("statsTodayCount");
const statsSavedBytes = document.getElementById("statsSavedBytes");
const statsRankingBars = document.getElementById("statsRankingBars");
const statsDailyBars = document.getElementById("statsDailyBars");

function renderStatsRanking(toolRanking) {
  if (!toolRanking || toolRanking.length === 0) {
    statsRankingBars.innerHTML = `<p class="stats-chart__empty">아직 데이터가 없습니다.</p>`;
    return;
  }

  const maxCount = Math.max(...toolRanking.map((item) => item.count));
  statsRankingBars.innerHTML = toolRanking
    .map((item) => {
      const label = `${item.source.toUpperCase()} → ${item.target.toUpperCase()}`;
      const percent = maxCount > 0 ? (item.count / maxCount) * 100 : 0;
      return `
        <div class="stats-bar-row" title="${escapeHtml(label)}: ${item.count}회">
          <span class="stats-bar-row__label">${escapeHtml(label)}</span>
          <span class="stats-bar-row__track">
            <span class="stats-bar-row__fill" style="width: ${percent}%;"></span>
          </span>
          <span class="stats-bar-row__count">${item.count}</span>
        </div>
      `;
    })
    .join("");
}

function renderStatsDaily(dailyCounts) {
  if (!dailyCounts || dailyCounts.length === 0) {
    statsDailyBars.innerHTML = `<p class="stats-chart__empty">아직 데이터가 없습니다.</p>`;
    return;
  }

  const maxCount = Math.max(...dailyCounts.map((item) => item.count), 1);
  statsDailyBars.innerHTML = dailyCounts
    .map((item) => {
      const percent = (item.count / maxCount) * 100;
      const shortLabel = item.date.slice(5).replace("-", "/");
      return `
        <div class="stats-daily-bar" title="${escapeHtml(item.date)}: ${item.count}건">
          <span class="stats-daily-bar__fill" style="height: ${percent}%;"></span>
          <span class="stats-daily-bar__label">${escapeHtml(shortLabel)}</span>
        </div>
      `;
    })
    .join("");
}

async function refreshStats() {
  try {
    const response = await fetch("/api/stats");
    const data = await response.json();
    statsTotalConversions.textContent = data.total_conversions;
    statsTodayCount.textContent = data.today_count;
    statsSavedBytes.textContent = formatBytes(data.total_saved_bytes);
    renderStatsRanking(data.tool_ranking);
    renderStatsDaily(data.daily_counts);
  } catch (error) {
    // 통계 로딩 실패는 조용히 무시한다 (핵심 변환 기능에는 영향 없음).
  }
}

refreshStats();

// ---- 이미지 -> PDF 묶기: 여러 파일을 모았다가 한 번에 하나로 합쳐서 보낸다 ----

const imagesToPdfCard = document.getElementById("imagesToPdfCard");

if (imagesToPdfCard) {
  const imagesToPdfInput = document.getElementById("imagesToPdfInput");
  const imagesToPdfStaged = document.getElementById("imagesToPdfStaged");
  const imagesToPdfJobs = document.getElementById("imagesToPdfJobs");
  const imagesToPdfResetBtn = document.getElementById("imagesToPdfResetBtn");
  const imagesToPdfBuildBtn = document.getElementById("imagesToPdfBuildBtn");

  let stagedItems = [];

  function renderStagedList() {
    imagesToPdfStaged.innerHTML = "";

    stagedItems.forEach((item, index) => {
      const row = document.createElement("div");
      row.className = "card__staged-item";

      const label = document.createElement("span");
      label.textContent = `${index + 1}. ${item.file.name}`;

      const removeBtn = document.createElement("button");
      removeBtn.type = "button";
      removeBtn.textContent = "✕";
      removeBtn.addEventListener("click", () => {
        stagedItems.splice(index, 1);
        renderStagedList();
      });

      row.appendChild(label);
      row.appendChild(removeBtn);
      imagesToPdfStaged.appendChild(row);
    });

    imagesToPdfBuildBtn.textContent = `PDF로 묶기 (${stagedItems.length}장)`;
    imagesToPdfBuildBtn.disabled = stagedItems.length === 0;
  }

  function addStagedItems(items) {
    stagedItems.push(...items);
    renderStagedList();
  }

  imagesToPdfInput.addEventListener("change", () => {
    addStagedItems(getItemsFromFileList(imagesToPdfInput.files));
    imagesToPdfInput.value = "";
  });

  ["dragenter", "dragover"].forEach((eventName) => {
    imagesToPdfCard.addEventListener(eventName, (event) => {
      event.preventDefault();
      event.stopPropagation();
      imagesToPdfCard.classList.add("card--dragover");
    });
  });

  ["dragleave", "drop"].forEach((eventName) => {
    imagesToPdfCard.addEventListener(eventName, (event) => {
      event.preventDefault();
      event.stopPropagation();
      imagesToPdfCard.classList.remove("card--dragover");
    });
  });

  imagesToPdfCard.addEventListener("drop", async (event) => {
    const items = await getItemsFromDataTransfer(event.dataTransfer);
    addStagedItems(items);
  });

  imagesToPdfResetBtn.addEventListener("click", () => {
    stagedItems = [];
    renderStagedList();
  });

  imagesToPdfBuildBtn.addEventListener("click", () => {
    if (stagedItems.length === 0) return;

    imagesToPdfBuildBtn.disabled = true;
    const job = createJobRow({ name: `이미지 ${stagedItems.length}장` }, "processing");
    imagesToPdfJobs.prepend(job);

    const formData = new FormData();
    stagedItems.forEach((item) => formData.append("files", item.file));

    const xhr = new XMLHttpRequest();
    xhr.open("POST", "/api/document/images-to-pdf");
    xhr.responseType = "blob";

    xhr.upload.addEventListener("progress", (event) => {
      if (event.lengthComputable) {
        setJobProgress(job, (event.loaded / event.total) * 50);
      }
    });

    xhr.addEventListener("load", () => {
      setJobProgress(job, 100);
      if (xhr.status >= 200 && xhr.status < 300) {
        const disposition = xhr.getResponseHeader("Content-Disposition") || "";
        const match = disposition.match(/filename="?([^"]+)"?/);
        const downloadName = match ? match[1] : "images.pdf";
        setJobDone(job, xhr.response, downloadName, "");
        refreshHistory();
        refreshStats();
        stagedItems = [];
        renderStagedList();
      } else {
        const reader = new FileReader();
        reader.onload = () => {
          try {
            const payload = JSON.parse(reader.result);
            setJobError(job, payload.error || "변환에 실패했습니다.");
          } catch {
            setJobError(job, "변환에 실패했습니다.");
          }
        };
        reader.readAsText(xhr.response);
        imagesToPdfBuildBtn.disabled = stagedItems.length === 0;
      }
    });

    xhr.addEventListener("error", () => {
      setJobProgress(job, 100);
      setJobError(job, "서버와 통신 중 오류가 발생했습니다.");
      imagesToPdfBuildBtn.disabled = stagedItems.length === 0;
    });

    setJobProgress(job, 5);
    xhr.send(formData);
  });
}

// ---- PDF 병합: 여러 PDF를 모았다가 순서대로 하나로 합쳐서 보낸다 (목록에서 드래그로 순서 변경 가능) ----

const pdfMergeCard = document.getElementById("pdfMergeCard");

if (pdfMergeCard) {
  const pdfMergeInput = document.getElementById("pdfMergeInput");
  const pdfMergeStaged = document.getElementById("pdfMergeStaged");
  const pdfMergeJobs = document.getElementById("pdfMergeJobs");
  const pdfMergeResetBtn = document.getElementById("pdfMergeResetBtn");
  const pdfMergeBuildBtn = document.getElementById("pdfMergeBuildBtn");

  let mergeStagedItems = [];
  let mergeDragFromIndex = null;

  function renderMergeStagedList() {
    pdfMergeStaged.innerHTML = "";

    mergeStagedItems.forEach((item, index) => {
      const row = document.createElement("div");
      row.className = "card__staged-item";
      row.draggable = true;

      row.addEventListener("dragstart", () => {
        mergeDragFromIndex = index;
        row.classList.add("card__staged-item--dragging");
      });

      row.addEventListener("dragend", () => {
        row.classList.remove("card__staged-item--dragging");
        mergeDragFromIndex = null;
      });

      row.addEventListener("dragover", (event) => {
        event.preventDefault();
        event.stopPropagation();
        row.classList.add("card__staged-item--dragover");
      });

      row.addEventListener("dragleave", () => {
        row.classList.remove("card__staged-item--dragover");
      });

      row.addEventListener("drop", (event) => {
        event.preventDefault();
        event.stopPropagation();
        row.classList.remove("card__staged-item--dragover");
        if (mergeDragFromIndex === null || mergeDragFromIndex === index) return;
        const [moved] = mergeStagedItems.splice(mergeDragFromIndex, 1);
        mergeStagedItems.splice(index, 0, moved);
        renderMergeStagedList();
      });

      const handle = document.createElement("span");
      handle.className = "card__staged-item__handle";
      handle.textContent = "☰";

      const label = document.createElement("span");
      label.className = "card__staged-item__label";
      label.textContent = `${index + 1}. ${item.file.name}`;

      const removeBtn = document.createElement("button");
      removeBtn.type = "button";
      removeBtn.textContent = "✕";
      removeBtn.addEventListener("click", () => {
        mergeStagedItems.splice(index, 1);
        renderMergeStagedList();
      });

      row.appendChild(handle);
      row.appendChild(label);
      row.appendChild(removeBtn);
      pdfMergeStaged.appendChild(row);
    });

    pdfMergeBuildBtn.textContent = `PDF로 합치기 (${mergeStagedItems.length}개)`;
    pdfMergeBuildBtn.disabled = mergeStagedItems.length < 2;
  }

  function addMergeStagedItems(items) {
    mergeStagedItems.push(...items);
    renderMergeStagedList();
  }

  pdfMergeInput.addEventListener("change", () => {
    addMergeStagedItems(getItemsFromFileList(pdfMergeInput.files));
    pdfMergeInput.value = "";
  });

  ["dragenter", "dragover"].forEach((eventName) => {
    pdfMergeCard.addEventListener(eventName, (event) => {
      event.preventDefault();
      event.stopPropagation();
      pdfMergeCard.classList.add("card--dragover");
    });
  });

  ["dragleave", "drop"].forEach((eventName) => {
    pdfMergeCard.addEventListener(eventName, (event) => {
      event.preventDefault();
      event.stopPropagation();
      pdfMergeCard.classList.remove("card--dragover");
    });
  });

  pdfMergeCard.addEventListener("drop", async (event) => {
    // 목록 안에서 순서를 바꾸려는 드롭은 각 행의 자체 핸들러가 처리하므로 여기서는 무시한다.
    if (event.target.closest(".card__staged-item")) return;
    const items = await getItemsFromDataTransfer(event.dataTransfer);
    addMergeStagedItems(items);
  });

  pdfMergeResetBtn.addEventListener("click", () => {
    mergeStagedItems = [];
    renderMergeStagedList();
  });

  pdfMergeBuildBtn.addEventListener("click", () => {
    if (mergeStagedItems.length < 2) return;

    pdfMergeBuildBtn.disabled = true;
    const job = createJobRow({ name: `PDF ${mergeStagedItems.length}개` }, "processing");
    pdfMergeJobs.prepend(job);

    const formData = new FormData();
    mergeStagedItems.forEach((item) => formData.append("files", item.file));

    const xhr = new XMLHttpRequest();
    xhr.open("POST", "/api/document/merge-pdfs");
    xhr.responseType = "blob";

    xhr.upload.addEventListener("progress", (event) => {
      if (event.lengthComputable) {
        setJobProgress(job, (event.loaded / event.total) * 50);
      }
    });

    xhr.addEventListener("load", () => {
      setJobProgress(job, 100);
      if (xhr.status >= 200 && xhr.status < 300) {
        const disposition = xhr.getResponseHeader("Content-Disposition") || "";
        const match = disposition.match(/filename="?([^"]+)"?/);
        const downloadName = match ? match[1] : "merged.pdf";
        setJobDone(job, xhr.response, downloadName, "");
        refreshHistory();
        refreshStats();
        mergeStagedItems = [];
        renderMergeStagedList();
      } else {
        const reader = new FileReader();
        reader.onload = () => {
          try {
            const payload = JSON.parse(reader.result);
            setJobError(job, payload.error || "병합에 실패했습니다.");
          } catch {
            setJobError(job, "병합에 실패했습니다.");
          }
        };
        reader.readAsText(xhr.response);
        pdfMergeBuildBtn.disabled = mergeStagedItems.length < 2;
      }
    });

    xhr.addEventListener("error", () => {
      setJobProgress(job, 100);
      setJobError(job, "서버와 통신 중 오류가 발생했습니다.");
      pdfMergeBuildBtn.disabled = mergeStagedItems.length < 2;
    });

    setJobProgress(job, 5);
    xhr.send(formData);
  });
}

// ---- 유튜브 음원 추출 / MR 제거 ----

const youtubeAudioCard = document.getElementById("youtubeAudioCard");

if (youtubeAudioCard) {
  const youtubeUrlInput = document.getElementById("youtubeUrlInput");
  const youtubeExtractBtn = document.getElementById("youtubeExtractBtn");
  const youtubeRemoveMrBtn = document.getElementById("youtubeRemoveMrBtn");
  const youtubeJobs = document.getElementById("youtubeJobs");

  function runYoutubeJob(endpoint, jobName, defaultDownloadName, triggerBtn) {
    const url = youtubeUrlInput.value.trim();
    if (!url) {
      alert("유튜브 링크를 입력해주세요.");
      return;
    }

    triggerBtn.disabled = true;
    const job = createJobRow({ name: jobName }, "processing");
    youtubeJobs.prepend(job);
    setJobProgress(job, 10);

    const formData = new FormData();
    formData.append("url", url);

    const xhr = new XMLHttpRequest();
    xhr.open("POST", endpoint);
    xhr.responseType = "blob";

    xhr.addEventListener("load", () => {
      setJobProgress(job, 100);
      triggerBtn.disabled = false;
      if (xhr.status >= 200 && xhr.status < 300) {
        const disposition = xhr.getResponseHeader("Content-Disposition") || "";
        const match = disposition.match(/filename="?([^"]+)"?/);
        const downloadName = match ? match[1] : defaultDownloadName;
        setJobDone(job, xhr.response, downloadName, "");
        refreshHistory();
        refreshStats();
      } else {
        const reader = new FileReader();
        reader.onload = () => {
          try {
            const payload = JSON.parse(reader.result);
            setJobError(job, payload.error || "처리에 실패했습니다.");
          } catch {
            setJobError(job, "처리에 실패했습니다.");
          }
        };
        reader.readAsText(xhr.response);
      }
    });

    xhr.addEventListener("error", () => {
      setJobProgress(job, 100);
      setJobError(job, "서버와 통신 중 오류가 발생했습니다.");
      triggerBtn.disabled = false;
    });

    xhr.send(formData);
  }

  youtubeExtractBtn.addEventListener("click", () => {
    runYoutubeJob("/api/youtube/extract-audio", "유튜브 MP3 추출", "youtube_audio.mp3", youtubeExtractBtn);
  });

  youtubeRemoveMrBtn.addEventListener("click", () => {
    runYoutubeJob("/api/youtube/remove-mr", "유튜브 MR 제거", "youtube_vocals.mp3", youtubeRemoveMrBtn);
  });
}

// ---- 마우스를 따라다니는 반짝이 효과 ----

const SPARKLE_CHARS = ["✦", "✧", "✨", "⋆"];
const SPARKLE_COLORS = ["#ff4fd8", "#b14bff", "#ffd166", "#58ffb0"];
const SPARKLE_MIN_INTERVAL_MS = 40;

let lastSparkleTime = 0;
const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

function spawnCursorSparkle(x, y) {
  const sparkle = document.createElement("span");
  sparkle.className = "cursor-sparkle";
  sparkle.textContent = SPARKLE_CHARS[Math.floor(Math.random() * SPARKLE_CHARS.length)];
  sparkle.style.left = `${x}px`;
  sparkle.style.top = `${y}px`;
  sparkle.style.color = SPARKLE_COLORS[Math.floor(Math.random() * SPARKLE_COLORS.length)];
  document.body.appendChild(sparkle);
  sparkle.addEventListener("animationend", () => sparkle.remove());
}

if (!prefersReducedMotion) {
  document.addEventListener("mousemove", (event) => {
    const now = Date.now();
    if (now - lastSparkleTime < SPARKLE_MIN_INTERVAL_MS) return;
    lastSparkleTime = now;
    spawnCursorSparkle(event.clientX, event.clientY);
  });
}

// ---- 핫폴더: 감시 폴더에 파일이 들어오면 자동으로 변환한다 ----

const HOTFOLDER_STATUS_POLL_MS = 4000;

const hotfolderWatchInput = document.getElementById("hotfolderWatchInput");
const hotfolderOutputInput = document.getElementById("hotfolderOutputInput");
const hotfolderStartBtn = document.getElementById("hotfolderStartBtn");
const hotfolderStopBtn = document.getElementById("hotfolderStopBtn");
const hotfolderStatus = document.getElementById("hotfolderStatus");

async function refreshHotfolderStatus() {
  if (!hotfolderStatus) return;

  try {
    const response = await fetch("/api/hotfolder/status");
    const data = await response.json();

    if (data.running) {
      let text = `감시 중: ${data.watch_dir} → ${data.output_dir} (지금까지 ${data.processed_count}개 처리)`;
      if (data.last_error) {
        text += ` · ${data.last_error}`;
      }
      hotfolderStatus.textContent = text;
      if (hotfolderWatchInput && !hotfolderWatchInput.matches(":focus")) {
        hotfolderWatchInput.value = data.watch_dir;
      }
      if (hotfolderOutputInput && !hotfolderOutputInput.matches(":focus")) {
        hotfolderOutputInput.value = data.output_dir;
      }
    } else {
      hotfolderStatus.textContent = "감시 중이 아닙니다.";
    }
  } catch (error) {
    // 상태 조회 실패는 조용히 무시한다 (다음 폴링 때 다시 시도).
  }
}

if (hotfolderStartBtn) {
  hotfolderStartBtn.addEventListener("click", async () => {
    const watchDir = hotfolderWatchInput.value.trim();
    const outputDir = hotfolderOutputInput.value.trim();

    if (!watchDir || !outputDir) {
      alert("감시 폴더와 완료 폴더 경로를 모두 입력해주세요.");
      return;
    }

    try {
      const response = await fetch("/api/hotfolder/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ watch_dir: watchDir, output_dir: outputDir }),
      });
      const data = await response.json();
      if (!data.success) alert(data.message);
      refreshHotfolderStatus();
    } catch (error) {
      alert("감시 시작에 실패했습니다.");
    }
  });
}

if (hotfolderStopBtn) {
  hotfolderStopBtn.addEventListener("click", async () => {
    try {
      const response = await fetch("/api/hotfolder/stop", { method: "POST" });
      const data = await response.json();
      if (!data.success) alert(data.message);
      refreshHotfolderStatus();
    } catch (error) {
      alert("감시 중지에 실패했습니다.");
    }
  });
}

if (hotfolderStatus) {
  refreshHotfolderStatus();
  setInterval(refreshHotfolderStatus, HOTFOLDER_STATUS_POLL_MS);
}
