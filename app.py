import os
import shutil
import uuid
from pathlib import Path

from flask import Flask, flash, redirect, render_template, request, send_file, url_for
from werkzeug.utils import secure_filename

app = Flask(__name__, template_folder="templates", static_folder=None)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "x1-despatch-label-local")
app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024

TMP_ROOT = Path(os.environ.get("TMPDIR") or os.environ.get("TEMP") or "/tmp")
JOBS_DIR = TMP_ROOT / "x1_despatch_label_jobs"
ALLOWED_EXTENSIONS = {".pdf"}
JOBS_DIR.mkdir(parents=True, exist_ok=True)


def is_allowed_file(filename: str) -> bool:
    return Path(filename).suffix.lower() in ALLOWED_EXTENSIONS


def get_job_paths(job_id: str) -> dict[str, Path]:
    job_dir = JOBS_DIR / job_id
    return {
        "job_dir": job_dir,
        "input_path": job_dir / "input.pdf",
        "output_path": job_dir / "despatch_label.pdf",
        "workdir": job_dir / "work",
    }


def format_item_numbers(item_numbers: list[int]) -> str:
    numbers = sorted(set(item_numbers))
    if not numbers:
        return ""

    ranges: list[str] = []
    start = previous = numbers[0]
    for number in numbers[1:]:
        if number == previous + 1:
            previous = number
            continue
        ranges.append(str(start) if start == previous else f"{start}-{previous}")
        start = previous = number
    ranges.append(str(start) if start == previous else f"{start}-{previous}")
    return ", ".join(ranges)


def build_colour_check(items) -> dict:
    colour_groups: dict[str, dict] = {}
    missing_items: list[int] = []

    for item in items:
        colour = " ".join(item.colour.split()).strip()
        if not colour:
            missing_items.append(item.no)
            continue

        key = colour.casefold()
        group = colour_groups.setdefault(key, {"colour": colour, "items": []})
        group["items"].append(item.no)

    groups = []
    for group in colour_groups.values():
        groups.append({
            "colour": group["colour"],
            "items": format_item_numbers(group["items"]),
        })

    has_mismatch = len(groups) > 1
    has_missing = bool(missing_items)
    return {
        "status": "warning" if has_mismatch or has_missing else "success",
        "has_mismatch": has_mismatch,
        "has_missing": has_missing,
        "item_count": len(items),
        "colour_count": len(groups),
        "groups": groups,
        "missing_items": format_item_numbers(missing_items),
    }


@app.get("/")
def index():
    return render_template("index.html")


@app.post("/generate")
def generate():
    uploaded_file = request.files.get("pdf_file")
    if not uploaded_file or not uploaded_file.filename:
        flash("Please choose a PDF file first.")
        return redirect(url_for("index"))

    safe_name = secure_filename(uploaded_file.filename)
    if not is_allowed_file(safe_name):
        flash("Only PDF files are supported.")
        return redirect(url_for("index"))

    job_id = uuid.uuid4().hex
    paths = get_job_paths(job_id)
    paths["job_dir"].mkdir(parents=True, exist_ok=True)
    uploaded_file.save(paths["input_path"])

    try:
        from x1_despatch_label_real_diagram import generate_despatch_label

        generate_despatch_label(paths["input_path"], paths["output_path"], paths["workdir"])
    except Exception as exc:
        shutil.rmtree(paths["job_dir"], ignore_errors=True)
        flash(f"Generation failed: {exc}")
        return redirect(url_for("index"))

    return redirect(url_for("result", job_id=job_id, source_name=safe_name))


@app.get("/result/<job_id>")
def result(job_id: str):
    paths = get_job_paths(job_id)
    if not paths["output_path"].is_file():
        flash("This generated file is no longer available.")
        return redirect(url_for("index"))

    source_name = request.args.get("source_name", "Uploaded PDF")
    colour_check = None
    try:
        from x1_despatch_label_real_diagram import parse_items

        colour_check = build_colour_check(parse_items(paths["input_path"]))
    except Exception:
        # Label generation has already succeeded, so a secondary colour check
        # must not prevent the user from downloading the PDF.
        colour_check = None
    return render_template(
        "result.html",
        job_id=job_id,
        source_name=source_name,
        colour_check=colour_check,
    )


@app.get("/download/<job_id>")
def download(job_id: str):
    paths = get_job_paths(job_id)
    if not paths["output_path"].is_file():
        flash("This generated file is no longer available.")
        return redirect(url_for("index"))

    source_name = request.args.get("source_name", "despatch_label")
    download_name = f"{Path(source_name).stem}_despatch_label.pdf"
    return send_file(
        paths["output_path"],
        as_attachment=True,
        download_name=download_name,
        mimetype="application/pdf",
    )


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "5000")),
        debug=False,
    )
