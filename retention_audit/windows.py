"""观察窗口与队列成熟度。

观察窗自结课日起算：第一轮第 7–10 日，第二轮第 14–18 日，首尾均计。
"""

# 窗口名 -> （自结课日起的最早日偏移, 最晚日偏移），首尾均计
WAVES = {
    1: (7, 10),
    2: (14, 18),
}

# 第二轮窗口到期（最后一日）的偏移
WAVE2_CLOSE_OFFSET = 18
WAVE2_OPEN_OFFSET = 14


def wave_window(ended, wave):
    """返回该队列某一轮的绝对日期闭区间 (lo, hi)。"""
    lo, hi = WAVES[wave]
    return ended + lo, ended + hi


def in_wave(day, ended, wave):
    """作答发生日是否落在该队列该轮的观察窗内（首尾均计）。"""
    lo, hi = wave_window(ended, wave)
    return lo <= day <= hi


def cohort_mature(ended, as_of):
    """第二轮窗口已全部到期才算成熟队列。"""
    return as_of >= ended + WAVE2_CLOSE_OFFSET


def window_status(ended, as_of):
    """队列整体窗口状态：

    - ``wave2_open``：第二轮窗口尚未开始（窗口未到）
    - ``wave2_running``：第二轮窗口进行中
    - ``closed``：第二轮窗口已到期
    """
    if as_of < ended + WAVE2_OPEN_OFFSET:
        return "wave2_open"
    if as_of < ended + WAVE2_CLOSE_OFFSET:
        return "wave2_running"
    return "closed"
