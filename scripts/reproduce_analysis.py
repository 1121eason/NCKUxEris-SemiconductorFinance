#!/usr/bin/env python3
"""Reproduce reviewed historical metrics and source-model diagnostics, offline."""
import argparse
import csv
import io
import json
import math
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1]


def read_rows(name):
    with (ROOT / 'data' / name).open(encoding='utf-8', newline='') as handle:
        return [{key: int(value) if key == 'year' else float(value)
                 for key, value in row.items()} for row in csv.DictReader(handle)]


def npv(rate, cashflows, initial):
    if not math.isfinite(rate) or rate <= -1:
        raise ValueError('Discount rate must be finite and greater than -1')
    if not all(math.isfinite(x) for x in [initial, *cashflows]):
        raise ValueError('Cash flows and initial outlay must be finite')
    return sum(cf / (1 + rate) ** t for t, cf in enumerate(cashflows, 1)) - initial


def csv_text(rows):
    output = io.StringIO(newline='')
    writer = csv.DictWriter(output, fieldnames=list(rows[0]), lineterminator='\n')
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


def svg_start(title, subtitle, height=620):
    return [f'<svg xmlns="http://www.w3.org/2000/svg" width="1160" height="{height}" viewBox="0 0 1160 {height}" role="img" aria-labelledby="title desc">',
            f'<title id="title">{escape(title)}</title><desc id="desc">{escape(subtitle)}</desc>',
            '<rect width="1160" height="100%" fill="#f6f8fb"/>',
            '<style>text{font-family:Arial,sans-serif;fill:#142c42} .muted{fill:#526878}</style>',
            f'<text x="48" y="56" font-size="28" font-weight="700">{escape(title)}</text>',
            f'<text x="48" y="86" font-size="16" class="muted">{escape(subtitle)}</text>']


def performance_chart(metrics):
    svg = svg_start('ERIS: margin improvement alongside a revenue contraction',
                    'Consolidated FY2019–FY2023 | Revenue in NTD million; margins in percent')
    svg += ['<text x="60" y="135" font-size="20" font-weight="700">Revenue</text>',
            '<text x="620" y="135" font-size="20" font-weight="700">Profitability</text>']
    for tick in range(0, 2501, 500):
        y = 450 - tick / 2500 * 260
        svg += [f'<line x1="90" x2="545" y1="{y}" y2="{y}" stroke="#dce3ea"/>',
                f'<text x="78" y="{y + 5}" text-anchor="end" font-size="13">{tick:,}</text>']
    for index, row in enumerate(metrics):
        x = 120 + index * 90
        height = row['revenue'] / 1000 / 2500 * 260
        svg += [f'<rect x="{x}" y="{450-height}" width="48" height="{height}" rx="4" fill="{"#c07825" if row["year"] == 2023 else "#236e85"}"/>',
                f'<text x="{x+24}" y="{440-height}" text-anchor="middle" font-size="13">{row["revenue"]/1000:,.0f}</text>',
                f'<text x="{x+24}" y="477" text-anchor="middle" font-size="14">{row["year"]}</text>']
    for tick in range(0, 41, 10):
        y = 450 - tick / 45 * 260
        svg += [f'<line x1="650" x2="1080" y1="{y}" y2="{y}" stroke="#dce3ea"/>',
                f'<text x="638" y="{y+5}" text-anchor="end" font-size="13">{tick}%</text>']
    for key, color, name, ly in [('gross_margin_pct', '#236e85', 'Gross margin', 516),
                                 ('operating_margin_pct', '#a16221', 'Operating margin', 548)]:
        points = ' '.join(f'{680+i*90},{450-r[key]/45*260}' for i, r in enumerate(metrics))
        svg.append(f'<polyline points="{points}" fill="none" stroke="{color}" stroke-width="3"/>')
        for i, r in enumerate(metrics):
            x, y = 680+i*90, 450-r[key]/45*260
            svg += [f'<circle cx="{x}" cy="{y}" r="4" fill="{color}"/>',
                    f'<text x="{x}" y="{y-12}" text-anchor="middle" font-size="13">{r[key]:.1f}</text>']
        svg += [f'<line x1="650" x2="680" y1="{ly-5}" y2="{ly-5}" stroke="{color}" stroke-width="3"/>',
                f'<text x="690" y="{ly}" font-size="15">{name}</text>']
    for i, r in enumerate(metrics):
        svg.append(f'<text x="{680+i*90}" y="477" text-anchor="middle" font-size="14">{r["year"]}</text>')
    svg += ['<text x="60" y="520" font-size="18" font-weight="700">2023 vs 2022</text>',
            '<text x="60" y="550" font-size="17">Revenue -20.13% | Operating profit -28.04%</text>',
            '<text x="48" y="594" font-size="13" class="muted">Source: ERIS 2023 Annual Report, PDF pp.76 and 82. Data and formulas: data/ and scripts/.</text>', '</svg>']
    return '\n'.join(svg) + '\n'


