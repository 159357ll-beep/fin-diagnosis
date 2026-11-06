# -*- coding: utf-8 -*-
"""
美的集团（000333）2025 年度财务分析脚本
===========================================================================
数据来源：美的集团《2025 年年度报告》合并报表
    · 合并资产负债表（第 132~133 页，2025-12-31 / 2024-12-31）
    · 合并利润表（第 135 页，2025 年度 / 2024 年度）
金额单位：人民币千元（报表原单位）；比率与周转率除外。

计算内容：
    1. 毛利率、净利率
    2. 平均存货周转率、平均应收账款周转率（含周转天数）
    3. 总资产周转率、资产负债率、权益乘数
    4. 杜邦分析：ROE = 净利率 × 总资产周转率 × 权益乘数
    5. 基于 if / elif / else 的智能诊断报告

口径说明（重要）：
    · 2025 年指标以「平均余额」为主口径：存货、应收账款、总资产、所有者权益
      均取 2024 年末与 2025 年末的平均值；
    · 2024 年缺少 2023 年末数据，无法计算平均余额，故按「期末余额」计算，
      并在结果中单独标注，避免与 2025 年平均口径直接比较；
    · 为便于跨年可比，脚本额外计算了 2025 年的「期末口径」指标。
    · 所有者权益、净利润均为合并口径（含少数股东），两者相互匹配。

运行环境：Python 3.6+，仅使用标准库，可直接复制到在线环境运行。
"""

from typing import Dict, Optional


# ===========================================================================
# 一、从合并报表中提取的数据（单位：人民币千元）
# ===========================================================================
DATA: Dict[str, Dict[str, float]] = {
    "2025": {
        "营业收入": 456_451_731,      # 合并利润表：营业收入（不含利息收入等）
        "营业成本": 335_989_528,      # 合并利润表：营业成本（原表以负数列示，取绝对值）
        "净利润": 44_520_196,         # 合并利润表：净利润（含少数股东损益）
        "应收账款": 40_450_097,       # 合并资产负债表：应收账款
        "存货": 64_628_834,           # 合并资产负债表：存货
        "总资产": 608_791_766,        # 合并资产负债表：资产总计
        "所有者权益": 236_424_223,     # 合并资产负债表：股东权益合计（含少数股东权益）
    },
    "2024": {
        "营业收入": 407_149_600,
        "营业成本": 299_584_935,
        "净利润": 38_757_214,
        "应收账款": 35_798_974,
        "存货": 63_339_188,
        "总资产": 604_351_853,
        "所有者权益": 227_667_391,
    },
}

# 辅助数据：有息负债明细（合并资产负债表），仅用于修正「资产负债率高 = 风险高」的误判
DEBT_DETAIL: Dict[str, Dict[str, float]] = {
    "2025": {
        "短期借款": 43_904_550,
        "一年内到期的非流动负债": 5_821_777,
        "长期借款": 12_658_843,
        "应付债券": 3_194_774,
    },
    "2024": {
        "短期借款": 31_008_549,
        "一年内到期的非流动负债": 39_662_733,
        "长期借款": 10_491_757,
        "应付债券": 3_266_775,
    },
}

# 诊断阈值（可按行业与自身经验调整）
ROE_EXCELLENT = 0.15      # ROE ≥ 15% 视为优秀
ROE_GOOD = 0.10           # ROE ≥ 10% 视为良好
DEBT_ALERT = 0.60         # 资产负债率 > 60% 触发预警
GROSS_MARGIN_STRONG = 0.25
NET_MARGIN_STRONG = 0.08
INVENTORY_TURN_FAST = 5.0
AR_TURN_FAST = 10.0
ASSET_TURN_GOOD = 0.80


# ===========================================================================
# 二、通用工具函数
# ===========================================================================
def safe_div(numerator: float, denominator: float) -> float:
    """安全除法：分母为 0 时返回 0，避免程序中断。"""
    return numerator / denominator if denominator else 0.0


