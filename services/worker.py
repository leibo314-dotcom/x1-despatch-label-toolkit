"""A fresh process per feature keeps OCR/native PDF crashes out of the web worker."""
import importlib
import json
from pathlib import Path
import sys
from services.jobs import FEATURES

if __name__ == '__main__':
    feature, request_path, output_path = sys.argv[1:]
    inputs = json.loads(Path(request_path).read_text(encoding='utf-8'))
    output = Path(output_path)
    result = importlib.import_module(FEATURES[feature][1]).run(inputs, output)
    (output/'worker-result.json').write_text(json.dumps(result), encoding='utf-8')