def sensitivity_chart(rows):
    svg = svg_start('Source-model sensitivity: positive NPV depends on assumptions',
                    'Diagnostic only. NPV in NTD million; selected original cash-flow proxies remain unvalidated.', 530)
    rates = sorted({row['discount_rate'] for row in rows})
    for i, rate in enumerate(rates):
        svg.append(f'<text x="{400+i*170}" y="152" text-anchor="middle" font-size="20">{rate:.1%}</text>')
    svg += ['<text x="655" y="120" text-anchor="middle" font-size="15">Illustrative discount rate</text>',
            '<text x="48" y="185" font-size="15">Extra annual CapEx</text>',
            '<text x="48" y="207" font-size="14">(NTD million)</text>']
    for j, capex in enumerate([0, 25000, 50000]):
        svg.append(f'<text x="220" y="{248+j*75}" text-anchor="end" font-size="21">{capex/1000:.0f}</text>')
        for i, rate in enumerate(rates):
            row = next(x for x in rows if x['discount_rate'] == rate and x['extra_annual_capex'] == capex)
            value = row['diagnostic_npv'] / 1000
            fill = '#cce8e1' if value >= 0 else '#f2d5cd'
            svg += [f'<rect x="{325+i*170}" y="{215+j*75}" width="150" height="58" rx="8" fill="{fill}"/>',
                    f'<text x="{400+i*170}" y="{252+j*75}" text-anchor="middle" font-size="23" font-weight="700">{value:+.1f}</text>']
    svg += ['<text x="48" y="470" font-size="15">CapEx scenarios are assumed deductions, not ERIS spending forecasts. No terminal value is introduced.</text>',
            '<text x="48" y="502" font-size="13" class="muted">Source: selected Working Paper cached inputs. See docs/capital-budgeting.zh-TW.md for unresolved scope.</text>', '</svg>']
    return '\n'.join(svg) + '\n'


