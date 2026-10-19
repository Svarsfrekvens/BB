"""Select a reviewed strategy from the server profile, never a client request."""

def _availability(profile):
    strategy = profile.get('engine_strategy')
    if strategy not in (None, 'flora-reassignment/1.0', 'reviewed-availability/1.0'):
        raise ValueError('Verksamhetens beräkningsmetod stöds inte av denna motorversion.')
    return strategy == 'reviewed-availability/1.0'


def prepare(profile, request):
    if _availability(profile):
        from .availability_import import prepare_case
        if request['objective_mode'] != 'coverage_then_temporary':
            raise ValueError('Tillgänglighetsprofilen stöder behovstäckning före vikarietid.')
        return prepare_case(request['input'], profile, request['scenario'])
    from .flora_import import prepare_case
    from .flora import check_case
    case = prepare_case(request['input'], profile, request['scenario'])
    check_case(case)
    return case


def solve(profile, case, request):
    if _availability(profile):
        from .availability import solve_case, validate_case
    else:
        from .flora import solve_case, validate_case
    result = solve_case(case, seconds=request['seconds'], workers=2,
                        objective_mode=request['objective_mode'])
    result['validation'] = validate_case(case, result)
    return result
