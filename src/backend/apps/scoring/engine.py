from collections import defaultdict
from decimal import Decimal

from django.db import transaction

from apps.beneficiaries.models import Beneficiary, BeneficiaryIndicator
from apps.criteria.models import Criterion
from apps.cycles.models import CycleApplication, ParticipationRecord


APPLICATION_UPDATE_FIELDS = ['status', 'computed_score', 'rank_position']

# Sentinel value used in sort keys so a missing created_at always sorts last.
MISSING_CREATED_AT = '9999-12-31T23:59:59'


def compute_rankings(cycle, applicant_ids):
    """
    Return ranked scoring results for the given beneficiary IDs.

    This function is read-only: it computes ranking data without writing to the
    database. `run_ranking` is responsible for persisting application status.
    """
    applicant_ids = list(dict.fromkeys(applicant_ids))
    if not applicant_ids:
        return []

    criteria = _active_criteria()
    if not criteria:
        return []

    entries = _score_entries(cycle, applicant_ids, criteria)
    _rank_entries(entries, criteria)
    return entries


@transaction.atomic
def run_ranking(cycle):
    """
    Rank APPLIED applications for a cycle and persist SELECTED/DEFERRED status.
    """
    applications = _applied_applications(cycle)
    if not applications:
        return []

    applicant_ids = [app.beneficiary_id for app in applications]
    criteria = _active_criteria()
    if not criteria:
        return []

    scored_entries = _score_entries(cycle, applicant_ids, criteria)
    entry_by_beneficiary = {entry['beneficiary_id']: entry for entry in scored_entries}
    app_by_beneficiary = {app.beneficiary_id: app for app in applications}

    deferred_ids = _household_deferred_ids(applications, entry_by_beneficiary, cycle.max_per_household)
    _rank_entries(scored_entries, criteria)

    selectable_entries = [
        entry
        for entry in scored_entries
        if entry['beneficiary_id'] not in deferred_ids
    ]
    selected_ids = {
        entry['beneficiary_id']
        for entry in selectable_entries[:cycle.slots]
    }

    updates = []
    results = []
    for entry in scored_entries:
        app = app_by_beneficiary[entry['beneficiary_id']]
        is_household_deferred = entry['beneficiary_id'] in deferred_ids
        app.status = (
            CycleApplication.STATUS_SELECTED
            if entry['beneficiary_id'] in selected_ids
            else CycleApplication.STATUS_DEFERRED
        )
        app.computed_score = entry['total_score']
        app.rank_position = entry['rank']
        updates.append(app)
        results.append(_application_result(app, entry, deferred_by_household=is_household_deferred))

    CycleApplication.objects.bulk_update(updates, APPLICATION_UPDATE_FIELDS)
    return results


def _active_criteria():
    return list(Criterion.objects.filter(is_active=True).order_by('name'))


def _applied_applications(cycle):
    return list(
        CycleApplication.objects
        .select_for_update()
        .select_related(
            'beneficiary',
            'beneficiary__family',
            'beneficiary__family__household',
            'beneficiary__household',
        )
        .filter(cycle=cycle, status=CycleApplication.STATUS_APPLIED)
    )


def _score_entries(cycle, applicant_ids, criteria):
    indicator_values = _indicator_values(applicant_ids, criteria)
    ranges = _criterion_ranges(criteria, indicator_values)
    participated_ids = _prior_participation_ids(cycle, applicant_ids)
    created_at_by_id = _beneficiary_created_at(applicant_ids)

    return [
        _score_beneficiary(
            beneficiary_id=beneficiary_id,
            criteria=criteria,
            indicator_values=indicator_values,
            ranges=ranges,
            participated_ids=participated_ids,
            created_at=created_at_by_id.get(beneficiary_id),
        )
        for beneficiary_id in applicant_ids
    ]


def _indicator_values(applicant_ids, criteria):
    values = {criterion.id: {} for criterion in criteria}
    rows = BeneficiaryIndicator.objects.filter(
        criterion_id__in=[criterion.id for criterion in criteria],
        beneficiary_id__in=applicant_ids,
    ).values('criterion_id', 'beneficiary_id', 'value', 'raw_value')

    for row in rows:
        values[row['criterion_id']][row['beneficiary_id']] = row
    return values


def _criterion_ranges(criteria, indicator_values):
    ranges = {}
    for criterion in criteria:
        values = [float(row['value']) for row in indicator_values[criterion.id].values()]
        if len(values) < 2:
            ranges[criterion.id] = {'single': True, 'min': 0.0, 'max': 0.0}
        else:
            ranges[criterion.id] = {'single': False, 'min': min(values), 'max': max(values)}
    return ranges


