"""Optional checks only. Never imports, calls, or gates the delivery generator."""
import json
import logging
from pathlib import Path
import threading
import uuid

LOG = logging.getLogger(__name__)
_lock = threading.Lock()


def unavailable(reason):
    return {'status': 'manual', 'summary': 'Needs review', 'details': [{'reason': reason}]}


def run_checks(pdf_path, job_dir, retry=False):
    # New cache key so earlier width/gap results are never returned or run.
    cache = Path(job_dir) / 'colour_checks.json'
    with _lock:
        if cache.is_file() and not retry:
            try:
                return json.loads(cache.read_text(encoding='utf-8'))
            except (OSError, ValueError):
                pass
        try:
            from services.documents import read_document
            documents = (read_document(Path(pdf_path), 'Uploaded PDF'),)
        except Exception:
            LOG.exception('Could not read check source')
            result = {name: unavailable('Could not read the source information. Please check the PDF manually.')
                      for name in ('colour',)}
        else:
            result = {}
            try:
                from features.colour.service import check_colours
                result['colour'] = check_colours(documents)
            except Exception:
                LOG.exception('Colour check failed')
                result['colour'] = unavailable('Colour check could not complete. Please review the colours manually.')
        # Failure to cache a check must not hide its current result.
        try:
            temporary = cache.with_name('checks-' + uuid.uuid4().hex + '.json')
            temporary.write_text(json.dumps(result), encoding='utf-8')
            temporary.replace(cache)
        except OSError:
            LOG.exception('Could not cache check results')
        return result