def to_yi(amount: float) -> float:
    """千元 → 亿元（1 亿元 = 100,000 千元）。"""
    return amount / 100_000.0


def fmt_pct(value: float) -> str:
    """把小数格式化为百分比，如 0.2639 → 26.39%。"""
    return f"{value:.2%}"


def fmt_num(value: float, digits: int = 2) -> str:
    """保留指定小数位并加千分位。"""
    return f"{value:,.{digits}f}"


def fmt_pp(value: float) -> str:
    """把小数差（如 0.0018）格式化为百分点，如 +0.18pp。"""
    return f"{value * 100:+.2f}pp"


def _disp_width(text: str) -> int:
    """计算中英文混排的显示宽度（全角字符按 2 列计），用于控制台对齐。"""
    import unicodedata

    return sum(
        2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1 for ch in text
    )


def _pad(text: str, width: int, align: str = "left") -> str:
    """按显示宽度补空格。"""
    gap = max(0, width - _disp_width(text))
    if align == "right":
        return " " * gap + text
    if align == "center":
        left = gap // 2
        return " " * left + text + " " * (gap - left)
    return text + " " * gap


def print_table(headers, rows, aligns) -> None:
    """打印等宽表格。"""
    widths = [
        max(_disp_width(row[i]) for row in [headers] + rows)
        for i in range(len(headers))
    ]
    line = "─" * (sum(widths) + 2 * (len(widths) - 1))
    print("  ".join(_pad(h, w, "center") for h, w in zip(headers, widths)))
    print(line)
    for row in rows:
        print("  ".join(_pad(c, w, a) for c, w, a in zip(row, widths, aligns)))
    print(line)


# ===========================================================================
# 三、核心指标计算
# ===========================================================================
def calc_metrics(cur: Dict[str, float],
                 prev: Optional[Dict[str, float]] = None,
                 year: str = "") -> Dict[str, float]:
    """计算单一年度的财务指标。

    参数
        cur  : 当年数据字典
        prev : 上年数据字典；传入时余额类科目取「(期初+期末)/2」，
               不传时退化为期末余额（用于缺少年初数据的 2024 年）。
        year : 年份标签，仅用于结果标识。

    返回
        包含金额、比率、周转率、周转天数与杜邦三因子的字典。
    """
    revenue = cur["营业收入"]
    cogs = cur["营业成本"]
    profit = cur["净利润"]
    assets = cur["总资产"]
    equity = cur["所有者权益"]
    liabilities = assets - equity          # 会计恒等式：负债 = 资产 - 所有者权益

    def average(key: str) -> float:
        """余额类科目取平均：有上年数据用平均值，否则用期末值。"""
        if prev is None:
            return cur[key]
        return (cur[key] + prev[key]) / 2.0

    avg_inventory = average("存货")
    avg_receivables = average("应收账款")
    avg_assets = average("总资产")
    avg_equity = average("所有者权益")

    # ---------- 盈利能力 ----------
    gross_margin = safe_div(revenue - cogs, revenue)      # 毛利率
    net_margin = safe_div(profit, revenue)                # 净利率

    # ---------- 营运能力 ----------
    inventory_turnover = safe_div(cogs, avg_inventory)    # 存货周转率（次）
    receivables_turnover = safe_div(revenue, avg_receivables)  # 应收账款周转率（次）
    asset_turnover = safe_div(revenue, avg_assets)        # 总资产周转率（次）
    inventory_days = safe_div(365.0, inventory_turnover)  # 存货周转天数
    receivables_days = safe_div(365.0, receivables_turnover)  # 应收周转天数

    # ---------- 偿债与杠杆 ----------
    debt_ratio = safe_div(liabilities, assets)            # 资产负债率
    equity_multiplier = safe_div(avg_assets, avg_equity)  # 权益乘数

    # ---------- 杜邦 ROE ----------
    roe = safe_div(profit, avg_equity)                    # 净资产收益率
    roa = safe_div(profit, avg_assets)                    # 总资产净利率

    return {
        "年份": year,
        "口径": "平均余额法" if prev is not None else "期末余额法",
        "营业收入": revenue,
        "营业成本": cogs,
        "净利润": profit,
        "总资产": assets,
        "所有者权益": equity,
        "负债合计": liabilities,
        "平均存货": avg_inventory,
        "平均应收账款": avg_receivables,
        "平均总资产": avg_assets,
        "平均所有者权益": avg_equity,
        "毛利率": gross_margin,
        "净利率": net_margin,
        "存货周转率": inventory_turnover,
        "存货周转天数": inventory_days,
        "应收账款周转率": receivables_turnover,
        "应收账款周转天数": receivables_days,
        "总资产周转率": asset_turnover,
        "资产负债率": debt_ratio,
        "权益乘数": equity_multiplier,
        "ROE": roe,
        "ROA": roa,
    }


