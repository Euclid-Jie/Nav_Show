document.addEventListener('DOMContentLoaded', () => {
    // Load data from global variable injected by report_data.js
    if (!window.reportData) {
        console.error("Report data not found. Ensure report_data.js is loaded.");
        return;
    }
    
    const chartConfig = window.reportData.chartConfig;
    const allData = window.reportData.allData;

    // --- LANGUAGE TRANSLATION SETUP ---
    let currentLang = 'zh';
    const translations = {
        zh: {
            mainTitle: '策略业绩报告',
            daily: '当日',
            weekly: '近一周',
            monthly: '近一月',
            threeMonth: '近三月',
            ytd: '今年以来',
            sinceInception: '成立以来',
            strategyReturn: '策略收益',
            benchmarkReturn: '基准收益',
            excessReturn: '超额收益',
            indicatorsTitle: '投资组合指标分析',
            btn1m: '近一月',
            btn3m: '近三月',
            btn6m: '近六月',
            btnYtd: '今年以来',
            btn1y: '近一年',
            btnAll: '成立以来',
            corePerformanceTitle: '核心表现',
            corePerformanceSubtitle: '策略与基准的绝对收益及风险',
            totalReturn: '总收益率',
            annualizedReturn: '年化收益率',
            winRate: '胜率',
            annualizedVolatility: '年化波动率',
            strategyMaxDrawdown: '策略最大回撤',
            maxDrawdownDesc: '衡量策略历史最大跌幅',
            avgDrawdownRecoveryDays: '策略平均回撤修复时间（天）',
            maxDrawdownRecoveryDays: '策略最大回撤修复时间（天）',
            riskAdjustedTitle: '风险调整后收益',
            riskAdjustedSubtitle: '注：无风险利率采用对应期SHIBOR均值',
            sharpeRatio: '夏普比率 (Sharpe Ratio)',
            sortinoRatio: '索提诺比率 (Sortino Ratio)',
            calmarRatio: '卡玛比率 (Calmar Ratio)',
            calmarRatioDesc: '年化收益 / 最大回撤',
            informationRatio: '信息比率 (Information Ratio)',
            informationRatioDesc: '主动管理能力的衡量',
            relativeAnalysisTitle: '相对基准分析',
            relativeAnalysisSubtitle: '策略相对基准的超额表现',
            annualizedAlpha: '年化Alpha',
            annualizedAlphaDesc: '策略超越基准的年化回报',
            trackingError: '跟踪误差',
            trackingErrorDesc: '超额收益的年化波动率',
            excessMaxDrawdown: '超额收益最大回撤',
            excessMaxDrawdownDesc: '超额收益曲线的最大跌幅',
            benchmarkPrefix: '基准: ',
            dateRangeSeparator: ' ~ ',
            tradingDaysSuffix: '个交易日',
        },
        en: {
            mainTitle: 'Strategy Performance Report',
            daily: 'Daily',
            weekly: 'Weekly',
            monthly: '1-Month',
            threeMonth: '3-Month',
            ytd: 'YTD',
            sinceInception: 'Since Inception',
            strategyReturn: 'Strategy Return',
            benchmarkReturn: 'Benchmark Return',
            excessReturn: 'Excess Return',
            indicatorsTitle: 'Portfolio Indicator Analysis',
            btn1m: '1M',
            btn3m: '3M',
            btn6m: '6M',
            btnYtd: 'YTD',
            btn1y: '1Y',
            btnAll: 'All',
            corePerformanceTitle: 'Core Performance',
            corePerformanceSubtitle: 'Absolute return and risk of the strategy and benchmark',
            totalReturn: 'Total Return',
            winRate:  'Win Rate',
            annualizedReturn: 'Annualized Return',
            annualizedVolatility: 'Annualized Volatility',
            strategyMaxDrawdown: 'Strategy Max Drawdown',
            maxDrawdownDesc: 'Measures the largest peak-to-trough decline',
            avgDrawdownRecoveryDays: 'Avg Drawdown Recovery Days',
            maxDrawdownRecoveryDays: 'Max Drawdown Recovery Days',
            riskAdjustedTitle: 'Risk-Adjusted Return',
            riskAdjustedSubtitle: 'Note: Risk-free rate is the avg SHIBOR for the period',
            sharpeRatio: 'Sharpe Ratio',
            sortinoRatio: 'Sortino Ratio',
            calmarRatio: 'Calmar Ratio',
            calmarRatioDesc: 'Annualized Return / Max Drawdown',
            informationRatio: 'Information Ratio',
            informationRatioDesc: 'A measure of active management skill',
            relativeAnalysisTitle: 'Relative Analysis',
            relativeAnalysisSubtitle: 'Strategy\'s excess performance relative to the benchmark',
            annualizedAlpha: 'Annualized Alpha',
            annualizedAlphaDesc: 'Strategy\'s annualized return beyond the benchmark',
            trackingError: 'Tracking Error',
            trackingErrorDesc: 'Annualized volatility of excess returns',
            excessMaxDrawdown: 'Excess Return Max Drawdown',
            excessMaxDrawdownDesc: 'The largest peak-to-trough decline of the excess return curve',
            benchmarkPrefix: 'Benchmark: ',
            dateRangeSeparator: ' to ',
            tradingDaysSuffix: ' trading days',
        }
    };

    const el = (id) => document.getElementById(id);

    const switchLanguage = (lang) => {
        if (currentLang === lang) return;
        currentLang = lang;

        document.documentElement.lang = lang === 'zh' ? 'zh-CN' : 'en';

        // Update button active state
        document.getElementById('lang-zh').classList.toggle('active', lang === 'zh');
        document.getElementById('lang-en').classList.toggle('active', lang === 'en');

        // Translate all static elements with data-lang-key
        document.querySelectorAll('[data-lang-key]').forEach(el => {
            const key = el.dataset.langKey;
            if (translations[lang] && translations[lang][key]) {
                el.innerText = translations[lang][key];
            }
        });

        // Re-render all dynamic content
        populateSummaryCards();
        updateIndicators(document.querySelector('.period-btn.active').dataset.period);

        // Also update the chart title if necessary
        const currentChartOption = myChart.getOption();
        if(currentChartOption.title && currentChartOption.title[0]) {
            currentChartOption.title[0].text = translations[currentLang].mainTitle;
            myChart.setOption(currentChartOption);
        }
    };

    document.getElementById('lang-zh').addEventListener('click', () => switchLanguage('zh'));
    document.getElementById('lang-en').addEventListener('click', () => switchLanguage('en'));
    // --- END LANGUAGE SETUP ---

    const myChart = echarts.init(document.getElementById('chart-container'));
    myChart.setOption(chartConfig);
    window.addEventListener('resize', () => myChart.resize());

    const populateSummaryCards = () => {
        const periods = ['daily', 'weekly', '1m', '3m', 'ytd', 'all'];
        periods.forEach(period => {
            const data = allData[period];
            if (!data) return;

            const dateEl = el(`summary-date-${period}`);
            if (dateEl) {
                const formatDateRange = (start, end) => (start === end) ? start : `${start}${translations[currentLang].dateRangeSeparator}${end}`;
                dateEl.innerText = formatDateRange(data.start_date, data.end_date);
            }

            ['strategy', 'benchmark', 'excess'].forEach(type => {
                let key, value;
                if (type === 'strategy') key = 'total_return_strategy';
                if (type === 'benchmark') key = 'total_return_benchmark';
                if (type === 'excess') key = 'total_ari_excess_return';

                value = data[key];
                const element = el(`summary-${type}-${period}`);
                if (element) {
                    const icon = value >= 0 ? '<span class="icon positive">▲</span>' : '<span class="icon negative">▼</span>';
                    element.innerHTML = `${icon} ${value.toFixed(2)}%`;
                }
            });
        });
    };

    const updateIndicators = (period) => {
        const data = allData[period];
        if (!data) {
            console.error(`Data for period "${period}" not found`);
            return;
        }
        const langDict = translations[currentLang];

        const formatPercent = (value) => value !== undefined ? `${value.toFixed(2)}%` : '--';
        const formatNumber = (value) => value !== undefined ? value.toFixed(2) : '--';
        const formatInteger = (value) => value !== undefined ? Math.round(value) : '--';

        const setText = (id, text) => {
            const e = el(id);
            if (e) e.innerText = text;
        };

        const setBenchmarkText = (elementId, value, formatter = formatNumber) => {
            const labelElement = el(elementId + '_label');
            const valueElement = el(elementId);
            if (labelElement && valueElement) {
                labelElement.innerHTML = `${langDict.benchmarkPrefix}<span id="${elementId}">${formatter(value)}</span>`;
            }
        }

        // --- Update date range header ---
        setText('indicator-date-range', `(${data.start_date}${langDict.dateRangeSeparator}${data.end_date}, ${data.days}${langDict.tradingDaysSuffix})`);

        // --- Column 1: Core Performance ---
        setText('total_return_strategy', formatPercent(data.total_return_strategy));
        setBenchmarkText('total_return_benchmark', data.total_return_benchmark, formatPercent);
        
        setText('annualized_return_strategy', formatPercent(data.annualized_return_strategy));
        setBenchmarkText('annualized_return_benchmark', data.annualized_return_benchmark, formatPercent);
        
        setText('volatility_strategy', formatPercent(data.volatility_strategy));
        setBenchmarkText('volatility_benchmark', data.volatility_benchmark, formatPercent);
        
        setText('max_drawdown_strategy', formatPercent(data.max_drawdown_strategy));
        
        setText('avg_drawdown_recovery_days_strategy', formatInteger(data.avg_drawdown_recovery_days_strategy));
        setBenchmarkText('avg_drawdown_recovery_days_benchmark', data.avg_drawdown_recovery_days_benchmark, formatInteger);
        
        setText('max_drawdown_recovery_days_strategy', formatInteger(data.max_drawdown_recovery_days_strategy));
        setBenchmarkText('max_drawdown_recovery_days_benchmark', data.max_drawdown_recovery_days_benchmark, formatInteger);

        // --- Column 2: Risk-Adjusted Return ---
        setText('sharpe_ratio_strategy', formatNumber(data.sharpe_ratio_strategy));
        setBenchmarkText('sharpe_ratio_benchmark', data.sharpe_ratio_benchmark);
        
        setText('win_rate_strategy', formatPercent(data.win_rate_strategy));
        setBenchmarkText('win_rate_benchmark', data.win_rate_benchmark, formatPercent);
        
        setText('sortino_ratio_strategy', formatNumber(data.sortino_ratio_strategy));
        setBenchmarkText('sortino_ratio_benchmark', data.sortino_ratio_benchmark);
        
        setText('calmar_ratio_strategy', formatNumber(data.calmar_ratio_strategy));
        setText('information_ratio', formatNumber(data.information_ratio));

        // --- Column 3: Relative Analysis ---
        setText('sharpe_ratio_excess',formatNumber(data.sharpe_ratio_excess));
        setText('annualized_alpha', formatPercent(data.annualized_alpha));
        setText('win_rate_excess', formatPercent(data.win_rate_excess));
        setText('max_drawdown_excess', formatPercent(data.max_drawdown_excess));
        setText('max_drawdown_recovery_days_excess', formatInteger(data.max_drawdown_recovery_days_excess));
        setText('max_drawdown_recovery_days_benchmark', formatInteger(data.max_drawdown_recovery_days_benchmark));
    };

    const buttons = document.querySelectorAll('.period-btn');
    buttons.forEach(button => {
        button.addEventListener('click', (event) => {
            const period = event.target.dataset.period;
            buttons.forEach(btn => btn.classList.remove('active'));
            event.target.classList.add('active');
            updateIndicators(period);
        });
    });

    // Initial load
    populateSummaryCards();
    updateIndicators('all');
});
