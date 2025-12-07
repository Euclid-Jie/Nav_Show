import pandas as pd
import numpy as np
from numpy.typing import NDArray
from typing import Optional, Tuple, Dict, Any
import json
import os
from pathlib import Path
from pyecharts import options as opts
from pyecharts.charts import Line, Grid
from utils import calculate_indicators, generate_trading_date
from config import SQL_HOST, SQL_PASSWORDS
import sqlalchemy
from pyecharts.commons.utils import JsCode


class PerformanceReportGenerator:
    """
    业绩报告生成器类
    负责数据准备、指标计算、图表配置生成及HTML渲染
    """

    def __init__(
        self,
        name: str,
        date: NDArray[np.datetime64],
        nav: NDArray[float],
        benchmark: Optional[NDArray[float]] = None,
    ):
        self.name = name
        self.df, self.has_benchmark = self._prepare_data(date, nav, benchmark)

    def _prepare_data(
        self,
        date: NDArray[np.datetime64],
        nav: NDArray[float],
        benchmark: Optional[NDArray[float]] = None,
    ) -> Tuple[pd.DataFrame, bool]:
        """准备数据：对齐日期，计算累计收益和回撤"""
        assert len(date) == len(nav), "日期与净值数据长度不匹配"

        has_benchmark = False
        data = {"Date": pd.to_datetime(date), "Strategy_Value": nav}

        if benchmark is not None:
            assert len(benchmark) == len(nav), "基准数据长度不匹配"
            benchmark = benchmark / benchmark[0]  # 归一化
            data["Benchmark_Value"] = benchmark
            has_benchmark = True

        df = pd.DataFrame(data).set_index("Date").sort_index()

        # 策略指标
        df["Strategy_Cumulative_Return"] = df["Strategy_Value"]
        df["Running_max_global"] = df["Strategy_Cumulative_Return"].cummax()
        df["Drawdown_global"] = (
            df["Strategy_Cumulative_Return"] / df["Running_max_global"]
        ) - 1

        # 基准及超额指标
        if has_benchmark:
            df["Benchmark_Cumulative_Return"] = df["Benchmark_Value"]
            df["Excess_Return_Pct"] = (
                df["Strategy_Cumulative_Return"].pct_change()
                - df["Benchmark_Cumulative_Return"].pct_change()
            )
            df["Excess_Return_Cumulative"] = (
                1 + df["Excess_Return_Pct"].fillna(0)
            ).cumprod()
            df["Running_max_excess"] = df["Excess_Return_Cumulative"].cummax()
            df["Drawdown_excess"] = (
                df["Excess_Return_Cumulative"] / df["Running_max_excess"]
            ) - 1
        else:
            df["Benchmark_Cumulative_Return"] = 1.0
            df["Excess_Return_Cumulative"] = 1.0
            df["Drawdown_excess"] = 0.0

        return df, has_benchmark

    def calculate_indicators(self) -> Dict[str, Any]:
        """计算各周期指标"""
        all_data = {}
        last_day = self.df.index.max()

        dates = self.df.index.values
        nav = self.df["Strategy_Cumulative_Return"].values
        bench = (
            self.df["Benchmark_Cumulative_Return"].values
            if self.has_benchmark
            else None
        )

        # 周期定义
        periods = {
            "weekly": pd.DateOffset(weeks=1),
            "1m": pd.DateOffset(months=1),
            "3m": pd.DateOffset(months=3),
            "6m": pd.DateOffset(months=6),
            "1y": pd.DateOffset(years=1),
        }

        # 标准周期
        for key, offset in periods.items():
            mask = self.df.index >= (last_day - offset)
            all_data[key] = calculate_indicators(
                dates[mask], nav[mask], bench[mask] if self.has_benchmark else None
            )

        # 特殊周期
        mask_ytd = self.df.index >= pd.Timestamp(str(last_day.year))
        all_data["ytd"] = calculate_indicators(
            dates[mask_ytd],
            nav[mask_ytd],
            bench[mask_ytd] if self.has_benchmark else None,
        )
        all_data["all"] = calculate_indicators(dates, nav, bench)

        # 当日指标
        try:
            cols = ["Strategy_Cumulative_Return"]
            if self.has_benchmark:
                cols.append("Benchmark_Cumulative_Return")

            last_pct = self.df[cols].pct_change().iloc[-1].fillna(0) * 100
            s_ret = last_pct["Strategy_Cumulative_Return"]
            b_ret = (
                last_pct["Benchmark_Cumulative_Return"] if self.has_benchmark else 0.0
            )
        except IndexError:
            s_ret, b_ret = 0.0, 0.0

        all_data["daily"] = {
            "total_return_strategy": s_ret,
            "total_return_benchmark": b_ret,
            "total_ari_excess_return": s_ret - b_ret,
            "start_date": last_day.strftime("%Y-%m-%d"),
            "end_date": last_day.strftime("%Y-%m-%d"),
        }

        return all_data

    def generate_chart_config(self) -> Dict[str, Any]:
        """生成图表配置"""

        date_list = self.df.index.strftime("%Y-%m-%d").tolist()

        def _fmt(s):
            return [round((x - 1) * 100, 2) for x in s]

        def _fmt_dd(s):
            return [round(x * 100, 2) for x in s]

        # 收益图
        line = (
            Line(init_opts=opts.InitOpts(height="500px", theme="light"))
            .add_xaxis(date_list)
            .add_yaxis(
                "策略收益",  # 修改：统一名称，避免Tooltip混淆
                _fmt(self.df["Strategy_Cumulative_Return"]),
                is_smooth=False,
                is_symbol_show=False,
                linestyle_opts=opts.LineStyleOpts(width=2, color="#d9534f"),
            )
        )

        if self.has_benchmark:
            line.add_yaxis(
                "基准收益",  # 修改：增加“收益”后缀
                _fmt(self.df["Benchmark_Cumulative_Return"]),
                is_smooth=False,
                is_symbol_show=False,
                linestyle_opts=opts.LineStyleOpts(width=2, color="#5cb85c"),
            ).add_yaxis(
                "超额收益",
                _fmt(self.df["Excess_Return_Cumulative"]),
                is_smooth=False,
                is_symbol_show=False,
                linestyle_opts=opts.LineStyleOpts(width=1, color="#007bff"),
                areastyle_opts=opts.AreaStyleOpts(opacity=0.2, color="#007bff"),
            )

        line.set_global_opts(
            title_opts=opts.TitleOpts(
                title=f"{self.name}收益回撤走势",  # 修改：移除self.name，使用通用标题
                pos_left="center",
                title_textstyle_opts=opts.TextStyleOpts(
                    font_size=20, font_weight="bold", color="#333"
                ),
            ),
            legend_opts=opts.LegendOpts(pos_top="8%", pos_left="68%"),
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
                    # 启用保存为图片功能
                    save_as_image=opts.ToolBoxFeatureSaveAsImageOpts(
                        title="保存为图片",
                        pixel_ratio=4,  # 提高分辨率
                        background_color="white",  # 设置背景色
                        name="performance_report_chart",  # 设置文件名
                    ),
                    # 启用还原按钮（重置视图）
                    restore=True,
                    # 禁用所有其他默认功能
                    magic_type=False,  # 关闭动态类型切换（如折线/柱状切换）
                    brush=False,  # 关闭区域选择
                    data_view=False,  # 关闭数据视图
                ),
            ),
        )

        # 回撤图
        dd_chart = (
            Line()
            .add_xaxis(date_list)
            .add_yaxis(
                "策略回撤",  # 修改：明确为回撤
                _fmt_dd(self.df["Drawdown_global"]),
                is_smooth=False,
                is_symbol_show=False,
                linestyle_opts=opts.LineStyleOpts(width=1, color="#d9534f"),
                areastyle_opts=opts.AreaStyleOpts(opacity=0.5, color="#d9534f"),
            )
        )

        if self.has_benchmark:
            dd_chart.add_yaxis(
                "超额收益回撤",  # 修改：明确含义
                _fmt_dd(self.df["Drawdown_excess"].dropna()),
                is_smooth=False,
                is_symbol_show=False,
                linestyle_opts=opts.LineStyleOpts(width=1, color="#5cb85c"),
                areastyle_opts=opts.AreaStyleOpts(opacity=0.5, color="#5cb85c"),
            )

        dd_chart.set_global_opts(
            yaxis_opts=opts.AxisOpts(
                name="回撤 (%)", axislabel_opts=opts.LabelOpts(formatter="{value} %")
            ),
            legend_opts=opts.LegendOpts(is_show=True, pos_left="73%", pos_top="70%"),
            xaxis_opts=opts.AxisOpts(is_show=False),
        )

        grid = Grid(init_opts=opts.InitOpts(width="100%", height="700px"))
        grid.add(line, grid_opts=opts.GridOpts(pos_top="12%", pos_bottom="33%"))
        grid.add(dd_chart, grid_opts=opts.GridOpts(pos_top="74%", pos_bottom="7%"))

        return json.loads(grid.dump_options_with_quotes())

    def render(self, output_html: str = "index.html"):
        """渲染HTML报告"""
        base_dir = Path(__file__).parent
        template_path = base_dir / "templates" / "report.html"

        if not template_path.exists():
            raise FileNotFoundError(f"模板文件未找到: {template_path}")

        with open(template_path, "r", encoding="utf-8") as f:
            html_content = f.read()

        js_data = f"""
        window.reportData = {{
            chartConfig: {json.dumps(self.generate_chart_config())},
            allData: {json.dumps(self.calculate_indicators())},
            hasBenchmark: {str(self.has_benchmark).lower()}
        }};
        """

        css_injection = ""
        if not self.has_benchmark:
            css_injection = (
                "<style>.benchmark-item { display: none !important; }</style>"
            )

        if "<!-- DATA_INJECTION -->" in html_content:
            html_content = html_content.replace(
                "<!-- DATA_INJECTION -->", f"<script>{js_data}</script>"
            )
        else:
            html_content = html_content.replace(
                "</body>", f"<script>{js_data}</script></body>"
            )

        if "<!-- STYLE_INJECTION -->" in html_content:
            html_content = html_content.replace(
                "<!-- STYLE_INJECTION -->", css_injection
            )
        else:
            html_content = html_content.replace("</head>", f"{css_injection}</head>")

        with open(output_html, "w", encoding="utf-8") as f:
            f.write(html_content)

        print(f"业绩报告已生成: {output_html}")