def dupont_attribution(cur: Dict[str, float],
                       base: Dict[str, float]) -> Dict[str, float]:
    """用连环替代法分解 ROE 变动，拆成净利率、周转率、权益乘数三部分。

    设 ROE = M × T × L（净利率 × 总资产周转率 × 权益乘数），
    依次替换 M、T、L，得到各因素对 ROE 变动（百分点）的贡献。
    """
    m0, t0, l0 = base["净利率"], base["总资产周转率"], base["权益乘数"]
    m1, t1, l1 = cur["净利率"], cur["总资产周转率"], cur["权益乘数"]

    effect_margin = (m1 - m0) * t0 * l0          # 净利率变动的影响
    effect_turnover = m1 * (t1 - t0) * l0        # 周转率变动的影响
    effect_leverage = m1 * t1 * (l1 - l0)        # 杠杆变动的影响

    return {
        "净利率贡献": effect_margin,
        "周转率贡献": effect_turnover,
        "杠杆贡献": effect_leverage,
        "合计": effect_margin + effect_turnover + effect_leverage,
    }


# ===========================================================================
# 四、结果展示
# ===========================================================================
def print_header() -> None:
    """打印报告标题与数据来源。"""
    print("=" * 76)
    print(_pad("美的集团（000333）2025 年度财务分析", 76, "center"))
    print("=" * 76)
    print("数据来源：美的集团 2025 年年度报告 · 合并资产负债表（P132-133）、")
    print("          合并利润表（P135）；金额单位：人民币千元，比率除外。")
    print()


def print_data_table() -> None:
    """打印基础数据（换算为亿元，便于阅读）。"""
    print("【一】基础数据（亿元）")
    headers = ["项目", "2025 年", "2024 年", "同比变动"]
    rows = []
    for key in ("营业收入", "营业成本", "净利润", "应收账款", "存货", "总资产", "所有者权益"):
        cur = DATA["2025"][key]
        old = DATA["2024"][key]
        change = safe_div(cur, old) - 1.0
        rows.append([key, fmt_num(to_yi(cur)), fmt_num(to_yi(old)), f"{change:+.2%}"])
    print_table(headers, rows, ["left", "right", "right", "right"])
    print()


