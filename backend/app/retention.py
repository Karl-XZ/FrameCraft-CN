from __future__ import annotations

import argparse
import json
import os
import shutil
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from . import store

DEFAULT_RETENTION_HOURS = 24
ACTIVE_JOB_STATUSES = {"pending", "running"}


@dataclass
class DeletedProject:
    project_id: str
    name: str
    reason: str
    updated_at: str
    job_ids: list[str]


def retention_hours() -> int:
    raw = str(os.getenv("FRAMECRAFT_RETENTION_HOURS") or "").strip()
    if not raw:
        return DEFAULT_RETENTION_HOURS
    try:
        value = int(raw)
    except ValueError:
        return DEFAULT_RETENTION_HOURS
    return max(1, value)


def retention_enabled() -> bool:
    raw = str(os.getenv("FRAMECRAFT_RETENTION_ENABLED") or "1").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def prune_expired_projects(
    *,
    now: datetime | None = None,
    hours: int | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    current = now or datetime.now(timezone.utc)
    keep_hours = hours if hours is not None else retention_hours()
    cutoff = current - timedelta(hours=keep_hours)

    deleted: list[DeletedProject] = []
    live_project_ids: set[str] = set()
    removed_paths: list[str] = []

    def op(data: dict[str, Any]) -> dict[str, Any]:
        projects = data.get("projects", {})
        assets = data.get("assets", {})
        jobs = data.get("jobs", {})
        versions = data.get("versions", {})
        chat = data.get("chat", {})

        candidates: list[DeletedProject] = []
        for project_id, project in list(projects.items()):
            project_ts = _project_timestamp(project)
            if project_ts is None or project_ts > cutoff:
                continue
            job_ids = [
                job_id
                for job_id, job in jobs.items()
                if job.get("project_id") == project_id and str(job.get("status") or "").strip() in ACTIVE_JOB_STATUSES
            ]
            if job_ids:
                continue
            candidates.append(
                DeletedProject(
                    project_id=project_id,
                    name=str(project.get("name") or project_id),
                    reason=f"older_than_{keep_hours}h",
                    updated_at=str(project.get("updated_at") or project.get("created_at") or ""),
                    job_ids=sorted(job_ids),
                )
            )

        if dry_run:
            live_project_ids.update(str(pid) for pid in projects.keys())
            return {"deleted": candidates}

        for item in candidates:
            deleted.append(item)
            project_id = item.project_id
            projects.pop(project_id, None)
            chat.pop(project_id, None)
            for asset_id in [key for key, value in assets.items() if value.get("project_id") == project_id]:
                assets.pop(asset_id, None)
            for version_id in [key for key, value in versions.items() if value.get("project_id") == project_id]:
                versions.pop(version_id, None)
            for job_id in [key for key, value in jobs.items() if value.get("project_id") == project_id]:
                jobs.pop(job_id, None)
                _append_unique_path(removed_paths, store.RUNTIME / "jobs" / job_id)
            _append_unique_path(removed_paths, store.upload_dir(project_id))
            _append_unique_path(removed_paths, store.project_dir(project_id))

        live_project_ids.update(str(pid) for pid in projects.keys())
        return {"deleted": candidates}

    result = store.mutate(op)
    if dry_run:
        deleted = result["deleted"]
        live_project_ids = set(store.snapshot().get("projects", {}).keys())

    for path in removed_paths:
        _safe_delete_path(Path(path))

    orphans = [] if dry_run else _cleanup_orphans(cutoff, live_project_ids)
    return {
        "ok": True,
        "retention_hours": keep_hours,
        "cutoff": cutoff.isoformat(),
        "deleted_projects": [
            {
                "project_id": item.project_id,
                "name": item.name,
                "reason": item.reason,
                "updated_at": item.updated_at,
                "job_ids": item.job_ids,
            }
            for item in deleted
        ],
        "deleted_count": len(deleted),
        "orphan_paths_removed": orphans,
    }


def startup_prune_if_enabled() -> dict[str, Any] | None:
    if not retention_enabled():
        return None
    return prune_expired_projects()


def cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Prune expired FrameCraft project resources.")
    parser.add_argument("--hours", type=int, default=None, help="Retention window in hours. Default comes from env or 24.")
    parser.add_argument("--dry-run", action="store_true", help="Report what would be deleted without mutating anything.")
    args = parser.parse_args(argv)
    result = prune_expired_projects(hours=args.hours, dry_run=args.dry_run)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def _project_timestamp(project: dict[str, Any]) -> datetime | None:
    for key in ("updated_at", "created_at"):
        value = str(project.get(key) or "").strip()
        parsed = _parse_iso(value)
        if parsed is not None:
            return parsed
    return None


def _parse_iso(value: str) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _append_unique_path(paths: list[str], candidate: Path) -> None:
    resolved = str(candidate.resolve())
    if resolved not in paths:
        paths.append(resolved)


def _cleanup_orphans(cutoff: datetime, live_project_ids: set[str]) -> list[str]:
    removed: list[str] = []
    for root in (store.UPLOADS, store.OUTPUTS):
        root.mkdir(parents=True, exist_ok=True)
        for child in root.iterdir():
            if not child.is_dir():
                continue
            if child.name in live_project_ids:
                continue
            modified_at = datetime.fromtimestamp(child.stat().st_mtime, tz=timezone.utc)
            if modified_at > cutoff:
                continue
            if _safe_delete_path(child):
                removed.append(str(child.resolve()))
    jobs_root = store.RUNTIME / "jobs"
    if jobs_root.is_dir():
        for child in jobs_root.iterdir():
            if not child.is_dir():
                continue
            modified_at = datetime.fromtimestamp(child.stat().st_mtime, tz=timezone.utc)
            if modified_at > cutoff:
                continue
            if _safe_delete_path(child):
                removed.append(str(child.resolve()))
    return removed


def _safe_delete_path(path: Path) -> bool:
    resolved = path.resolve()
    allowed_roots = [store.UPLOADS.resolve(), store.OUTPUTS.resolve(), store.RUNTIME.resolve()]
    if not any(_is_within(resolved, root) and resolved != root for root in allowed_roots):
        return False
    if not resolved.exists():
        return False
    if resolved.is_dir():
        shutil.rmtree(resolved, ignore_errors=True)
    else:
        resolved.unlink(missing_ok=True)
    return True


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


if __name__ == "__main__":
    raise SystemExit(cli())
