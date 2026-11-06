# -*- coding: utf-8 -*-
"""
企业全景财务诊断与估值系统 v6.0 · 基于四表一注
===========================================================================
模式 B 按真实报表结构录入原始科目：
    📄 利润表 → 📊 资产负债表 → 💵 现金流量表 → 📝 附注
系统自动生成统一“指标池”，四个 Tab 全部复用：
    核心 EBIT、NOPAT、净利润、CapEx、ΔNWC、FCFF、
    毛利率、净利率、总资产周转率、权益乘数、ROE、
    流动比率、速动比率、资产负债率、存货/应收周转率、DOL/DFL/DTL。

模式 A 保留二手指标直接输入（FCFF / 杠杆 / 杜邦 / 营运偿债各自录入）。

运行（两种方式都可以）：
    1) streamlit run app.py
       （本项目便携环境：.\\python.cmd -m streamlit run app.py）
    2) python app.py
       （若检测到未处于 Streamlit 运行时，会自动转交 `streamlit run` 并打开浏览器）

依赖：streamlit、pandas
"""

import os
import subprocess
import sys

import pandas as pd
import streamlit as st
from streamlit.runtime import exists as _streamlit_runtime_exists


def _relaunch_with_streamlit() -> None:
    """直接 `python app.py` 时，自动改用 `streamlit run` 重新启动本脚本。

    直接运行时 Streamlit 处于 bare mode，`st.session_state` 等接口不可用，
    因此这里转交给官方启动器，保证脚本在真实服务器上下文中执行。
    额外命令行参数（如 --server.port 8502）会原样透传给 `streamlit run`。
    """
    script = os.path.abspath(__file__)
    cmd = [sys.executable, "-m", "streamlit", "run", script, *sys.argv[1:]]
    print("[启动] 正在通过 `streamlit run` 启动服务，浏览器将自动打开……")
    try:
        subprocess.run(cmd, check=False)
    except KeyboardInterrupt:
        print("\n[退出] 已手动停止服务。")
    sys.exit(0)


# 未运行在 Streamlit 服务器上下文时，自动转交启动（不会重复启动）
if not _streamlit_runtime_exists():
    _relaunch_with_streamlit()

# ===========================================================================
# 全局常量与页面配置
# ===========================================================================
MODE_A = "模式 A：二手指标输入"
MODE_B = "模式 B：四表原始数据"

st.set_page_config(
    page_title="智能财务诊断与估值系统 v6.0",
    page_icon="📊",
    layout="wide",
)

_CSS = """
<style>
    .stApp { background: #f5f7fb; }
    .block-container { padding-top: 2.2rem; padding-bottom: 3rem; max-width: 1180px; }
    .hero {
        background: linear-gradient(135deg, #0e2a47 0%, #1d4e79 100%);
        color: #fff; padding: 30px 34px; border-radius: 16px; margin-bottom: 24px;
        box-shadow: 0 10px 24px rgba(14, 42, 71, 0.18);
    }
    .hero-title { font-size: 30px; font-weight: 700; letter-spacing: 1px; margin-bottom: 6px; }
    .hero-sub { font-size: 13px; color: #b9cde2; letter-spacing: 2px; }
    .hero-badge {
        display: inline-block; margin-left: 10px; padding: 2px 10px;
        border: 1px solid #6f9ac4; border-radius: 999px; font-size: 12px; color: #cfe1f3;
    }
    div[data-testid="stMetric"] {
        background: #fff; border: 1px solid #e4eaf2; border-radius: 14px;
        padding: 16px 20px; box-shadow: 0 2px 8px rgba(15, 42, 71, 0.04);
    }
    div[data-testid="stMetricLabel"] p { font-size: 14px; color: #5a6b80; }
    div[data-testid="stMetricValue"] { font-size: 28px; font-weight: 700; color: #0e3a63; }
    .flow {
        background: #fff; border: 1px solid #e4eaf2; border-left: 4px solid #1d4e79;
        border-radius: 10px; padding: 14px 18px; margin: 4px 0 18px 0;
        font-size: 14px; color: #38495c;
    }
    .flow span { color: #1d4e79; font-weight: 600; }
    .explain {
        background: #fff; border: 1px solid #e4eaf2; border-radius: 12px;
        padding: 16px 20px; margin-bottom: 12px;
    }
    .explain h4 { margin: 0 0 6px 0; color: #0e3a63; font-size: 15px; }
    .explain p { margin: 0; color: #4a5a75; font-size: 14px; line-height: 1.8; }
    section[data-testid="stSidebar"] {
        background: #fff; border-right: 1px solid #e4eaf2;
    }
    section[data-testid="stSidebar"] .block-container { padding-top: 1.4rem; }

    .st-key-fcff_big div[data-testid="stMetric"] {
        background: linear-gradient(135deg, #eef4ff 0%, #dce8f8 100%);
        border: 1px solid #b9cde2;
        padding: 26px 30px;
    }
    .st-key-fcff_big div[data-testid="stMetricValue"] {
        font-size: 54px; color: #0b3d6b; letter-spacing: 1px;
    }
    .st-key-fcff_big div[data-testid="stMetricLabel"] p {
        font-size: 16px; color: #1d4e79;
    }

    .chain { display: flex; gap: 8px; align-items: stretch; margin: 14px 0 18px 0; flex-wrap: wrap; }
    .chain .node {
        flex: 1; min-width: 130px; background: #fff; border: 1px solid #e4eaf2;
        border-radius: 12px; padding: 14px 12px; text-align: center;
    }
    .chain .node .k { font-size: 12px; color: #5a6b80; margin-bottom: 4px; }
    .chain .node .v { font-size: 24px; font-weight: 700; color: #0e3a63; }
    .chain .op { align-self: center; color: #1d4e79; font-size: 20px; font-weight: 700; }
    .chain .node.result {
        background: linear-gradient(135deg, #eef4ff 0%, #dce8f8 100%);
        border-color: #b9cde2;
    }
    .badge { display: inline-block; padding: 4px 10px; border-radius: 999px; font-size: 13px; margin-right: 8px; }
    .badge.ok { background: #e6f4ea; color: #1e7b34; }
    .badge.bad { background: #fdecea; color: #b3261e; }
    .badge.warn { background: #fff4e5; color: #8a5a00; }
</style>
"""

