"""Calendar and continuous rolling-history helpers for the isolated engine.

All numeric timestamps are whole minutes since the Unix epoch in UTC. Naive
source ISO timestamps mean Europe/Stockholm civil time. Intervals are half
open: [start, end). Jo is counted from its actual subsegments, never from the
start date or the span of an entire work-and-Jo duty. These functions are
deliberately independent of the solver and do not infer missing history.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from fractions import Fraction
from math import ceil, floor
from typing import Any, Iterable, Mapping
from zoneinfo import ZoneInfo

LOCAL_ZONE = ZoneInfo("Europe/Stockholm")
DAY_MINUTES = 1440
WEEK_MINUTES = 10080
FOUR_WEEK_MINUTES = 40320
_JO_CODES = {"jo", "jour", "sleeping_oncall", "sovandejour", "sovande_jour"}


def utc_minute(value: Any) -> int:
    """Normalize a timestamp, rejecting a silent subminute truncation."""
    if isinstance(value, bool):
        raise ValueError("A timestamp cannot be Boolean")
    if isinstance(value, (int, float)):
        if not float(value).is_integer():
            raise ValueError("Numeric timestamps must be whole UTC minutes")
        return int(value)
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if not isinstance(value, datetime):
        raise TypeError("Expected an ISO datetime, datetime, or absolute UTC minute")
    if value.tzinfo is None:
        value = value.replace(tzinfo=LOCAL_ZONE)
    seconds = value.astimezone(timezone.utc).timestamp()
    if seconds % 60:
        raise ValueError("Source timestamp is not aligned to whole minutes")
    return int(seconds // 60)


def local_iso(value: Any) -> str:
    return datetime.fromtimestamp(utc_minute(value) * 60, timezone.utc).astimezone(LOCAL_ZONE).isoformat(timespec="minutes")


def _local_datetime(value: Any) -> datetime:
    return datetime.fromtimestamp(utc_minute(value) * 60, timezone.utc).astimezone(LOCAL_ZONE)


def overlap(start: Any, end: Any, lo: Any, hi: Any) -> int:
    return max(0, min(utc_minute(end), utc_minute(hi)) - max(utc_minute(start), utc_minute(lo)))


def _pair(record: Any) -> tuple[int, int]:
    if isinstance(record, Mapping):
        start, end = record.get("start"), record.get("end")
    else:
        start, end = record
    start, end = utc_minute(start), utc_minute(end)
    if end <= start:
        raise ValueError("A time segment must have a positive duration")
    return start, end


def merged_intervals(intervals: Iterable[Any]) -> list[tuple[int, int]]:
    """Union overlapping/adjacent source spans without double-counting Jo."""
    result: list[tuple[int, int]] = []
    for start, end in sorted(_pair(x) for x in intervals):
        if result and start <= result[-1][1]:
            result[-1] = result[-1][0], max(end, result[-1][1])
        else:
            result.append((start, end))
    return result


def jour_intervals(duty: Mapping[str, Any]) -> list[tuple[int, int]]:
    """Read explicitly typed Jo. Untyped whole duties never become Jo."""
    for key in ("jour_segments", "jour_intervals", "jour"):
        if key in duty:
            value = duty[key]
            if value is None:
                return []
            return merged_intervals(value)
    if "segments" in duty:
        return merged_intervals(
            segment for segment in duty["segments"]
            if str(segment.get("source_code", segment.get("code", segment.get("kind", segment.get("category", ""))))).casefold() in _JO_CODES
        )
    code = str(duty.get("source_code", duty.get("code", duty.get("kind", duty.get("category", ""))))).casefold()
    return [_pair(duty)] if code in _JO_CODES or duty.get("counts_as_oncall_presence") is True else []


def _single_employee(records: list[Mapping[str, Any]]) -> None:
    employees = {str(x.get("employee_id", x.get("person_id"))) for x in records if x.get("employee_id", x.get("person_id")) is not None}
    if len(employees) > 1:
        raise ValueError("History must be checked separately for each employee")


def _total(intervals: Iterable[tuple[int, int]], end: int, span: int) -> int:
    start = end - span
    return sum(max(0, min(right, end) - max(left, start)) for left, right in intervals)


def _rolling_breakpoints(intervals: Iterable[tuple[int, int]], lo: int, hi: int, span: int) -> list[int]:
    points = {lo, hi}
    for start, end in intervals:
        for point in (start, end, start - span, end - span, start + span, end + span):
            if lo <= point <= hi:
                points.add(point)
    return sorted(points)


def jour_windows(
    frozen_duties: Iterable[Mapping[str, Any]],
    candidates: Iterable[Mapping[str, Any]],
    lo: Any,
    hi: Any,
    window_minutes: int = FOUR_WEEK_MINUTES,
    cap_minutes: int = 2880,
) -> list[dict[str, Any]]:
    """Return a complete linear rolling-Jo constraint basis for one employee.

    The window *end* lies in [lo, hi]. Include hi+window_minutes explicitly
    when inspecting a P2 tail; unseen future work is unknown, not zero.
    A frozen excess is reported without making every model infeasible.
    In that window new mutable Jo must be zero; otherwise it may use the
    remaining capacity. The legal cap remains unchanged. Besides event
    extrema, cap-crossing points are included because the non-worsening
    bound max(0, cap-frozen) has an additional piecewise-linear corner.
    """
    lo, hi = utc_minute(lo), utc_minute(hi)
    if hi < lo or window_minutes <= 0 or cap_minutes < 0:
        raise ValueError("Invalid rolling-window range, duration, or cap")
    frozen_duties, candidates = list(frozen_duties), list(candidates)
    _single_employee(frozen_duties + candidates)
    frozen = merged_intervals(interval for duty in frozen_duties for interval in jour_intervals(duty))
    mutable: list[tuple[str, list[tuple[int, int]]]] = []
    seen: set[str] = set()
    for candidate in candidates:
        candidate_id = candidate.get("candidate_id", candidate.get("id", candidate.get("segment_id")))
        if candidate_id is None:
            raise ValueError("Each mutable candidate must have a unique candidate_id or id")
        candidate_id = str(candidate_id)
        if candidate_id in seen:
            raise ValueError(f"Duplicate mutable candidate ID: {candidate_id}")
        seen.add(candidate_id)
        mutable.append((candidate_id, jour_intervals(candidate)))
    all_intervals = frozen + [interval for _, intervals in mutable for interval in intervals]
    points = _rolling_breakpoints(all_intervals, lo, hi, window_minutes)
    # A pure frozen union has slope -1, 0, or 1, but retaining an exact
    # Fraction and both adjacent integer minutes also handles future APIs.
    crossings: set[int] = set()
    for left, right in zip(points, points[1:]):
        a, b = _total(frozen, left, window_minutes), _total(frozen, right, window_minutes)
        if (a < cap_minutes < b) or (b < cap_minutes < a):
            crossing = Fraction(left) + Fraction(cap_minutes - a, b - a) * (right - left)
            crossings.update((floor(crossing), ceil(crossing)))
    points = sorted(set(points) | crossings)
    result = []
    for end in points:
        fixed = _total(frozen, end, window_minutes)
        terms = [[candidate_id, minutes] for candidate_id, intervals in mutable if (minutes := _total(intervals, end, window_minutes)) > 0]
        excess = max(0, fixed - cap_minutes)
        result.append({
            "start": end - window_minutes, "end": end,
            "frozen_minutes": fixed, "terms": terms,
            "historical_excess_minutes": excess,
            "mutable_allowance_minutes": max(0, cap_minutes - fixed),
            "classification": "INHERITED_FROZEN_BREACH" if excess else "CAP_APPLIES_WITH_MUTABLE_ALLOWANCE",
            "cap_minutes": cap_minutes,
        })
    return result


def occupied_calendar_days(start: Any, end: Any, lo: Any, hi: Any) -> list[str]:
    """Every civil calendar day touched by actual duty, clipped to range."""
    start, end = max(utc_minute(start), utc_minute(lo)), min(utc_minute(end), utc_minute(hi))
    if end <= start:
        return []
    current = _local_datetime(start).date()
    last = _local_datetime(end - 1).date()
    result = []
    while current <= last:
        result.append(current.isoformat())
        current += timedelta(days=1)
    return result


def weekly_windows(lo: Any, hi: Any, anchor: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    """Known fixed seven-civil-day periods; missing anchor produces no rule."""
    if anchor is None:
        return []
    lo, hi = utc_minute(lo), utc_minute(hi)
    if hi <= lo:
        return []
    weekday = anchor.get("weekday")
    if isinstance(weekday, bool) or not isinstance(weekday, int) or not 0 <= weekday <= 6:
        raise ValueError("A verified weekday from 0 (Monday) to 6 is required")
    if "clock" not in anchor:
        raise ValueError("A verified weekly break time is required")
    clock = time.fromisoformat(anchor["clock"])
    if clock.second or clock.microsecond:
        raise ValueError("Weekly anchor must use whole minutes")
    current_date = _local_datetime(lo).date()
    current_date -= timedelta(days=(current_date.weekday() - weekday) % 7)
    current = datetime.combine(current_date, clock, LOCAL_ZONE)
    if utc_minute(current) > lo:
        current_date -= timedelta(days=7)
        current = datetime.combine(current_date, clock, LOCAL_ZONE)
    result = []
    while utc_minute(current) < hi:
        end_date = current_date + timedelta(days=7)
        end = datetime.combine(end_date, clock, LOCAL_ZONE)
        result.append({"start": utc_minute(current), "end": utc_minute(end), "anchor": dict(anchor),
                       "requires_history_before_lo": utc_minute(current) < lo,
                       "requires_future_after_hi": utc_minute(end) > hi})
        current_date, current = end_date, end
    return result


def free_day_windows(lo: Any, hi: Any, mode: str | None) -> list[dict[str, Any]]:
    """28 civil-calendar-day periods, both explicitly diagnostic if unknown."""
    lo, hi = utc_minute(lo), utc_minute(hi)
    if hi <= lo:
        return []
    left, right = _local_datetime(lo), _local_datetime(hi)
    if left.time() != time(0) or right.time() != time(0):
        raise ValueError("Free-day period limits must be civil midnights")
    aliases = {"fixed": "fixed", "fixed28": "fixed", "fixed_p2": "fixed", "rolling": "rolling", "rolling28": "rolling", "rolling4w": "rolling"}
    if mode is not None and mode not in aliases:
        raise ValueError("Free-day mode must be verified fixed/rolling or None")
    modes = ["fixed", "rolling"] if mode is None else [aliases[mode]]
    result = []
    for current_mode in modes:
        if current_mode == "fixed":
            starts = []
            current = left.date()
            while current + timedelta(days=28) <= right.date():
                starts.append(current)
                current += timedelta(days=28)
        else:
            starts = [left.date() - timedelta(days=28) + timedelta(days=j)
                      for j in range((right.date() - left.date()).days + 1)]
        for start_day in starts:
            end_day = start_day + timedelta(days=28)
            dates = [(start_day + timedelta(days=j)).isoformat() for j in range(28)]
            start = utc_minute(datetime.combine(start_day, time(0), LOCAL_ZONE))
            end = utc_minute(datetime.combine(end_day, time(0), LOCAL_ZONE))
            result.append({"start": start, "end": end, "calendar_dates": dates, "mode": current_mode,
                           "active_rule": mode is not None, "diagnostic_only": mode is None,
                           "requires_history_before_lo": start < lo})
    return result


def longest_rest_minutes(duties: Iterable[Mapping[str, Any]], lo: Any, hi: Any) -> int:
    """Known-record longest gap only: absence of unknown history is not proof."""
    lo, hi = utc_minute(lo), utc_minute(hi)
    if hi <= lo:
        return 0
    intervals = merged_intervals(duty for duty in duties if overlap(duty["start"], duty["end"], lo, hi))
    cursor, best = lo, 0
    for start, end in intervals:
        start, end = max(lo, start), min(hi, end)
        best, cursor = max(best, start - cursor), max(cursor, end)
    return max(best, hi - cursor)
