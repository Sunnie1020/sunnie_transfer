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

function convertFile(card, file) {
  const format = card.dataset.format;
  const jobsContainer = card.querySelector(".card__jobs");
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

  input.addEventListener("change", () => {
    Array.from(input.files).forEach((file) => convertFile(card, file));
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
    Array.from(event.dataTransfer.files).forEach((file) => convertFile(card, file));
  });
});

document.querySelectorAll(".card--soon").forEach((card) => {
  card.addEventListener("click", () => {
    alert("이 기능은 아직 준비 중입니다. 곧 추가될 예정이에요.");
  });
});
