from django import template

register = template.Library()

LABEL_MAP = {
    'eats_immediately': 'Eats all food immediately',
    'returns_later': 'Returns later to eat',
    'hand_fed': 'Needs to be hand-fed',
    'table_scraps': 'Eats table scraps',
    'one_person': 'Only one person',
    'will_try': 'Will try best',
    'indoors': 'Indoors',
    'outdoors': 'Outdoors',
    'both': 'Both',
    'yes': 'Yes',
    'no': 'No',
    'sometimes': 'Sometimes',
    'urban': 'Urban',
    'rural': 'Rural',
    'monthly': 'Monthly',
    '3monthly': 'Every 3 months',
    '6monthly': 'Every 6 months',
    'lt_15min': '< 15 min',
    'lt_30min': '< 30 min',
    'lt_45min': '< 45 min',
    'lt_1hr': '< 1 hour',
    'gt_1hr': '> 1 hour',
    'lt_1x': '< 1x/day',
    '1_2x': '1-2x/day',
    'gt_3x': '> 3x/day',
}


def _label(token):
    if token is None:
        return ''
    t = str(token).strip()
    if not t:
        return ''
    mapped = LABEL_MAP.get(t)
    if mapped:
        return mapped
    return t.replace('_', ' ').replace('|', ' ').strip().capitalize()


@register.filter
def pretty_token(value):
    return _label(value) or '-'


@register.filter
def pretty_csv(value):
    if not value:
        return '-'
    items = [_label(v) for v in str(value).split(',') if str(v).strip()]
    items = [i for i in items if i]
    return ', '.join(items) if items else '-'


@register.filter
def pretty_med_admin(value):
    if not value:
        return '-'
    raw = str(value)
    segments = []
    for part in raw.split('|'):
        if ':' in part:
            k, v = part.split(':', 1)
            key_label = _label(k)
            val_label = v.strip() or '-'
            segments.append(f"{key_label}: {val_label}")
        else:
            segments.extend([_label(x) for x in part.split(',') if x.strip()])
    segments = [s for s in segments if s]
    return ', '.join(segments) if segments else '-'
