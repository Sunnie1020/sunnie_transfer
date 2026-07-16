const activeCards = document.querySelectorAll(".card--active");

const ENDPOINTS = {
  image: "/api/convert/image",
  video: "/api/convert/video",
  audio: "/api/convert/audio",
  process: "/api/process/image",
  "video-to-gif": "/api/convert/gif-from-video",
  "gif-to-video": "/api/convert/video-from-gif",
  "pdf-to-images": "/api/document/pdf-to-images",
  "video-thumbnail": "/api/document/video-thumbnail",
};

const FFMPEG_REQUIRED_CATEGORIES = ["video", "audio", "video-to-gif", "gif-to-video", "video-thumbnail"];
const DEFAULT_AUDIO_BITRATE = "192k";
const DEFAULT_IMAGE_QUALITY = "85";
const DEFAULT_VIDEO_CODEC = "h264";
const DEFAULT_VIDEO_CRF = "23";
const DEFAULT_GIF_WIDTH = "480";
const DEFAULT_GIF_FPS = "10";
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
    </div>
    <div class="job__progress"><div class="job__progress-fill"></div></div>
    <span class="job__error" hidden></span>
  `;
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

  // "전체 다운로드"가 이 job을 zip에 담을 수 있도록 결과를 DOM 노드에 그대로 들고 있는다.
  job._downloadBlob = blob;
  job._downloadPath = buildZipPath(sourceRelativePath || "", downloadName);
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
    } else if (category === "video") {
      formData.append("resolution", options.resolution || "original");
      formData.append("codec", options.codec || DEFAULT_VIDEO_CODEC);
      formData.append("crf", options.crf || DEFAULT_VIDEO_CRF);
    } else if (category === "process") {
      formData.append("width", options.width || "original");
      formData.append("quality", options.quality || DEFAULT_IMAGE_QUALITY);
      if (options.watermarkFile) {
        formData.append("watermark", options.watermarkFile);
      }
      formData.append("position", options.watermarkPosition || "bottom-right");
      formData.append("opacity", options.watermarkOpacity || "50");
    } else if (category === "video-to-gif") {
      formData.append("start", options.start || "0");
      formData.append("duration", options.duration || "3");
      formData.append("width", options.width || DEFAULT_GIF_WIDTH);
      formData.append("fps", options.fps || DEFAULT_GIF_FPS);
    } else if (category === "pdf-to-images") {
      formData.append("dpi", options.dpi || DEFAULT_PDF_DPI);
    } else if (category === "video-thumbnail") {
      formData.append("timestamp", options.timestamp || "0");
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
        refreshHistory();
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
      };
    }
    if (category === "process") {
      return {
        width: widthSelect ? widthSelect.value : "original",
        quality: qualitySelect ? qualitySelect.value : DEFAULT_IMAGE_QUALITY,
        watermarkFile: watermarkInput && watermarkInput.files[0] ? watermarkInput.files[0] : null,
        watermarkPosition: watermarkPositionSelect ? watermarkPositionSelect.value : "bottom-right",
        watermarkOpacity: watermarkOpacitySelect ? watermarkOpacitySelect.value : "50",
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
    return {
      maxDimension: sizeSelect ? sizeSelect.value : "original",
      quality: qualitySelect ? qualitySelect.value : DEFAULT_IMAGE_QUALITY,
    };
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