def print_metric_table(m25: Dict[str, float],
                       m25_end: Dict[str, float],
                       m24: Dict[str, float]) -> None:
    """打印核心指标：2025 平均口径、2025 期末口径、2024 期末口径。"""
    print("【二】核心财务指标")
    headers = ["指标", "2025（平均）", "2025（期末）", "2024（期末）"]
    rows = [
        ["毛利率", fmt_pct(m25["毛利率"]), fmt_pct(m25_end["毛利率"]), fmt_pct(m24["毛利率"])],
        ["净利率", fmt_pct(m25["净利率"]), fmt_pct(m25_end["净利率"]), fmt_pct(m24["净利率"])],
        ["存货周转率", f'{m25["存货周转率"]:.2f} 次', f'{m25_end["存货周转率"]:.2f} 次', f'{m24["存货周转率"]:.2f} 次'],
        ["存货周转天数", f'{m25["存货周转天数"]:.1f} 天', f'{m25_end["存货周转天数"]:.1f} 天', f'{m24["存货周转天数"]:.1f} 天'],
        ["应收账款周转率", f'{m25["应收账款周转率"]:.2f} 次', f'{m25_end["应收账款周转率"]:.2f} 次', f'{m24["应收账款周转率"]:.2f} 次'],
        ["应收账款周转天数", f'{m25["应收账款周转天数"]:.1f} 天', f'{m25_end["应收账款周转天数"]:.1f} 天', f'{m24["应收账款周转天数"]:.1f} 天'],
        ["总资产周转率", f'{m25["总资产周转率"]:.2f} 次', f'{m25_end["总资产周转率"]:.2f} 次', f'{m24["总资产周转率"]:.2f} 次'],
        ["资产负债率", fmt_pct(m25["资产负债率"]), fmt_pct(m25_end["资产负债率"]), fmt_pct(m24["资产负债率"])],
        ["权益乘数", f'{m25["权益乘数"]:.2f}', f'{m25_end["权益乘数"]:.2f}', f'{m24["权益乘数"]:.2f}'],
        ["ROE", fmt_pct(m25["ROE"]), fmt_pct(m25_end["ROE"]), fmt_pct(m24["ROE"])],
        ["ROA", fmt_pct(m25["ROA"]), fmt_pct(m25_end["ROA"]), fmt_pct(m24["ROA"])],
    ]
    print_table(headers, rows, ["left", "right", "right", "right"])
    print("注：2024 年缺 2023 年末余额，周转率与 ROE 按期末余额计算；")
    print("    2025 年同时给出平均、期末两种口径，便于与 2024 年同口径对比。")
    print()


def print_dupont(m25: Dict[str, float],
                 m25_end: Dict[str, float],
                 m24: Dict[str, float]) -> None:
    """打印杜邦分析：主口径 + 期末口径的跨年归因。"""
    print("【三】杜邦分析")
    print("  ROE = 净利率 × 总资产周转率 × 权益乘数")
    print(
        f"      = {m25['净利率']:.2%} × {m25['总资产周转率']:.2f} × "
        f"{m25['权益乘数']:.2f} = {m25['ROE']:.2%}（2025 平均口径）"
    )
    print(
        f"      = {m25_end['净利率']:.2%} × {m25_end['总资产周转率']:.2f} × "
        f"{m25_end['权益乘数']:.2f} = {m25_end['ROE']:.2%}（2025 期末口径）"
    )
    print(
        f"      = {m24['净利率']:.2%} × {m24['总资产周转率']:.2f} × "
        f"{m24['权益乘数']:.2f} = {m24['ROE']:.2%}（2024 期末口径）"
    )
    print()

    attribution = dupont_attribution(m25_end, m24)
    diff = m25_end["ROE"] - m24["ROE"]
    print(f"  2025 vs 2024（均为期末口径）ROE 变动：{fmt_pp(diff)}")
    print("  连环替代法归因：")
    print(f"    净利率变动贡献      {fmt_pp(attribution['净利率贡献'])}")
    print(f"    总资产周转率贡献    {fmt_pp(attribution['周转率贡献'])}")
    print(f"    权益乘数贡献        {fmt_pp(attribution['杠杆贡献'])}")
    print(f"    合计                {fmt_pp(attribution['合计'])}")
    print()


