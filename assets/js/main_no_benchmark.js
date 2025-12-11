document.addEventListener('DOMContentLoaded', () => {
    // 检查数据是否注入成功
    if (!window.reportData) {
        console.error("未找到报告数据，请确保数据已正确注入。");
        return;
    }

    const chartConfig = window.reportData.chartConfig;
    const allData = window.reportData.allData;
    const hasBenchmark = window.reportData.hasBenchmark;

    // 初始化图表
    const myChart = echarts.init(document.getElementById('chart-container'));
    myChart.setOption(chartConfig);
    window.addEventListener('resize', () => myChart.resize());

    // 辅助函数
    const el = (id) => document.getElementById(id);
    const formatPercent = (val) => (val !== undefined && val !== null) ? (val * 100).toFixed(2) + '%' : '--';
    const formatNumber = (val) => (val !== undefined && val !== null) ? val.toFixed(2) : '--';
    const formatDate = (dateStr) => dateStr ? dateStr.split(' ')[0] : '--'; // 简单处理日期格式

    // 1. 填充顶部概览卡片
    const populateSummaryCards = () => {
        // 定义需要展示的周期 Key，对应 Python 生成的 Key
        // recent_week: 近一周, recent_month: 近一月, ytd: 今年以来, recent_year: 近一年, interval: 成立以来
        const periods = ['recent_week', 'recent_month', 'ytd', "recent_year", 'interval'];

        periods.forEach(period => {
            // 策略数据
            const sData = allData[period];
            if (!sData) return;

            // 设置日期范围
            const dateEl = el(`summary-date-${period}`);
            if (dateEl) {
                dateEl.innerText = `${formatDate(sData.start_date)} ~ ${formatDate(sData.end_date)}`;
            }

            // 设置策略收益, 年化收益, 最大回撤
            const sEl = el(`summary-strategy-${period}`);
            if (sEl) sEl.innerText = formatPercent(sData.interval_return);
            const sAnnualEl = el(`summary-strategy-annual-${period}`);
            if (sAnnualEl) sAnnualEl.innerText = formatPercent(sData.interval_anual_return);
            const sMddEl = el(`summary-strategy-mdd-${period}`);
            if (sMddEl) sMddEl.innerText = formatPercent(sData.interval_MDD);
        });
    };

    // 2. 更新详细指标区域
    const updateIndicators = (period) => {
        // 获取当前周期的数据
        const sData = allData[period];
        const bData = hasBenchmark ? allData[`${period}_Benchmark`] : null;
        const eData = hasBenchmark ? allData[`${period}_Excess`] : null;

        if (!sData) {
            console.warn(`未找到周期 ${period} 的数据`);
            return;
        }

        // 更新标题旁的日期范围
        const rangeEl = el('indicator-date-range');
        if (rangeEl) {
            rangeEl.innerText = `(${formatDate(sData.start_date)} ~ ${formatDate(sData.end_date)})`;
        }

        // --- 策略列 ---
        el('ind-return-strategy').innerText = formatPercent(sData.interval_return);
        el('ind-annual-return-strategy').innerText = formatPercent(sData.interval_anual_return);
        el('ind-annual-vol-strategy').innerText = formatPercent(sData.interval_annual_vol);
        el('ind-mdd-strategy').innerText = formatPercent(sData.interval_MDD);
        el('ind-sharpe-strategy').innerText = formatNumber(sData.interval_sharpe);
        el('ind-karma-strategy').innerText = formatNumber(sData.interval_karma);
    };

    // 绑定按钮点击事件
    const buttons = document.querySelectorAll('.period-btn');
    buttons.forEach(button => {
        button.addEventListener('click', (event) => {
            const period = event.target.dataset.period;
            // 切换激活状态
            buttons.forEach(btn => btn.classList.remove('active'));
            event.target.classList.add('active');
            // 更新数据
            updateIndicators(period);
        });
    });

    // 初始化执行
    populateSummaryCards();
    // 默认显示 "interval" (成立以来) 或第一个可用的周期
    updateIndicators('interval');
});
