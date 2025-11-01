import pandas as pd
import json
from datetime import timedelta
from pyecharts import options as opts
from pyecharts.charts import Line, Grid
from utils import calculate_indicators, get_rate_interbank_df


def generate_performance_page_from_template(
    rate_interbank_df,
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

    if "Benchmark_Value" not in df.columns or df["Benchmark_Value"].isna().all():
        # 创建值为1的基准（表示无变化）
        df["Benchmark_Value"] = 1.0
        df["Benchmark_Cumulative_Return"] = 1.0
        print("警告：未找到有效的基准数据，使用默认基准值1")
    else:
        # 如果有基准数据，计算基准累计收益
        df["Benchmark_Cumulative_Return"] = df["Benchmark_Value"]

    df["Strategy_Cumulative_Return"] = df["Strategy_Value"]
    df["Benchmark_Cumulative_Return"] = df["Benchmark_Value"]
    df["Excess_Return_Pct"] = (
        df["Strategy_Cumulative_Return"].pct_change()
        - df["Benchmark_Cumulative_Return"].pct_change()
    )
    df["Excess_Return_Cumulative"] = (1 + df["Excess_Return_Pct"].fillna(0)).cumprod()

    df["Running_max_global"] = df["Strategy_Cumulative_Return"].cummax()
    df["Drawdown_global"] = (df["Strategy_Cumulative_Return"] / df["Running_max_global"]) - 1
    df["Running_max_excess"] = df["Excess_Return_Cumulative"].cummax()
    df["Drawdown_excess"] = (df["Excess_Return_Cumulative"] / df["Running_max_excess"]) - 1

    # 2. Calculate data for all periods
    all_data = {}
    today = df.index.max()

    indicator_periods = {
        "1m": df.loc[today - pd.DateOffset(months=1) :],
        "3m": df.loc[today - pd.DateOffset(months=3) :],
        "6m": df.loc[today - pd.DateOffset(months=6) :],
        "ytd": df.loc[str(today.year) :],
        "1y": df.loc[today - pd.DateOffset(years=1) :],
        "all": df,
    }
    for key, period_df in indicator_periods.items():
        all_data[key] = calculate_indicators(period_df, rate_interbank_df)

    try:
        daily_returns_s = df["Strategy_Cumulative_Return"].pct_change()
        daily_returns_b = df["Benchmark_Cumulative_Return"].pct_change()
        s_return = daily_returns_s.loc[today] * 100
        b_return = daily_returns_b.loc[today] * 100
        all_data["daily"] = {
            "total_return_strategy": s_return,
            "total_return_benchmark": b_return,
            "total_ari_excess_return": s_return - b_return,
            "start_date": today.strftime("%Y-%m-%d"),
            "end_date": today.strftime("%Y-%m-%d"),
        }

    except KeyError:  # 如果当天不是交易日
        all_data["daily"] = {
            "total_return_strategy": 0,
            "total_return_benchmark": 0,
            "total_ari_excess_return": 0,
            "start_date": today.strftime("%Y-%m-%d"),
            "end_date": today.strftime("%Y-%m-%d"),
        }

    # 近一周
    weekly_df = df.loc[today - timedelta(weeks=1) :]
    all_data["weekly"] = calculate_indicators(weekly_df, rate_interbank_df)

    # 4. Generate Pyecharts configuration
    date_list = df.index.strftime("%Y-%m-%d").tolist()
    strategy_data = [
        round((val - 1) * 100, 2) for val in df["Strategy_Cumulative_Return"]
    ]
    benchmark_data = [
        round((val - 1) * 100, 2) for val in df["Benchmark_Cumulative_Return"]
    ]
    excess_data = [round((val - 1) * 100, 2) for val in df["Excess_Return_Cumulative"]]
    drawdown_data_strategy = [round(val * 100, 2) for val in df["Drawdown_global"]]
    drawdown_data_excess = [round(val * 100, 2) for val in df["Drawdown_excess"].dropna()]

    line_chart = (
        Line(init_opts=opts.InitOpts(height="500px", theme="light"))
        .add_xaxis(xaxis_data=date_list)
        .add_yaxis(
            "策略收益(NetValue1)",
            strategy_data,
            is_smooth=True,
            is_symbol_show=False,
            linestyle_opts=opts.LineStyleOpts(width=2, color="#d9534f"),
            label_opts=opts.LabelOpts(is_show=False),
        )
        .add_yaxis(
            "基准收益(NetValue2)",
            benchmark_data,
            is_smooth=True,
            is_symbol_show=False,
            linestyle_opts=opts.LineStyleOpts(width=2, color="#5cb85c"),
            label_opts=opts.LabelOpts(is_show=False),
        )
        .add_yaxis(
            "累计几何超额收益",
            excess_data,
            is_smooth=True,
            is_symbol_show=False,
            linestyle_opts=opts.LineStyleOpts(width=1, color="#007bff"),
            areastyle_opts=opts.AreaStyleOpts(opacity=0.2, color="#007bff"),
            label_opts=opts.LabelOpts(is_show=False),
        )
        .set_global_opts(
            title_opts=opts.TitleOpts(
                title="策略收益回撤走势",
                pos_left="center",
                title_textstyle_opts=opts.TextStyleOpts(
                    font_size=20,        # 字体大小
                    font_weight="bold",  # 字体粗细
                    color="#333"         # 字体颜色
                    )
                ),
            legend_opts=opts.LegendOpts(pos_top="8%", pos_left="60.5%"),
            tooltip_opts=opts.TooltipOpts(trigger="axis", axis_pointer_type="cross"),
            axispointer_opts=opts.AxisPointerOpts(
                is_show=True, link=[{"xAxisIndex": "all"}]
            ),
            xaxis_opts=opts.AxisOpts(type_="category", boundary_gap=False),
            yaxis_opts=opts.AxisOpts(
                name="收益率 (%)", axislabel_opts=opts.LabelOpts(formatter="{value} %")
            ),
            datazoom_opts=[
                opts.DataZoomOpts(
                    type_="slider", xaxis_index=[0, 1], range_start=0, range_end=100
                )
            ],
            toolbox_opts=opts.ToolboxOpts(
                is_show=True,
                pos_left="right",
                feature=opts.ToolBoxFeatureOpts(
                    save_as_image=opts.ToolBoxFeatureSaveAsImageOpts(
                        title="保存为图片",
                        pixel_ratio=4,  # 提高分辨率
                        background_color="white",  # 设置背景色
                        name="performance_report_chart",  # 设置文件名
                    )
                ),
            ),
        )
    )
    drawdown_chart = (
        Line()
        .add_xaxis(date_list)
        .add_yaxis(
            "策略回撤",
            drawdown_data_strategy,
            is_smooth=True,
            is_symbol_show=False,
            label_opts=opts.LabelOpts(is_show=False),
            linestyle_opts=opts.LineStyleOpts(width=1, color="#d9534f"),
            areastyle_opts=opts.AreaStyleOpts(opacity=0.5, color="#d9534f"),
        )
        .add_yaxis(
            "几何超额收益回撤",
            drawdown_data_excess,
            is_smooth=True,
            is_symbol_show=False,
            label_opts=opts.LabelOpts(is_show=False),
            linestyle_opts=opts.LineStyleOpts(width=1, color="#5cb85c"),
            areastyle_opts=opts.AreaStyleOpts(opacity=0.5, color="#5cb85c"),
        )
        .set_global_opts(
            yaxis_opts=opts.AxisOpts(
                name="回撤 (%)", axislabel_opts=opts.LabelOpts(formatter="{value} %")
            ),
            legend_opts=opts.LegendOpts(is_show=True, pos_left="73%", pos_top="70%"),
            xaxis_opts=opts.AxisOpts(is_show=False),
        )
    )
    grid_chart = Grid(init_opts=opts.InitOpts(width="100%", height="700px"))
    grid_chart.add(line_chart, grid_opts=opts.GridOpts(pos_top="12%", pos_bottom="33%"))
    grid_chart.add(
        drawdown_chart, grid_opts=opts.GridOpts(pos_top="74%", pos_bottom="7%")
    )

    # 5. Prepare data for template injection
    chart_config_json = grid_chart.dump_options_with_quotes()
    all_data_json = json.dumps(all_data)

    # 6. Read template, inject data, and write to output file
    with open(template_path, "r", encoding="utf-8") as f:
        template_content = f.read()

    final_html = template_content.replace("'{{ CHART_CONFIG_JSON }}'", chart_config_json)
    final_html = final_html.replace("'{{ ALL_DATA_JSON }}'", all_data_json)

    with open(output_html, "w", encoding="utf-8") as f:
        f.write(final_html)

    print(f"独立的业绩报告文件已生成: {output_html}")


if __name__ == "__main__":
    rate_interbank_df = get_rate_interbank_df()
    generate_performance_page_from_template(
        data_path="Normalized_NetValue.csv",
        template_path="template.html",
        rate_interbank_df=rate_interbank_df,
        output_html="index.html",
    )