def build():
    history = read_rows('historical-financials.csv')
    ratios = read_rows('reported-ratios.csv')
    source = json.loads((ROOT / 'data/source-model-diagnostic.json').read_text())
    controls = []

    def control(name, condition):
        if not condition:
            raise AssertionError(name)
        controls.append(name)

    def close(name, first, second, tolerance=.01):
        control(name, abs(first-second) <= tolerance)

    control('historical years', [r['year'] for r in history] == list(range(2019, 2024)))
    control('ratio years align', [r['year'] for r in history] == [r['year'] for r in ratios])
    metrics = []
    for index, (r, ratio) in enumerate(zip(history, ratios)):
        year = r['year']
        close(f'{year} balance sheet', r['total_assets'], r['total_liabilities']+r['total_equity'])
        close(f'{year} gross profit', r['gross_profit'], r['revenue']-r['cogs'])
        close(f'{year} operating profit', r['operating_profit'], r['gross_profit']-r['operating_expenses'])
        close(f'{year} pretax profit', r['pretax_profit'], r['operating_profit']+r['non_operating_income'])
        close(f'{year} net profit', r['net_profit'], r['pretax_profit']-r['tax_expense_signed'])
        close(f'{year} current ratio', r['current_assets']/r['current_liabilities']*100, ratio['current_ratio_pct'])
        close(f'{year} liability ratio', r['total_liabilities']/r['total_assets']*100, ratio['liabilities_assets_pct'])
        close(f'{year} net margin', r['net_profit']/r['revenue']*100, ratio['net_margin_pct'])
        metrics.append({'year': year, 'revenue': r['revenue'],
                        'revenue_growth_pct': None if index == 0 else (r['revenue']/history[index-1]['revenue']-1)*100,
                        'gross_margin_pct': r['gross_profit']/r['revenue']*100,
                        'operating_margin_pct': r['operating_profit']/r['revenue']*100,
                        'net_margin_pct': r['net_profit']/r['revenue']*100,
                        'pretax_margin_pct': r['pretax_profit']/r['revenue']*100,
                        'rd_revenue_pct': r['rd_expense']/r['revenue']*100,
                        'current_ratio_x': r['current_assets']/r['current_liabilities'],
                        'liabilities_equity_x': r['total_liabilities']/r['total_equity'],
                        'accounting_nwc': r['current_assets']-r['current_liabilities'],
                        'approx_ccc_days': 365/ratio['receivables_turnover']+365/ratio['inventory_turnover']-365/ratio['payables_turnover']})
    old, new = history[-2:]
    bridge = {'revenue_at_prior_margin': (new['revenue']-old['revenue'])*old['gross_profit']/old['revenue'],
              'margin_at_current_revenue': new['revenue']*(new['gross_profit']/new['revenue']-old['gross_profit']/old['revenue']),
              'expense_reduction': old['operating_expenses']-new['operating_expenses']}
    close('operating profit bridge', sum(bridge.values()), new['operating_profit']-old['operating_profit'])
    close('2023 official tax benefit', new['tax_expense_signed'], -37195)
    close('2023 official net profit', new['net_profit'], 337792)
    diagnostic_npv = npv(source['discount_rate'], source['cash_flow_proxy'], source['initial_outlay'])
    close('source cached discounting', diagnostic_npv, source['workbook_cached_npv'])
    close('NPV timing zero discount', npv(0, [40, 60], 100), 0)
    close('NPV timing first-period discount', npv(.1, [110], 100), 0)
    close('NPV empty future cashflows', npv(.1, [], 100), -100)
    sensitivity = []
    for capex in [0, 25000, 50000]:
        for rate in [.022, .06, .08, .10]:
            sensitivity.append({'discount_rate': rate, 'extra_annual_capex': capex,
                                'diagnostic_npv': round(npv(rate, [cf-capex for cf in source['cash_flow_proxy']], source['initial_outlay']), 6)})
    for capex in [0, 25000, 50000]:
        values = [row['diagnostic_npv'] for row in sensitivity if row['extra_annual_capex'] == capex]
        control(f'discount monotonicity at capex {capex}', all(a > b for a,b in zip(values, values[1:])))
    for rate in [.022, .06, .08, .10]:
        values = [row['diagnostic_npv'] for row in sensitivity if row['discount_rate'] == rate]
        control(f'capex monotonicity at rate {rate}', all(a > b for a,b in zip(values, values[1:])))
    result = {'scope': 'reviewed historical metrics and unvalidated source-model diagnostics',
              'unit': 'NTD_thousand except ratios and days', 'historical': metrics,
              'operating_profit_bridge_2023': bridge,
              'rd_growth_2023_pct': (new['rd_expense']/old['rd_expense']-1)*100,
              'operating_profit_growth_2023_pct': (new['operating_profit']/old['operating_profit']-1)*100,
              'source_model_diagnostic_npv': diagnostic_npv,
              'source_model_slide_npv': source['slide_reported_npv'],
              'controls_passed': len(controls), 'controls': controls}
    report = ['# 可重算分析結果', '', '資料單位：新台幣仟元；比率以百分比或倍數標示。', '',
              '| 年度 | 營收 | 毛利率 | 營益率 | 淨利率 | 研發費用率 | 流動比率 | 近似 CCC 天數 |',
              '|---|---:|---:|---:|---:|---:|---:|---:|']
    for row in metrics:
        report.append(f'| {row["year"]} | {row["revenue"]:,.0f} | {row["gross_margin_pct"]:.2f}% | {row["operating_margin_pct"]:.2f}% | {row["net_margin_pct"]:.2f}% | {row["rd_revenue_pct"]:.2f}% | {row["current_ratio_x"]:.2f}x | {row["approx_ccc_days"]:.1f} |')
    report += ['', '## 2023 年營業利益橋接', '',
               f'- 規模效果：{bridge["revenue_at_prior_margin"]:,.3f}',
               f'- 毛利率效果：{bridge["margin_at_current_revenue"]:,.3f}',
               f'- 費用下降貢獻：{bridge["expense_reduction"]:,.3f}',
               f'- 合計：{sum(bridge.values()):,.3f}', '',
               '## 來源模型折現診斷', '',
               f'選定原快取現金流以 2.2% 重折現並扣初始 800,000，NPV = **{diagnostic_npv:,.3f}**。簡報另列 {source["slide_reported_npv"]:,.0f}，未確認版本差異。', '',
               '此項僅核對選定代理值的折現算術，未執行原工作簿全表重算，也未確認真實增量 FCFF 或 WACC。12 組敏感度為診斷假設。', '',
               f'本次執行通過 **{len(controls)} 項計算控制**；檢查數學與資料勾稽，不代表所有原稿主張、估值或公司營運已驗證。', '',
               '[資料定義](../data/README.md) · [模型限制](../docs/model-review.md)', '']
    return {'outputs/metrics.json': json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)+'\n',
            'outputs/npv-sensitivity.csv': csv_text(sensitivity),
            'outputs/analysis.md': '\n'.join(report),
            'assets/financial-performance.svg': performance_chart(metrics),
            'assets/npv-sensitivity.svg': sensitivity_chart(sensitivity)}, len(controls)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Verify saved outputs without modifying files')
    args = parser.parse_args()
    files, count = build()
    for relative, text in files.items():
        path = ROOT / relative
        if args.check:
            if not path.exists() or path.read_text(encoding='utf-8') != text:
                raise AssertionError(f'Output missing or stale: {relative}')
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding='utf-8')
    print(f'PASS: {count} calculation controls; {len(files)} generated outputs ' + ('verified' if args.check else 'written'))


if __name__ == '__main__':
    main()
