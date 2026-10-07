"""Independent output jobs: no common generation lock, parser, renderer or error state."""
import json
import logging
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

LOG = logging.getLogger(__name__)


def run_output(paths, kind, generate_docket, retry=False):
    from services.job_storage import persist, restore
    target = paths['output_path'] if kind=='docket' else paths['labels_path']
    state_path = paths['job_dir']/f'{kind}_status.json'
    if restore(paths, target):
        # A previous request may have rendered locally but failed to upload.
        if retry:
            try:
                persist(paths, target)
            except Exception:
                return {'status': 'error', 'error': 'Could not save this PDF. Please retry.'}
        return {'status': 'ready'}
    if state_path.is_file() and not retry:
        try:
            previous = json.loads(state_path.read_text(encoding='utf-8'))
            if previous.get('status')=='error':
                return previous
        except (OSError, ValueError):
            pass
    try:
        # Each request owns its scratch files; a failed generator cannot remove
        # the source, the other output, or another request's work directory.
        with TemporaryDirectory(prefix=kind+'-', dir=paths['job_dir']) as folder:
            root = Path(folder)
            output = root/'output.pdf'
            if kind=='docket':
                generate_docket(dict(paths, output_path=output, workdir=root/'work'))
                metadata = {}
            else:
                from features.item_labels.service import generate_item_labels
                metadata = generate_item_labels(paths['input_path'], output, root/'work')
            output.replace(target)
            persist(paths, target)
        result = dict(status='ready', **metadata)
    except Exception as exc:
        LOG.exception('%s generation failed', kind)
        result = {'status': 'error', 'error': str(exc) if isinstance(exc, ValueError)
                  else 'This PDF could not be generated. Please retry.'}
    try:
        temporary = state_path.with_name(kind+'-'+uuid4().hex+'.json')
        temporary.write_text(json.dumps(result), encoding='utf-8')
        temporary.replace(state_path)
    except OSError:
        LOG.exception('Could not cache %s status', kind)
    return result
