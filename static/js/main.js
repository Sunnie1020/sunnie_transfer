const activeCards = document.querySelectorAll(".card--active");

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
function convertJob(job, file, format) {
  return new Promise((resolve) => {
    setJobProcessing(job);

    const formData = new FormData();
    formData.append("file", file);
    formData.append("format", format);

    const xhr = new XMLHttpRequest();
    xhr.open("POST", "/api/convert/image");
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
function convertFile(jobsContainer, format, file) {
  const job = createJobRow(file, "processing");
  jobsContainer.prepend(job);
  return convertJob(job, file, format);
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

activeCards.forEach((card) => {
  const input = card.querySelector(".card__input");
  const format = card.dataset.format;
  const jobsContainer = card.querySelector(".card__jobs");

  input.addEventListener("change", () => {
    Array.from(input.files).forEach((file) => convertFile(jobsContainer, format, file));
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
    Array.from(event.dataTransfer.files).forEach((file) => convertFile(jobsContainer, format, file));
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
};

const CANONICAL_IMAGE_FORMATS = ["jpg", "png", "webp", "bmp", "gif", "tiff"];

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
  return detection.extension_mismatch ? `${detectedLabel} 이미지 (확장자 다름)` : `${detectedLabel} 이미지`;
}

function commonRecommendedFormats(entries) {
  const supportedEntries = entries.filter((entry) => entry.detection.supported);
  if (supportedEntries.length === 0) return [];

  return CANONICAL_IMAGE_FORMATS.filter((format) =>
    supportedEntries.every((entry) => entry.detection.recommended_formats.includes(format))
  );
}

function renderBatchUI(entries) {
  smartDropResult.hidden = false;
  smartDropResult.innerHTML = "";

  const supportedCount = entries.filter((entry) => entry.detection.supported).length;

  const header = document.createElement("div");
  header.className = "smart-drop__result-header";
  header.textContent = `파일 ${entries.length}개 중 ${supportedCount}개 변환 가능`;
  smartDropResult.appendChild(header);

  const formats = commonRecommendedFormats(entries);

  const controls = document.createElement("div");
  controls.className = "smart-drop__batch-controls";

  if (supportedCount === 0) {
    const desc = document.createElement("div");
    desc.className = "smart-drop__warning";
    desc.textContent = "변환 가능한 이미지 파일이 없습니다. PDF·영상·오디오는 아직 준비 중이에요.";
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

    convertAllBtn.addEventListener("click", () => {
      convertAllBtn.disabled = true;
      const chosenFormat = select.value;
      const tasks = entries
        .filter((entry) => entry.detection.supported)
        .map((entry) => () => convertJob(entry.job, entry.file, chosenFormat));
      runWithConcurrencyLimit(tasks, BATCH_CONCURRENCY).finally(() => {
        convertAllBtn.disabled = false;
      });
    });

    controls.appendChild(select);
    controls.appendChild(convertAllBtn);
    smartDropResult.appendChild(controls);
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