def _prior_participation_ids(cycle, applicant_ids):
    return set(
        ParticipationRecord.objects
        .filter(beneficiary_id__in=applicant_ids)
        .exclude(cycle=cycle)
        .values_list('beneficiary_id', flat=True)
        .distinct()
    )


def _beneficiary_created_at(applicant_ids):
    return dict(
        Beneficiary.objects
        .filter(id__in=applicant_ids)
        .values_list('id', 'created_at')
    )


def _score_beneficiary(beneficiary_id, criteria, indicator_values, ranges, participated_ids, created_at):
    total_score = Decimal('0')
    breakdown = []

    for criterion in criteria:
        row = indicator_values[criterion.id].get(beneficiary_id)
        raw_value = float(row['value']) if row else 0.0
        normalized = _normalized_value(criterion, raw_value, ranges[criterion.id])
        contribution = Decimal(str(normalized)) * criterion.weight
        total_score += contribution

        breakdown.append({
            'criterion_id': criterion.id,
            'criterion_name': criterion.name,
            'weight': criterion.weight,
            'raw_value': row['raw_value'] if row else '',
            'normalized': round(normalized, 6),
            'contribution': contribution,
        })

    return {
        'beneficiary_id': beneficiary_id,
        'total_score': total_score,
        'has_participated': beneficiary_id in participated_ids,
        'breakdown': breakdown,
        'created_at': created_at,
    }


def _normalized_value(criterion, raw_value, value_range):
    if value_range['single'] or value_range['max'] == value_range['min']:
        return 0.0

    span = value_range['max'] - value_range['min']
    if criterion.type == Criterion.TYPE_COST:
        return (value_range['max'] - raw_value) / span
    return (raw_value - value_range['min']) / span


def _rank_entries(entries, criteria):
    if not entries:
        return

    hw_id = max(criteria, key=lambda c: c.weight).id

    # Build a lookup dict once so the sort comparator is O(1), not O(n_criteria).
    hw_scores = {
        entry['beneficiary_id']: next(
            (item['normalized'] for item in entry['breakdown'] if item['criterion_id'] == hw_id),
            0.0,
        )
        for entry in entries
    }
    entries.sort(key=lambda entry: _ranking_key(entry, hw_scores))
    for rank, entry in enumerate(entries, start=1):
        entry['rank'] = rank


def _ranking_key(entry, hw_scores):
    created_at = entry['created_at']
    return (
        -float(entry['total_score']),
        1 if entry['has_participated'] else 0,
        -hw_scores[entry['beneficiary_id']],
        created_at.isoformat() if created_at else MISSING_CREATED_AT,
    )


def _household_deferred_ids(applications, entry_by_beneficiary, max_per_household):
    deferred_ids = set()
    for household_apps in _applications_by_household(applications).values():
        if len(household_apps) <= max_per_household:
            continue

        household_apps.sort(
            key=lambda app: _household_priority(app, entry_by_beneficiary),
            reverse=True,
        )
        deferred_ids.update(app.beneficiary_id for app in household_apps[max_per_household:])
    return deferred_ids


def _applications_by_household(applications):
    groups = defaultdict(list)
    for app in applications:
        household_id = _household_id(app.beneficiary)
        if household_id:
            groups[household_id].append(app)
    return groups


def _household_id(beneficiary):
    if beneficiary.family_id and beneficiary.family.household_id:
        return beneficiary.family.household_id
    return beneficiary.household_id


def _household_priority(app, entry_by_beneficiary):
    entry = entry_by_beneficiary.get(app.beneficiary_id)
    if not entry:
        return Decimal('0')
    return entry['total_score']


def _unscored_entry(beneficiary_id):
    """Blank entry used when scoring is skipped (all-selected or household-deferred)."""
    return {
        'beneficiary_id': beneficiary_id,
        'rank': None,
        'total_score': None,
        'has_participated': False,
        'breakdown': [],
    }


def _ranked_status(rank, slots):
    if rank <= slots:
        return CycleApplication.STATUS_SELECTED
    return CycleApplication.STATUS_DEFERRED


def _application_result(app, entry, deferred_by_household):
    return {
        **entry,
        'application_id': app.id,
        'status': app.status,
        'deferred_by_household': deferred_by_household,
    }


def _household_deferred_result(app):
    return _application_result(app, _unscored_entry(app.beneficiary_id), deferred_by_household=True)
