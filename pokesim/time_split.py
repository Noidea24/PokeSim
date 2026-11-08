"""Noidea24 fork: where a game's time goes, logged every five minutes.

A game's worker spends its time deciding what to press, emulating frames, drawing and encoding frames
for live viewers, and sleeping to hold its speed. When a game uses a whole CPU core or falls short of
its speed, one line in the log says which of those it is, for example:

    time split over 300s: deciding 41% (6,120 decisions, 20.1 ms each), emulating 35%,
    live view 18% (17,940 frames), sleeping 6%

Each part is measured with the wall clock around it on the game's own thread, so the parts add up to
the time that passed, apart from what the rest of the loop takes (saves, guards), shown as other.
"""
import logging
import time

log = logging.getLogger('pokesim.time')
PERIOD = 300.0


class TimeSplit:
    def __init__(self, period=PERIOD, clock=time.perf_counter, sink=None):
        self.period = period
        self.clock = clock
        self.sink = sink or log.info
        self.start = clock()
        self.parts = {'deciding': 0.0, 'emulating': 0.0, 'live view': 0.0, 'sleeping': 0.0}
        self.decisions = 0
        self.published = 0

    def add(self, part, seconds):
        self.parts[part] += seconds

    def decided(self, seconds):
        self.parts['deciding'] += seconds
        self.decisions += 1

    def drew(self, seconds):
        self.parts['live view'] += seconds
        self.published += 1

    def report(self):
        """Log the split if a period has passed, then start a new one. Returns the line or None."""
        now = self.clock()
        elapsed = now - self.start
        if elapsed < self.period:
            return None
        share = {part: 100 * seconds / elapsed for part, seconds in self.parts.items()}
        other = max(0.0, 100 - sum(share.values()))
        each = 1000 * self.parts['deciding'] / self.decisions if self.decisions else 0
        line = (f"time split over {elapsed:.0f}s: deciding {share['deciding']:.0f}% "
                f"({self.decisions:,} decisions, {each:.1f} ms each), emulating {share['emulating']:.0f}%, "
                f"live view {share['live view']:.0f}% ({self.published:,} frames), "
                f"sleeping {share['sleeping']:.0f}%, other {other:.0f}%")
        self.sink(line)
        self.start = now
        self.parts = dict.fromkeys(self.parts, 0.0)
        self.decisions = self.published = 0
        return line
