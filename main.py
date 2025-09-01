import pandas as pd
from datetime import timedelta, date
from pyecharts import options as opts
from pyecharts.charts import Line

# 不再需要 Page, Html，因为我们将手动拼接 HTML
# from pyecharts.charts import Page, Html


def generate_performance_page_pyecharts(
    data_path="performance_data.csv", output_html="performance_report.html"
):
    """
    使用手动 HTML 拼接和 Pyecharts 渲染嵌入方式，生成包含业绩概览和净值曲线图的HTML页面。
    """
    # 1. 数据加载与处理 (无变化)
    df = pd.read_csv(data_path, parse_dates=["Date"])
    df.set_index("Date", inplace=True)
    df.sort_index(inplace=True)
    df["Strategy_Cumulative_Return"] = df["Strategy_Value"]
    df["Benchmark_Cumulative_Return"] = df["Benchmark_Value"]
    df["Excess_Return"] = (
        df["Strategy_Cumulative_Return"] - df["Benchmark_Cumulative_Return"]
    )

    # 2. 计算业绩概览数据 (无变化)
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

    # 3. 绘制净值曲线图 (无变化)
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
        .set_global_opts(
            title_opts=opts.TitleOpts(
                title="时间加权实盘净值曲线",
                subtitle="策略收益与基准收益率对比及超额收益",
                pos_left="center",
            ),
            tooltip_opts=opts.TooltipOpts(
                trigger="axis",
                axis_pointer_type="cross",
                background_color="rgba(255, 255, 255, 0.8)",
            ),
            legend_opts=opts.LegendOpts(pos_top="8%", pos_left="center"),
            xaxis_opts=opts.AxisOpts(type_="category", boundary_gap=False),
            yaxis_opts=opts.AxisOpts(
                type_="value",
                name="收益率 (%)",
                axislabel_opts=opts.LabelOpts(formatter="{value} %"),
            ),
            datazoom_opts=[
                opts.DataZoomOpts(type_="inside", range_start=0, range_end=100),
                opts.DataZoomOpts(type_="slider", range_start=0, range_end=100),
            ],
        )
    )

    # 4. 生成 summary cards 的 HTML (无变化)
    cards_html = ""
    for period, data in summary_data.items():
        cards_html += f"""<div class="card"><p class="period-title">{period}</p><p class="date-range">{periods[period][0].strftime('%Y-%m-%d')} ~ {periods[period][1].strftime('%Y-%m-%d')}</p><div class="metric"><p>策略收益</p><p class="value {'positive' if data['strategy_return'] >= 0 else 'negative'}">{'▲' if data['strategy_return'] >= 0 else '▼'} {data['strategy_return']:.2f}%</p></div><div class="metric"><p>基准收益</p><p class="value {'positive' if data['benchmark_return'] >= 0 else 'negative'}">{'▲' if data['benchmark_return'] >= 0 else '▼'} {data['benchmark_return']:.2f}%</p></div><div class="metric"><p>超额收益</p><p class="value {'positive' if data['excess_return'] >= 0 else 'negative'}">{'▲' if data['excess_return'] >= 0 else '▼'} {data['excess_return']:.2f}%</p></div></div>"""

    # 5. 获取 Pyecharts 图表生成的 HTML 片段和所需的 JS 依赖
    pyecharts_chart_embed_html = line_chart.render_embed()

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
            body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; margin: 20px; background-color: #f0f2f5; color: #333; }}
            .container {{ max-width: 1200px; margin: auto; background-color: #ffffff; padding: 30px; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); }}
            h1 {{ color: #2c3e50; text-align: center; margin-bottom: 40px; }}
            .summary-cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-bottom: 40px; }}
            .card {{ background-color: #fff; border: 1px solid #e0e0e0; border-radius: 6px; padding: 20px; text-align: center; }}
            .card .period-title {{ font-size: 1.1em; font-weight: bold; color: #007bff; margin-bottom: 5px; }}
            .card .date-range {{ font-size: 0.8em; color: #666; margin-bottom: 15px; }}
            .metric {{ margin-bottom: 10px; }}
            .metric p {{ margin: 0; font-size: 0.9em; color: #555; }}
            .metric .value {{ font-size: 1.1em; font-weight: bold; margin-top: 5px; }}
            .positive {{ color: #28a745; }}
            .negative {{ color: #dc3545; }}
            .chart-section {{ border: 1px solid #e0e0e0; border-radius: 6px; padding: 20px; }}
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
        </div>
    </body>
    </html>
    """

    with open(output_html, "w", encoding="utf-8") as f:
        f.write(final_html_content)
    print(f"Pyecharts 业绩报告已生成到: {output_html}")



if __name__ == "__main__":
    generate_performance_page_pyecharts()
