"""Shared upload storage for independent requests across serverless instances.

Only new two-output jobs use private Blob storage; legacy delivery jobs retain
their original local path. Each PDF is stored and recovered independently.
"""
import logging
import os
from uuid import uuid4

LOG = logging.getLogger(__name__)
PREFIX = 'x1-item-label-jobs'


def remote_path(paths, filename):
    return f"{PREFIX}/{paths['job_dir'].name}/{filename}"


def persist(paths, path):
    if not os.environ.get('BLOB_READ_WRITE_TOKEN'):
        return
    from vercel.blob import put
    with path.open('rb') as stream:
        put(remote_path(paths, path.name), stream, access='private',
            content_type='application/pdf', overwrite=True, cache_control_max_age=60)


def restore(paths, path):
    if path.is_file():
        return True
    if not os.environ.get('BLOB_READ_WRITE_TOKEN'):
        return False
    from vercel.blob import download_file
    paths['job_dir'].mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(uuid4().hex+'.download')
    try:
        download_file(remote_path(paths, path.name), temporary, access='private', timeout=120)
        temporary.replace(path)
        return True
    except Exception:
        return False
    finally:
        temporary.unlink(missing_ok=True)
