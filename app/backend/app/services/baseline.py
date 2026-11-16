# math logic for the baseline progress trend

from dataclasses import dataclass
from typing import List, Optional, Tuple

def fit_line(ys: List[float]) -> Optional[Tuple[float, float]]:
    # y = m * x + b and returns (m, b)
    n = len(ys)
    if n < 2:
        return None
    mean_x = (n + 1) / 2.0
    mean_y = sum(ys) / n 
    sum_x_x = sum((x - mean_x) ** 2 for x in range(1, n + 1))
    sum_x_y = sum((x - mean_x) * (y - mean_y) for x, y in zip(range(1, n + 1), ys))
    m = sum_x_y / sum_x_x
    return m, mean_y - m * mean_x

@dataclass
class ProgressTrend:
    m_prescribed: float # will recommend volume increase per session
    m_actual: float # the user's completed volume increase
    m_next: float # future assessment's prescribed volume increase

def next_slope(m_prescribed: float, m_actual: float) -> float:
    # move the new progress line towards actual assessment by dividing 2
    return (m_prescribed + m_actual) / 2.0

def weekly_trend(prescribed: List[float], actual: List[float]) -> Optional[ProgressTrend]:
    # prescribed and actual are volumes per session for one category
    p, a = fit_line(prescribed), fit_line(actual)
    if p is None or a is None:
        return None
    return ProgressTrend(round(p[0], 2), round(a[0], 2), round(next_slope(p[0], a[0]), 2))