import pandas as pd
from datetime import timedelta, date
from pyecharts import options as opts
from pyecharts.charts import Line, Grid
import os


def calculate_indicators(df_period, risk_free_rate=0.02):
    """
    Calculates key performance indicators for a given period of data.
    Assumes 252 trading days in a year.
    """
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

    # Max Drawdown (already calculated daily, just find the min for the period)
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


def generate_performance_page_pyecharts(
    data_path="performance_data.csv", output_html="index.html"
):
    """
    生成包含业绩概览和净值曲线图的HTML页面。
    """
    # 1. 数据加载与处理
    df = pd.read_csv(data_path, parse_dates=["Date"])
    df.set_index("Date", inplace=True)
    df.sort_index(inplace=True)
    df["Strategy_Cumulative_Return"] = df["Strategy_Value"]
    df["Benchmark_Cumulative_Return"] = df["Benchmark_Value"]
    df["Excess_Return"] = (
        df["Strategy_Cumulative_Return"] - df["Benchmark_Cumulative_Return"]
    )

    # 2. 计算业绩概览数据
    today = df.index.max()
    year_start = pd.Timestamp(today.year, 1, 1)
    periods = {
        "当日": (today - timedelta(days=1), today),
        "近一周": (today - timedelta(weeks=1), today),
        "近一月": (today - timedelta(days=30), today),
        "近三月": (today - timedelta(days=90), today),
        "今年以来": (year_start, today),
    }
    summary_data = {}
    for period_name, (start_date, end_date) in periods.items():
        try:
            # 确保开始日期和结束日期在数据框的有效范围内
            if start_date < df.index.min():
                start_date_actual = df.index.min()
            else:
                start_date_actual = df.index.asof(start_date)

            if end_date > df.index.max():
                end_date_actual = df.index.max()
            else:
                end_date_actual = df.index.asof(end_date)

            period_df = df.loc[start_date_actual:end_date_actual]
            if len(period_df) < 2:
                raise ValueError("Not enough data")  # 至少需要两天数据来计算收益

            strategy_return = (
                period_df["Strategy_Cumulative_Return"].iloc[-1]
                / period_df["Strategy_Cumulative_Return"].iloc[0]
            ) - 1
            benchmark_return = (
                period_df["Benchmark_Cumulative_Return"].iloc[-1]
                / period_df["Benchmark_Cumulative_Return"].iloc[0]
            ) - 1
            excess_return = strategy_return - benchmark_return
        except (KeyError, IndexError, ValueError):
            strategy_return, benchmark_return, excess_return = (
                0.0,
                0.0,
                0.0,
            )  # 无法计算时设为0
        summary_data[period_name] = {
            "strategy_return": strategy_return * 100,
            "benchmark_return": benchmark_return * 100,
            "excess_return": excess_return * 100,
        }

    # drawdown
    df['Running_max'] = df['Strategy_Cumulative_Return'].cummax()
    df['Drawdown'] = df['Strategy_Cumulative_Return'] / df['Running_max'] - 1

    all_indicators_data = {
        '1m': calculate_indicators(df.loc[today - pd.DateOffset(months=1):]),
        '3m': calculate_indicators(df.loc[today - pd.DateOffset(months=3):]),
        '6m': calculate_indicators(df.loc[today - pd.DateOffset(months=6):]),
        '1y': calculate_indicators(df.loc[today - pd.DateOffset(years=1):]),
        'ytd': calculate_indicators(df.loc[str(today.year):]),
        'all': calculate_indicators(df),
    }

    # 3. 绘制净值曲线图
    date_list = df.index.strftime("%Y-%m-%d").tolist()
    # 收益率显示为百分比 (例如，1.2 变成 20%)
    strategy_data = [
        round(val * 100 - 100, 2) for val in df["Strategy_Cumulative_Return"]
    ]
    benchmark_data = [
        round(val * 100 - 100, 2) for val in df["Benchmark_Cumulative_Return"]
    ]
    excess_data = [
        round(val * 100, 2) for val in df["Excess_Return"]
    ]  # 超额收益直接是数值
    drawdown_data = [round(val * 100, 2 ) for val in df["Drawdown"]]

    line_chart = (
        Line(init_opts=opts.InitOpts(width="100%", height="500px", theme="light"))
        .add_xaxis(xaxis_data=date_list)
        .add_yaxis(
            series_name="策略收益",
            y_axis=strategy_data,
            is_smooth=True,
            linestyle_opts=opts.LineStyleOpts(width=2, color="#d9534f"),
            label_opts=opts.LabelOpts(is_show=False),
        )
        .add_yaxis(
            series_name="基准收益 (中证500)",
            y_axis=benchmark_data,
            is_smooth=True,
            linestyle_opts=opts.LineStyleOpts(width=2, color="#5cb85c"),
            label_opts=opts.LabelOpts(is_show=False),
            areastyle_opts=opts.AreaStyleOpts(opacity=0.2, color="#5cb85c"),
        )
        .add_yaxis(
            series_name="超额收益 (几何)",
            y_axis=excess_data,
            is_smooth=True,
            linestyle_opts=opts.LineStyleOpts(width=0),
            label_opts=opts.LabelOpts(is_show=False),
            areastyle_opts=opts.AreaStyleOpts(opacity=0.3, color="#808080"),
            z_level=-1,
        )
        # In the net_value_chart definition:
        .set_global_opts(
            title_opts=opts.TitleOpts(
                title="时间加权实盘净值曲线",
                subtitle="策略收益与基准收益率对比及超额收益",
                pos_left="center",
                pos_top="2%",
                item_gap=15,
            ),
            legend_opts=opts.LegendOpts(pos_top="12%", pos_left="center"),
            # This combines the tooltip and the synchronized crosshair
            tooltip_opts=opts.TooltipOpts(
                trigger="axis",
                axis_pointer_type="cross",
            ),
            axispointer_opts=opts.AxisPointerOpts(
                is_show=True, link=[{"xAxisIndex": "all"}]
            ),
            xaxis_opts=opts.AxisOpts(
                type_="category",
                boundary_gap=False,
                axislabel_opts=opts.LabelOpts(is_show=False),
            ),
            yaxis_opts=opts.AxisOpts(
                type_="value",
                name="收益率 (%)",
                axislabel_opts=opts.LabelOpts(formatter="{value} %"),
            ),
            # This correctly adds the synchronized slider
            datazoom_opts=[
                opts.DataZoomOpts(
                    type_="slider",
                    xaxis_index=[0, 1],  # Link to x-axis of chart 0 and chart 1
                    range_start=0,
                    range_end=100,
                )
            ],
            # This adds the toolbox
            toolbox_opts=opts.ToolboxOpts(is_show=True, pos_left="right"),
        )
    )

    drawdown_chart = (
        Line()
        .add_xaxis(xaxis_data=date_list)
        .add_yaxis(
            series_name="策略回撤",
            y_axis=drawdown_data,
            is_smooth=True,
            linestyle_opts=opts.LineStyleOpts(width=1, color="#d9534f"),
            label_opts=opts.LabelOpts(is_show=False),
            # Style as a red area chart
            areastyle_opts=opts.AreaStyleOpts(opacity=0.5, color="#d9534f"),
        )
        .set_global_opts(
            xaxis_opts=opts.AxisOpts(type_="category", boundary_gap=False, grid_index=1),
            yaxis_opts=opts.AxisOpts(type_="value", name="回撤 (%)", axislabel_opts=opts.LabelOpts(formatter="{value} %"), grid_index=1),
            legend_opts=opts.LegendOpts(is_show=False),
        )
    )

    grid_chart = (
        Grid(init_opts=opts.InitOpts(width="100%", height="700px"))
        .add(line_chart, grid_opts=opts.GridOpts(pos_top="15%", pos_bottom="30%"))
        .add(drawdown_chart, grid_opts=opts.GridOpts(pos_top="78%"))
    )

    # 4. 生成 summary cards 的 HTML
    cards_html = ""
    for period, data in summary_data.items():
        cards_html += f"""
        <div class="card">
            <p class="period-title">{period}</p>
            <p class="date-range">
                {periods[period][0].strftime('%Y-%m-%d')} ~ {periods[period][1].strftime('%Y-%m-%d')}
            </p>
            <div class="metric">
                <p>策略收益</p>
                <p class="value {'positive' if data['strategy_return'] >= 0 else 'negative'}">
                    <span class="{'icon-positive' if data['strategy_return'] >= 0 else 'icon-negative'}">
                        {'▲' if data['strategy_return'] >= 0 else '▼'}
                    </span>
                    {data['strategy_return']:.2f}%
                </p>
            </div>
            <div class="metric">
                <p>基准收益</p>
                <p class="value {'positive' if data['benchmark_return'] >= 0 else 'negative'}">
                    <span class="{'icon-positive' if data['benchmark_return'] >= 0 else 'icon-negative'}">
                        {'▲' if data['benchmark_return'] >= 0 else '▼'}
                    </span>
                    {data['benchmark_return']:.2f}%
                </p>
            </div>
            <div class="metric">
                <p>超额收益</p>
                <p class="value {'positive' if data['excess_return'] >= 0 else 'negative'}">
                    <span class="{'icon-positive' if data['excess_return'] >= 0 else 'icon-negative'}">
                        {'▲' if data['excess_return'] >= 0 else '▼'}
                    </span>
                    {data['excess_return']:.2f}%
                </p>
            </div>
        </div>
        """

    # 生成 indicators table 的 HTML
    # 生成 indicators card-style 的 HTML
    all_data = all_indicators_data["all"]
    indicator_html = f"""
    <div class="indicators-section">
        <h2>
            投资组合指标分析
            <p class="date-range-header">{all_data['start_date']} 至 {all_data['end_date']} ({all_data['days']}个交易日)</p>
        </h2>
        <div class="indicators-grid">
            <div class="indicator-column">
                <h3>收益指标</h3>
                <div class="indicator-card-row">
                    <div class="indicator-card">
                        <p class="metric-title">总收益率</p>
                        <p class="metric-value">{all_data['total_return_strategy']:.2f}%</p>
                        <p class="metric-benchmark">基准: {all_data['total_return_benchmark']:.2f}%</p>
                    </div>
                    <div class="indicator-card">
                        <p class="metric-title">年化收益率</p>
                        <p class="metric-value">{all_data['annualized_return_strategy']:.2f}%</p>
                        <p class="metric-benchmark">基准: {all_data['annualized_return_benchmark']:.2f}%</p>
                    </div>
                </div>
                <div class="indicator-card-row">
                    <div class="indicator-card full-width">
                         <p class="metric-title">超额收益 (几何)</p>
                        <p class="metric-value">{all_data['excess_return']:.2f}%</p>
                        <p class="metric-benchmark">年化: {all_data['annualized_alpha']:.2f}%</p>
                    </div>
                </div>
            </div>
            <div class="indicator-column">
                <h3>风险指标</h3>
                <div class="indicator-card-row">
                    <div class="indicator-card">
                        <p class="metric-title">波动率</p>
                        <p class="metric-value">{all_data['volatility_strategy']:.2f}%</p>
                        <p class="metric-benchmark">基准: {all_data['volatility_benchmark']:.2f}%</p>
                    </div>
                    <div class="indicator-card">
                        <p class="metric-title">夏普比率</p>
                        <p class="metric-value">{all_data['sharpe_ratio_strategy']:.2f}</p>
                        <p class="metric-benchmark">基准: {all_data['sharpe_ratio_benchmark']:.2f}</p>
                    </div>
                </div>
                <div class="indicator-card-row">
                     <div class="indicator-card">
                        <p class="metric-title">策略最大回撤</p>
                        <p class="metric-value drawdown">{all_data['max_drawdown_strategy']:.2f}%</p>
                        <p class="metric-benchmark">基于策略收益计算</p>
                    </div>
                     <div class="indicator-card">
                        <p class="metric-title">信息比率</p>
                        <p class="metric-value">{all_data['information_ratio']:.2f}</p>
                        <p class="metric-benchmark">超额收益风险调整后回报</p>
                    </div>
                </div>
            </div>
        </div>
    </div>
    """

    # 5. 获取 Pyecharts 图表生成的 HTML 片段和所需的 JS 依赖
    pyecharts_chart_embed_html = grid_chart.render_embed()

    # 获取 JS 依赖，并格式化成 <script> 标签
    # Note: line_chart.js_dependencies 是一个 OrderedSet, 需要先转为 list
    js_links_html = '<script src="https://assets.pyecharts.org/assets/v5/echarts.min.js"></script>'

    # 6. 组合成完整的 HTML 页面
    # 我们将自定义的 CSS 和 summary cards 放在 head 和 body 的开头
    final_html_content = f"""
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <title>策略业绩报告</title>
        {js_links_html}
        <style>
            body {{font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; margin: 20px; background-color: #f0f2f5; color: #333;}}
            .container {{ max-width: 1200px; margin: auto; background-color: #ffffff; padding: 30px; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); }}
            h1 {{ color: #2c3e50; text-align: center; margin-bottom: 40px; }}
            .summary-cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-bottom: 40px; }}
            .card {{ background-color: #fff; border: 1px solid #e0e0e0; border-radius: 6px; padding: 20px; text-align: center; }}
            .card .period-title {{ font-size: 1.1em; font-weight: bold; color: #007bff; margin-bottom: 5px; }}
            .card .date-range {{ font-size: 0.8em; color: #666; margin-bottom: 15px; }}
            .metric {{ margin-bottom: 10px; }}
            .metric p {{ margin: 0; font-size: 0.9em; color: #555; }}
            .metric .value {{
                font-size: 1.1em;
                font-weight: 700;
                margin-top: 5px;
                color: #333; /* Make the number dark grey/black */
            }}
            .icon-positive {{
                color: #28a745; /* Green */
            }}
            .icon-negative {{
                color: #dc3545; /* Red */
            }}
            .positive {{ color: #28a745; }}
            .negative {{ color: #dc3545; }}
            .chart-section {{ border: 1px solid #e0e0e0; border-radius: 6px; padding: 20px; }}

            .indicators-section {{
                margin-top: 40px;
                background-color: #ffffff;
                padding: 20px;
                border-radius: 8px;
            }}
            .indicators-section h2 {{
                margin-top: 0;
                margin-bottom: 25px;
            }}
            .date-range-header {{
                font-size: 0.7em;
                font-weight: normal;
                color: #666;
                margin-top: 5px;
            }}
            .indicators-grid {{
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 40px;
            }}
            .indicator-column h3 {{
                text-align: left;
                margin-top: 0;
                margin-bottom: 20px;
                font-size: 1.2em;
                color: #333;
            }}
            .indicator-card-row {{
                display: flex;
                gap: 20px;
                margin-bottom: 20px;
            }}
            .indicator-card {{
                background-color: #f8f9fa;
                border-radius: 8px;
                padding: 20px;
                flex: 1; /* Each card takes equal space in a row */
                text-align: left;
                box-shadow: 0 2px 4px rgba(0,0,0,0.03);
            }}
            .indicator-card.full-width {{
                flex-basis: 100%;
            }}
            p.metric-title {{
                margin: 0 0 10px 0;
                color: #555;
                font-size: 0.9em;
            }}
            p.metric-value {{
                margin: 0 0 8px 0;
                font-size: 1.8em;
                font-weight: 600;
                color: #333;
            }}
            p.metric-value.drawdown {{
                color: #d9534f; /* Red for drawdown */
            }}
            p.metric-benchmark {{
                margin: 0;
                color: #777;
                font-size: 0.85em;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>我的策略业绩报告</h1>
            <div class="summary-cards">
                {cards_html}
            </div>
            <div class="chart-section">
                {pyecharts_chart_embed_html}
            </div>
                {indicator_html}
        </div>
    </body>
    </html>
    """

    with open(output_html, "w", encoding="utf-8") as f:
        f.write(final_html_content)
    print(f"Pyecharts 业绩报告已生成到: {output_html}")


if __name__ == "__main__":
    generate_performance_page_pyecharts()
