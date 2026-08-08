import os
import re
import shutil
import uuid
from pathlib import Path

from flask import Flask, flash, jsonify, redirect, render_template, request, send_file, url_for
from werkzeug.utils import secure_filename

app = Flask(__name__, template_folder="templates", static_folder=None)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "x1-despatch-label-local")
app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024

TMP_ROOT = Path(os.environ.get("TMPDIR") or os.environ.get("TEMP") or "/tmp")
JOBS_DIR = TMP_ROOT / "x1_despatch_label_jobs"
ALLOWED_EXTENSIONS = {".pdf"}
MAX_BLOB_UPLOAD_BYTES = 100 * 1024 * 1024
BLOB_PATH_RE = re.compile(
    r"^x1-inputs/[0-9a-f]{32}-[A-Za-z0-9][A-Za-z0-9._-]{0,99}\.pdf$"
)
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


def generate_job(paths: dict[str, Path]) -> None:
    from x1_despatch_label_real_diagram import generate_despatch_label

    generate_despatch_label(paths["input_path"], paths["output_path"], paths["workdir"])


@app.get("/")
def index():
    return render_template(
        "index.html",
        blob_upload_enabled=bool(os.environ.get("BLOB_READ_WRITE_TOKEN")),
        max_upload_mb=MAX_BLOB_UPLOAD_BYTES // (1024 * 1024),
    )


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
        generate_job(paths)
    except Exception as exc:
        shutil.rmtree(paths["job_dir"], ignore_errors=True)
        flash(f"Generation failed: {exc}")
        return redirect(url_for("index"))

    return redirect(url_for("result", job_id=job_id, source_name=safe_name))


@app.post("/generate-from-blob")
def generate_from_blob():
    if not os.environ.get("BLOB_READ_WRITE_TOKEN"):
        return jsonify(error="Large-file upload is not available in this environment."), 503

    payload = request.get_json(silent=True) or {}
    blob_pathname = str(payload.get("blob_pathname") or "")
    source_name = secure_filename(str(payload.get("source_name") or ""))

    if not BLOB_PATH_RE.fullmatch(blob_pathname) or ".." in blob_pathname:
        return jsonify(error="Invalid uploaded PDF reference."), 400
    if not source_name or not is_allowed_file(source_name):
        source_name = "uploaded.pdf"

    job_id = uuid.uuid4().hex
    paths = get_job_paths(job_id)
    paths["job_dir"].mkdir(parents=True, exist_ok=True)

    try:
        from vercel.blob import download_file

        download_file(
            blob_pathname,
            paths["input_path"],
            access="private",
            timeout=120,
        )

        if paths["input_path"].stat().st_size > MAX_BLOB_UPLOAD_BYTES:
            raise ValueError("The uploaded PDF is larger than 100 MB.")
        with paths["input_path"].open("rb") as pdf_file:
            if pdf_file.read(5) != b"%PDF-":
                raise ValueError("The uploaded file is not a valid PDF.")

        generate_job(paths)
    except Exception as exc:
        shutil.rmtree(paths["job_dir"], ignore_errors=True)
        return jsonify(error=f"Generation failed: {exc}"), 400
    finally:
        try:
            from vercel.blob import delete

            delete(blob_pathname)
        except Exception:
            app.logger.exception("Could not delete temporary Blob upload %s", blob_pathname)

    return jsonify(
        result_url=url_for("result", job_id=job_id, source_name=source_name)
    )


@app.get("/result/<job_id>")
def result(job_id: str):
    paths = get_job_paths(job_id)
    if not paths["output_path"].is_file():
        flash("This generated file is no longer available.")
        return redirect(url_for("index"))

    source_name = request.args.get("source_name", "Uploaded PDF")
    return render_template(
        "result.html",
        job_id=job_id,
        source_name=source_name,
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
