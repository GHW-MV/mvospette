from __future__ import annotations

import io
import logging
import os
import re
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from fastapi import Depends, FastAPI, Header, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from jinja2 import Environment, StrictUndefined
from pydantic import BaseModel, Field

BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATE_PATH = BASE_DIR / "data" / "boilerplate_templates.yaml"
PRIMARY_TOKEN_ENV = "TERRITORY_API_TOKEN"
FALLBACK_TOKEN_ENV = "BOILERPLATE_API_TOKEN"

logger = logging.getLogger("boilerplate_api")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

ALLOWED_ORIGINS = [
    "https://app.mvospette.com",
    "http://localhost:9000",
    "http://127.0.0.1:9000",
]


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip())
    return slug.strip("-").lower()


def pascal_case(value: str) -> str:
    return "".join(part.capitalize() for part in re.split(r"[^a-zA-Z0-9]", value) if part)


env = Environment(undefined=StrictUndefined, autoescape=False, trim_blocks=True, lstrip_blocks=True)
env.filters["slugify"] = slugify
env.filters["pascal"] = pascal_case


class TemplateDefinition(BaseModel):
    id: str
    name: str
    version: str
    category: str
    language: str
    description: str
    tags: List[str] = Field(default_factory=list)
    defaults: Dict[str, Any] = Field(default_factory=dict)
    files: Dict[str, str]


class GenerateRequest(BaseModel):
    template_id: str = Field(..., description="ID of the template to render")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Values injected into templates")
    mode: str = Field("zip", pattern="^(zip|files)$", description="Return a zip archive or JSON file map")


def get_token() -> str:
    token = os.getenv(PRIMARY_TOKEN_ENV, "").strip() or os.getenv(FALLBACK_TOKEN_ENV, "").strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Missing API token; set env var {PRIMARY_TOKEN_ENV}",
        )
    return token


def auth_dependency(token: str = Depends(get_token), authorization: str = Header(None)) -> None:
    provided = ""
    if authorization:
        parts = authorization.split()
        provided = parts[-1] if parts else ""
    if not provided:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing token")
    if provided != token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


def load_templates() -> Dict[str, TemplateDefinition]:
    if not TEMPLATE_PATH.exists():
        raise RuntimeError(f"Template catalog not found at {TEMPLATE_PATH}")
    raw = yaml.safe_load(TEMPLATE_PATH.read_text(encoding="utf-8")) or []
    templates: Dict[str, TemplateDefinition] = {}
    for entry in raw:
        tmpl = TemplateDefinition(**entry)
        templates[tmpl.id] = tmpl
    return templates


TEMPLATES = load_templates()

app = FastAPI(title="Boilerplate Factory", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request, call_next):
    start = datetime.utcnow()
    response = None
    try:
        response = await call_next(request)
        return response
    finally:
        duration_ms = (datetime.utcnow() - start).total_seconds() * 1000
        logger.info(
            "request",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status": getattr(response, "status_code", "n/a"),
                "duration_ms": round(duration_ms, 2),
                "client": request.client.host if request.client else "n/a",
            },
        )


def render_template(template: TemplateDefinition, parameters: Dict[str, Any]) -> Dict[str, str]:
    context = {
        **template.defaults,
        **parameters,
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "template_id": template.id,
        "template_version": template.version,
    }
    rendered: Dict[str, str] = {}
    for path, contents in template.files.items():
        try:
            rendered[path] = env.from_string(contents).render(**context)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Failed rendering {path}: {exc}") from exc
    return rendered


def make_archive(files: Dict[str, str]) -> io.BytesIO:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path, contents in files.items():
            archive.writestr(path, contents)
    buffer.seek(0)
    return buffer


def filter_templates(language: Optional[str], tag: Optional[str], category: Optional[str]) -> List[TemplateDefinition]:
    results = []
    for tmpl in TEMPLATES.values():
        if language and tmpl.language.lower() != language.lower():
            continue
        if category and tmpl.category.lower() != category.lower():
            continue
        if tag and tag.lower() not in {t.lower() for t in tmpl.tags}:
            continue
        results.append(tmpl)
    return results


@app.get("/health", dependencies=[Depends(auth_dependency)])
def health() -> dict:
    updated_at = None
    try:
        updated_at = TEMPLATE_PATH.stat().st_mtime
    except OSError:
        updated_at = None
    return {"status": "ok", "templates": len(TEMPLATES), "template_catalog": str(TEMPLATE_PATH), "updated_at": updated_at}


@app.get("/templates", dependencies=[Depends(auth_dependency)])
def list_templates(
    language: Optional[str] = Query(None, description="Filter by language (python, node, terraform, sop)"),
    tag: Optional[str] = Query(None, description="Filter by tag"),
    category: Optional[str] = Query(None, description="Filter by category (backend, ops, process)"),
) -> dict:
    matches = filter_templates(language, tag, category)
    payload = [
        {
            "id": tmpl.id,
            "name": tmpl.name,
            "version": tmpl.version,
            "language": tmpl.language,
            "category": tmpl.category,
            "description": tmpl.description,
            "tags": tmpl.tags,
            "defaults": tmpl.defaults,
            "files": list(tmpl.files.keys()),
        }
        for tmpl in matches
    ]
    return {"items": payload, "count": len(payload)}


@app.get("/templates/{template_id}", dependencies=[Depends(auth_dependency)])
def get_template(template_id: str) -> dict:
    tmpl = TEMPLATES.get(template_id)
    if not tmpl:
        raise HTTPException(status_code=404, detail="Template not found")
    return {
        "id": tmpl.id,
        "name": tmpl.name,
        "version": tmpl.version,
        "language": tmpl.language,
        "category": tmpl.category,
        "description": tmpl.description,
        "tags": tmpl.tags,
        "defaults": tmpl.defaults,
        "files": list(tmpl.files.keys()),
    }


@app.post("/generate")
def generate_boilerplate(request: GenerateRequest, _: None = Depends(auth_dependency)):
    tmpl = TEMPLATES.get(request.template_id)
    if not tmpl:
        raise HTTPException(status_code=404, detail="Template not found")
    rendered_files = render_template(tmpl, request.parameters)
    metadata = {
        "template_id": tmpl.id,
        "template_version": tmpl.version,
        "generated_at": datetime.utcnow().isoformat() + "Z",
    }
    if request.mode == "files":
        return JSONResponse({"metadata": metadata, "files": rendered_files})
    archive = make_archive(rendered_files)
    filename = f"{tmpl.id}-{tmpl.version}.zip"
    headers = {
        "X-Template-ID": tmpl.id,
        "X-Template-Version": tmpl.version,
        "Content-Disposition": f'attachment; filename="{filename}"',
    }
    return StreamingResponse(archive, media_type="application/zip", headers=headers)
