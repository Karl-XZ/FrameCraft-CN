from __future__ import annotations

import asyncio
import json
import mimetypes
import os
import shutil
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel

from . import store
from .ingest import ensure_version_subtitles, read_script_text, write_script_text
from .retention import startup_prune_if_enabled
from .security import cors_origin_regex, cors_origins, get_access_token, require_access_token, token_help
from .single_agent import ProjectBusyError, runner

app = FastAPI(title="FrameCraft openJiuwen Agent API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins(),
    allow_origin_regex=cors_origin_regex(),
    allow_methods=["*"],
    allow_headers=["*"],
)
app.middleware("http")(require_access_token)


@app.on_event("startup")
def startup_security_notice():
    if os.getenv("FRAMECRAFT_DISABLE_AUTH", "").strip() in {"1", "true", "yes"}:
        print("[FrameCraft] WARNING auth disabled by FRAMECRAFT_DISABLE_AUTH", flush=True)
    else:
        get_access_token()
        print(f"[FrameCraft] Access token source: {token_help()}", flush=True)


@app.on_event("startup")
def startup_retention_pass():
    try:
        result = startup_prune_if_enabled()
        if result is None:
            print("[FrameCraft] Retention cleanup disabled", flush=True)
            return
        print(
            f"[FrameCraft] Retention cleanup checked {result['cutoff']}, "
            f"deleted={result['deleted_count']}, orphans={len(result['orphan_paths_removed'])}",
            flush=True,
        )
    except Exception as exc:
        print(f"[FrameCraft] Retention cleanup skipped: {exc}", flush=True)


class ProjectIn(BaseModel):
    name: str
    aspect_ratio: str = "9:16"
    target_duration: int = 60
    target_style: str = "faceless_explainer"
    output_language: str = "zh"
    generate_draft: bool = False
    keep_hyperframes: bool = True
    script_text: str = ""


class AnalyzeIn(BaseModel):
    strategy: str = "complete"
    platform: str = "douyin"


class GenerateIn(BaseModel):
    resolution: str = "1080p"
    fps: int = 24
    strategy: str = "complete"


class ChatIn(BaseModel):
    message: str
    apply: bool = True


class ApplyPatchIn(BaseModel):
    patch: dict[str, Any]


class ScriptIn(BaseModel):
    text: str = ""


@app.get("/api/health")
def health():
    return {"ok": True, "mode": "openjiuwen-multi-agent"}


@app.post("/api/projects")
def create_project(body: ProjectIn):
    pid = store.new_id("proj")
    now = store.now_iso()
    project = {
        "id": pid,
        "agent_session_id": None,
        "name": body.name,
        "status": "uploading",
        "aspect_ratio": body.aspect_ratio,
        "target_style": body.target_style,
        "target_duration": body.target_duration,
        "output_language": body.output_language,
        "generate_draft": body.generate_draft,
        "keep_hyperframes": body.keep_hyperframes,
        "script_text": body.script_text.strip(),
        "current_version_id": None,
        "created_at": now,
        "updated_at": now,
    }

    def op(data):
        data["projects"][pid] = project
        data["chat"][pid] = []
        return project

    created = store.mutate(op)
    if body.script_text.strip():
        write_script_text(pid, body.script_text)
    return store.public_project(created)


@app.get("/api/projects")
def list_projects():
    data = store.snapshot()
    projects = list(data["projects"].values())
    projects.sort(key=lambda p: p.get("updated_at") or "", reverse=True)
    return [store.public_project(p) for p in projects]


