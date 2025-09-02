import pandas as pd
import numpy as np
import json
from datetime import timedelta, date
from pyecharts import options as opts
from pyecharts.charts import Line, Grid
import os


def calculate_indicators(df_period, risk_free_rate=0.02):
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


def generate_performance_page_from_template(
    data_path="performance_data.csv",
    template_path="template.html",
    output_html="index.html",
):
    """
    Reads data, populates an HTML template, and generates a self-contained report file.
    """
    # 1. Data loading and processing
    df = pd.read_csv(data_path, parse_dates=["Date"])
    df.set_index("Date", inplace=True)
    df.sort_index(inplace=True)
    df["Strategy_Cumulative_Return"] = df["Strategy_Value"]
    df["Benchmark_Cumulative_Return"] = df["Benchmark_Value"]

    df["Running_max_global"] = df["Strategy_Cumulative_Return"].cummax()
    df["Drawdown_global"] = (
        df["Strategy_Cumulative_Return"] / df["Running_max_global"] - 1
    )

    # 2. Calculate data for all periods
    today = df.index.max()
    all_indicators_data = {
        "1m": calculate_indicators(df.loc[today - pd.DateOffset(months=1) :]),
        "3m": calculate_indicators(df.loc[today - pd.DateOffset(months=3) :]),
        "6m": calculate_indicators(df.loc[today - pd.DateOffset(months=6) :]),
        "ytd": calculate_indicators(df.loc[str(today.year) :]),
        "1y": calculate_indicators(df.loc[today - pd.DateOffset(years=1) :]),
        "all": calculate_indicators(df),
    }

    # 3. Generate HTML for summary cards
    year_start = pd.Timestamp(today.year, 1, 1)
    periods = {
        "当日": (today, today),
        "近一周": (today - timedelta(weeks=1), today),
        "近一月": (today - timedelta(days=30), today),
        "近三月": (today - timedelta(days=90), today),
        "今年以来": (year_start, today),
        "成立以来": (df.index.min(), today),
    }
    summary_cards_html = ""
    for period_name, (start_date, end_date) in periods.items():
        try:
            start_date_actual = df.index.asof(start_date)
            end_date_actual = df.index.asof(end_date)
            period_df = df.loc[start_date_actual:end_date_actual]

            if period_name == "当日":
                daily_returns = df["Strategy_Cumulative_Return"].pct_change()
                strategy_return = daily_returns.get(end_date_actual, 0.0)
                benchmark_daily_returns = df["Benchmark_Cumulative_Return"].pct_change()
                benchmark_return = benchmark_daily_returns.get(end_date_actual, 0.0)
            elif len(period_df) < 2:
                raise ValueError("Not enough data")
            else:
                strategy_return = (
                    period_df["Strategy_Cumulative_Return"].iloc[-1]
                    / period_df["Strategy_Cumulative_Return"].iloc[0]
                ) - 1
                benchmark_return = (
                    period_df["Benchmark_Cumulative_Return"].iloc[-1]
                    / period_df["Benchmark_Cumulative_Return"].iloc[0]
                ) - 1

            excess_return = strategy_return - benchmark_return
        except (KeyError, IndexError, ValueError, TypeError):
            strategy_return, benchmark_return, excess_return = (0.0, 0.0, 0.0)

        start_display = start_date.strftime("%Y-%m-%d")
        end_display = end_date.strftime("%Y-%m-%d")
        date_range_str = (
            f"{start_display} ~ {end_display}"
            if start_display != end_display
            else start_display
        )

        summary_cards_html += f"""
        <div class="card">
            <p class="period-title">{period_name}</p><p class="date-range">{date_range_str}</p>
            <div class="metric"><p>策略收益</p><p class="value {'positive' if strategy_return >= 0 else 'negative'}">{'▲' if strategy_return >= 0 else '▼'} {strategy_return * 100:.2f}%</p></div>
            <div class="metric"><p>基准收益</p><p class="value {'positive' if benchmark_return >= 0 else 'negative'}">{'▲' if benchmark_return >= 0 else '▼'} {benchmark_return * 100:.2f}%</p></div>
            <div class="metric"><p>超额收益</p><p class="value {'positive' if excess_return >= 0 else 'negative'}">{'▲' if excess_return >= 0 else '▼'} {excess_return * 100:.2f}%</p></div>
        </div>"""

    # 4. Generate Pyecharts configuration
    date_list = df.index.strftime("%Y-%m-%d").tolist()
    strategy_data = [
        round((val - 1) * 100, 2) for val in df["Strategy_Cumulative_Return"]
    ]
    benchmark_data = [
        round((val - 1) * 100, 2) for val in df["Benchmark_Cumulative_Return"]
    ]
    excess_data = [round(s - b, 2) for s, b in zip(strategy_data, benchmark_data)]
    drawdown_data = [round(val * 100, 2) for val in df["Drawdown_global"]]

    line_chart = (
        Line(init_opts=opts.InitOpts(height="500px", theme="light"))
        .add_xaxis(xaxis_data=date_list)
        .add_yaxis(
            "策略收益",
            strategy_data,
            is_smooth=True,
            linestyle_opts=opts.LineStyleOpts(width=2, color="#d9534f"),
        )
        .add_yaxis(
            "基准收益 (中证500)",
            benchmark_data,
            is_smooth=True,
            linestyle_opts=opts.LineStyleOpts(width=2, color="#5cb85c"),
        )
        .add_yaxis(
            "超额收益",
            excess_data,
            is_smooth=True,
            linestyle_opts=opts.LineStyleOpts(width=1, type_="dashed", color="#007bff"),
        )
        .set_global_opts(
            title_opts=opts.TitleOpts(title="时间加权实盘净值曲线", pos_left="center"),
            legend_opts=opts.LegendOpts(pos_top="8%", pos_left="center"),
            tooltip_opts=opts.TooltipOpts(trigger="axis", axis_pointer_type="cross"),
            axispointer_opts=opts.AxisPointerOpts(
                is_show=True, link=[{"xAxisIndex": "all"}]
            ),
            xaxis_opts=opts.AxisOpts(type_="category", boundary_gap=False),
            yaxis_opts=opts.AxisOpts(
                name="收益率 (%)", axislabel_opts=opts.LabelOpts(formatter="{value} %")
            ),
            datazoom_opts=[opts.DataZoomOpts(type_="slider", xaxis_index=[0, 1])],
            toolbox_opts=opts.ToolboxOpts(is_show=True, pos_left="right"),
        )
    )
    drawdown_chart = (
        Line()
        .add_xaxis(date_list)
        .add_yaxis(
            "策略回撤",
            drawdown_data,
            is_smooth=True,
            label_opts=opts.LabelOpts(is_show=False),
            linestyle_opts=opts.LineStyleOpts(width=1, color="#d9534f"),
            areastyle_opts=opts.AreaStyleOpts(opacity=0.5, color="#d9534f"),
        )
        .set_global_opts(
            yaxis_opts=opts.AxisOpts(
                name="回撤 (%)", axislabel_opts=opts.LabelOpts(formatter="{value} %")
            )
        )
    )
    grid_chart = Grid(init_opts=opts.InitOpts(width="100%", height="700px"))
    grid_chart.add(line_chart, grid_opts=opts.GridOpts(pos_top="15%", pos_bottom="30%"))
    grid_chart.add(
        drawdown_chart, grid_opts=opts.GridOpts(pos_top="75%", pos_bottom="5%")
    )

    # 5. Prepare data for template injection
    chart_config_json = grid_chart.dump_options_with_quotes()
    all_indicators_json = json.dumps(all_indicators_data)

    # 6. Read template, inject data, and write to output file
    with open(template_path, "r", encoding="utf-8") as f:
        template_content = f.read()

    final_html = template_content.replace(
        "{{ SUMMARY_CARDS_HTML }}", summary_cards_html
    )
    final_html = final_html.replace("'{{ CHART_CONFIG_JSON }}'", chart_config_json)
    final_html = final_html.replace("'{{ ALL_INDICATORS_JSON }}'", all_indicators_json)

    with open(output_html, "w", encoding="utf-8") as f:
        f.write(final_html)

    print(f"独立的业绩报告文件已生成: {output_html}")


if __name__ == "__main__":
    # Run the report generation
    generate_performance_page_from_template()
