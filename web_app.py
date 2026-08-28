import os
import sys
import json
import csv
import re
import hashlib
from pathlib import Path
from datetime import datetime
from typing import List, Optional

from flask import Flask, render_template, request, jsonify, redirect, url_for
from threading import Lock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import AppConfig, UserProfile
from pdf_reader import build_company_records, save_to_csv, save_to_json, load_from_json
from templates import render_template as render_email_template, get_builtin_templates, save_builtin_templates, list_templates, TEMPLATES_DIR
from openai_enhancer import enhance_with_openai, enhance_subject_line
from storage import Storage, EmailLog, Campaign
from campaign import EmailCampaign

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "coldemailing_secret_key")

CONFIG_PATH = "config.json"
COMPANIES_JSON = "companies.json"
COMPANIES_CSV = "companies.csv"
OUTPUT_DIR = "output"
CACHE_PATH = os.path.join(OUTPUT_DIR, "openai_cache.json")

_task_registry = {}
_task_lock = Lock()
_task_counter = 0


def _load_openai_cache() -> dict:
    if os.path.exists(CACHE_PATH):
        try:
            with open(CACHE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save_openai_cache(cache: dict) -> None:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2)


def _cache_key(company: str, role: str, user_name: str, skills: str) -> str:
    raw = f"{company}|{role}|{user_name}|{skills}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def _get_cached(cache: dict, key: str) -> Optional[dict]:
    return cache.get(key)


def _set_cached(cache: dict, key: str, value: dict) -> None:
    cache[key] = value
    _save_openai_cache(cache)


def _next_task_id() -> str:
    global _task_counter
    with _task_lock:
        _task_counter += 1
        return f"task_{_task_counter}"


def _run_generate_task(task_id: str, cfg: AppConfig, template_name: str, role: str, use_openai: bool, skip_sent: bool, company_filter: str, limit: int) -> None:
    try:
        campaign = EmailCampaign(cfg, template_name=template_name)
        if not campaign.records and cfg.pdf_path and os.path.exists(cfg.pdf_path):
            campaign.load_companies_from_pdf()

        target_records = campaign.records
        if company_filter:
            target_records = [r for r in target_records if company_filter in r.company.lower() or any(company_filter in e.lower() for e in r.emails)]
        if limit and len(target_records) > limit:
            target_records = target_records[:limit]

        user_vars = {
            "name": cfg.user.name or "Your Name",
            "role": role,
            "company": "{company}",
            "experience_years": cfg.user.experience_years or "3",
            "skills": cfg.user.skills or "Python, JavaScript, React",
            "portfolio": cfg.user.portfolio or "https://yourportfolio.com",
            "linkedin": cfg.user.linkedin or "https://linkedin.com",
            "github": cfg.user.github or "https://github.com",
            "phone": cfg.user.phone or "+923001234567",
            "subject_line": f"Application for {role}",
            "custom_message": f"I am interested in exploring opportunities at your company.",
        }

        cache = _load_openai_cache() if use_openai else {}
        sent_email_set = set(campaign.storage.get_sent_emails()) if skip_sent else set()
        results = []
        skipped = 0
        for rec in target_records:
            for email_addr in rec.emails:
                if skip_sent and email_addr.lower() in sent_email_set:
                    skipped += 1
                    continue

                body = render_email_template(template_name, {**user_vars, "company": rec.company})
                subject = f"Application for {role} at {rec.company}"

                if use_openai and cfg.openai_api_key:
                    key = _cache_key(rec.company, role, cfg.user.name or "", cfg.user.skills or "")
                    cached = _get_cached(cache, key)
                    if cached:
                        body = cached.get("body", body)
                        subject = cached.get("subject", subject)
                    else:
                        try:
                            subject = enhance_subject_line(cfg.openai_api_key, rec.company, role)
                            body = enhance_with_openai(
                                cfg.openai_api_key,
                                rec.company,
                                role,
                                body,
                                {
                                    "name": cfg.user.name,
                                    "skills": cfg.user.skills,
                                    "experience_years": cfg.user.experience_years,
                                    "achievements": cfg.user.achievements,
                                    "portfolio": cfg.user.portfolio,
                                    "linkedin": cfg.user.linkedin,
                                },
                            )
                            _set_cached(cache, key, {"body": body, "subject": subject})
                        except Exception as e:
                            body = body + f"\n\n[Enhancement error: {str(e)}]"

                results.append({
                    "to": email_addr,
                    "company": rec.company,
                    "subject": subject,
                    "body": body,
                    "skipped_duplicate": False,
                })

        os.makedirs(OUTPUT_DIR, exist_ok=True)
        path = os.path.join(OUTPUT_DIR, f"drafts_{cfg.campaign_name}.csv")
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["To", "Company", "Subject", "Body"])
            for d in results:
                writer.writerow([d["to"], d["company"], d["subject"], d["body"]])

        with _task_lock:
            _task_registry[task_id] = {
                "status": "done",
                "result": {
                    "drafted": len(results),
                    "skipped": skipped,
                    "drafts_path": path,
                    "message": f"Generated {len(results)} drafts. {skipped} duplicates skipped.",
                },
            }
    except Exception as e:
        with _task_lock:
            _task_registry[task_id] = {"status": "error", "result": {"message": str(e)}}


