"""Person-bound task support for the explicit no-break Flora experiment.

The legacy method only checked a shared staffing pool and selected task
executors afterwards. This opt-in model binds every selected need to actual Ar
work by one or more named people before the solver can call it covered.
"""

from collections import defaultdict


def _may_overlap(left, right):
    la, lb = min(a for a, _ in left['domains']), max(b for _, b in left['domains']) + left['duration']
    ra, rb = min(a for a, _ in right['domains']), max(b for _, b in right['domains']) + right['duration']
    return la < rb and ra < lb


def _must_be_sequential(left, right, non_individual):
    if left['exclusive'] or right['exclusive']:
        return True
    customers = (left['customer'], right['customer'])
    return customers[0] != customers[1] and all(customer not in non_individual for customer in customers)


def add_person_task_assignments(case, model, variables, tasks):
    """Constrain selected tasks to actual worker presence and customer order."""
    H = case['horizon']
    non_individual = set(case['config']['non_individual_customer_ids'])
    movable = {sid for unit in case['reassignable_temporary_units'] for sid in unit['segment_ids']}
    hosts = defaultdict(list)
    for row in case['fixed_segments']:
        if row['id'] not in movable and row['code'] == 'Ar':
            hosts[row['person']].append((row['start'], row['end'], None))
    for choice in model._reassignment_choices:
        for row in choice['unit']['rows']:
            if row['code'] == 'Ar':
                for person, selected in choice['options']:
                    hosts[person].append((row['start'], row['end'], selected))
    step = case['config']['shift_step']
    for shift in variables:
        hosts[shift['c']['person']].append((shift['s'] * step, shift['e'] * step, shift['pr']))
    for choice in model._whole_duty_choices:
        for part in choice['c']['parts']:
            if part['code'] == 'Ar':
                hosts[choice['c']['person']].append((part['start'], part['end'], choice['pr']))

    per_person = defaultdict(list)
    for task in tasks:
        need, start, present = task['n'], task['st'], task['pr']
        assigned_people = []
        for person, spans in hosts.items():
            supports = []
            for a, b, host_present in spans:
                # Static bounds are only a pruning aid; the reified constraints
                # below check the selected shift's exact start and end.
                lo = a if isinstance(a, int) else 0
                hi = b if isinstance(b, int) else H
                if all(max(lo, dom_a) > min(hi - need['duration'], dom_b)
                       for dom_a, dom_b in need['domains']):
                    continue
                support = model.NewBoolVar('task_host')
                if host_present is not None:
                    model.Add(support <= host_present)
                model.Add(start >= a).OnlyEnforceIf(support)
                model.Add(start + need['duration'] <= b).OnlyEnforceIf(support)
                supports.append(support)
            if not supports:
                continue
            assigned = model.NewBoolVar('task_person')
            model.Add(sum(supports) == assigned)
            interval = model.NewOptionalFixedSizeIntervalVar(start, need['duration'], assigned, 'task_person_interval')
            per_person[person].append((need, interval))
            assigned_people.append((person, assigned))
        model.Add(sum(value for _, value in assigned_people) == need['count'] * present)
        task['assigned_people'] = assigned_people

    for assigned_tasks in per_person.values():
        for index, (left, left_interval) in enumerate(assigned_tasks):
            for right, right_interval in assigned_tasks[index + 1:]:
                if _may_overlap(left, right) and _must_be_sequential(left, right, non_individual):
                    model.AddNoOverlap([left_interval, right_interval])
