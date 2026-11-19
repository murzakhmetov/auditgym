"""Time primitives without a time zone database.

Each company time zone is described by a small built-in rule (fixed offset or
one of three daylight-saving rules). The policy shipped with every episode
lists the explicit UTC-offset schedule for the episode window, so agents never
need a tz database either. Timestamps are ISO-8601 with an explicit offset.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

UTC = timezone.utc

# name -> (rule, standard offset minutes, daylight offset minutes)
TZ_RULES = {
    "UTC": ("fixed", 0, 0),
    "Asia/Almaty": ("fixed", 300, 300),
    "Asia/Tokyo": ("fixed", 540, 540),
    "Asia/Kolkata": ("fixed", 330, 330),
    "Asia/Kathmandu": ("fixed", 345, 345),
    "Asia/Kuwait": ("fixed", 180, 180),
    "America/Sao_Paulo": ("fixed", -180, -180),
    "Europe/Berlin": ("eu", 60, 120),
    "Europe/London": ("eu", 0, 60),
    "America/New_York": ("us", -300, -240),
    "Australia/Sydney": ("au", 600, 660),
}


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    """n-th (1-based) weekday of a month; n=-1 means the last one. Monday=0."""
    if n > 0:
        d = date(year, month, 1)
        d += timedelta(days=(weekday - d.weekday()) % 7)
        return d + timedelta(weeks=n - 1)
    nxt = date(year + (month == 12), month % 12 + 1, 1)
    d = nxt - timedelta(days=1)
    return d - timedelta(days=(d.weekday() - weekday) % 7)


def _at(d: date, hour: int) -> datetime:
    return datetime(d.year, d.month, d.day, hour, tzinfo=UTC)


def dst_window_utc(tz: str, year: int) -> tuple[datetime, datetime] | None:
    """(start, end) UTC instants of daylight time for a northern rule, or the
    (end, start) pair for the southern AU rule (daylight outside the window)."""
    rule, std, _dst = TZ_RULES[tz]
    if rule == "eu":
        return _at(_nth_weekday(year, 3, 6, -1), 1), _at(_nth_weekday(year, 10, 6, -1), 1)
    if rule == "us":
        start_local = _nth_weekday(year, 3, 6, 2)  # 02:00 standard time
        end_local = _nth_weekday(year, 11, 6, 1)  # 02:00 daylight time
        start = _at(start_local, 2) - timedelta(minutes=std)
        end = _at(end_local, 2) - timedelta(minutes=std + 60)
        return start, end
    if rule == "au":
        end_local = _nth_weekday(year, 4, 6, 1)  # daylight ends 03:00 daylight time
        start_local = _nth_weekday(year, 10, 6, 1)  # daylight starts 02:00 standard time
        end = _at(end_local, 3) - timedelta(minutes=std + 60)
        start = _at(start_local, 2) - timedelta(minutes=std)
        return end, start
    return None


def offset_minutes(tz: str, instant: datetime) -> int:
    rule, std, dst = TZ_RULES[tz]
    if rule == "fixed":
        return std
    inst = instant.astimezone(UTC)
    a, b = dst_window_utc(tz, inst.year)
    if rule == "au":
        return std if a <= inst < b else dst
    return dst if a <= inst < b else std


def offset_schedule(tz: str, start: datetime, end: datetime) -> list[dict]:
    """Explicit schedule: offset in force from each listed UTC instant."""
    start = start.astimezone(UTC)
    end = end.astimezone(UTC)
    changes = []
    for year in range(start.year - 1, end.year + 2):
        window = dst_window_utc(tz, year)
        if window:
            changes.extend(window)
    sched = [{"from_utc": format_utc(start), "offset": format_offset(offset_minutes(tz, start))}]
    for c in sorted(changes):
        if start < c < end:
            sched.append({"from_utc": format_utc(c), "offset": format_offset(offset_minutes(tz, c))})
    return sched


def format_offset(minutes: int) -> str:
    sign = "+" if minutes >= 0 else "-"
    m = abs(minutes)
    return f"{sign}{m // 60:02d}:{m % 60:02d}"


def format_utc(instant: datetime) -> str:
    return instant.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def format_ts(instant: datetime, offset_min: int) -> str:
    local = instant.astimezone(timezone(timedelta(minutes=offset_min)))
    return local.strftime("%Y-%m-%dT%H:%M:%S") + format_offset(offset_min)


def format_local(instant: datetime, tz: str) -> str:
    return format_ts(instant, offset_minutes(tz, instant))


def parse_ts(text: str) -> datetime:
    if not isinstance(text, str):
        raise ValueError("timestamp must be a string")
    s = text.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        raise ValueError("timestamp without offset")
    return dt.astimezone(UTC)


def to_local(instant: datetime, tz: str) -> datetime:
    return instant.astimezone(timezone(timedelta(minutes=offset_minutes(tz, instant))))


def local_date(instant: datetime, tz: str) -> date:
    return to_local(instant, tz).date()


def local_datetime(tz: str, d: date, hour: int = 0, minute: int = 0, second: int = 0) -> datetime:
    """UTC instant for a local wall-clock time. Rules never move clocks at
    midnight, and generated documents avoid the skipped/repeated hour."""
    rule, std, dst = TZ_RULES[tz]
    naive = datetime(d.year, d.month, d.day, hour, minute, second)
    for off in (std, dst) if rule != "fixed" else (std,):
        candidate = (naive - timedelta(minutes=off)).replace(tzinfo=UTC)
        if offset_minutes(tz, candidate) == off:
            return candidate
    return (naive - timedelta(minutes=std)).replace(tzinfo=UTC)


def local_midnight(tz: str, d: date) -> datetime:
    return local_datetime(tz, d, 0, 0, 0)


def month_bounds(tz: str, year: int, month: int) -> tuple[datetime, datetime]:
    start = local_midnight(tz, date(year, month, 1))
    nxt = date(year + (month == 12), month % 12 + 1, 1)
    return start, local_midnight(tz, nxt)


def in_ambiguous_hour(tz: str, instant: datetime) -> bool:
    """True within 75 minutes of a DST change (generator avoids these times)."""
    rule = TZ_RULES[tz][0]
    if rule == "fixed":
        return False
    inst = instant.astimezone(UTC)
    for c in dst_window_utc(tz, inst.year):
        if abs((inst - c).total_seconds()) < 75 * 60:
            return True
    return False
