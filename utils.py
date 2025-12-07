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


def calculate_indicators(
    dates: np.ndarray, strategy_nav: np.ndarray, benchmark_nav: np.ndarray = None
):
    """
    计算关键业绩指标 (KPIs)

    参数:
    dates: 日期数组
    strategy_nav: 策略净值数组
    benchmark_nav: 基准净值数组 (可选)

    返回:
    包含各项指标的字典
    """
    # 确保日期格式为 datetime64[D]
    dates_D = dates.astype("datetime64[D]")

    try:
        custom_holidays = np.loadtxt(
            "Chinese_special_holiday.txt", dtype="datetime64[D]"
        )
    except OSError:
        custom_holidays = np.array([], dtype="datetime64[D]")

    # 处理数据不足的情况
    if len(dates) < 2:
        return _get_empty_metrics(dates_D)

    # 基础信息
    start_date = str(dates_D[0])
    end_date = str(dates_D[-1])

    # 计算平均交易日间隔，用于年化计算
    intervals = np.busday_count(dates_D[:-1], dates_D[1:], holidays=custom_holidays)
    avg_interval = intervals.mean() if intervals.size > 0 else 1

    days = int(np.busday_count(dates_D[0], dates_D[-1], holidays=custom_holidays) + 1)
    years = days / 252 if days > 0 else 0
    risk_free_rate = 0.02  # 假设无风险利率 2%

    # --- 策略指标计算 ---
    strategy_returns = np.diff(strategy_nav) / strategy_nav[:-1]

    # 胜率
    win_rate_s = (
        np.sum(strategy_returns > 0) / len(strategy_returns)
        if len(strategy_returns) > 0
        else 0
    )

    # 总收益与年化收益
    total_return_strategy = (strategy_nav[-1] / strategy_nav[0]) - 1
    annualized_return_strategy = (
        (1 + total_return_strategy) ** (1 / years) - 1 if years > 0 else 0
    )

    # 波动率与夏普比率
    volatility_strategy = (
        strategy_returns.std(ddof=1) * np.sqrt(252 / avg_interval)
        if len(strategy_returns) > 1
        else 0
    )
    sharpe_ratio_strategy = (
        (annualized_return_strategy - risk_free_rate) / volatility_strategy
        if volatility_strategy != 0
        else 0
    )

    # 索提诺比率 (下行风险)
    neg_ret_s = strategy_returns[strategy_returns < 0]
    downside_dev_s = (
        neg_ret_s.std(ddof=1) * np.sqrt(252 / avg_interval) if len(neg_ret_s) > 1 else 0
    )
    sortino_ratio_strategy = (
        (annualized_return_strategy - risk_free_rate) / downside_dev_s
        if downside_dev_s != 0
        else 0
    )

    # 最大回撤与卡玛比率
    running_max_s = np.maximum.accumulate(strategy_nav)
    drawdown_s = (strategy_nav / running_max_s) - 1
    max_drawdown_strategy = drawdown_s.min()
    calmar_ratio_strategy = (
        annualized_return_strategy / abs(max_drawdown_strategy)
        if max_drawdown_strategy != 0
        else 0
    )

    # 回撤统计
    max_dd_recovery_days_s = calculate_drawdown_stats(
        dates_D, strategy_nav, custom_holidays
    )

    # --- 基准指标计算 ---
    has_benchmark = benchmark_nav is not None and len(benchmark_nav) == len(
        strategy_nav
    )

    if has_benchmark:
        benchmark_returns = np.diff(benchmark_nav) / benchmark_nav[:-1]
        win_rate_b = (
            np.sum(benchmark_returns > 0) / len(benchmark_returns)
            if len(benchmark_returns) > 0
            else 0
        )

        total_return_benchmark = (benchmark_nav[-1] / benchmark_nav[0]) - 1
        annualized_return_benchmark = (
            (1 + total_return_benchmark) ** (1 / years) - 1 if years > 0 else 0
        )

        volatility_benchmark = (
            benchmark_returns.std(ddof=1) * np.sqrt(252 / avg_interval)
            if len(benchmark_returns) > 1
            else 0
        )
        sharpe_ratio_benchmark = (
            (annualized_return_benchmark - risk_free_rate) / volatility_benchmark
            if volatility_benchmark != 0
            else 0
        )

        neg_ret_b = benchmark_returns[benchmark_returns < 0]
        downside_dev_b = (
            neg_ret_b.std(ddof=1) * np.sqrt(252 / avg_interval)
            if len(neg_ret_b) > 1
            else 0
        )
        sortino_ratio_benchmark = (
            (annualized_return_benchmark - risk_free_rate) / downside_dev_b
            if downside_dev_b != 0
            else 0
        )

        # --- 超额收益指标 ---
        total_ari_excess_return = total_return_strategy - total_return_benchmark
        annualized_alpha = annualized_return_strategy - annualized_return_benchmark

        excess_daily_returns = strategy_returns - benchmark_returns
        win_rate_e = (
            np.sum(excess_daily_returns > 0) / len(excess_daily_returns)
            if len(excess_daily_returns) > 0
            else 0
        )

        cumulative_excess_return = np.cumprod(1 + excess_daily_returns)
        total_geo_excess_return = cumulative_excess_return[-1] - 1

        volatility_excess = excess_daily_returns.std(ddof=1) * np.sqrt(
            252 / avg_interval
        )
        information_ratio = (
            annualized_alpha / volatility_excess if volatility_excess != 0 else 0
        )

        annualized_return_excess = (
            (1 + total_geo_excess_return) ** (1 / years) - 1 if years > 0 else 0
        )
        sharpe_ratio_excess = (
            (annualized_return_excess - risk_free_rate) / volatility_excess
            if volatility_excess != 0
            else 0
        )

        running_max_excess = np.maximum.accumulate(cumulative_excess_return)
        drawdown_excess = (cumulative_excess_return / running_max_excess) - 1
        max_drawdown_excess = drawdown_excess.min()

        max_dd_recovery_days_e = calculate_drawdown_stats(
            dates_D, cumulative_excess_return, custom_holidays
        )

        max_dd_recovery_days_b = calculate_drawdown_stats(
            dates_D, benchmark_nav, custom_holidays
        )

    else:
        # 无基准时的默认值
        total_return_benchmark = 0
        win_rate_b = 0
        annualized_return_benchmark = 0
        volatility_benchmark = 0
        sharpe_ratio_benchmark = 0
        sortino_ratio_benchmark = 0
        total_ari_excess_return = 0
        total_geo_excess_return = 0
        win_rate_e = 0
        annualized_alpha = 0
        information_ratio = 0
        volatility_excess = 0
        sharpe_ratio_excess = 0
        max_drawdown_excess = 0
        max_dd_recovery_days_e = 0
        max_dd_recovery_days_b = 0

    return {
        # 策略指标
        "total_return_strategy": total_return_strategy * 100,
        "win_rate_strategy": win_rate_s * 100,
        "annualized_return_strategy": annualized_return_strategy * 100,
        "volatility_strategy": volatility_strategy * 100,
        "sharpe_ratio_strategy": sharpe_ratio_strategy,
        "sortino_ratio_strategy": sortino_ratio_strategy,
        "calmar_ratio_strategy": calmar_ratio_strategy,
        "max_drawdown_strategy": abs(max_drawdown_strategy * 100),
        # 基准指标
        "total_return_benchmark": total_return_benchmark * 100,
        "win_rate_benchmark": win_rate_b * 100,
        "annualized_return_benchmark": annualized_return_benchmark * 100,
        "volatility_benchmark": volatility_benchmark * 100,
        "sharpe_ratio_benchmark": sharpe_ratio_benchmark,
        "sortino_ratio_benchmark": sortino_ratio_benchmark,
        # 超额指标
        "total_ari_excess_return": total_ari_excess_return * 100,
        "total_geo_excess_return": total_geo_excess_return * 100,
        "win_rate_excess": win_rate_e * 100,
        "annualized_alpha": annualized_alpha * 100,
        "information_ratio": information_ratio,
        "volatility_excess": volatility_excess * 100,
        "sharpe_ratio_excess": sharpe_ratio_excess,
        "max_drawdown_excess": abs(max_drawdown_excess * 100),
        # 通用信息
        "start_date": start_date,
        "end_date": end_date,
        "days": days,
        # 回撤分析
        "max_drawdown_recovery_days_strategy": max_dd_recovery_days_s,
        "max_drawdown_recovery_days_benchmark": max_dd_recovery_days_b,
        "max_drawdown_recovery_days_excess": max_dd_recovery_days_e,
    }