# ===========================================================================
# 五、智能诊断（if / elif / else）
# ===========================================================================
def diagnose(m25: Dict[str, float], m25_end: Dict[str, float],
             m24: Dict[str, float],
             interest_debt_2025: float, interest_debt_2024: float) -> None:
    """根据指标阈值输出诊断报告，并补充有息负债视角。"""
    print("【四】智能诊断报告")
    print("─" * 76)

    # ---------- ① 盈利能力（ROE） ----------
    roe = m25["ROE"]
    if roe >= ROE_EXCELLENT:
        print(f"① 盈利质量：ROE {roe:.2%} ≥ 15%，【盈利能力优秀】")
    elif roe >= ROE_GOOD:
        print(f"① 盈利质量：ROE {roe:.2%} 介于 10%~15%，盈利能力良好")
    else:
        print(f"① 盈利质量：ROE {roe:.2%} < 10%，盈利能力偏弱，需关注资产效率与费用控制")

    # ---------- ② 资本结构与债务风险 ----------
    debt_ratio = m25["资产负债率"]
    interest_debt_ratio = safe_div(interest_debt_2025, m25["总资产"])
    debt_change = interest_debt_2025 - interest_debt_2024
    if debt_ratio > DEBT_ALERT:
        print(f"② 债务风险：资产负债率 {debt_ratio:.2%} > 60%，【债务风险预警】")
        # 用有息负债率做二次判断，避免把经营性占款误判为偿债压力
        if interest_debt_ratio < 0.15:
            print(
                f"   补充：有息负债 {to_yi(interest_debt_2025):,.2f} 亿元"
                f"（同比 {to_yi(debt_change):+,.2f} 亿元），"
                f"有息负债率 {interest_debt_ratio:.2%}；"
            )
            print("   负债主体为应付账款、合同负债等经营性占款，真实偿债压力可控，")
            print("   建议将预警级别下调为「关注」，重点跟踪应付账款与短期借款的周转。")
        else:
            print("   有息负债率同样偏高，需警惕再融资与利率上行风险。")
    elif debt_ratio >= 0.40:
        print(f"② 债务风险：资产负债率 {debt_ratio:.2%} 处于 40%~60%，资本结构稳健")
    else:
        print(f"② 债务风险：资产负债率 {debt_ratio:.2%} < 40%，财务政策偏保守")

    # ---------- ③ 毛利率与净利率 ----------
    gm, nm = m25["毛利率"], m25["净利率"]
    gm_change = m25["毛利率"] - m24["毛利率"]
    revenue_growth = safe_div(m25["营业收入"], m24["营业收入"]) - 1.0
    profit_growth = safe_div(m25["净利润"], m24["净利润"]) - 1.0
    print(
        f"③ 盈利结构：营业收入同比 {revenue_growth:+.2%}，"
        f"净利润同比 {profit_growth:+.2%}，利润增速快于收入"
        if profit_growth > revenue_growth
        else f"③ 盈利结构：营业收入同比 {revenue_growth:+.2%}，净利润同比 {profit_growth:+.2%}"
    )
    if gm >= GROSS_MARGIN_STRONG:
        gm_text = "毛利率处于高位，产品结构与成本管控具备竞争力"
    elif gm >= 0.15:
        gm_text = "毛利率处于行业中等水平"
    else:
        gm_text = "毛利率偏低，需关注原材料成本与价格竞争"
    print(f"   毛利率 {gm:.2%}（同比 {fmt_pp(gm_change)}），{gm_text}")

    if nm >= NET_MARGIN_STRONG:
        print(f"   净利率 {nm:.2%} ≥ 8%，费用控制良好，利润转化效率较高")
    elif nm >= 0.05:
        print(f"   净利率 {nm:.2%} 处于 5%~8%，盈利转化能力一般")
    else:
        print(f"   净利率 {nm:.2%} < 5%，利润空间偏薄")

    # ---------- ④ 营运能力 ----------
    inv_turn, ar_turn = m25["存货周转率"], m25["应收账款周转率"]
    print(
        f"④ 营运效率：存货周转 {inv_turn:.2f} 次（{m25['存货周转天数']:.0f} 天），"
        f"应收账款周转 {ar_turn:.2f} 次（{m25['应收账款周转天数']:.0f} 天）"
    )
    if inv_turn >= INVENTORY_TURN_FAST:
        print("   存货周转快，库存管理效率高")
    elif inv_turn >= 3.0:
        print("   存货周转正常，需结合行业淡旺季判断")
    else:
        print("   存货周转偏慢，存在库存积压风险")

    if ar_turn >= AR_TURN_FAST:
        print("   应收账款回款速度快，坏账风险相对较低")
    elif ar_turn >= 6.0:
        print("   应收账款回款速度一般，需持续跟踪账龄结构")
    else:
        print("   应收账款回款偏慢，警惕信用政策放松带来的坏账风险")

    asset_turn = m25["总资产周转率"]
    if asset_turn >= ASSET_TURN_GOOD:
        print(f"   总资产周转率 {asset_turn:.2f} 次，资产使用效率较高")
    elif asset_turn >= 0.50:
        print(f"   总资产周转率 {asset_turn:.2f} 次，资产使用效率正常")
    else:
        print(f"   总资产周转率 {asset_turn:.2f} 次，资产偏重、周转偏慢")

    # ---------- ⑤ 杜邦归因 ----------
    attribution = dupont_attribution(m25_end, m24)  # 统一用期末口径，跨年可比
    print("⑤ 杜邦归因：ROE 由「净利率 × 周转率 × 权益乘数」三因子驱动")
    print(
        f"   净利率 {m25['净利率']:.2%}、周转率 {m25['总资产周转率']:.2f}、"
        f"权益乘数 {m25['权益乘数']:.2f}；"
    )
    print(
        f"   2025 vs 2024（期末口径）：净利率贡献 {fmt_pp(attribution['净利率贡献'])}、"
        f"周转率贡献 {fmt_pp(attribution['周转率贡献'])}、"
        f"杠杆贡献 {fmt_pp(attribution['杠杆贡献'])}。"
    )
    print(
        f"   其中权益乘数 {m25['权益乘数']:.2f} 意味着每 1 元股东权益支撑 "
        f"{m25['权益乘数']:.2f} 元资产，杠杆是 ROE 的放大器。"
    )

    # ---------- ⑥ 综合结论 ----------
    print("─" * 76)
    print("综合结论：")
    if roe >= ROE_EXCELLENT and debt_ratio > DEBT_ALERT and interest_debt_ratio < 0.15:
        print("  公司呈现「高盈利、高周转、表观高负债、低有息负债」的组合：")
        print("  ROE 主要由净利率与资产周转率驱动，杠杆贡献有限；")
        print("  资产负债率虽超过 60%，但以经营性负债为主，短期偿债风险可控。")
        print("  建议：保持应收与存货管理，关注分红与回购对权益规模的影响。")
    elif roe >= ROE_EXCELLENT:
        print("  公司盈利能力优秀，资本结构处于合理区间，可重点关注增长质量与现金流。")
    else:
        print("  公司盈利能力一般，建议从提升毛利率、加快资产周转两方面改善 ROE。")


