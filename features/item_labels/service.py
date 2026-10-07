"""The label pipeline shares only the source file with delivery."""
from pathlib import Path
from .source import read_labels
from .extract import extract_diagram_images
from .render import make_labels


def generate_item_labels(input_path, output_path, workdir):
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    quote, kind, items = read_labels(Path(input_path))
    diagrams = extract_diagram_images(Path(input_path), items, workdir/'diagrams', kind)
    make_labels(items, diagrams, Path(output_path), quote)
    return {'quote': quote, 'items': len(items), 'pages': (len(items)+9)//10}