st.markdown(_CSS, unsafe_allow_html=True)


# ===========================================================================
# 通用工具
# ===========================================================================
def fmt(value: float) -> str:
    """金额格式：千分位 + 两位小数。"""
    return f"{value:,.2f}"


def fmt_ratio(value) -> str:
    """倍数格式；无法计算时返回占位符。"""
    return "—" if value is None else f"{value:.2f}"


def fmt_pct(value) -> str:
    """百分比格式；无法计算时返回占位符。"""
    return "—" if value is None else f"{value:.2%}"


def safe_div(numerator: float, denominator: float):
    """安全除法：分母为 0 返回 None，避免 ZeroDivisionError。"""
    return numerator / denominator if denominator else None


def render_hero() -> None:
    """页头。"""
    st.markdown(
        """
        <div class="hero">
            <div class="hero-title">智能财务诊断与估值系统<span class="hero-badge">v6.0 · 四表一注</span></div>
            <div class="hero-sub">FCFF · Leverage · DuPont · Liquidity</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ===========================================================================
# 一、指标池：把四表原始科目转换为统一分析指标
# ===========================================================================
def build_pool(p: dict) -> dict:
    """由四表原始数据生成全量指标池。

    核心口径：
        核心 EBIT = 营业收入 - 营业成本 - 税金及附加 - 期间费用
        净利润   = (核心 EBIT - 利息费用 + 营业外收入 - 营业外支出) × (1 - 25%)
        NOPAT    = 核心 EBIT × (1 - 25%)
        CapEx    = 购建支付 - 处置收回
        ΔNWC     = (流动资产期末-期初) - (流动负债期末-期初)
        FCFF     = NOPAT + D&A - CapEx - ΔNWC
    """
    revenue = p["revenue"]
    if revenue <= 0:
        raise ValueError("营业收入必须大于 0，请检查利润表输入。")

    period_expenses = p["selling"] + p["admin"] + p["rnd"]
    ebit = revenue - p["cogs"] - p["surcharges"] - period_expenses

    pretax = ebit - p["interest"] + p["nonop_income"] - p["nonop_expense"]
    net_profit = pretax * 0.75          # 按 25% 法定税率
    nopat = ebit * 0.75

    capex = p["capex_paid"] - p["disposal"]
    dnwc = (p["ca_end"] - p["ca_beg"]) - (p["cl_end"] - p["cl_beg"])
    fcff = nopat + p["da"] - capex - dnwc

    avg_ar = (p["ar_beg"] + p["ar_end"]) / 2.0
    avg_inventory = (p["inv_beg"] + p["inv_end"]) / 2.0
    avg_assets = (p["assets_beg"] + p["assets_end"]) / 2.0
    avg_equity = p["equity"]           # 资产负债表只填一个权益数，视作平均权益

    gross_margin = safe_div(revenue - p["cogs"], revenue)
    net_margin = safe_div(net_profit, revenue)
    asset_turnover = safe_div(revenue, avg_assets)
    equity_multiplier = safe_div(avg_assets, avg_equity)
    roe = safe_div(net_profit, avg_equity)

    current_ratio = safe_div(p["ca_end"], p["cl_end"])
    quick_ratio = safe_div(p["ca_end"] - p["inv_end"], p["cl_end"])
    inventory_turnover = safe_div(p["cogs"], avg_inventory)
    receivable_turnover = safe_div(revenue, avg_ar)
    debt_ratio = safe_div(p["total_liabilities"], p["assets_end"])

    effective_tax_rate = safe_div(p["income_tax"], pretax) if pretax > 0 else None

    return {
        "inputs": p["inputs"],
        "revenue": revenue,
        "cogs": p["cogs"],
        "surcharges": p["surcharges"],
        "period_expenses": period_expenses,
        "selling": p["selling"],
        "admin": p["admin"],
        "rnd": p["rnd"],
        "interest": p["interest"],
        "nonop_income": p["nonop_income"],
        "nonop_expense": p["nonop_expense"],
        "nonop_net": p["nonop_income"] - p["nonop_expense"],
        "income_tax": p["income_tax"],
        "effective_tax_rate": effective_tax_rate,
        "ebit": ebit,
        "pretax": pretax,
        "net_profit": net_profit,
        "nopat": nopat,
        "da": p["da"],
        "capex_paid": p["capex_paid"],
        "disposal": p["disposal"],
        "capex": capex,
        "dnwc": dnwc,
        "fcff": fcff,
        "avg_ar": avg_ar,
        "avg_inventory": avg_inventory,
        "avg_assets": avg_assets,
        "avg_equity": avg_equity,
        "ca_beg": p["ca_beg"],
        "ca_end": p["ca_end"],
        "cl_beg": p["cl_beg"],
        "cl_end": p["cl_end"],
        "ar_beg": p["ar_beg"],
        "ar_end": p["ar_end"],
        "inv_beg": p["inv_beg"],
        "inv_end": p["inv_end"],
        "assets_beg": p["assets_beg"],
        "assets_end": p["assets_end"],
        "total_liabilities": p["total_liabilities"],
        "gross_margin": gross_margin,
        "net_margin": net_margin,
        "asset_turnover": asset_turnover,
        "equity_multiplier": equity_multiplier,
        "roe": roe,
        "current_ratio": current_ratio,
        "quick_ratio": quick_ratio,
        "inventory_turnover": inventory_turnover,
        "receivable_turnover": receivable_turnover,
        "debt_ratio": debt_ratio,
        "variable_cost": p["variable_cost"],
        "fixed_cost": p["fixed_cost"],
    }


# ===========================================================================
# 二、FCFF 计算与展示
# ===========================================================================
def render_fcff_empty(mode: str) -> None:
    """FCFF 未计算时的引导。"""
    st.info("👈 请在左侧录入数据并生成结果。")
    st.markdown(
        f"""
        <div class="flow">
            当前模式：<span>{mode}</span>。系统会自动完成经营利润还原、NOPAT 与自由现金流推导。
        </div>
        """,
        unsafe_allow_html=True,
    )


def calc_mode_a(ebit: float, tax_pct: float, da: float, capex: float, dnwc: float) -> dict:
    """模式 A：二手指标直接计算 FCFF。"""
    tax_rate = tax_pct / 100.0
    nopat = ebit * (1.0 - tax_rate)
    fcff = nopat + da - capex - dnwc
    return {
        "mode": MODE_A,
        "ebit": ebit,
        "tax_pct": tax_pct,
        "da": da,
        "capex": capex,
        "dnwc": dnwc,
        "nopat": nopat,
        "fcff": fcff,
    }


def render_fcff_result(result: dict, current_inputs: tuple) -> None:
    """FCFF 结果区：推导 → 特大号 FCFF → 诊断。"""
    if result["inputs"] != current_inputs:
        st.warning("参数已修改，下方结果仍是上一次计算的，请重新生成。")

    if result["mode"] == MODE_B:
        st.success(
            f"✅ 系统已自动剔除营业外收支，还原核心经营利润：{fmt(result['ebit'])} 万元。"
        )
        if abs(result["non_operating"]) > 1e-9:
            st.caption(
                f"营业外收支净额 {fmt(result['non_operating'])} 万元已剔除，不计入核心 EBIT。"
            )

    st.subheader("计算推导过程")
    left, right = st.columns(2)

    with left:
        st.markdown("#### NOPAT 推导")
        if result["mode"] == MODE_B:
            st.markdown(
                f"""
                - 营业收入：**{fmt(result['revenue'])}** 万元
                - 减：营业成本：**{fmt(result['cogs'])}** 万元
                - 减：税金及附加：**{fmt(result['surcharges'])}** 万元
                - 减：期间费用：**{fmt(result['opex'])}** 万元
                """
            )
        st.metric("核心 EBIT（万元）", fmt(result["ebit"]))
        st.markdown(f"×（1 − {result['tax_pct']:.2f}%）")
        st.metric("NOPAT（万元）", fmt(result["nopat"]))

    with right:
        st.markdown("#### CapEx 与 ΔNWC 推导")
        if result["mode"] == MODE_B:
            st.markdown(
                f"""
                - 购建长期资产支付：**{fmt(result['capex_paid'])}** 万元
                - 减：处置收回：**{fmt(result['disposal'])}** 万元
                """
            )
        st.metric("真实 CapEx（万元）", fmt(result["capex"]))
        if result["mode"] == MODE_B:
            st.markdown(
                f"""
                - 经营性流动资产增加：**{fmt(result['ca_increase'])}** 万元
                - 减：经营性流动负债增加：**{fmt(result['cl_increase'])}** 万元
                """
            )
        st.metric("ΔNWC（万元）", fmt(result["dnwc"]))
        st.caption(f"折旧与摊销 D&A：{fmt(result['da'])} 万元")

    st.subheader("最终结果")
    with st.container(key="fcff_big"):
        st.metric(
            "FCFF（企业自由现金流，万元）",
            fmt(result["fcff"]),
            delta=f"较 NOPAT {result['fcff'] - result['nopat']:+,.2f} 万元",
        )

    st.subheader("智能诊断")
    fcff, nopat = result["fcff"], result["nopat"]
    capex, da, dnwc = result["capex"], result["da"], result["dnwc"]

    if fcff > 0:
        st.success("企业创造了正向的自由现金流，具备造血能力。")
    else:
        st.error(
            "警告：自由现金流为负，企业可能面临资金链断裂风险或正在进行重资产扩张，"
            "需关注融资压力。"
        )

    if capex > da:
        st.warning("企业处于产能扩张期，需关注未来转化。")

    if nopat > 0:
        if dnwc > 0.3 * nopat:
            st.error("企业可能面临较大的营运资金压力。")
            st.caption(f"ΔNWC 相当于 NOPAT 的 {dnwc / nopat:.1%}，已超过 30% 警戒线。")
        else:
            st.caption(f"ΔNWC 相当于 NOPAT 的 {dnwc / nopat:.1%}，处于安全区间。")
    elif dnwc > 0:
        st.error("企业可能面临较大的营运资金压力。")


# ===========================================================================
# 三、杠杆与风险
# ===========================================================================
DOL_WARNING = (
    "【⚠️ 经营风险预警】固定成本过高。一旦市场销量下滑，利润将面临断崖式下跌。"
    "建议优化成本结构。"
)
DFL_WARNING = "【🚨 财务风险预警】债务负担沉重。高额利息正在吞噬利润，警惕资金链断裂。"
DTL_WARNING = (
    "【💣 双重暴雷预警】经营与财务双重高杠杆叠加，企业极其脆弱，"
    "任何宏观波动都可能导致破产。"
)
LEVERAGE_SAFE = "【✅ 风险可控】企业杠杆水平健康，具备良好的抗风险能力。"


def calc_leverage(
    revenue: float, variable_cost: float, fixed_cost: float, interest: float, tax_pct: float
) -> dict:
    """边际贡献、EBIT 与 DOL / DFL / DTL。"""
    contribution = revenue - variable_cost
    ebit = contribution - fixed_cost

    dol = contribution / ebit if ebit != 0 else None
    denominator = ebit - interest
    dfl = ebit / denominator if denominator != 0 else None
    dtl = dol * dfl if (dol is not None and dfl is not None) else None

    return {
        "revenue": revenue,
        "variable_cost": variable_cost,
        "contribution": contribution,
        "fixed_cost": fixed_cost,
        "ebit": ebit,
        "interest": interest,
        "pretax_profit": denominator,
        "tax_pct": tax_pct,
        "after_tax_profit": denominator * (1.0 - tax_pct / 100.0),
        "dol": dol,
        "dfl": dfl,
        "dtl": dtl,
    }


def render_leverage_result(result: dict, current_inputs: tuple) -> None:
    """杠杆指标、诊断、推导与通俗解释。"""
    if result["inputs"] != current_inputs:
        st.warning("参数已修改，下方结果仍是上一次计算的，请重新生成。")

    dol, dfl, dtl = result["dol"], result["dfl"], result["dtl"]
    ebit, interest = result["ebit"], result["interest"]

    st.subheader("杠杆系数")
    c1, c2, c3 = st.columns(3)
    c1.metric("DOL 经营杠杆", fmt_ratio(dol), help="销售每变动 1%，EBIT 变动的百分比。")
    c2.metric("DFL 财务杠杆", fmt_ratio(dfl), help="EBIT 每变动 1%，净利润变动的百分比。")
    c3.metric("DTL 联合杠杆", fmt_ratio(dtl), help="销售每变动 1%，净利润变动的百分比。")

    st.caption(
        f"边际贡献 {fmt(result['contribution'])} 万元，EBIT {fmt(ebit)} 万元，"
        f"利息费用 {fmt(interest)} 万元。"
    )

    st.subheader("智能诊断")
    warnings: list[str] = []
    errors: list[str] = []

    if dol is None:
        errors.append("EBIT 为 0，DOL 无法计算（分母为 0），请检查成本结构。")
    elif dol < 0:
        errors.append("EBIT 为负，经营杠杆为负值，说明收入不足以覆盖固定成本与变动成本。")
    elif dol > 3:
        warnings.append(DOL_WARNING)

    if dfl is None:
        errors.append("EBIT 等于利息费用，DFL 无法计算（分母为 0），企业处于盈亏临界点。")
    elif ebit < interest:
        errors.append(
            "企业已陷入财务困境，DFL 为负：利息支出已超过息税前利润，"
            "需尽快改善资本结构或压缩债务。"
        )
    elif dfl > 2:
        errors.append(DFL_WARNING)

    if dtl is not None and dtl > 5:
        errors.append(DTL_WARNING)

    for text in warnings:
        st.warning(text)
    for text in errors:
        st.error(text)

    safe = (
        dol is not None and dfl is not None and dtl is not None
        and ebit > 0 and ebit > interest
        and dol <= 3 and dfl <= 2 and dtl <= 5
    )
    if safe:
        st.success(LEVERAGE_SAFE)

    with st.expander("查看杠杆推导明细", expanded=False):
        rows = [
            {"项目": "营业收入", "金额（万元）": fmt(result["revenue"])},
            {"项目": "减：变动成本", "金额（万元）": fmt(result["variable_cost"])},
            {"项目": "边际贡献", "金额（万元）": fmt(result["contribution"])},
            {"项目": "减：固定成本（不含利息）", "金额（万元）": fmt(result["fixed_cost"])},
            {"项目": "EBIT", "金额（万元）": fmt(ebit)},
            {"项目": "减：利息费用", "金额（万元）": fmt(interest)},
            {"项目": "税前利润", "金额（万元）": fmt(result["pretax_profit"])},
            {"项目": "税后利润", "金额（万元）": fmt(result["after_tax_profit"])},
        ]
        st.dataframe(pd.DataFrame(rows), hide_index=True)

    st.subheader("这三个指标是什么意思？")
    st.markdown(
        f"""
        <div class="explain">
            <h4>DOL · 经营杠杆（当前 {fmt_ratio(dol)}）</h4>
            <p>销售每变动 1%，EBIT 会变动 DOL%。固定成本越高、DOL 越大，
            销量下滑时利润跌得越狠，反映“经营风险”。</p>
        </div>
        <div class="explain">
            <h4>DFL · 财务杠杆（当前 {fmt_ratio(dfl)}）</h4>
            <p>EBIT 每变动 1%，净利润会变动 DFL%。利息越高、DFL 越大；
            一旦 EBIT 跌破利息，DFL 转负，企业进入“赚的钱不够付利息”的困境。</p>
        </div>
        <div class="explain">
            <h4>DTL · 联合杠杆（当前 {fmt_ratio(dtl)}）</h4>
            <p>DOL 与 DFL 的乘积：销售每变动 1%，净利润会变动 DTL%。
            它把经营风险与财务风险叠加，DTL 越高，周期下行时越脆弱。</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.caption("杠杆系数为税前口径；所得税率仅用于推导明细中的税后利润。")


# ===========================================================================
# 四、杜邦与盈利能力
# ===========================================================================
def calc_dupont_a(
    profit: float,
    revenue: float,
    avg_assets: float,
    avg_equity: float,
    gross_margin_pct: float,
    net_margin_pct: float,
) -> dict:
    """模式 A：二手指标计算杜邦分解。"""
    net_margin = profit / revenue if revenue else net_margin_pct / 100.0
    turnover = safe_div(revenue, avg_assets)
    multiplier = safe_div(avg_assets, avg_equity)
    roe = (
        net_margin * turnover * multiplier
        if (turnover is not None and multiplier is not None)
        else None
    )
    return {
        "mode": MODE_A,
        "gross_margin": gross_margin_pct / 100.0,
        "net_margin": net_margin,
        "net_margin_input": net_margin_pct / 100.0,
        "turnover": turnover,
        "multiplier": multiplier,
        "roe": roe,
    }


def render_dupont_chain(nm, turnover, multiplier, roe) -> None:
    """ROE 拆解链路图：净利率 × 周转率 × 权益乘数 = ROE。"""
    st.markdown(
        f"""
        <div class="chain">
            <div class="node"><div class="k">净利率</div><div class="v">{fmt_pct(nm)}</div></div>
            <div class="op">×</div>
            <div class="node"><div class="k">总资产周转率</div><div class="v">{fmt_ratio(turnover)}</div></div>
            <div class="op">×</div>
            <div class="node"><div class="k">权益乘数</div><div class="v">{fmt_ratio(multiplier)}</div></div>
            <div class="op">=</div>
            <div class="node result"><div class="k">ROE</div><div class="v">{fmt_pct(roe)}</div></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_dupont_result(result: dict, current_inputs=None) -> None:
    """杜邦指标、链路图、诊断与驱动标签。"""
    if current_inputs is not None and result.get("inputs") != current_inputs:
        st.warning("参数已修改，下方结果仍是上一次计算的，请重新生成。")

    gm, nm = result["gross_margin"], result["net_margin"]
    turnover, multiplier, roe = result["turnover"], result["multiplier"], result["roe"]

    st.subheader("杜邦分解结果")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("毛利率", fmt_pct(gm))
    c2.metric("净利率", fmt_pct(nm))
    c3.metric("总资产周转率", fmt_ratio(turnover))
    c4.metric("权益乘数", fmt_ratio(multiplier))
    c5.metric("ROE（杜邦）", fmt_pct(roe))

    render_dupont_chain(nm, turnover, multiplier, roe)

    if (
        result.get("net_margin_input") is not None
        and nm is not None
        and abs(result["net_margin_input"] - nm) > 0.005
    ):
        st.caption(
            f"提示：您填写的净利率为 {result['net_margin_input']:.2%}，"
            f"与「净利润 ÷ 营业收入」计算的 {nm:.2%} 有差异，ROE 按计算值推导。"
        )

    st.subheader("智能诊断")
    if roe is None:
        st.error("关键分母为 0，无法计算 ROE，请检查平均总资产或平均股东权益。")
        return

    if roe > 0.15:
        drivers: list[str] = []
        if nm is not None and nm >= 0.10:
            drivers.append("高净利率驱动")
        if turnover is not None and turnover >= 0.80:
            drivers.append("高周转驱动")
        if multiplier is not None and multiplier >= 2.50:
            drivers.append("高杠杆驱动")
        if not drivers:
            drivers.append("均衡驱动")

        st.success(f"ROE {roe:.2%} > 15%，盈利能力优秀。")
        st.markdown("驱动标签：" + "　".join(f"`{tag}`" for tag in drivers))
        st.caption(
            "判定参考：净利率 ≥ 10% 视为高利润率；总资产周转率 ≥ 0.8 视为高周转；"
            "权益乘数 ≥ 2.5 视为高杠杆。标签可能同时命中多个。"
        )
    else:
        st.warning(f"ROE {roe:.2%} ≤ 15%，盈利能力一般，建议从净利率、周转或资本结构找改进空间。")


# ===========================================================================
# 五、营运与偿债能力
# ===========================================================================
def calc_ops_b(
    current_assets: float,
    inventory: float,
    current_liabilities: float,
    receivables_avg: float,
    revenue: float,
    cogs: float,
    total_liabilities: float,
    total_assets: float,
) -> dict:
    """模式 B：由指标池参数计算营运与偿债指标。"""
    return {
        "mode": MODE_B,
        "current_ratio": safe_div(current_assets, current_liabilities),
        "quick_ratio": safe_div(current_assets - inventory, current_liabilities),
        "inventory_turnover": safe_div(cogs, inventory),
        "receivable_turnover": safe_div(revenue, receivables_avg),
        "debt_ratio": safe_div(total_liabilities, total_assets),
    }


def render_ops_result(result: dict, current_inputs=None) -> None:
    """营运与偿债指标、红绿灯诊断。"""
    if current_inputs is not None and result.get("inputs") != current_inputs:
        st.warning("参数已修改，下方结果仍是上一次计算的，请重新生成。")

    cr = result["current_ratio"]
    qr = result["quick_ratio"]
    inv = result["inventory_turnover"]
    ar = result["receivable_turnover"]
    debt = result["debt_ratio"]

    st.subheader("营运与偿债指标")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("流动比率", fmt_ratio(cr))
    c2.metric("速动比率", fmt_ratio(qr))
    c3.metric("存货周转率", fmt_ratio(inv))
    c4.metric("应收账款周转率", fmt_ratio(ar))
    c5.metric("资产负债率", fmt_pct(debt))

    # 红绿灯徽章
    badges = []
    badges.append(
        f'<span class="badge {"ok" if cr is not None and cr >= 1 else "bad"}">'
        f'流动比率 {fmt_ratio(cr)}</span>'
    )
    badges.append(
        f'<span class="badge {"ok" if debt is not None and debt <= 0.6 else "warn"}">'
        f'负债率 {fmt_pct(debt)}</span>'
    )
    badges.append(
        f'<span class="badge {"ok" if inv is not None and inv >= 3 else "warn"}">'
        f'存货周转 {fmt_ratio(inv)}</span>'
    )
    badges.append(
        f'<span class="badge {"ok" if ar is not None and ar >= 3 else "warn"}">'
        f'应收周转 {fmt_ratio(ar)}</span>'
    )
    st.markdown("".join(badges), unsafe_allow_html=True)

    if result.get("mode") == MODE_B:
        st.caption("周转率按平均余额（期初+期末）/2 计算；资产负债率按期末数计算。")

    st.subheader("智能诊断")
    triggered = False

    if cr is not None and cr < 1:
        st.error("短期偿债风险极高，可能面临资金链断裂")
        triggered = True

    if debt is not None and debt > 0.60:
        st.warning("杠杆偏高，需关注债务结构")
        triggered = True

    if (inv is not None and inv < 3) or (ar is not None and ar < 3):
        st.warning("营运资金占用过大，警惕坏账或滞销")
        triggered = True

    if not triggered:
        st.success("营运与偿债指标处于安全区间。")


# ===========================================================================
# 六、侧边栏：四表输入（模式 B）
# ===========================================================================
def render_mode_b_sidebar() -> dict:
    """渲染四表折叠面板，返回原始输入字典（不含 inputs 快照）。"""
    with st.expander("📄 利润表（核心科目）", expanded=True):
        revenue = st.number_input("营业收入", min_value=0.0, value=5000.0, step=100.0, format="%.2f", key="b_revenue")
        cogs = st.number_input("营业成本", min_value=0.0, value=3500.0, step=100.0, format="%.2f", key="b_cogs")
        surcharges = st.number_input("税金及附加", min_value=0.0, value=50.0, step=10.0, format="%.2f", key="b_surcharges")
        selling = st.number_input("销售费用", min_value=0.0, value=300.0, step=10.0, format="%.2f", key="b_selling")
        admin = st.number_input("管理费用", min_value=0.0, value=200.0, step=10.0, format="%.2f", key="b_admin")
        rnd = st.number_input("研发费用", min_value=0.0, value=100.0, step=10.0, format="%.2f", key="b_rnd")
        interest = st.number_input("财务费用-利息费用", min_value=0.0, value=100.0, step=10.0, format="%.2f", key="b_interest")
        nonop_income = st.number_input("营业外收入", min_value=0.0, value=0.0, step=10.0, format="%.2f", key="b_nonop_income")
        nonop_expense = st.number_input("营业外支出", min_value=0.0, value=0.0, step=10.0, format="%.2f", key="b_nonop_expense")
        income_tax = st.number_input("所得税费用", min_value=0.0, value=187.5, step=10.0, format="%.2f", key="b_income_tax")
        st.caption("补充：用于杠杆分析的成本拆分")
        variable_cost = st.number_input("变动成本（补充）", min_value=0.0, value=3000.0, step=100.0, format="%.2f", key="b_variable_cost")
        fixed_cost = st.number_input("固定成本（不含利息，补充）", min_value=0.0, value=1200.0, step=50.0, format="%.2f", key="b_fixed_cost")

    with st.expander("📊 资产负债表（关键科目）", expanded=False):
        ar_beg = st.number_input("应收账款（期初）", min_value=0.0, value=400.0, step=50.0, format="%.2f", key="b_ar_beg")
        ar_end = st.number_input("应收账款（期末）", min_value=0.0, value=500.0, step=50.0, format="%.2f", key="b_ar_end")
        inv_beg = st.number_input("存货（期初）", min_value=0.0, value=700.0, step=50.0, format="%.2f", key="b_inv_beg")
        inv_end = st.number_input("存货（期末）", min_value=0.0, value=800.0, step=50.0, format="%.2f", key="b_inv_end")
        ca_beg = st.number_input("流动资产合计（期初）", min_value=0.0, value=2800.0, step=100.0, format="%.2f", key="b_ca_beg")
        ca_end = st.number_input("流动资产合计（期末）", min_value=0.0, value=3000.0, step=100.0, format="%.2f", key="b_ca_end")
        cl_beg = st.number_input("流动负债合计（期初）", min_value=0.0, value=1900.0, step=100.0, format="%.2f", key="b_cl_beg")
        cl_end = st.number_input("流动负债合计（期末）", min_value=0.0, value=2000.0, step=100.0, format="%.2f", key="b_cl_end")
        fixed_assets = st.number_input("固定资产", min_value=0.0, value=1500.0, step=100.0, format="%.2f", key="b_fixed_assets")
        assets_beg = st.number_input("总资产（期初）", min_value=0.0, value=4000.0, step=100.0, format="%.2f", key="b_assets_beg")
        assets_end = st.number_input("总资产（期末）", min_value=0.0, value=4200.0, step=100.0, format="%.2f", key="b_assets_end")
        total_liabilities = st.number_input("总负债", min_value=0.0, value=2150.0, step=100.0, format="%.2f", key="b_total_liabilities")
        equity = st.number_input("所有者权益", min_value=0.0, value=2050.0, step=100.0, format="%.2f", key="b_equity")

    with st.expander("💵 现金流量表（投资与经营）", expanded=False):
        cfo = st.number_input("经营活动产生的现金流量净额（CFO）", value=600.0, step=50.0, format="%.2f", key="b_cfo")
        capex_paid = st.number_input("购建长期资产支付的现金", min_value=0.0, value=400.0, step=20.0, format="%.2f", key="b_capex_paid")
        disposal = st.number_input("处置长期资产收回的现金净额", min_value=0.0, value=50.0, step=10.0, format="%.2f", key="b_disposal")

    with st.expander("📝 财务报表附注", expanded=False):
        da = st.number_input("折旧与摊销（D&A）总额", min_value=0.0, value=300.0, step=20.0, format="%.2f", key="b_da")

    return {
        "revenue": revenue, "cogs": cogs, "surcharges": surcharges,
        "selling": selling, "admin": admin, "rnd": rnd,
        "interest": interest,
        "nonop_income": nonop_income, "nonop_expense": nonop_expense,
        "income_tax": income_tax,
        "variable_cost": variable_cost, "fixed_cost": fixed_cost,
        "ar_beg": ar_beg, "ar_end": ar_end,
        "inv_beg": inv_beg, "inv_end": inv_end,
        "ca_beg": ca_beg, "ca_end": ca_end,
        "cl_beg": cl_beg, "cl_end": cl_end,
        "fixed_assets": fixed_assets,
        "assets_beg": assets_beg, "assets_end": assets_end,
        "total_liabilities": total_liabilities, "equity": equity,
        "cfo": cfo, "capex_paid": capex_paid, "disposal": disposal,
        "da": da,
    }


# ===========================================================================
# 七、主程序
# ===========================================================================
def main() -> None:
    render_hero()

    with st.sidebar:
        st.header("输入模式")
        input_mode = st.radio(
            "选择输入模式",
            [MODE_A, MODE_B],
            index=1,
            key="global_mode",
            help="模式 A 直接输入指标；模式 B 输入四表原始科目，由系统自动换算。",
        )
        st.divider()

        if input_mode == MODE_B:
            st.header("四表原始数据")
            st.caption("金额单位：万元；点击折叠面板录入")
            raw = render_mode_b_sidebar()
            pool_submitted = st.button("生成指标池 / 更新结果", type="primary")

            current_inputs = (
                raw["revenue"], raw["cogs"], raw["surcharges"],
                raw["selling"], raw["admin"], raw["rnd"],
                raw["interest"], raw["nonop_income"], raw["nonop_expense"],
                raw["income_tax"], raw["variable_cost"], raw["fixed_cost"],
                raw["ar_beg"], raw["ar_end"], raw["inv_beg"], raw["inv_end"],
                raw["ca_beg"], raw["ca_end"], raw["cl_beg"], raw["cl_end"],
                raw["fixed_assets"], raw["assets_beg"], raw["assets_end"],
                raw["total_liabilities"], raw["equity"],
                raw["cfo"], raw["capex_paid"], raw["disposal"], raw["da"],
            )
            raw["inputs"] = current_inputs

            if pool_submitted:
                try:
                    st.session_state["v6_pool"] = build_pool(raw)
                except (ValueError, ZeroDivisionError) as exc:
                    st.sidebar.error(f"指标池生成失败：{exc}")
                except Exception as exc:  # 兜底，避免整页崩溃
                    st.sidebar.error(f"指标池生成异常：{exc}")
        else:
            st.header("核心估值参数")
            st.caption("二手指标 · 金额单位：万元")
            ebit = st.number_input("核心经营利润 EBIT（万元）", value=1000.0, step=50.0, format="%.2f")
            tax_pct = st.number_input("所得税率（%）", min_value=0.0, max_value=100.0, value=25.0, step=1.0)
            da_a = st.number_input("折旧与摊销 D&A（万元）", min_value=0.0, value=100.0, step=10.0, format="%.2f")
            capex_a = st.number_input("资本性支出 CapEx（万元）", min_value=0.0, value=120.0, step=10.0, format="%.2f")
            dnwc_a = st.number_input("营运资本增加额 ΔNWC（万元，可为负）", value=30.0, step=5.0, format="%.2f")
            fcff_submitted = st.button("计算 FCFF", type="primary")

            st.divider()
            st.header("杠杆与风险参数")
            lev_revenue = st.number_input("营业收入（杠杆模块）", min_value=0.0, value=5000.0, step=100.0, format="%.2f")
            cost_mode = st.radio("变动成本录入方式", ["按金额（万元）", "按收入占比（%）"], horizontal=True)
            if cost_mode.startswith("按金额"):
                variable_cost_a = st.number_input("变动成本（万元）", min_value=0.0, value=3000.0, step=100.0, format="%.2f")
                variable_rate = None
            else:
                variable_rate = st.number_input("变动成本率（%）", min_value=0.0, max_value=100.0, value=60.0, step=1.0)
                variable_cost_a = lev_revenue * variable_rate / 100.0
            fixed_cost_a = st.number_input("固定成本（不含利息，万元）", min_value=0.0, value=1200.0, step=50.0, format="%.2f")
            interest_a = st.number_input("利息费用（万元）", min_value=0.0, value=100.0, step=10.0, format="%.2f")
            lev_tax_pct = st.number_input("所得税率（杠杆模块，%）", min_value=0.0, max_value=100.0, value=25.0, step=1.0)
            lev_submitted = st.button("计算杠杆")

    # ---------------- 模式 B ----------------
    if input_mode == MODE_B:
        pool = st.session_state.get("v6_pool")
        if pool is None:
            tab_fcff, tab_lev, tab_dupont, tab_ops = st.tabs(
                ["1. 全景估值 FCFF", "2. 杠杆与经营风险", "3. 杜邦与盈利能力", "4. 营运与偿债能力"]
            )
            with tab_fcff:
                st.info("👈 请在左侧四个折叠面板录入四表数据，然后点击「生成指标池 / 更新结果」。")
            with tab_lev:
                st.info("指标池生成后，这里会展示 DOL / DFL / DTL。")
            with tab_dupont:
                st.info("指标池生成后，这里会展示 ROE 杜邦拆解链路。")
            with tab_ops:
                st.info("指标池生成后，这里会展示流动比率、周转率与红绿灯诊断。")
            return

        pool_inputs = pool["inputs"]

        fcff_result = {
            "mode": MODE_B,
            "inputs": pool_inputs,
            "revenue": pool["revenue"],
            "cogs": pool["cogs"],
            "surcharges": pool["surcharges"],
            "opex": pool["period_expenses"],
            "non_operating": pool["nonop_net"],
            "tax_pct": 25.0,
            "da": pool["da"],
            "capex_paid": pool["capex_paid"],
            "disposal": pool["disposal"],
            "ca_increase": pool["ca_end"] - pool["ca_beg"],
            "cl_increase": pool["cl_end"] - pool["cl_beg"],
            "ebit": pool["ebit"],
            "nopat": pool["nopat"],
            "capex": pool["capex"],
            "dnwc": pool["dnwc"],
            "fcff": pool["fcff"],
        }

        lev_pool = calc_leverage(
            pool["revenue"], pool["variable_cost"], pool["fixed_cost"], pool["interest"], 25.0
        )
        lev_pool["inputs"] = pool_inputs

        dupont_pool = {
            "mode": MODE_B,
            "inputs": pool_inputs,
            "gross_margin": pool["gross_margin"],
            "net_margin": pool["net_margin"],
            "net_margin_input": None,
            "turnover": pool["asset_turnover"],
            "multiplier": pool["equity_multiplier"],
            "roe": pool["roe"],
        }

        ops_pool = {
            "mode": MODE_B,
            "inputs": pool_inputs,
            "current_ratio": pool["current_ratio"],
            "quick_ratio": pool["quick_ratio"],
            "inventory_turnover": pool["inventory_turnover"],
            "receivable_turnover": pool["receivable_turnover"],
            "debt_ratio": pool["debt_ratio"],
        }

        tab_fcff, tab_lev, tab_dupont, tab_ops = st.tabs(
            ["1. 全景估值 FCFF", "2. 杠杆与经营风险", "3. 杜邦与盈利能力", "4. 营运与偿债能力"]
        )

        with tab_fcff:
            render_fcff_result(fcff_result, pool_inputs)
            if pool["effective_tax_rate"] is not None and abs(pool["effective_tax_rate"] - 0.25) > 0.01:
                st.caption(
                    f"注：报表所得税费用对应有效税率 {pool['effective_tax_rate']:.2%}，"
                    "本模型按 25% 法定税率计算净利润与 NOPAT。"
                )

        with tab_lev:
            render_leverage_result(lev_pool, pool_inputs)

        with tab_dupont:
            render_dupont_result(dupont_pool, pool_inputs)
            st.caption("净利润按 25% 法定税率计算；平均权益取自资产负债表所有者权益。")

        with tab_ops:
            render_ops_result(ops_pool, pool_inputs)

        with st.expander("查看指标池（后台自动换算结果）", expanded=False):
            rows = [
                {"指标": "核心 EBIT", "数值": fmt(pool["ebit"])},
                {"指标": "NOPAT", "数值": fmt(pool["nopat"])},
                {"指标": "净利润", "数值": fmt(pool["net_profit"])},
                {"指标": "真实 CapEx", "数值": fmt(pool["capex"])},
                {"指标": "ΔNWC", "数值": fmt(pool["dnwc"])},
                {"指标": "FCFF", "数值": fmt(pool["fcff"])},
                {"指标": "毛利率", "数值": fmt_pct(pool["gross_margin"])},
                {"指标": "净利率", "数值": fmt_pct(pool["net_margin"])},
                {"指标": "ROE", "数值": fmt_pct(pool["roe"])},
                {"指标": "流动比率", "数值": fmt_ratio(pool["current_ratio"])},
                {"指标": "资产负债率", "数值": fmt_pct(pool["debt_ratio"])},
            ]
            st.dataframe(pd.DataFrame(rows), hide_index=True)
        return

    # ---------------- 模式 A ----------------
    fcff_inputs = (float(ebit), float(tax_pct), float(da_a), float(capex_a), float(dnwc_a))
    fcff_results = st.session_state.setdefault("v6_fcff_a", {})

    if fcff_submitted:
        result = calc_mode_a(
            ebit=float(ebit), tax_pct=float(tax_pct), da=float(da_a),
            capex=float(capex_a), dnwc=float(dnwc_a),
        )
        result["inputs"] = fcff_inputs
        fcff_results[MODE_A] = result

    lev_inputs = (
        float(lev_revenue), float(variable_cost_a), float(fixed_cost_a),
        float(interest_a), float(lev_tax_pct),
        0.0 if variable_rate is None else float(variable_rate),
    )
    if lev_submitted:
        if lev_revenue <= 0:
            st.error("营业收入应大于 0，请检查杠杆模块输入。")
        else:
            lev_result = calc_leverage(
                revenue=float(lev_revenue), variable_cost=float(variable_cost_a),
                fixed_cost=float(fixed_cost_a), interest=float(interest_a),
                tax_pct=float(lev_tax_pct),
            )
            lev_result["inputs"] = lev_inputs
            st.session_state["v6_leverage_a"] = lev_result

    tab_fcff, tab_lev, tab_dupont, tab_ops = st.tabs(
        ["1. 全景估值 FCFF", "2. 杠杆与经营风险", "3. 杜邦与盈利能力", "4. 营运与偿债能力"]
    )

    with tab_fcff:
        result = fcff_results.get(MODE_A)
        if result is None:
            render_fcff_empty(MODE_A)
        else:
            render_fcff_result(result, fcff_inputs)

    with tab_lev:
        lev_result = st.session_state.get("v6_leverage_a")
        if lev_result is None:
            st.info("👈 在左侧「杠杆与风险参数」中录入数据，然后点击「计算杠杆」。")
        else:
            render_leverage_result(lev_result, lev_inputs)

    with tab_dupont:
        st.subheader("杜邦分析输入")
        d1, d2, d3 = st.columns(3)
        with d1:
            dup_profit = st.number_input("净利润（万元）", value=450.0, step=50.0, format="%.2f", key="dup_profit")
            dup_revenue = st.number_input("营业收入（万元）", value=5000.0, step=100.0, format="%.2f", key="dup_rev")
        with d2:
            dup_assets = st.number_input("平均总资产（万元）", value=4100.0, step=100.0, format="%.2f", key="dup_assets")
            dup_equity = st.number_input("平均股东权益（万元）", value=2050.0, step=100.0, format="%.2f", key="dup_equity")
        with d3:
            dup_gm_pct = st.number_input("毛利率（%）", min_value=-100.0, max_value=100.0, value=30.0, step=1.0, key="dup_gm")
            dup_nm_pct = st.number_input("净利率（%）", min_value=-100.0, max_value=100.0, value=9.0, step=1.0, key="dup_nm")

        dup_submitted = st.button("计算杜邦分析", key="dup_btn")
        dupont_results = st.session_state.setdefault("v6_dupont_a", {})
        if dup_submitted:
            dup_inputs = (
                float(dup_profit), float(dup_revenue), float(dup_assets),
                float(dup_equity), float(dup_gm_pct), float(dup_nm_pct),
            )
            dup_result = calc_dupont_a(
                profit=float(dup_profit), revenue=float(dup_revenue),
                avg_assets=float(dup_assets), avg_equity=float(dup_equity),
                gross_margin_pct=float(dup_gm_pct),
                net_margin_pct=float(dup_nm_pct),
            )
            dup_result["inputs"] = dup_inputs
            dupont_results[MODE_A] = dup_result

        dup_result = dupont_results.get(MODE_A)
        if dup_result is None:
            st.info("填写上方数据后点击「计算杜邦分析」。")
        else:
            render_dupont_result(dup_result, dup_result["inputs"])

    with tab_ops:
        st.subheader("营运与偿债输入")
        o1, o2, o3 = st.columns(3)
        with o1:
            ops_cr = st.number_input("流动比率", min_value=0.0, value=1.5, step=0.1, format="%.2f", key="ops_cr")
            ops_qr = st.number_input("速动比率", min_value=0.0, value=1.1, step=0.1, format="%.2f", key="ops_qr")
        with o2:
            ops_inv = st.number_input("存货周转率（次）", min_value=0.0, value=4.4, step=0.1, format="%.2f", key="ops_inv")
            ops_ar = st.number_input("应收账款周转率（次）", min_value=0.0, value=10.0, step=0.1, format="%.2f", key="ops_ar")
        with o3:
            ops_debt_pct = st.number_input("资产负债率（%）", min_value=0.0, max_value=100.0, value=60.0, step=1.0, key="ops_debt")

        ops_submitted = st.button("计算营运与偿债指标", key="ops_btn")
        ops_results = st.session_state.setdefault("v6_ops_a", {})
        if ops_submitted:
            ops_inputs = (
                float(ops_cr), float(ops_qr), float(ops_inv),
                float(ops_ar), float(ops_debt_pct),
            )
            ops_result = {
                "mode": MODE_A,
                "inputs": ops_inputs,
                "current_ratio": float(ops_cr),
                "quick_ratio": float(ops_qr),
                "inventory_turnover": float(ops_inv),
                "receivable_turnover": float(ops_ar),
                "debt_ratio": float(ops_debt_pct) / 100.0,
            }
            ops_results[MODE_A] = ops_result

        ops_result = ops_results.get(MODE_A)
        if ops_result is None:
            st.info("填写上方数据后点击「计算营运与偿债指标」。")
        else:
            render_ops_result(ops_result, ops_result["inputs"])


if __name__ == "__main__":
    main()