def _get_empty_metrics(dates_D):
    """返回空指标字典"""
    keys = [
        "total_return_strategy",
        "annualized_return_strategy",
        "volatility_strategy",
        "sharpe_ratio_strategy",
        "sortino_ratio_strategy",
        "calmar_ratio_strategy",
        "max_drawdown_strategy",
        "total_return_benchmark",
        "annualized_return_benchmark",
        "volatility_benchmark",
        "sharpe_ratio_benchmark",
        "sortino_ratio_benchmark",
        "volatility_excess",
        "total_ari_excess_return",
        "total_geo_excess_return",
        "sharpe_ratio_excess",
        "annualized_alpha",
        "win_rate_strategy",
        "win_rate_benchmark",
        "win_rate_excess",
        "information_ratio",
        "max_drawdown_excess",
        "days",
        "avg_drawdown_magnitude_strategy",
        "avg_drawdown_recovery_days_strategy",
        "max_drawdown_recovery_days_strategy",
        "avg_drawdown_magnitude_benchmark",
        "avg_drawdown_recovery_days_benchmark",
        "max_drawdown_recovery_days_benchmark",
        "avg_drawdown_magnitude_excess",
        "avg_drawdown_recovery_days_excess",
        "max_drawdown_recovery_days_excess",
    ]
    metrics = {k: 0 for k in keys}
    metrics["start_date"] = str(dates_D[0]) if len(dates_D) > 0 else ""
    metrics["end_date"] = str(dates_D[-1]) if len(dates_D) > 0 else ""
    return metrics