def generate_performance_page_from_template(
    name: str,
    date: NDArray[np.datetime64],
    nav: NDArray[float],
    benchmark: Optional[NDArray[float]] = None,
    output_html="index.html",
):
    """兼容旧接口的包装函数"""
    report = PerformanceReportGenerator(name, date, nav, benchmark)
    report.render(output_html)


if __name__ == "__main__":
    # 示例运行代码
    engine_data = sqlalchemy.create_engine(
        f"mysql+pymysql://dev:{SQL_PASSWORDS}@{SQL_HOST}:3306/UpdatedData?charset=utf8mb4"
    )
    benchmark_code = "000852.SH"

    data_path = Path(
        r"C:\Euclid_Jie\nav_data_tracking\cache_data\SQF225_星阔上林1号中证1000指数增强.csv"
    )

    raw_data = pd.read_csv(data_path)
    raw_data["日期"] = pd.to_datetime(raw_data["日期"])
    raw_data.set_index("日期", inplace=True)

    begin_date = raw_data.index.min()
    end_date = raw_data.index.max()

    bench_df = pd.read_sql_query(
        f"SELECT date,CLOSE FROM bench_basic_data WHERE code = '{benchmark_code}'",
        engine_data,
    )
    bench_df["date"] = pd.to_datetime(bench_df["date"])
    bench_df.set_index("date", inplace=True)

    trade_date, weekly_trade_date = generate_trading_date(
        begin_date - np.timedelta64(10, "D"),
        end_date + np.timedelta64(5, "D"),
    )

    nav_series = raw_data["复权净值"].reindex(weekly_trade_date)
    nav_series = nav_series[nav_series.index >= begin_date]
    nav_series = nav_series[nav_series.notna()]

    nav = nav_series.values
    date = nav_series.index.values
    bench_df = bench_df.reindex(nav_series.index)

    generate_performance_page_from_template(
        name="星阔上林1号中证1000指数增强",
        date=date,
        nav=nav,
        benchmark=bench_df["CLOSE"].values,
        output_html="index.html",
    )
