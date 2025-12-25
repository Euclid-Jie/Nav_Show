import pandas as pd
import numpy as np
from numpy.typing import NDArray
from typing import Optional, Tuple, Dict, Any
import json
import shutil
from pathlib import Path
from pyecharts import options as opts
from pyecharts.charts import Line, Grid
try:
    from .nav_interval_metric.nav_metric import NavMetric
    from .nav_interval_metric.utils import generate_trading_date
except ImportError:
    from nav_interval_metric.nav_metric import NavMetric
    from nav_interval_metric.utils import generate_trading_date

try:
    from .config import SQL_HOST, SQL_PASSWORDS
except ImportError:
    from config import SQL_HOST, SQL_PASSWORDS

import sqlalchemy


class PerformanceReportGenerator:
    """
    业绩报告生成器类
    负责数据准备、指标计算、图表配置生成及HTML渲染
    """

    def __init__(
        self,
        name: str,
        date: NDArray[np.datetime64],
        nav: NDArray[np.floating],
        benchmark: Optional[NDArray[np.floating]] = None,
        last_date: Optional[np.datetime64] = None,
        last_week_date: Optional[np.datetime64] = None,
    ):
        self.name = name
        self.last_date = last_date if last_date is not None else date[-1]
        self.last_week_date = last_week_date if last_week_date is not None else date[-2]
        self._prepare_data(date, nav, benchmark)

    def _prepare_data(
        self,
        date: NDArray[np.datetime64],
        nav: NDArray[np.floating],
        benchmark: Optional[NDArray[np.floating]] = None,
    ):
        """准备数据：对齐日期，计算累计收益和回撤"""
        assert len(date) == len(nav), "日期与净值数据长度不匹配"
        self.date = date
        self.nav = nav / nav[0]  # 归一化
        self.df = (
            pd.DataFrame({"date": pd.to_datetime(date), "nav": self.nav})
            .set_index("date")
            .sort_index()
        )
        cummax = np.maximum.accumulate(self.nav)
        self.df["drawdown"] = (self.nav - cummax) / cummax

        if benchmark is not None:
            assert len(date) == len(benchmark), "日期与基准数据长度不匹配"
            self.has_benchmark = True
            self.df["benchmark"] = benchmark / benchmark[0]
            self.df["excess_nav"] = self.nav / self.df["benchmark"].values

            cummax_bench = np.maximum.accumulate(
                np.asarray(self.df["benchmark"].values)
            )
            cummax_excess = np.maximum.accumulate(
                np.asarray(self.df["excess_nav"].values)
            )
            self.df["drawdown_benchmark"] = (
                self.df["benchmark"] - cummax_bench
            ) / cummax_bench
            self.df["drawdown_excess"] = (
                self.df["excess_nav"] - cummax_excess
            ) / cummax_excess
        else:
            self.has_benchmark = False

    def calculate_indicators(self) -> Dict[str, float]:
        """计算各周期指标"""
        all_data = {}

        # 周期定义
        base_interval = NavMetric.generate_intervals(
            last_day=self.last_date, last_week_day=self.last_week_date
        )

        # 辅助函数：提取指标数据
        def _extract_metrics(metric: NavMetric, intervals: list, suffix: str = ""):
            data = {}
            # 区间指标
            data[f"interval{suffix}"] = {
                "start_date": np.datetime_as_string(metric.begin_date, unit="D"),
                "end_date": np.datetime_as_string(metric.end_date, unit="D"),
                "interval_return": metric.base_metric_dict["区间收益率"],
                "interval_anual_return": metric.base_metric_dict["年化收益率"],
                "interval_annual_vol": metric.base_metric_dict["年化波动率"],
                "interval_MDD": metric.base_metric_dict["最大回撤"],
                "interval_sharpe": metric.base_metric_dict["夏普比率"],
                "interval_karma": metric.base_metric_dict["卡玛比率"],
            }
            # 标准周期指标
            calculated_intervals = metric.calculate_interval_return(intervals)
            for _interval in calculated_intervals:
                data[_interval.name + suffix] = {
                    "start_date": np.datetime_as_string(_interval.start_date, unit="D"),
                    "end_date": np.datetime_as_string(_interval.end_date, unit="D"),
                    "interval_return": _interval.interval_return,
                    "interval_anual_return": _interval.interval_anual_return,
                    "interval_annual_vol": _interval.interval_annual_vol,
                    "interval_MDD": _interval.interval_MDD,
                    "interval_sharpe": _interval.interval_sharpe,
                    "interval_karma": _interval.interval_karma,
                }
            return data

        # 计算策略指标
        nav_metric = NavMetric(self.name, self.nav, self.date, "W")
        all_data.update(_extract_metrics(nav_metric, base_interval))

        if self.has_benchmark:
            # 计算基准指标
            benchmark_metric = NavMetric(
                f"{self.name}_Benchmark",
                np.asarray(self.df["benchmark"].values, dtype=np.float64),
                self.date,
                "W",
            )
            all_data.update(
                _extract_metrics(benchmark_metric, base_interval, "_Benchmark")
            )

            # 计算超额收益指标
            excess_metric = NavMetric(
                f"{self.name}_Excess",
                np.asarray(self.df["excess_nav"].values, dtype=np.float64),
                self.date,
                "W",
            )
            all_data.update(_extract_metrics(excess_metric, base_interval, "_Excess"))

        return all_data

    def generate_chart_config(self) -> Dict[str, Any]:
        """生成图表配置"""

        date_list = self.date.astype("M8[D]").astype(str).tolist()

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
                _fmt(self.nav),
                is_smooth=False,
                is_symbol_show=False,
                linestyle_opts=opts.LineStyleOpts(width=2, color="#d9534f"),
            )
        )

        if self.has_benchmark:
            line.add_yaxis(
                "基准收益",
                _fmt(self.df["benchmark"]),
                is_smooth=False,
                is_symbol_show=False,
                linestyle_opts=opts.LineStyleOpts(width=2, color="#5cb85c"),
            ).add_yaxis(
                "超额收益",
                _fmt(self.df["excess_nav"]),
                is_smooth=False,
                is_symbol_show=False,
                linestyle_opts=opts.LineStyleOpts(width=1, color="#007bff"),
                areastyle_opts=opts.AreaStyleOpts(opacity=0.2, color="#007bff"),
            )

        line.set_global_opts(
            title_opts=opts.TitleOpts(
                title=f"收益回撤走势",  # 修改：移除self.name，使用通用标题
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
                _fmt_dd(self.df["drawdown"]),
                is_smooth=False,
                is_symbol_show=False,
                linestyle_opts=opts.LineStyleOpts(width=1, color="#d9534f"),
                areastyle_opts=opts.AreaStyleOpts(opacity=0.5, color="#d9534f"),
            )
        )

        if self.has_benchmark:
            dd_chart.add_yaxis(
                "超额收益回撤",  # 修改：明确含义
                _fmt_dd(self.df["drawdown_excess"].dropna()),
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
        grid.add(dd_chart, grid_opts=opts.GridOpts(pos_top="75%", pos_bottom="5%"))

        return json.loads(grid.dump_options_with_quotes())

    def render(self, output_html: str = "index.html"):
        """渲染HTML报告"""
        base_dir = Path(__file__).parent
        template_path = (
            base_dir
            / "templates"
            / ("report.html" if self.has_benchmark else "report_no_benchmark.html")
        )

        if not template_path.exists():
            raise FileNotFoundError(f"模板文件未找到: {template_path}")

        with open(template_path, "r", encoding="utf-8") as f:
            html_content = f.read()

        # 统一替换模板中的静态资源路径为 ./assets/...
        # 适配可能存在的不同写法（绝对/相对），尽可能规范到同一路径
        html_content = (
            html_content.replace(
                "Nav_Show/assets/css/style.css", "./assets/css/style.css"
            )
            .replace("assets/css/style.css", "./assets/css/style.css")
            .replace("Nav_Show/assets/js/main.js", "./assets/js/main.js")
            .replace("assets/js/main.js", "./assets/js/main.js")
        )
        # 修改h1标题
        html_content = html_content.replace(
            "<h1>区间基础指标</h1>", f"<h1>{self.name} 业绩报告</h1>"
        )
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

        # 将 Nav_Show/assets 复制到输出目录的 assets 下，保证本地预览和 GitHub Pages 可用
        output_path = Path(output_html)
        output_dir = output_path.parent if output_path.parent != Path("") else Path(".")
        src_assets = base_dir / "assets"
        dest_assets = output_dir / "assets"
        if src_assets.exists() and output_dir != Path("."):
            shutil.copytree(src_assets, dest_assets, dirs_exist_ok=True)

        with open(output_html, "w", encoding="utf-8") as f:
            f.write(html_content)

        print(f"业绩报告已生成: {output_html}")


def generate_performance_page_from_template(
    name: str,
    date: NDArray[np.datetime64],
    nav: NDArray[np.floating],
    benchmark: Optional[NDArray[np.floating]] = None,
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

    data_path = Path("SQF225_星阔上林1号中证1000指数增强.csv")

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
