const activeCards = document.querySelectorAll(".card--active");

function createJobRow(file) {
  const job = document.createElement("div");
  job.className = "job job--processing";
  job.innerHTML = `
    <div class="job__row">
      <span class="job__name">${file.name}</span>
      <span class="job__badge job__badge--processing">처리 중</span>
    </div>
    <div class="job__progress"><div class="job__progress-fill"></div></div>
    <span class="job__error" hidden></span>
  `;
  return job;
}

function setJobProgress(job, percent) {
  job.querySelector(".job__progress-fill").style.width = `${percent}%`;
}

function setJobDone(job, blob, downloadName) {
  job.className = "job job--done";
  job.querySelector(".job__badge").className = "job__badge job__badge--done";
  job.querySelector(".job__badge").textContent = "완료";

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
  job.querySelector(".job__badge").textContent = "실패";
  const errorEl = job.querySelector(".job__error");
  errorEl.textContent = message;
  errorEl.hidden = false;
}

function convertFile(jobsContainer, format, file) {
  const job = createJobRow(file);
  jobsContainer.prepend(job);

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
    if (xhr.status >= 200 && xhr.status < 300) {
      setJobProgress(job, 100);
      const disposition = xhr.getResponseHeader("Content-Disposition") || "";
      const match = disposition.match(/filename="?([^"]+)"?/);
      const downloadName = match ? match[1] : `converted.${format}`;
      setJobDone(job, xhr.response, downloadName);
    } else {
      setJobProgress(job, 100);
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
    }
  });

  xhr.addEventListener("error", () => {
    setJobProgress(job, 100);
    setJobError(job, "서버와 통신 중 오류가 발생했습니다.");
  });

  setJobProgress(job, 5);
  xhr.send(formData);
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

// ---- 스마트 업로드: 파일 종류를 자동 인식해서 변환 가능한 포맷을 추천한다 ----

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

function renderSmartDropResult(file, detection) {
  smartDropResult.hidden = false;
  smartDropResult.innerHTML = "";

  const header = document.createElement("div");
  header.className = "smart-drop__result-header";
  header.textContent = `📄 ${file.name}`;
  smartDropResult.appendChild(header);

  const desc = document.createElement("div");
  desc.className = "smart-drop__result-desc";

  if (!detection.supported) {
    const categoryLabel = CATEGORY_LABELS[detection.category] || "알 수 없는 형식";
    desc.textContent =
      detection.category === "unknown"
        ? "어떤 형식인지 확인하지 못했습니다."
        : `${categoryLabel} 파일로 확인됐어요. 이 종류는 아직 변환 기능이 준비 중입니다.`;
    smartDropResult.appendChild(desc);
    return;
  }

  const detectedLabel = FORMAT_LABELS[detection.detected_format] || detection.detected_format.toUpperCase();
  desc.textContent = `${detectedLabel} 이미지로 확인됐어요. 아래 포맷 중 하나를 골라 변환하세요.`;
  smartDropResult.appendChild(desc);

  if (detection.extension_mismatch) {
    const warning = document.createElement("div");
    warning.className = "smart-drop__warning";
    warning.textContent = `⚠️ 확장자는 .${detection.extension}이지만, 실제 내용은 ${detectedLabel} 파일이에요.`;
    smartDropResult.appendChild(warning);
  }

  const formatsRow = document.createElement("div");
  formatsRow.className = "smart-drop__formats";

  const jobsList = document.createElement("div");
  jobsList.className = "card__jobs";

  detection.recommended_formats.forEach((format) => {
    const chip = document.createElement("button");
    chip.type = "button";
    chip.className = "format-chip";
    chip.textContent = `${FORMAT_LABELS[format] || format.toUpperCase()}로 변환`;
    chip.addEventListener("click", () => convertFile(jobsList, format, file));
    formatsRow.appendChild(chip);
  });

  smartDropResult.appendChild(formatsRow);
  smartDropResult.appendChild(jobsList);
}

async function handleSmartDropFile(file) {
  smartDropResult.hidden = false;
  smartDropResult.innerHTML = `<div class="smart-drop__result-desc">${file.name} 분석 중...</div>`;

  try {
    const detection = await detectFile(file);
    renderSmartDropResult(file, detection);
  } catch (error) {
    smartDropResult.innerHTML = `<div class="smart-drop__warning">${error.message}</div>`;
  }
}

smartDropInput.addEventListener("change", () => {
  if (smartDropInput.files.length > 0) {
    handleSmartDropFile(smartDropInput.files[0]);
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
  const file = event.dataTransfer.files[0];
  if (file) {
    handleSmartDropFile(file);
  }
});