@app.get("/api/projects/{project_id}")
def get_project(project_id: str):
    project = store.snapshot()["projects"].get(project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    project = dict(project)
    project["script_text"] = read_script_text(project)
    return store.public_project(project)


@app.delete("/api/projects/{project_id}", status_code=204)
def delete_project(project_id: str):
    def op(data):
        if project_id not in data["projects"]:
            raise HTTPException(404, "Project not found")
        data["projects"].pop(project_id, None)
        data["chat"].pop(project_id, None)
        for key in [k for k, a in data["assets"].items() if a["project_id"] == project_id]:
            data["assets"].pop(key, None)
        for key in [k for k, v in data["versions"].items() if v["project_id"] == project_id]:
            data["versions"].pop(key, None)
        for key in [k for k, j in data["jobs"].items() if j["project_id"] == project_id]:
            data["jobs"].pop(key, None)
    store.mutate(op)
    shutil.rmtree(store.upload_dir(project_id), ignore_errors=True)
    shutil.rmtree(store.project_dir(project_id), ignore_errors=True)
    return None


@app.get("/api/projects/{project_id}/assets")
def list_assets(project_id: str):
    data = store.snapshot()
    return [store.public_asset(a) for a in data["assets"].values() if a["project_id"] == project_id]


@app.get("/api/projects/{project_id}/script")
def get_script(project_id: str):
    project = _ensure_project(project_id)
    return {"text": read_script_text(project)}


@app.put("/api/projects/{project_id}/script")
def put_script(project_id: str, body: ScriptIn):
    text = (body.text or "").strip()

    def op(data):
        project = data["projects"].get(project_id)
        if not project:
            raise HTTPException(404, "Project not found")
        project["script_text"] = text
        project["updated_at"] = store.now_iso()
        return project

    project = store.mutate(op)
    write_script_text(project_id, text)
    project = dict(project)
    project["script_text"] = text
    return store.public_project(project)


@app.post("/api/projects/{project_id}/assets/upload")
async def upload_asset(
    project_id: str,
    file: UploadFile = File(...),
    user_label: str = Form(""),
    user_note: str = Form(""),
):
    data = store.snapshot()
    if project_id not in data["projects"]:
        raise HTTPException(404, "Project not found")
    aid = store.new_id("asset")
    filename = Path(file.filename or f"{aid}.bin").name
    dest = store.upload_dir(project_id) / f"{aid}_{filename}"
    with dest.open("wb") as f:
        shutil.copyfileobj(file.file, f)
    guessed_mime = mimetypes.guess_type(filename)[0]
    mime = guessed_mime if not file.content_type or file.content_type == "application/octet-stream" else file.content_type
    mime = mime or "application/octet-stream"
    file_type = (
        "video"
        if mime.startswith("video/")
        else "audio"
        if mime.startswith("audio/")
        else "image"
        if mime.startswith("image/")
        else "file"
    )
    asset = {
        "id": aid,
        "project_id": project_id,
        "file_name": filename,
        "file_type": file_type,
        "mime_type": mime,
        "size": dest.stat().st_size,
        "duration": None,
        "user_label": user_label,
        "user_note": user_note,
        "must_use": False,
        "priority": 0,
        "analysis_status": "pending",
        "thumbnail_url": None,
        "path": str(dest),
        "created_at": store.now_iso(),
    }

    def op(db):
        db["assets"][aid] = asset
        db["projects"][project_id]["status"] = "uploading"
        db["projects"][project_id]["updated_at"] = store.now_iso()
        return asset

    return store.public_asset(store.mutate(op))


@app.patch("/api/assets/{asset_id}")
def update_asset(asset_id: str, body: dict[str, Any]):
    def op(data):
        asset = data["assets"].get(asset_id)
        if not asset:
            raise HTTPException(404, "Asset not found")
        for key in ("user_label", "user_note", "must_use", "priority"):
            if key in body:
                asset[key] = body[key]
        return asset
    return store.public_asset(store.mutate(op))


@app.get("/api/assets/{asset_id}/analysis")
def get_asset_analysis(asset_id: str):
    data = store.snapshot()
    asset = data["assets"].get(asset_id)
    if not asset:
        raise HTTPException(404, "Asset not found")
    return {
        "ready": asset.get("analysis_status") == "completed",
        "asset_id": asset_id,
        "auto_summary": asset.get("auto_summary", "由单一 Agent 在任务中分析。"),
        "recommended_usage": asset.get("recommended_usage", []),
        "ocr_text": asset.get("ocr_text", ""),
        "vision_status": "agent-managed",
        "vision_error": None,
        "ocr_status": "agent-managed",
        "ocr_error": None,
        "meta": {},
        "frame_urls": [],
        "broll_segments": [],
    }


@app.post("/api/projects/{project_id}/assets/analyze")
def analyze(project_id: str, body: AnalyzeIn):
    _ensure_project(project_id)
    return _start_job(project_id, "analyze", body.model_dump())


@app.get("/api/projects/{project_id}/edit-plan")
def get_edit_plan(project_id: str):
    _ensure_project(project_id)
    path = store.project_dir(project_id) / "analysis" / "edit_plan.json"
    if not path.is_file():
        raise HTTPException(404, "Edit plan not found; run analyze first")
    return json.loads(path.read_text(encoding="utf-8"))


@app.post("/api/projects/{project_id}/generate")
def generate(project_id: str, body: GenerateIn):
    _ensure_project(project_id)
    return _start_job(project_id, "generate", body.model_dump())


@app.post("/api/projects/{project_id}/apply-patch")
def apply_patch(project_id: str, body: ApplyPatchIn):
    _ensure_project(project_id)
    return _start_job(project_id, "apply_patch", {"patch": body.patch})


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    job = store.snapshot()["jobs"].get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return store.public_job(job)


@app.get("/api/projects/{project_id}/jobs/active")
def get_active_project_job(project_id: str):
    _ensure_project(project_id)
    jobs = [
        j for j in store.snapshot()["jobs"].values()
        if j.get("project_id") == project_id and j.get("status") not in {"completed", "failed", "cancelled", "needs_input"}
    ]
    jobs.sort(key=lambda j: j.get("created_at") or "", reverse=True)
    return store.public_job(jobs[0]) if jobs else None


@app.post("/api/jobs/{job_id}/cancel", status_code=204)
def cancel_job(job_id: str):
    def op(data):
        job = data["jobs"].get(job_id)
        if not job:
            raise HTTPException(404, "Job not found")
        if job["status"] in {"completed", "failed", "cancelled"}:
            return job
        job["status"] = "cancelled"
        job["completed_at"] = store.now_iso()
        return job
    store.mutate(op)
    return None


@app.get("/api/jobs/{job_id}/events")
async def job_events(job_id: str, request: Request):
    async def stream():
        while True:
            data = store.snapshot()
            job = data["jobs"].get(job_id)
            if not job:
                yield "event: error\ndata: {\"error\":\"Job not found\"}\n\n"
                return
            payload = json.dumps(store.public_job(job), ensure_ascii=False)
            yield f"data: {payload}\n\n"
            if job["status"] in {"completed", "failed", "cancelled"}:
                return
            await asyncio.sleep(1)
    return StreamingResponse(stream(), media_type="text/event-stream")


@app.get("/api/projects/{project_id}/versions")
def list_versions(project_id: str):
    _ensure_project(project_id)
    versions = [v for v in store.snapshot()["versions"].values() if v["project_id"] == project_id]
    versions.sort(key=lambda v: int(v.get("version_number", 0)), reverse=True)
    return [store.public_version(v) for v in versions]


@app.post("/api/projects/{project_id}/versions/{version_id}/activate")
def activate_version(project_id: str, version_id: str):
    def op(data):
        if version_id not in data["versions"]:
            raise HTTPException(404, "Version not found")
        data["projects"][project_id]["current_version_id"] = version_id
        data["projects"][project_id]["updated_at"] = store.now_iso()
    store.mutate(op)
    return {"ok": True, "current_version_id": version_id}


@app.get("/api/projects/{project_id}/versions/{version_id}/preview")
def version_preview(project_id: str, version_id: str):
    version = _version(project_id, version_id)
    return FileResponse(version["preview_path"], media_type="video/mp4")


@app.get("/api/projects/{project_id}/versions/{version_id}/timeline")
def version_timeline(project_id: str, version_id: str):
    version = _version(project_id, version_id)
    path = Path(version["version_dir"]) / "timeline.json"
    return _file_or_json(path, {"project_id": project_id, "version_id": version_id})


@app.get("/api/projects/{project_id}/versions/{version_id}/subtitles")
def version_subtitles(project_id: str, version_id: str):
    version = _version(project_id, version_id)
    path = Path(version["version_dir"]) / "subtitles.srt"
    ensure_version_subtitles(project_id, Path(version["version_dir"]))
    return _file_or_json(path, "")


@app.get("/api/projects/{project_id}/versions/{version_id}/hyperframes")
def version_hyperframes(project_id: str, version_id: str):
    version = _version(project_id, version_id)
    path = Path(version["version_dir"]) / "hyperframes_project.zip"
    if path.is_file():
        return FileResponse(path)
    raise HTTPException(404, "HyperFrames zip not found")


@app.get("/api/projects/{project_id}/versions/{version_id}/draft")
def version_draft(project_id: str, version_id: str):
    version = _version(project_id, version_id)
    path = Path(version.get("draft_path") or Path(version["version_dir"]) / "jianying_draft.zip")
    if path.is_file():
        return FileResponse(
            path,
            media_type="application/zip",
            filename=f"{version_id}_jianying_draft.zip",
        )
    raise HTTPException(404, "Jianying draft zip not found")


@app.get("/api/projects/{project_id}/versions/{version_id}/import-guide")
def import_guide(project_id: str, version_id: str):
    version = _version(project_id, version_id)
    guide_path = Path(version.get("import_guide_path") or Path(version["version_dir"]) / "jianying_import_guide.md")
    if guide_path.is_file():
        return {"content": guide_path.read_text(encoding="utf-8")}
    return {"content": "当前版本不生成剪映草稿，因此没有导入说明。"}


@app.post("/api/projects/{project_id}/chat")
def chat(project_id: str, body: ChatIn):
    _ensure_project(project_id)
    user = {
        "id": store.new_id("msg"),
        "role": "user",
        "content": body.message,
        "created_at": store.now_iso(),
    }

    def op(data):
        data.setdefault("chat", {}).setdefault(project_id, []).append(user)
    store.mutate(op)
    try:
        job = _start_job(project_id, "chat", {"message": body.message, "apply": body.apply})
    except Exception:
        def failed_op(data):
            data.setdefault("chat", {}).setdefault(project_id, []).append({
                "id": store.new_id("msg"),
                "project_id": project_id,
                "role": "agent",
                "content": "这条消息已经收到，但 Agent 没能启动。请检查后端日志或 DeepSeek API 配置后重试。",
                "status": "failed",
                "created_at": store.now_iso(),
            })
        store.mutate(failed_op)
        raise
    accepted = {
        "id": store.new_id("msg"),
        "project_id": project_id,
        "role": "agent",
        "content": "已收到，我正在把这条消息交给当前项目的 Agent。后续进度会直接显示在这里。",
        "patch": None,
        "job_id": job["id"],
        "status": "running",
        "created_at": store.now_iso(),
    }

    def accepted_op(data):
        data.setdefault("chat", {}).setdefault(project_id, []).append(accepted)
    store.mutate(accepted_op)
    return store.public_chat_message(accepted)


@app.get("/api/projects/{project_id}/chat")
def get_chat(project_id: str):
    _ensure_project(project_id)
    return [store.public_chat_message(message) for message in store.snapshot().get("chat", {}).get(project_id, [])]


@app.get("/api/model-providers")
def model_providers():
    return {
        "providers": [
            {
                "id": "deepseek",
                "label": "DeepSeek",
                "base_url": "https://api.deepseek.com",
                "note": "后端使用 openJiuwen 多 Agent 团队与 DeepSeek V4 驱动视频设计、代码生成和视觉验收。",
            }
        ],
        "deepseek": {
            "label": "DeepSeek",
            "base_url": "https://api.deepseek.com",
            "note": "默认并行模型：deepseek-v4-flash；代码总监：deepseek-v4-pro；视觉验收：deepseek-v4-flash-vision-exp。Key 仅存后端，不回显到前端。",
        },
    }


@app.get("/api/settings/model")
def get_settings():
    return store.public_settings(store.snapshot()["settings"])


@app.patch("/api/settings/model")
def save_settings(body: dict[str, str]):
    def op(data):
        allowed = {
            "provider",
            "text_model",
            "vision_model",
            "pro_model",
            "base_url",
            "asr_model",
            "tts_model",
            "tts_voice",
            "api_key",
        }
        for key in allowed:
            if key in body:
                data["settings"][key] = body[key]
        return store.public_settings(data["settings"])
    return store.mutate(op)


def _ensure_project(project_id: str) -> dict[str, Any]:
    project = store.snapshot()["projects"].get(project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    return project


def _start_job(project_id: str, job_type: str, payload: dict[str, Any]):
    try:
        return runner.start(project_id, job_type, payload)
    except ProjectBusyError as exc:
        raise HTTPException(409, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc


def _version(project_id: str, version_id: str) -> dict[str, Any]:
    version = store.snapshot()["versions"].get(version_id)
    if not version or version["project_id"] != project_id:
        raise HTTPException(404, "Version not found")
    return version


def _file_or_json(path: Path, fallback: Any):
    if path.is_file():
        return FileResponse(path)
    return JSONResponse(fallback)