# ===========================================================================
# 六、主程序
# ===========================================================================
def main() -> None:
    # 计算三种口径
    m25 = calc_metrics(DATA["2025"], DATA["2024"], "2025")   # 2025 平均余额口径
    m25_end = calc_metrics(DATA["2025"], None, "2025")      # 2025 期末口径（与 2024 可比）
    m24 = calc_metrics(DATA["2024"], None, "2024")          # 2024 期末口径

    interest_debt_2025 = sum(DEBT_DETAIL["2025"].values())
    interest_debt_2024 = sum(DEBT_DETAIL["2024"].values())

    print_header()
    print_data_table()
    print_metric_table(m25, m25_end, m24)
    print_dupont(m25, m25_end, m24)

    print("【附】有息负债结构（亿元）")
    print(
        f"  2025 年有息负债 {to_yi(interest_debt_2025):,.2f} 亿元，"
        f"有息负债率 {safe_div(interest_debt_2025, m25['总资产']):.2%}；"
    )
    print(
        f"  2024 年有息负债 {to_yi(interest_debt_2024):,.2f} 亿元，"
        f"有息负债率 {safe_div(interest_debt_2024, m24['总资产']):.2%}。"
    )
    print()

    diagnose(m25, m25_end, m24, interest_debt_2025, interest_debt_2024)


if __name__ == "__main__":
    main()
