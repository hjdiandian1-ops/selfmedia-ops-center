# -*- coding: utf-8 -*-
"""
成品库 Router (/api/outputs/*)
"""
import os

from fastapi import APIRouter, HTTPException

import core

router = APIRouter(tags=["成品库"])


@router.get("/api/outputs/{job_id}")
def api_outputs(job_id: str):
    """列出 outputs/<job_id>/ 下的产出文件树（md/html/png/jpg 等）。"""
    jdir = os.path.join(core.OUTPUTS_DIR, job_id)
    if not os.path.isdir(jdir):
        return {"job_id": job_id, "files": []}
    files = []
    for root, _dirs, names in os.walk(jdir):
        for n in sorted(names):
            p = os.path.join(root, n)
            rel = os.path.relpath(p, jdir)
            files.append({
                "rel": rel.replace(os.sep, "/"),
                "size": os.path.getsize(p),
                "kind": ("img" if n.lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".gif"))
                         else "html" if n.lower().endswith((".html", ".htm"))
                         else "md" if n.lower().endswith(".md")
                         else "other"),
            })
    return {"job_id": job_id, "files": files}


@router.get("/api/outputs/{job_id}/file")
def api_output_file(job_id: str, rel: str):
    """读取产出文件文本内容（md/txt 等）。图片与 html 用 /assets/outputs/... 静态 URL。"""
    rel = rel.replace("\\", "/")
    if rel.startswith("/") or ".." in rel.split("/"):
        raise HTTPException(status_code=400, detail="非法路径")
    jdir = os.path.join(core.OUTPUTS_DIR, job_id)
    full = os.path.normpath(os.path.join(jdir, rel))
    if not full.startswith(os.path.normpath(jdir)) or not os.path.isfile(full):
        raise HTTPException(status_code=404, detail="文件不存在")
    try:
        return {"job_id": job_id, "rel": rel, "content": core.read_text(full)[:8000]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
