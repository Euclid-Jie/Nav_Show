import pandas as pd
import numpy as np
import akshare as ak


def get_rate_interbank_df():
    rate_interbank_df = ak.rate_interbank(
        market="上海银行同业拆借市场", symbol="Shibor人民币", indicator="3月"
    )
    return rate_interbank_df

def calculate_rf_rate(rate_interbank_df, start_date, end_date):
    """
    Calculate the mean rf rate during a period to assist the calculation of the risk indicatiors like sharpe, etc.
    SHIBOR is chosen as default to be the rf rate.
    """
    rate_interbank_df["报告日"] = pd.to_datetime(rate_interbank_df["报告日"])
    mask = (rate_interbank_df["报告日"] >= start_date) & (rate_interbank_df["报告日"] <= end_date)
    return rate_interbank_df.loc[mask, "利率"].mean()


def calculate_indicators(df_period, rate_interbank_df):
    """
    Calculates key performance indicators for a given period of data.
    Assumes 252 trading days in a year.
    Combines original structure with new calculations.
    """
    # Create a copy to avoid SettingWithCopyWarning
    df_period = df_period.copy()

    custom_holidays = np.loadtxt("Chinese_special_holiday.txt", dtype="datetime64[D]")
    # Calculate average business day intervals
    if not df_period.empty and len(df_period) > 1:
        dates = df_period.index.values.astype("datetime64[D]")
        intervals = np.busday_count(dates[:-1], dates[1:], holidays=custom_holidays)
        avg_interval = intervals.mean() if intervals.size > 0 else 1
    else:
        avg_interval = 1

    # Handle cases with insufficient data
    if df_period.empty or len(df_period) < 2:
        return {
            metric: 0
            for metric in [
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
                "beta",
                "information_ratio",
                "max_drawdown_excess",
                "start_date",
                "end_date",
                "days",
                "avg_drawdown_magnitude_strategy",
                "avg_drawdown_recovery_days_strategy",
                "max_drawdown_recovery_days_strategy",
                "avg_drawdown_magnitude_benchmark",
                "avg_drawdown_recovery_days_benchmark",
                "max_drawdown_recovery_days_benchmark",
            ]
        }

    # Basic Info
    start_date_obj = df_period.index[0]
    end_date_obj = df_period.index[-1]
    start_date = df_period.index[0].strftime("%Y-%m-%d")
    end_date = df_period.index[-1].strftime("%Y-%m-%d")
    days = int(
        np.busday_count(
            start_date_obj.date(), end_date_obj.date(), holidays=custom_holidays
        )
        + 1
    )
    years = days / 252 if days > 0 else 0

    # Risk-free rate (assumed to be annualized)
    risk_free_rate = (
        calculate_rf_rate(rate_interbank_df, start_date, end_date) / 100
        if years > 0
        else 0
    )

    # --- Strategy Calculations ---
    strategy_returns = df_period["Strategy_Cumulative_Return"].pct_change().dropna()
    total_return_strategy = (
        df_period["Strategy_Cumulative_Return"].iloc[-1]
        / df_period["Strategy_Cumulative_Return"].iloc[0]
    ) - 1
    annualized_return_strategy = (
        (1 + total_return_strategy) ** (1 / years) - 1 if years > 0 else 0
    )
    volatility_strategy = (
        strategy_returns.std() * ((252 / avg_interval) ** 0.5)
        if not strategy_returns.empty
        else 0
    )
    sharpe_ratio_strategy = (
        (annualized_return_strategy - risk_free_rate) / volatility_strategy
        if volatility_strategy != 0
        else 0
    )

    # Sortino Ratio for Strategy
    negative_returns_strategy = strategy_returns[strategy_returns < 0]
    downside_deviation_strategy = (
        negative_returns_strategy.std() * ((252 / avg_interval) ** 0.5)
        if not negative_returns_strategy.empty
        else 0
    )
    sortino_ratio_strategy = (
        (annualized_return_strategy - risk_free_rate) / downside_deviation_strategy
        if downside_deviation_strategy != 0
        else 0
    )

    # --- Benchmark Calculations ---
    benchmark_returns = df_period["Benchmark_Cumulative_Return"].pct_change().dropna()
    total_return_benchmark = (
        df_period["Benchmark_Cumulative_Return"].iloc[-1]
        / df_period["Benchmark_Cumulative_Return"].iloc[0]
    ) - 1
    annualized_return_benchmark = (
        (1 + total_return_benchmark) ** (1 / years) - 1 if years > 0 else 0
    )
    volatility_benchmark = (
        benchmark_returns.std() * ((252 / avg_interval) ** 0.5)
        if not benchmark_returns.empty
        else 0
    )
    sharpe_ratio_benchmark = (
        (annualized_return_benchmark - risk_free_rate) / volatility_benchmark
        if volatility_benchmark != 0
        else 0
    )
    negative_returns_benchmark = benchmark_returns[benchmark_returns < 0]
    downside_deviation_benchmark = (
        negative_returns_benchmark.std() * ((252 / avg_interval) ** 0.5)
        if not negative_returns_benchmark.empty
        else 0
    )
    sortino_ratio_benchmark = (
        (annualized_return_benchmark - risk_free_rate) / downside_deviation_benchmark
        if downside_deviation_benchmark != 0
        else 0
    )

    # --- Alpha / Excess Return Calculations ---
    total_ari_excess_return = total_return_strategy - total_return_benchmark
    annualized_alpha = annualized_return_strategy - annualized_return_benchmark
    aligned_returns = pd.DataFrame(
        {"strategy": strategy_returns, "benchmark": benchmark_returns}
    ).dropna()
    excess_daily_returns = aligned_returns["strategy"] - aligned_returns["benchmark"]
    if not aligned_returns.empty and len(aligned_returns) > 1:
        covariance = aligned_returns["strategy"].cov(aligned_returns["benchmark"])
        variance = aligned_returns["benchmark"].var()
        beta = covariance / variance if variance != 0 else 0
    else:
        beta = 0
    if not excess_daily_returns.empty:
        cumulative_excess_return = (1 + excess_daily_returns).cumprod()
        total_geo_excess_return = cumulative_excess_return.iloc[-1] - 1
        volatility_excess = excess_daily_returns.std() * ((252 / avg_interval) ** 0.5)
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
    else:
        total_geo_excess_return = 0
        volatility_excess = 0
        information_ratio = 0
        sharpe_ratio_excess = 0

      # --- Max Drawdown Calculations ---
    df_period["Running_max_Strategy"] = df_period["Strategy_Cumulative_Return"].cummax()
    df_period["Drawdown_Strategy"] = (df_period["Strategy_Cumulative_Return"] / df_period["Running_max_Strategy"]) - 1
    max_drawdown_strategy = df_period["Drawdown_Strategy"].min()
    calmar_ratio_strategy = (annualized_return_strategy / abs(max_drawdown_strategy) if max_drawdown_strategy != 0 else 0)

    # NEW: Added Max Drawdown for Benchmark
    df_period["Running_max_Benchmark"] = df_period["Benchmark_Cumulative_Return"].cummax()
    df_period["Drawdown_Benchmark"] = (df_period["Benchmark_Cumulative_Return"] / df_period["Running_max_Benchmark"]) - 1
    max_drawdown_benchmark = df_period["Drawdown_Benchmark"].min()

    if not excess_daily_returns.empty:
        cumulative_excess_series = (1 + excess_daily_returns).cumprod()
        drawdown_excess = (cumulative_excess_series / cumulative_excess_series.cummax()) - 1
        max_drawdown_excess = drawdown_excess.min()
    else:
        max_drawdown_excess = 0

    # --- Strategy Drawdown Recovery Time & Magnitude ---
    s_recovery_times, s_drawdown_magnitudes = [], []
    s_hwm_indices = df_period.index[df_period["Strategy_Cumulative_Return"].cummax().diff() > 0]
    s_all_peaks = df_period.index[:1].union(s_hwm_indices)
    for i in range(len(s_all_peaks) - 1):
        peak_date, next_peak_date = s_all_peaks[i], s_all_peaks[i+1]
        period = df_period.loc[peak_date:next_peak_date]
        peak_val, trough_val = period.loc[peak_date, "Strategy_Cumulative_Return"], period["Strategy_Cumulative_Return"].min()
        if trough_val < peak_val:
            s_drawdown_magnitudes.append(abs((trough_val / peak_val) - 1))
            duration = np.busday_count(peak_date.date(), next_peak_date.date(), holidays=custom_holidays)
            s_recovery_times.append(duration)
    avg_dd_recovery_days_s = np.mean(s_recovery_times) if s_recovery_times else 0
    max_dd_recovery_days_s = np.max(s_recovery_times) if s_recovery_times else 0
    avg_dd_magnitude_s = np.mean(s_drawdown_magnitudes) if s_drawdown_magnitudes else 0

    # NEW: --- Benchmark Drawdown Recovery Time & Magnitude ---
    b_recovery_times, b_drawdown_magnitudes = [], []
    b_hwm_indices = df_period.index[df_period["Benchmark_Cumulative_Return"].cummax().diff() > 0]
    b_all_peaks = df_period.index[:1].union(b_hwm_indices)
    for i in range(len(b_all_peaks) - 1):
        peak_date, next_peak_date = b_all_peaks[i], b_all_peaks[i+1]
        period = df_period.loc[peak_date:next_peak_date]
        peak_val, trough_val = period.loc[peak_date, "Benchmark_Cumulative_Return"], period["Benchmark_Cumulative_Return"].min()
        if trough_val < peak_val:
            b_drawdown_magnitudes.append(abs((trough_val / peak_val) - 1))
            duration = np.busday_count(peak_date.date(), next_peak_date.date(), holidays=custom_holidays)
            b_recovery_times.append(duration)
    avg_dd_recovery_days_b = np.mean(b_recovery_times) if b_recovery_times else 0
    max_dd_recovery_days_b = np.max(b_recovery_times) if b_recovery_times else 0
    avg_dd_magnitude_b = np.mean(b_drawdown_magnitudes) if b_drawdown_magnitudes else 0

    return {
        # Strategy Metrics
        "total_return_strategy": total_return_strategy * 100,
        "annualized_return_strategy": annualized_return_strategy * 100,
        "volatility_strategy": volatility_strategy * 100,
        "sharpe_ratio_strategy": sharpe_ratio_strategy,
        "sortino_ratio_strategy": sortino_ratio_strategy,
        "calmar_ratio_strategy": calmar_ratio_strategy,
        "max_drawdown_strategy": abs(max_drawdown_strategy * 100),
        # Benchmark Metrics
        "total_return_benchmark": total_return_benchmark * 100,
        "annualized_return_benchmark": annualized_return_benchmark * 100,
        "volatility_benchmark": volatility_benchmark * 100,
        "sharpe_ratio_benchmark": sharpe_ratio_benchmark,
        "sortino_ratio_benchmark": sortino_ratio_benchmark,
        # Excess Return Metrics
        "total_ari_excess_return": total_ari_excess_return * 100,
        "total_geo_excess_return": total_geo_excess_return * 100,
        "annualized_alpha": annualized_alpha * 100,
        "beta": beta,
        "information_ratio": information_ratio,
        "volatility_excess": volatility_excess * 100,
        "sharpe_ratio_excess": sharpe_ratio_excess,
        "max_drawdown_excess": abs(max_drawdown_excess * 100),
        # General Info
        "start_date": start_date,
        "end_date": end_date,
        "days": days,
        # Drawdown Analysis Metrics
        "avg_drawdown_magnitude_strategy": avg_dd_magnitude_s * 100,
        "avg_drawdown_recovery_days_strategy": avg_dd_recovery_days_s,
        "max_drawdown_recovery_days_strategy": max_dd_recovery_days_s,
        "avg_drawdown_magnitude_benchmark": avg_dd_magnitude_b * 100,
        "avg_drawdown_recovery_days_benchmark": avg_dd_recovery_days_b,
        "max_drawdown_recovery_days_benchmark": max_dd_recovery_days_b,
    }
