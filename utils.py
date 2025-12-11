import numpy as np
import pandas as pd
from pathlib import Path
from typing import Tuple


def generate_trading_date(
    begin_date: np.datetime64 = np.datetime64("2015-01-04"),
    end_date: np.datetime64 = np.datetime64("today"),
) -> Tuple[np.ndarray, np.ndarray]:
    """
    生成交易日历

    参数:
    begin_date: 开始日期
    end_date: 结束日期

    返回:
    (交易日数组, 每周最后一个交易日数组)
    """
    assert begin_date >= np.datetime64(
        "2015-01-04"
    ), "系统预设起始日期仅支持2015年1月4日以后"

    # 尝试定位节假日文件，假设在当前文件同级目录下
    holiday_file = (
        Path(__file__).resolve().parent.joinpath("Chinese_special_holiday.txt")
    )

    if not holiday_file.exists():
        print(f"警告: 节假日文件未找到 {holiday_file}")
        chinese_special_holiday = np.array([], dtype="datetime64[D]")
    else:
        with open(holiday_file, "r") as f:
            chinese_special_holiday = pd.Series(
                [date.strip() for date in f.readlines()]
            ).values.astype("datetime64[D]")

    working_date = pd.date_range(begin_date, end_date, freq="B").values.astype(
        "datetime64[D]"
    )
    trading_date = np.setdiff1d(working_date, chinese_special_holiday)

    # 计算每周最后一个交易日
    trading_date_df = pd.DataFrame(working_date, columns=["working_date"])
    trading_date_df["is_friday"] = trading_date_df["working_date"].apply(
        lambda x: x.weekday() == 4
    )
    trading_date_df["trading_date"] = (
        trading_date_df["working_date"]
        .apply(lambda x: x if x in trading_date else np.nan)
        .ffill()
    )

    weekly_dates = np.unique(
        trading_date_df[trading_date_df["is_friday"]]["trading_date"].values[1:]
    ).astype("datetime64[D]")

    return trading_date, weekly_dates


def calculate_drawdown_stats(dates, nav, holidays):
    """
    使用numpy计算回撤统计信息

    参数:
    dates: 日期数组 np.ndarray[datetime64[D]]
    nav: 净值数组 np.ndarray[float]
    holidays: 节假日数组 np.ndarray[datetime64[D]]

    返回:
    (平均回撤幅度, 平均回撤恢复天数, 最大回撤恢复天数)
    """
    # 计算累计最大值
    running_max = np.maximum.accumulate(nav)

    # 寻找创新高的位置 (running_max 增加的点)
    # 我们需要 running_max[i] > running_max[i-1] 的索引
    is_new_peak = np.diff(running_max, prepend=running_max[0] - 1) > 0
    peak_indices = np.where(is_new_peak)[0]

    # 确保第一个点被视为峰值起点（如果它不是）
    if peak_indices.size == 0 or peak_indices[0] != 0:
        peak_indices = np.insert(peak_indices, 0, 0)

    recovery_times = []
    drawdown_magnitudes = []

    for i in range(len(peak_indices) - 1):
        idx_start = peak_indices[i]
        idx_end = peak_indices[i + 1]

        # 两个峰值之间的片段
        segment_nav = nav[idx_start : idx_end + 1]
        peak_val = nav[idx_start]
        trough_val = np.min(segment_nav)

        # 如果存在回撤
        if trough_val < peak_val:
            drawdown_magnitudes.append(abs((trough_val / peak_val) - 1))

            d_start = dates[idx_start]
            d_end = dates[idx_end]
            # 计算恢复期（自然日或交易日，此处使用busday_count排除特定节假日）
            duration = np.busday_count(d_start, d_end, holidays=holidays)
            recovery_times.append(duration)

    max_recovery = np.max(recovery_times) if recovery_times else 0
    return int(max_recovery)

