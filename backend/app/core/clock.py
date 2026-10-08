"""What time it is — asked in one place, so a seed or a test can answer.

Anything that stamps a work's history asks this module rather than the system
clock: a stage change, a ledger entry, a line in a timeline. Normally the two
agree. Two callers need them not to. The seed builds a work that was "proposed
twelve weeks ago" by putting it through the same rules a real one goes through,
so it has to be able to say when each step happened. And a rule about a work
sitting at one stage for sixty days cannot be tested by waiting.

`now()` never returns the same instant twice. One request often writes several
history rows — a complaint is linked to a work and moved to In Progress in the
same breath — and they are read back ordered by timestamp. On a clock that
ticks in milliseconds, which Windows' does, two of them can tie, and tied rows
come back in whichever order the database feels like.
"""

from __future__ import annotations

import threading
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date, datetime, time, timedelta, timezone

_TICK = timedelta(microseconds=1)
_lock = threading.Lock()

# Set only inside `at()`. Process-wide rather than per-thread on purpose: the
# test client serves requests on another thread, and a test that moves the
# clock needs the request to see it.
_frozen: datetime | None = None
_last: datetime | None = None


def now() -> datetime:
    """The current moment in UTC, strictly later than the last one handed out."""
    global _frozen, _last
    with _lock:
        if _frozen is not None:
            moment = _frozen
            _frozen = moment + _TICK
            return moment
        moment = datetime.now(timezone.utc)
        if _last is not None and moment <= _last:
            moment = _last + _TICK
        _last = moment
        return moment


def today() -> date:
    with _lock:
        if _frozen is not None:
            return _frozen.date()
    return date.today()


@contextmanager
def at(moment: datetime | date) -> Iterator[None]:
    """Run the enclosed block as though it were `moment`.

    A bare date means late morning that day. Calls to `now()` inside still come
    out in order, a microsecond apart, so history written in one block reads
    back in the order it was written.
    """
    global _frozen
    if not isinstance(moment, datetime):
        moment = datetime.combine(moment, time(6, 0), timezone.utc)
    elif moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)

    with _lock:
        previous, _frozen = _frozen, moment
    try:
        yield
    finally:
        with _lock:
            _frozen = previous
