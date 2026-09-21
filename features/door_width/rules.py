from decimal import Decimal

RULE_VERSION='tl40-width-50936-v1'
TOLERANCE=Decimal('0.01')


def calculate_width(door_type, width, left, right):
    if door_type not in ('single','french'):
        raise ValueError('Door family has no verified rule.')
    if left not in ('frame','sidelight','coupled') or right not in ('frame','sidelight','coupled'):
        raise ValueError('Unknown boundary.')
    if {left,right}=={'sidelight','coupled'}:
        raise ValueError('Mixed integrated and coupled boundaries are not verified.')
    w=Decimal(str(width))
    if not w.is_finite() or w<=0:
        raise ValueError('Door width must be positive.')
    s=(left,right).count('sidelight'); c=(left,right).count('coupled')
    expected=(w-(204 if door_type=='single' else 328)+18*s-20*c)/(1 if door_type=='single' else 2)
    if expected<=0:
        raise ValueError('Dimensions are outside the rule range.')
    return expected


def compare_widths(door_type, width, left, right, actual):
    expected=calculate_width(door_type,width,left,right)
    differences=[Decimal(str(value))-expected for value in actual]
    return dict(expected_v661=float(expected),actual_v661=list(actual),
                differences=[float(v) for v in differences],
                status=('manual' if not actual else 'mismatch' if any(abs(v)>TOLERANCE for v in differences) else 'passed'),
                formula=f'({width:g} - {204 if door_type=="single" else 328} + 18*{(left,right).count("sidelight")} - 20*{(left,right).count("coupled")}) / {1 if door_type=="single" else 2}',
                rule_version=RULE_VERSION,tolerance_mm=float(TOLERANCE))
