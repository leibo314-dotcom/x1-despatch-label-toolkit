import re
from services.documents import read_sources, require_one_quote


def check_colours(documents):
    require_one_quote(documents)
    colours={}
    unresolved=[]
    item_numbers=set()
    for doc in documents:
        for item in doc.items:
            if not item.frame:
                continue
            item_numbers.add(item.number)
            value=' '.join(item.colour.split())
            evidence=dict(item=item.number,source=doc.name,pages=list(item.pages),colour=value)
            if not value or re.search(r'\b\d+\s+of\b|standard\s+\d+\s+colou?rs|TBC|TBD',value,re.I):
                unresolved.append({**evidence,'reason':'Actual finish is missing or a generic colour selection.'})
            else:
                key=value.casefold()
                colours.setdefault(key,{'colour':value,'items':set(),'sources':set()})
                colours[key]['items'].add(item.number)
                colours[key]['sources'].add(doc.name)
    groups=[{**v,'items':sorted(v['items']),'sources':sorted(v['sources'])} for v in colours.values()]
    if not item_numbers:
        return dict(status='manual',summary='No item-level colour information was found.',details=[])
    mismatch=len(groups)>1
    status='warning' if mismatch else 'manual' if unresolved else 'success'
    return dict(status=status,
        summary=(f'{len(groups)} different named finishes need review; confirm against the specification.' if mismatch
                 else 'Some actual finishes could not be verified.' if unresolved else 'All named item finishes match.'),
        item_count=len(item_numbers),groups=groups,details=unresolved)


def run(inputs, output_dir):
    return check_colours(read_sources(inputs))
