"""Pure statistical helpers for the analysis engine.

Robust trend, smoothing and change-point detection over date-keyed series. ORM-free
and dependency-free (stdlib only) so they're trivially unit-testable. Every function
takes ``points`` as an iterable of ``(date, value)`` and ignores None values.
"""
from __future__ import annotations


def _clean(points):
    """Sorted [(date, float)] with Nones dropped."""
    pts = [(d, float(v)) for d, v in points if v is not None]
    pts.sort(key=lambda p: p[0])
    return pts


def _offsets(pts):
    """[(day_offset_from_first, value)] for a cleaned, sorted series."""
    base = pts[0][0]
    return [((d - base).days, v) for d, v in pts]


def ewma(points, halflife_days: float = 10.0):
    """Exponentially-weighted moving average over irregularly-spaced points.

    The previous smoothed value decays with `halflife_days`, so real calendar gaps
    are handled (a 7-day gap discounts the old estimate more than a 1-day gap). This
    is the standard way to pull a stable trend line out of noisy daily bodyweight.
    Returns [(date, smoothed)].
    """
    pts = _clean(points)
    if not pts:
        return []
    per_day_decay = 0.5 ** (1.0 / max(0.5, halflife_days))
    out = [pts[0]]
    smoothed = pts[0][1]
    prev = pts[0][0]
    for d, v in pts[1:]:
        gap = max(1, (d - prev).days)
        w = per_day_decay**gap  # weight retained by the previous estimate
        smoothed = w * smoothed + (1.0 - w) * v
        out.append((d, smoothed))
        prev = d
    return out


def linear_slope(points):
    """Ordinary least-squares slope per day (None if <2 points or no spread)."""
    pts = _clean(points)
    if len(pts) < 2:
        return None
    xy = _offsets(pts)
    n = len(xy)
    mx = sum(x for x, _ in xy) / n
    my = sum(y for _, y in xy) / n
    denom = sum((x - mx) ** 2 for x, _ in xy)
    if denom == 0:
        return None
    return sum((x - mx) * (y - my) for x, y in xy) / denom


def theil_sen_slope(points):
    """Median of all pairwise slopes per day — robust to outliers (e.g. a water-weight
    spike). None if there aren't two points at distinct dates.
    """
    pts = _clean(points)
    if len(pts) < 2:
        return None
    xy = _offsets(pts)
    slopes = [
        (xy[j][1] - xy[i][1]) / (xy[j][0] - xy[i][0])
        for i in range(len(xy))
        for j in range(i + 1, len(xy))
        if xy[j][0] != xy[i][0]
    ]
    if not slopes:
        return None
    slopes.sort()
    n = len(slopes)
    mid = n // 2
    return slopes[mid] if n % 2 else (slopes[mid - 1] + slopes[mid]) / 2.0


def _line_rss(xy):
    """Residual sum of squares of the least-squares line through [(x, y)]."""
    n = len(xy)
    if n < 2:
        return 0.0
    mx = sum(x for x, _ in xy) / n
    my = sum(y for _, y in xy) / n
    denom = sum((x - mx) ** 2 for x, _ in xy)
    slope = 0.0 if denom == 0 else sum((x - mx) * (y - my) for x, y in xy) / denom
    inter = my - slope * mx
    return sum((y - (slope * x + inter)) ** 2 for x, y in xy)


def detect_change_points(
    points, min_size: int = 8, min_gain_frac: float = 0.15, max_points: int = 4
):
    """Piecewise-linear change points via binary segmentation.

    Recursively splits the series at the index that most reduces total squared error
    vs a single straight line, as long as each side keeps >= `min_size` points and the
    split explains at least `min_gain_frac` of the segment's error. Good for spotting a
    plateau or a change in trend slope (e.g. a cut stalling). Returns the change dates.
    """
    pts = _clean(points)
    if len(pts) < 2 * min_size:
        return []
    xy = _offsets(pts)
    dates = [d for d, _ in pts]

    found: list[int] = []

    def segment(lo, hi):
        if len(found) >= max_points or (hi - lo) < 2 * min_size:
            return
        whole = _line_rss(xy[lo:hi])
        if whole <= 0:
            return
        best_k, best_gain = None, 0.0
        for k in range(lo + min_size, hi - min_size + 1):
            gain = whole - (_line_rss(xy[lo:k]) + _line_rss(xy[k:hi]))
            if gain > best_gain:
                best_k, best_gain = k, gain
        if best_k is None or best_gain < min_gain_frac * whole:
            return
        found.append(best_k)
        segment(lo, best_k)
        segment(best_k, hi)

    segment(0, len(xy))
    return [dates[k] for k in sorted(found)]
