"""Reads a route's free-text schedule for the arrival planner: running days, last departure, evening service."""
import re

DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
NAMES = {"monday": "mon", "tuesday": "tue", "wednesday": "wed", "thursday": "thu", "friday": "fri", "saturday": "sat", "sunday": "sun",
         "mon": "mon", "tue": "tue", "tues": "tue", "wed": "wed", "thu": "thu", "thur": "thu", "thurs": "thu", "fri": "fri", "sat": "sat", "sun": "sun"}


def infer(schedule):
    """Returns (days, last_departure, evening). Empty values mean 'not sure'."""
    text = (schedule or "").lower()
    days, last, evening = "", "", ""
    if re.search(r"\b(no|except|not on)\s+fridays?\b|\bno friday\b", text) or re.search(r"saturday\s*[–-]\s*thursday", text):
        days = ",".join(d for d in DAYS if d != "fri")
    else:
        found = [NAMES[w] for w in re.findall(r"\b(" + "|".join(NAMES) + r")\b", text)]
        if found and not re.search(r"\bdaily\b|every day", text):
            days = ",".join(d for d in DAYS if d in found)
    times = [(int(h), int(m)) for h, m in re.findall(r"\b([01]?\d|2[0-3])[:.]([0-5]\d)\b", text)]
    if times:
        h, m = max(times)
        last = f"{h:02d}:{m:02d}"
    if re.search(r"\bany ?time\b|24 ?(hours|h|/7)|on request", text):
        evening = "yes"
    return days, last, evening