def _run_send_task(task_id: str, cfg: AppConfig, template_name: str, role: str, use_openai: bool, skip_sent: bool, batch_size: int) -> None:
    try:
        campaign = EmailCampaign(cfg, template_name=template_name)
        result = campaign.run_campaign(
            role=role,
            use_openai=use_openai,
            dry_run=False,
            skip_sent=skip_sent,
        )
        with _task_lock:
            _task_registry[task_id] = {
                "status": "done",
                "result": {
                    "total": campaign.storage.campaign.total_targets,
                    "sent": result.get("sent", 0),
                    "failed": result.get("failed", 0),
                    "skipped": result.get("skipped", 0),
                    "duplicates_skipped": result.get("duplicates_skipped", 0),
                    "logs": result.get("drafts", []),
                    "message": result.get("message", ""),
                },
            }
    except Exception as e:
        with _task_lock:
            _task_registry[task_id] = {"status": "error", "result": {"message": str(e)}}


# ── helpers ──────────────────────────────────────────────────────────
def get_config() -> AppConfig:
    return AppConfig.load(CONFIG_PATH)


def set_config(cfg: AppConfig) -> None:
    cfg.save(CONFIG_PATH)


def get_records() -> List:
    if os.path.exists(COMPANIES_JSON):
        return load_from_json(COMPANIES_JSON)
    return []


# ── routes ───────────────────────────────────────────────────────────
@app.route("/")
def index():
    cfg = get_config()
    records = get_records()
    storage = Storage(output_dir=OUTPUT_DIR, campaign_name=cfg.campaign_name)
    stats = storage.get_stats()
    return render_template(
        "index.html",
        companies_count=len(records),
        emails_count=sum(len(r.emails) for r in records),
        stats=stats,
        config=cfg,
    )


# ── configuration ────────────────────────────────────────────────────
@app.route("/config", methods=["GET", "POST"])
def config_page():
    cfg = get_config()
    if request.method == "POST":
        form = request.form
        cfg.user.name = form.get("name", cfg.user.name)
        cfg.user.role = form.get("role", cfg.user.role)
        cfg.user.company = form.get("company", cfg.user.company)
        cfg.user.experience_years = form.get("experience_years", cfg.user.experience_years)
        cfg.user.skills = form.get("skills", cfg.user.skills)
        cfg.user.portfolio = form.get("portfolio", cfg.user.portfolio)
        cfg.user.phone = form.get("phone", cfg.user.phone)
        cfg.user.linkedin = form.get("linkedin", cfg.user.linkedin)
        cfg.user.github = form.get("github", cfg.user.github)
        cfg.user.achievements = form.get("achievements", cfg.user.achievements)
        cfg.openai_api_key = form.get("openai_api_key", cfg.openai_api_key)
        cfg.smtp_email = form.get("smtp_email", cfg.smtp_email)
        cfg.smtp_password = form.get("smtp_password", cfg.smtp_password)
        cfg.smtp_server = form.get("smtp_server", cfg.smtp_server)
        cfg.smtp_port = int(form.get("smtp_port", cfg.smtp_port) or 587)
        cfg.pdf_path = form.get("pdf_path", cfg.pdf_path)
        cfg.output_dir = form.get("output_dir", cfg.output_dir)
        cfg.campaign_name = form.get("campaign_name", cfg.campaign_name)
        set_config(cfg)
        return redirect(url_for("config_page") + "?saved=1")
    return render_template("config.html", config=cfg)


