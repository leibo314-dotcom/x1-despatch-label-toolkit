from pathlib import Path
from services.documents import read_sources, require_one_quote


def run(inputs, output_dir: Path):
    from .renderer import generate_despatch_label
    docs=read_sources(inputs)
    require_one_quote(docs)
    schedules=[d for d in docs if d.kind=='schedule']
    assemblies=[d for d in docs if d.kind=='assembly']
    choices=schedules or assemblies
    if len(choices)!=1:
        return dict(status='manual',summary='Choose one Schedule (preferred) or one Assembly PDF for the docket.',details=[])
    source=choices[0]
    generate_despatch_label(source.path,output_dir/'despatch_label.pdf',output_dir/'work')
    return dict(status='success',summary='Delivery docket ready.',
                details=[{'source':source.name,'quote':source.quote}],artifact='despatch_label.pdf')
