"""Pure interval utilities. No solver imports or validation verdicts."""
from datetime import datetime, timedelta

def minute(value, origin):
    return int((datetime.fromisoformat(value) - datetime.fromisoformat(origin)).total_seconds() // 60)

def timestamp(value, origin):
    return (datetime.fromisoformat(origin) + timedelta(minutes=int(value))).isoformat(timespec='minutes')

def merge(intervals):
    out = []
    for start, end in sorted(intervals):
        if end <= start:
            continue
        if out and start <= out[-1][1]:
            out[-1][1] = max(out[-1][1], end)
        else:
            out.append([start, end])
    return out

def days(start, end, first, last):
    return set(range(max(first, start // 1440), min(last, (end-1)//1440+1))) if end > start else set()

def runs(values):
    pos = 0
    while pos < len(values):
        end = pos + 1
        while end < len(values) and values[end] == values[pos]:
            end += 1
        yield pos, end, int(values[pos])
        pos = end
