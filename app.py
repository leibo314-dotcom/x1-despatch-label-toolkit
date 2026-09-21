import io
import os
from pathlib import Path
import re
from flask import Flask, abort, flash, jsonify, redirect, render_template, request, send_file, url_for
from werkzeug.utils import secure_filename
from services.jobs import FEATURES, JobStore, run_feature

app = Flask(__name__, template_folder='templates', static_folder='public', static_url_path='')
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'x1-despatch-label-local')
app.config['MAX_CONTENT_LENGTH'] = 25 * 1024 * 1024
MAX_BLOB_UPLOAD_BYTES = 100 * 1024 * 1024
MAX_FILES = 3
BLOB_PATH_RE = re.compile(r'^x1-inputs/[0-9a-f]{32}-[A-Za-z0-9][A-Za-z0-9._-]{0,99}\.pdf$')
store = JobStore(Path(os.environ.get('TMPDIR') or os.environ.get('TEMP') or '/tmp'),
                 remote=bool(os.environ.get('BLOB_READ_WRITE_TOKEN')))


def validate_pdf(name, content):
    if Path(name).suffix.lower() != '.pdf' or not content.startswith(b'%PDF-'):
        raise ValueError('Only valid PDF files are supported.')
    if len(content) > MAX_BLOB_UPLOAD_BYTES:
        raise ValueError('The combined upload limit is 100 MB.')


@app.get('/')
def index():
    return render_template('index.html', blob_upload_enabled=store.remote,
                           max_upload_mb=100 if store.remote else 25)


@app.errorhandler(413)
def too_large(error):
    return render_template('error.html', message='The local upload limit is 25 MB in total.'), 413


@app.errorhandler(FileNotFoundError)
def missing_job(error):
    if request.path.startswith('/api/'):
        return jsonify(error='This job is no longer available. Please upload again.'), 404
    return render_template('error.html', message='This job is no longer available. Please upload again.'), 404


@app.post('/generate')
def generate():
    uploaded = request.files.getlist('pdf_file')
    try:
        if not 1 <= len(uploaded) <= MAX_FILES:
            raise ValueError('Choose one to three PDFs from the same quote.')
        files = []
        for upload in uploaded:
            name = secure_filename(upload.filename or '')
            content = upload.read()
            validate_pdf(name, content)
            files.append((name, content))
        job_id = store.create(files)
    except ValueError as exc:
        flash(str(exc))
        return redirect(url_for('index'))
    return redirect(url_for('result', job_id=job_id))


@app.post('/generate-from-blob')
def generate_from_blob():
    if not store.remote:
        return jsonify(error='Large-file upload is not available here.'), 503
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify(error='Invalid upload request.'), 400
    uploads = payload.get('files', [payload])
    if not isinstance(uploads, list) or not 1 <= len(uploads) <= MAX_FILES:
        return jsonify(error='Choose one to three PDFs from the same quote.'), 400
    paths = []
    for item in uploads:
        pathname = str(item.get('blob_pathname', '')) if isinstance(item, dict) else ''
        if not BLOB_PATH_RE.fullmatch(pathname) or '..' in pathname or pathname in paths:
            return jsonify(error='Invalid uploaded PDF reference.'), 400
        paths.append(pathname)
    try:
        from vercel.blob import get
        files = []
        total = 0
        for item, pathname in zip(uploads, paths):
            content = get(pathname, access='private', use_cache=False, timeout=120).content
            name = secure_filename(str(item.get('source_name') or 'uploaded.pdf'))
            validate_pdf(name, content)
            total += len(content)
            if total > MAX_BLOB_UPLOAD_BYTES:
                raise ValueError('The combined upload limit is 100 MB.')
            files.append((name, content))
        job_id = store.create(files)
    except Exception:
        app.logger.exception('Could not store uploaded PDFs')
        return jsonify(error='Could not prepare the uploaded PDFs. Check the files and try again.'), 400
    finally:
        try:
            from vercel.blob import delete
            delete(paths)
        except Exception:
            app.logger.exception('Could not remove temporary uploads')
    return jsonify(result_url=url_for('result', job_id=job_id))


@app.get('/result/<job_id>')
def result(job_id):
    manifest = store.json(job_id, 'manifest.json')
    return render_template('result.html', job_id=job_id, features=FEATURES,
                           inputs=manifest['inputs'], results=store.results(job_id))


@app.post('/api/jobs/<job_id>/<feature>/run')
def feature_run(job_id, feature):
    if feature not in FEATURES:
        abort(404)
    return jsonify(run_feature(store, job_id, feature))


@app.get('/api/jobs/<job_id>/<feature>/report')
def feature_report(job_id, feature):
    if feature not in FEATURES:
        abort(404)
    content = store.read(job_id, f'{feature}/result.json')
    return send_file(io.BytesIO(content), mimetype='application/json', as_attachment=True,
                     download_name=f'{feature}_report.json')


@app.get('/download/<job_id>')
def download(job_id):
    result = store.json(job_id, 'delivery/result.json')
    if result.get('status') != 'success' or result.get('artifact') != 'despatch_label.pdf':
        abort(404)
    content = store.read(job_id, 'delivery/despatch_label.pdf')
    return send_file(io.BytesIO(content), as_attachment=True, download_name='despatch_label.pdf', mimetype='application/pdf')


@app.post('/jobs/<job_id>/delete')
def delete_job(job_id):
    store.delete(job_id)
    flash('Uploaded files and tool results deleted.')
    return redirect(url_for('index'))


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=int(os.environ.get('PORT', '5000')), debug=False)