# ── extract ──────────────────────────────────────────────────────────
@app.route("/extract", methods=["GET", "POST"])
def extract_page():
    message = ""
    records_count = 0
    emails_count = 0
    if request.method == "POST":
        pdf_file = request.files.get("pdf_file")
        pdf_path = request.form.get("pdf_path", "").strip()
        if pdf_file and pdf_file.filename:
            save_dir = os.path.dirname(os.path.abspath(__file__))
            save_path = os.path.join(save_dir, pdf_file.filename)
            pdf_file.save(save_path)
            pdf_path = save_path
        if not pdf_path or not os.path.exists(pdf_path):
            message = "Please provide a valid PDF file."
        else:
            records = build_company_records(pdf_path)
            save_to_json(records, COMPANIES_JSON)
            save_to_csv(records, COMPANIES_CSV)
            records_count = len(records)
            emails_count = sum(len(r.emails) for r in records)
            message = f"Extracted {records_count} companies with {emails_count} emails."
    return render_template("extract.html", message=message, records_count=records_count, emails_count=emails_count)


# ── companies list ───────────────────────────────────────────────────
@app.route("/companies")
def companies_page():
    records = get_records()
    search = request.args.get("search", "").strip().lower()
    page = int(request.args.get("page", 1))
    per_page = 30
    if search:
        records = [r for r in records if search in r.company.lower() or any(search in e.lower() for e in r.emails)]
    total_pages = max(1, (len(records) + per_page - 1) // per_page)
    page = min(page, total_pages)
    start = (page - 1) * per_page
    page_records = records[start:start + per_page]
    return render_template(
        "companies.html",
        records=page_records,
        search=search,
        page=page,
        total_pages=total_pages,
        total=len(records),
    )


# ── templates ────────────────────────────────────────────────────────
@app.route("/templates")
def templates_page():
    templates = list_templates()
    raw = {}
    for t in templates:
        try:
            raw[t] = render_email_template(t, {})
        except Exception as e:
            raw[t] = f"Error: {e}"
    return render_template("templates.html", templates=templates, raw=raw)


@app.route("/templates/view/<name>")
def template_view(name):
    content = render_email_template(name, {})
    return render_template("template_view.html", name=name, content=content)


@app.route("/templates/edit/<name>", methods=["GET", "POST"])
def template_edit(name):
    path = TEMPLATES_DIR / f"{name}.txt"
    if request.method == "POST":
        content = request.form.get("content", "")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return redirect(url_for("templates_page") + "?saved=1")
    if not path.exists():
        return redirect(url_for("templates_page"))
    content = path.read_text(encoding="utf-8")
    return render_template("template_edit.html", name=name, content=content)


@app.route("/templates/create", methods=["GET", "POST"])
def template_create():
    if request.method == "POST":
        name = request.form.get("name", "").strip().lower().replace(" ", "_")
        if not name:
            return redirect(url_for("templates_page") + "?error=Name required")
        content = request.form.get("content", "")
        path = TEMPLATES_DIR / f"{name}.txt"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return redirect(url_for("templates_page") + "?created=1")
    return render_template("template_create.html")


@app.route("/templates/delete/<name>", methods=["POST"])
def template_delete(name):
    path = TEMPLATES_DIR / f"{name}.txt"
    if path.exists() and name not in ("default", "software_engineer", "custom"):
        path.unlink()
    return redirect(url_for("templates_page") + "?deleted=1")


# ── generate ─────────────────────────────────────────────────────────
@app.route("/generate", methods=["GET", "POST"])
def generate_page():
    cfg = get_config()
    templates = list_templates()
    drafts = []
    error = ""
    message = ""
    task_id = request.args.get("task_id")

    if request.method == "POST":
        role = request.form.get("role", "Software Engineer")
        template_name = request.form.get("template", "default")
        use_openai = request.form.get("use_openai") == "on"
        company_filter = request.form.get("company_filter", "").strip().lower()
        limit = int(request.form.get("limit", 0) or 0)
        skip_sent = request.form.get("skip_sent") == "on"

        tid = _next_task_id()
        with _task_lock:
            _task_registry[tid] = {"status": "running", "result": None}

        import threading
        thread = threading.Thread(
            target=_run_generate_task,
            args=(tid, cfg, template_name, role, use_openai, skip_sent, company_filter, limit),
            daemon=True,
        )
        thread.start()

        return redirect(url_for("generate_page") + f"?task_id={tid}")

    if task_id:
        with _task_lock:
            task = _task_registry.get(task_id)
        if task:
            if task.get("status") == "done":
                result = task.get("result") or {}
                message = result.get("message", "Done")
            elif task.get("status") == "error":
                error = task.get("result", {}).get("message", "Unknown error")

    return render_template("generate.html", templates=templates, drafts=drafts, error=error, message=message, companies_count=len(get_records()), task_id=task_id)


# ── send campaign ────────────────────────────────────────────────────
@app.route("/send", methods=["GET", "POST"])
def send_page():
    cfg = get_config()
    templates = list_templates()
    result = None
    error = ""
    task_id = request.args.get("task_id")

    if request.method == "POST":
        role = request.form.get("role", "Software Engineer")
        template_name = request.form.get("template", "default")
        use_openai = request.form.get("use_openai") == "on"
        batch_size = int(request.form.get("batch_size", 10) or 10)
        skip_sent = request.form.get("skip_sent") == "on"

        tid = _next_task_id()
        with _task_lock:
            _task_registry[tid] = {"status": "running", "result": None}

        import threading
        thread = threading.Thread(
            target=_run_send_task,
            args=(tid, cfg, template_name, role, use_openai, skip_sent, batch_size),
            daemon=True,
        )
        thread.start()

        return redirect(url_for("send_page") + f"?task_id={tid}")

    if task_id:
        with _task_lock:
            task = _task_registry.get(task_id)
        if task:
            if task.get("status") == "done":
                result = task.get("result")
            elif task.get("status") == "error":
                error = task.get("result", {}).get("message", "Unknown error")

    return render_template(
        "send.html",
        templates=templates,
        error=error,
        config=cfg,
        result=result,
        companies_count=len(get_records()),
        task_id=task_id,
    )


# ── stats ────────────────────────────────────────────────────────────
@app.route("/stats")
def stats_page():
    storage = Storage(output_dir=OUTPUT_DIR, campaign_name=get_config().campaign_name)
    campaign = storage.campaign
    return render_template(
        "stats.html",
        stats=storage.get_stats(),
        logs=campaign.logs,
        campaign=campaign,
    )


# ── API helpers ──────────────────────────────────────────────────────
@app.route("/api/tasks/<task_id>")
def api_task_status(task_id):
    with _task_lock:
        task = _task_registry.get(task_id)
    if not task:
        return jsonify({"error": "Task not found"}), 404
    return jsonify(task)


@app.route("/api/config")
def api_config():
    cfg = get_config()
    return jsonify({
        "user": cfg.user.__dict__,
        "openai_api_key": cfg.openai_api_key,
        "smtp_email": cfg.smtp_email,
        "smtp_password": cfg.smtp_password,
        "smtp_server": cfg.smtp_server,
        "smtp_port": cfg.smtp_port,
        "pdf_path": cfg.pdf_path,
        "output_dir": cfg.output_dir,
        "campaign_name": cfg.campaign_name,
    })


@app.route("/api/templates", methods=["POST"])
def api_create_template():
    name = request.json.get("name", "").strip().lower().replace(" ", "_")
    content = request.json.get("content", "")
    if not name:
        return jsonify({"error": "Name required"}), 400
    path = TEMPLATES_DIR / f"{name}.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return jsonify({"success": True, "name": name})


@app.route("/api/templates/<name>", methods=["DELETE"])
def api_delete_template(name):
    path = TEMPLATES_DIR / f"{name}.txt"
    if path.exists() and name not in ("default", "software_engineer", "custom"):
        path.unlink()
        return jsonify({"success": True})
    return jsonify({"error": "Cannot delete system template"}), 400


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
