"""오래 걸리는 변환 작업(예: 대용량 영상 압축)의 진행률을 스레드 간에 공유하는 간단한 메모리 저장소."""

import threading
import uuid

_jobs: dict[str, dict] = {}
_lock = threading.Lock()


def create_job() -> str:
    job_id = uuid.uuid4().hex
    with _lock:
        _jobs[job_id] = {"status": "processing", "percent": 0, "error": None}
    return job_id


def update_job(job_id: str, **fields) -> None:
    with _lock:
        if job_id in _jobs:
            _jobs[job_id].update(fields)


def get_job(job_id: str) -> dict | None:
    with _lock:
        job = _jobs.get(job_id)
        return dict(job) if job is not None else None


def delete_job(job_id: str) -> None:
    with _lock:
        _jobs.pop(job_id, None)
