"""Storage and feature dispatch. Features own independent outputs and failures."""
import json
import logging
from pathlib import Path
import re
import tempfile
import uuid
import subprocess
import sys

FEATURES = {
    'delivery': ('Delivery docket', 'features.delivery.service'),
    'colour': ('Colour check', 'features.colour.service'),
    'door_width': ('Door panel width', 'features.door_width.service'),
}
LOG = logging.getLogger(__name__)


class JobStore:
    def __init__(self, root, remote=False):
        self.root = Path(root)
        self.remote = remote

    def key(self, job_id, relative):
        if not re.fullmatch(r'[0-9a-f]{32}', job_id):
            raise FileNotFoundError('Invalid job reference.')
        if '..' in Path(relative).parts or Path(relative).is_absolute():
            raise ValueError('Invalid artifact path.')
        return f'x1-test-jobs/{job_id}/{relative}'

    def write(self, job_id, relative, content, mime='application/json'):
        key = self.key(job_id, relative)
        if self.remote:
            from vercel.blob import put
            put(key, content, access='private', content_type=mime,
                add_random_suffix=False, overwrite=True, cache_control_max_age=60)
        else:
            path = self.root / key
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_name(path.name + '.' + uuid.uuid4().hex)
            temporary.write_bytes(content)
            temporary.replace(path)

    def read(self, job_id, relative):
        key = self.key(job_id, relative)
        if self.remote:
            from vercel.blob import get, BlobNotFoundError
            try:
                return get(key, access='private', use_cache=False).content
            except BlobNotFoundError as exc:
                raise FileNotFoundError('Job or result is no longer available.') from exc
        return (self.root / key).read_bytes()

    def json(self, job_id, relative):
        return json.loads(self.read(job_id, relative))

    def write_json(self, job_id, relative, value):
        self.write(job_id, relative, json.dumps(value, ensure_ascii=False).encode('utf-8'))

    def create(self, files):
        job_id = uuid.uuid4().hex
        inputs = []
        for i, (name, content) in enumerate(files):
            relative = f'inputs/{i}.pdf'
            self.write(job_id, relative, content, 'application/pdf')
            inputs.append({'name': name, 'relative': relative})
        self.write_json(job_id, 'manifest.json', {'inputs': inputs})
        return job_id

    def results(self, job_id):
        self.json(job_id, 'manifest.json')
        results = {}
        for feature in FEATURES:
            try:
                results[feature] = self.json(job_id, f'{feature}/result.json')
            except FileNotFoundError:
                results[feature] = {'status': 'pending', 'summary': 'Ready to run.'}
        return results

    def delete(self, job_id):
        manifest = self.json(job_id, 'manifest.json')
        if self.remote:
            from vercel.blob import delete
            paths = ['manifest.json'] + [i['relative'] for i in manifest['inputs']]
            paths += [f'{f}/result.json' for f in FEATURES] + ['delivery/despatch_label.pdf']
            delete([self.key(job_id, p) for p in paths])
        else:
            import shutil
            target = (self.root / self.key(job_id, '')).resolve()
            if target.parent != (self.root / 'x1-test-jobs').resolve():
                raise ValueError('Invalid job directory.')
            shutil.rmtree(target)


def execute_feature(feature, inputs, output):
    request_path = output.parent / 'worker-input.json'
    request_path.write_text(json.dumps(inputs, default=str), encoding='utf-8')
    subprocess.run([sys.executable, '-m', 'services.worker', feature, str(request_path), str(output)],
                   cwd=Path(__file__).resolve().parent.parent, check=True, timeout=150,
                   capture_output=True, text=True)
    return json.loads((output/'worker-result.json').read_text(encoding='utf-8'))


def run_feature(store, job_id, feature):
    if feature not in FEATURES:
        raise KeyError(feature)
    manifest = store.json(job_id, 'manifest.json')
    try:
        with tempfile.TemporaryDirectory(prefix=f'x1-{feature}-') as temporary:
            directory = Path(temporary)
            inputs = []
            for index, item in enumerate(manifest['inputs']):
                path = directory / f'input-{index}.pdf'
                path.write_bytes(store.read(job_id, item['relative']))
                inputs.append({'name': item['name'], 'path': path})
            output = directory / 'output'
            output.mkdir()
            result = execute_feature(feature, inputs, output)
            artifact = result.get('artifact')
            if artifact:
                if Path(artifact).name != artifact:
                    raise ValueError('Invalid generated artifact.')
                store.write(job_id, f'{feature}/{artifact}', (output/artifact).read_bytes(), 'application/pdf')
    except Exception:
        LOG.exception('Feature %s failed for job %s', feature, job_id)
        result = {'status': 'error', 'summary': 'This feature could not complete. Retry it or check the source PDF. The other tools can continue.', 'details': []}
    store.write_json(job_id, f'{feature}/result.json', result)
    return result
