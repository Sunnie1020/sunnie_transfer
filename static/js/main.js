const activeCards = document.querySelectorAll(".card--active");

const ENDPOINTS = {
  image: "/api/convert/image",
  video: "/api/convert/video",
  audio: "/api/convert/audio",
};

const FFMPEG_REQUIRED_CATEGORIES = ["video", "audio"];
const DEFAULT_AUDIO_BITRATE = "192k";
const DEFAULT_IMAGE_QUALITY = "85";
const DEFAULT_VIDEO_CODEC = "h264";
const DEFAULT_VIDEO_CRF = "23";

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

function setJobDone(job, blob, downloadName) {
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
// options.bitrate가 있으면 오디오 변환 시 음질로 함께 전달한다.
function convertJob(job, file, format, category = "image", options = {}) {
  return new Promise((resolve) => {
    setJobProcessing(job);

    const formData = new FormData();
    formData.append("file", file);
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
        setJobDone(job, xhr.response, downloadName);
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
function convertFile(jobsContainer, format, file, category = "image", options = {}) {
  const job = createJobRow(file, "processing");
  jobsContainer.prepend(job);
  return convertJob(job, file, format, category, options);
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
  const input = card.querySelector(".card__input");
  const format = card.dataset.format;
  const category = card.dataset.category || "image";
  const jobsContainer = card.querySelector(".card__jobs");

  const bitrateSelect = card.querySelector(".card__bitrate");
  const sizeSelect = card.querySelector(".card__size");
  const qualitySelect = card.querySelector(".card__quality");
  const resolutionSelect = card.querySelector(".card__resolution");
  const codecSelect = card.querySelector(".card__codec");
  const crfSelect = card.querySelector(".card__crf");

  if (card.dataset.accept) {
    input.accept = card.dataset.accept;
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
    return {
      maxDimension: sizeSelect ? sizeSelect.value : "original",
      quality: qualitySelect ? qualitySelect.value : DEFAULT_IMAGE_QUALITY,
    };
  }

  async function handleFiles(files) {
    if (FFMPEG_REQUIRED_CATEGORIES.includes(category) && !(await ensureFfmpegChecked())) {
      renderFfmpegPrompt(jobsContainer, () => handleFiles(files));
      return;
    }
    const options = collectOptions();
    files.forEach((file) => convertFile(jobsContainer, format, file, category, options));
  }

  input.addEventListener("change", () => {
    handleFiles(Array.from(input.files));
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

  card.addEventListener("drop", (event) => {
    handleFiles(Array.from(event.dataTransfer.files));
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
        (entry) => () => convertJob(entry.job, entry.file, chosenFormat, entry.detection.category, options)
      );
      runWithConcurrencyLimit(tasks, BATCH_CONCURRENCY).finally(() => {
        convertAllBtn.disabled = false;
      });
    }

    convertAllBtn.addEventListener("click", startBatchConvert);

    controls.appendChild(select);
    controls.appendChild(convertAllBtn);
    smartDropResult.appendChild(controls);
    smartDropResult.appendChild(ffmpegPromptBox);
  }

  const jobsList = document.createElement("div");
  jobsList.className = "card__jobs";

  entries.forEach((entry) => {
    const status = entry.detection.supported ? "waiting" : "unsupported";
    const job = createJobRow(entry.file, status);
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

async function handleSmartDropFiles(files) {
  smartDropResult.hidden = false;
  smartDropResult.innerHTML = `<div class="smart-drop__result-desc">파일 ${files.length}개 분석 중...</div>`;

  try {
    const entries = await Promise.all(
      files.map(async (file) => ({ file, detection: await detectFile(file) }))
    );
    renderBatchUI(entries);
  } catch (error) {
    smartDropResult.innerHTML = `<div class="smart-drop__warning">${error.message}</div>`;
  }
}

smartDropInput.addEventListener("change", () => {
  if (smartDropInput.files.length > 0) {
    handleSmartDropFiles(Array.from(smartDropInput.files));
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

smartDropZone.addEventListener("drop", (event) => {
  const files = Array.from(event.dataTransfer.files);
  if (files.length > 0) {
    handleSmartDropFiles(files);
  }
});
