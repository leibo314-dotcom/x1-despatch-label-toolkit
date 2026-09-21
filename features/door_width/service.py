"""Source association and reporting for the independently versioned width rule."""
from collections import Counter
import re
from services.documents import read_sources, require_one_quote
from .rules import RULE_VERSION, compare_widths


def candidate(item):
    return bool(re.search(r'Hinged|French\s+Door',item.frame,re.I) or
                any(p.code in ('V650','V651','V660','V661','V220') for p in item.profiles))


def check_item(doc,item,drawing_reader=None):
    base=dict(item=item.number,description=item.description,source=doc.name,pages=list(item.pages),
              quote=doc.quote,rule_version=RULE_VERSION)
    def stop(reason,status='manual',**evidence):
        return {**base,**evidence,'status':status,'reason':reason}
    if not re.search(r'\bTL40\b|Thermal Linear 40',item.frame,re.I):
        return stop('System is outside the verified TL40 scope.','unsupported')
    if doc.kind!='assembly':
        return stop('An itemised Assembly Detail with an elevation and profile cut list is required. Schedule/aggregate BOM alone cannot verify V661.')
    codes={p.code for p in item.profiles}
    frames=codes&{'V650','V651'}
    if not frames:
        return stop('V650/V651 frame evidence is missing.')
    if len(frames)!=1:
        return stop('Multiple frame opening families in one item are not verified.','unsupported')
    if item.quantity!=1:
        return stop('Per-item versus per-unit profile quantities must be verified for quantities other than one.')
    needed={'V660','V661','V662','V700','V246','V220'}
    if any(p.length is None or p.quantity is None or p.length<=0 or p.quantity<=0 for p in item.profiles if p.code in needed):
        return stop('A required profile-table length or quantity is missing or invalid.')
    if 'V661' not in codes or 'V660' not in codes:
        return stop('V661 rail or V660 panel-count evidence is missing.')
    quantities={code:sum(p.quantity for p in item.profiles if p.code==code) for code in needed}
    french='V220' in codes
    if quantities['V660']!=(4 if french else 2) or (french and quantities['V220']!=1):
        return stop('Multiple doors, unequal groups or an unverified panel arrangement.','unsupported')
    if quantities['V661']!=(4 if french else 2):
        return stop('Unexpected V661 rail count for this panel arrangement.','unsupported')
    if quantities['V662'] and (quantities['V700'] or quantities['V246']):
        return stop('Mixed integrated and coupled adjacency has not been validated.','unsupported')
    if quantities['V700']!=quantities['V246']:
        return stop('V700/V246 quantities disagree; coupling boundaries need confirmation.')
    s,c=quantities['V662'],quantities['V700']
    if s not in (0,1,2) or c not in (0,1,2):
        return stop('The number of sidelights/couplings is outside the verified rule family.','unsupported')
    from .drawing import DrawingUnclear, read_drawing
    drawing_reader = drawing_reader or read_drawing
    try:
        drawing=drawing_reader(doc.path,item.pages[0])
    except (DrawingUnclear,ImportError) as exc:
        return stop(str(exc))
    indices=drawing['door_indices']; widths=drawing['section_widths']
    if len(indices)!=(2 if french else 1):
        return stop('Drawing door count disagrees with V220/V660 profile evidence.',drawing=drawing)
    left_present=indices[0]>0; right_present=indices[-1]<len(widths)-1
    if int(left_present)+int(right_present)!=s+c:
        return stop('Drawing neighbours disagree with profile quantities; possible transom/top light or incomplete BOM.',drawing=drawing)
    boundary='sidelight' if s else 'coupled' if c else 'frame'
    left=boundary if left_present else 'frame'; right=boundary if right_present else 'frame'
    trim=re.search(r'Trim\s+Size\s+\d+(?:\.\d+)?\s*x\s*(\d+(?:\.\d+)?)',item.text,re.I)
    if not trim or abs(float(trim[1])-30-drawing['total_width'])>.01:
        return stop('Raster total width cannot be corroborated by the X1 trim width (30 mm allowance).',drawing=drawing)
    if french:
        adjustment={'frame':0,'sidelight':18,'coupled':-20}
        effective=[widths[indices[0]]+adjustment[left],widths[indices[1]]+adjustment[right]]
        if abs(effective[0]-effective[1])>.01:
            return stop('Unequal effective French-door leaves are outside the verified equal-rail rule.','unsupported',drawing=drawing)
    door_type='french' if french else 'single'
    actual=sorted({p.length for p in item.profiles if p.code=='V661'})
    comparison=compare_widths(door_type,drawing['door_width'],left,right,actual)
    return {**base,**comparison,'door_type':door_type,'system':'TL40',
            'opening':'open_out' if 'V650' in frames else 'open_in',
            'door_width':drawing['door_width'],'left_boundary':left,'right_boundary':right,
            'sidelight_count':int(s),'coupled_count':int(c),'drawing':drawing,
            'reason':'V661 width differs from the candidate rule; review both the construction and rule applicability.' if comparison['status']=='mismatch' else ''}


def check_documents(docs):
    require_one_quote(docs)
    groups={}
    for doc in docs:
        for item in doc.items:
            if candidate(item): groups.setdefault(item.number,[]).append((doc,item))
    results=[]
    for number,entries in sorted(groups.items()):
        assembly=[(doc,item) for doc,item in entries if doc.kind=='assembly']
        if len(assembly)>1:
            results.append(dict(item=number,status='manual',reason='Duplicate Assembly items: remove duplicate/revised sources before checking.'))
            continue
        doc,item=(assembly or entries)[0]
        # Do not silently use one of two contradictory BOMs.
        rail_sets={tuple(sorted(((p.length,p.quantity) for p in entry.profiles if p.code=='V661'),key=repr))
                   for _,entry in entries if any(p.code=='V661' for p in entry.profiles)}
        if len(rail_sets)>1:
            results.append(dict(item=number,status='manual',reason='Conflicting V661 values across the uploaded documents.'))
            continue
        try:
            results.append(check_item(doc,item))
        except Exception:
            # A malformed item must not hide results for other doors.
            results.append(dict(item=number,status='manual',source=doc.name,pages=list(item.pages),
                                reason='Item extraction failed; check its source drawing manually.'))
    counts=Counter(r['status'] for r in results)
    summary={k:counts[k] for k in ('passed','mismatch','manual','unsupported')}
    summary['total']=len(results)
    status=('warning' if counts['mismatch'] else 'manual' if counts['manual'] else
            'unsupported' if counts['unsupported'] else 'success' if results else 'manual')
    return dict(status=status,summary=(f'{len(results)} door items: {counts["passed"]} passed, '
        f'{counts["mismatch"]} mismatches, {counts["manual"]} manual, {counts["unsupported"]} unsupported.'
        if results else 'No verifiable hinged-door items found. Upload the itemised Assembly Detail; no pass has been issued.'),
        counts=summary,details=[r for r in results if r['status']!='passed'],items=results,
        rule_version=RULE_VERSION,
        note='Candidate TL40 width rules validated against quote 50936 only. System deductions are not physical gaps. Height and glass dimensions are not checked.')


def run(inputs,output_dir):
    return check_documents(read_sources(inputs))
