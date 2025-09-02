import pandas as pd


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
    """
    # Create a copy to avoid SettingWithCopyWarning
    df_period = df_period.copy()

    if df_period.empty or len(df_period) < 2:
        return {
            metric: 0
            for metric in [
                "total_return_strategy",
                "annualized_return_strategy",
                "volatility_strategy",
                "sharpe_ratio_strategy",
                "max_drawdown_strategy",
                "total_return_benchmark",
                "annualized_return_benchmark",
                "volatility_benchmark",
                "sharpe_ratio_benchmark",
                "excess_return",
                "annualized_alpha",
                "information_ratio",
                "start_date",
                "end_date",
                "days",
            ]
        }

    # Basic Info
    start_date = df_period.index[0].strftime("%Y-%m-%d")
    end_date = df_period.index[-1].strftime("%Y-%m-%d")
    days = len(df_period)
    years = days / 252

    # Risk-free rate
    risk_free_rate = calculate_rf_rate(rate_interbank_df, start_date, end_date) / 100 if days > 0 else 0

    # Strategy Calculations
    strategy_returns = df_period["Strategy_Cumulative_Return"].pct_change().dropna()
    total_return_strategy = (
        df_period["Strategy_Cumulative_Return"].iloc[-1]
        / df_period["Strategy_Cumulative_Return"].iloc[0]
    ) - 1
    annualized_return_strategy = (
        (1 + total_return_strategy) ** (1 / years) - 1 if years > 0 else 0
    )
    volatility_strategy = strategy_returns.std() * (252**0.5)
    sharpe_ratio_strategy = (
        (annualized_return_strategy - risk_free_rate) / volatility_strategy
        if volatility_strategy != 0
        else 0
    )

    # Benchmark Calculations
    benchmark_returns = df_period["Benchmark_Cumulative_Return"].pct_change().dropna()
    total_return_benchmark = (
        df_period["Benchmark_Cumulative_Return"].iloc[-1]
        / df_period["Benchmark_Cumulative_Return"].iloc[0]
    ) - 1
    annualized_return_benchmark = (
        (1 + total_return_benchmark) ** (1 / years) - 1 if years > 0 else 0
    )
    volatility_benchmark = benchmark_returns.std() * (252**0.5)
    sharpe_ratio_benchmark = (
        (annualized_return_benchmark - risk_free_rate) / volatility_benchmark
        if volatility_benchmark != 0
        else 0
    )

    # Alpha / Excess Return Calculations
    excess_return = total_return_strategy - total_return_benchmark
    annualized_alpha = annualized_return_strategy - annualized_return_benchmark
    excess_daily_returns = strategy_returns - benchmark_returns
    volatility_of_alpha = excess_daily_returns.std() * (252**0.5)
    information_ratio = (
        annualized_alpha / volatility_of_alpha if volatility_of_alpha != 0 else 0
    )

    # Max Drawdown for the period
    df_period["Running_max"] = df_period["Strategy_Cumulative_Return"].cummax()
    df_period["Drawdown"] = (
        df_period["Strategy_Cumulative_Return"] / df_period["Running_max"] - 1
    )
    max_drawdown_strategy = df_period["Drawdown"].min()

    return {
        "total_return_strategy": total_return_strategy * 100,
        "annualized_return_strategy": annualized_return_strategy * 100,
        "volatility_strategy": volatility_strategy * 100,
        "sharpe_ratio_strategy": sharpe_ratio_strategy,
        "max_drawdown_strategy": abs(max_drawdown_strategy * 100),
        "total_return_benchmark": total_return_benchmark * 100,
        "annualized_return_benchmark": annualized_return_benchmark * 100,
        "volatility_benchmark": volatility_benchmark * 100,
        "sharpe_ratio_benchmark": sharpe_ratio_benchmark,
        "excess_return": excess_return * 100,
        "annualized_alpha": annualized_alpha * 100,
        "information_ratio": information_ratio,
        "start_date": start_date,
        "end_date": end_date,
        "days": days,
    }
