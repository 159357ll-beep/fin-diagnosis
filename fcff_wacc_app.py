# -*- coding: utf-8 -*-
"""
企业价值评估工作台（Streamlit Web 版）
===========================================================================
把已有的 FCFF 折现估值脚本与新增的 WACC 计算器整合进同一个应用，
用 st.tabs 分成两个功能模块：

    模块一「FCFF 估值」  ：输入假设 → 逐年 FCFF、折现、终值 → 企业价值 EV，
                          并可直接下载 Excel 结果；
    模块二「WACC 计算器」：输入 Rf / MRP / βu / 目标资本结构 / Rd / T，
                          重新加杠杆得到 βl → CAPM 算 Ke → 税后债务成本
                          → 加权得到 WACC，并用图表展示权重与成本率。

启动方式（在本文件所在目录执行）：
    streamlit run fcff_wacc_app.py

依赖：
    streamlit >= 1.30、pandas、openpyxl
    FCFF 的计算逻辑复用同目录下的 fcff_dcf_valuation.py，不重复实现。
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from fcff_dcf_valuation import Assumptions, excel_bytes, run_valuation


# ===========================================================================
# 页面基础配置
# ===========================================================================
st.set_page_config(
    page_title="企业价值评估工作台",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# 自定义 CSS：让 WACC 结果用大号字体突出显示
st.markdown(
    """
    <style>
    .wacc-card {
        background: linear-gradient(135deg, #eef4ff 0%, #dbe7ff 100%);
        border: 1px solid #c7d7f5;
        border-radius: 14px;
        padding: 22px 28px 16px 28px;
        text-align: center;
        margin: 6px 0 18px 0;
    }
    .wacc-card .label {
        font-size: 15px;
        color: #4a5a75;
        letter-spacing: 2px;
    }
    .wacc-card .value {
        font-size: 58px;
        font-weight: 800;
        color: #123f7c;
        line-height: 1.15;
        margin: 4px 0;
    }
    .wacc-card .formula {
        font-size: 13px;
        color: #5b6b85;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ===========================================================================
# 通用小工具
# ===========================================================================
def _apply_wacc_to_fcff() -> None:
    """回调：把 WACC 计算器的结果写回 FCFF 模块的 WACC 输入框。

    放在 on_click 回调里执行，能在脚本重新运行之前修改 session_state，
    从而绕开「控件实例化后不能再改状态」的限制。
    """
    result = st.session_state.get("wacc_result")
    if result:
        st.session_state["fcff_wacc"] = round(result["wacc"] * 100, 2)


# ===========================================================================
# 模块一：FCFF 两阶段折现估值
# ===========================================================================
def render_fcff_tab() -> None:
    """第一个标签页：复用 fcff_dcf_valuation.py 的计算引擎，结果用表格展示。"""
    st.subheader("FCFF 两阶段折现估值")
    st.caption(
        "FCFF = EBIT×(1−税率) + 折旧摊销 − 资本性支出 − 营运资本增加；"
        "EV = Σ FCFF_t/(1+WACC)^t + TV_n/(1+WACC)^n，其中 TV_n = FCFF_n×(1+g)/(WACC−g)"
    )

    # 首次进入时给 WACC 输入框一个默认值（后续可被 WACC 计算器回填）
    if "fcff_wacc" not in st.session_state:
        st.session_state["fcff_wacc"] = 10.0

    # ---------------- 输入区：三组参数 ----------------
    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("**① 盈利假设**")
        ebit = st.number_input(
            "基期 EBIT（万元）", min_value=0.0, value=1000.0, step=50.0, format="%.2f"
        )
        growth = st.number_input(
            "EBIT 年增长率（%）", min_value=-50.0, max_value=100.0, value=5.0, step=0.5
        )
        tax = st.number_input(
            "企业所得税率（%）", min_value=0.0, max_value=100.0, value=25.0, step=1.0
        )

    with col2:
        st.markdown("**② 现金流结构（占 EBIT 的比例）**")
        da = st.number_input(
            "折旧摊销 / EBIT（%）", min_value=0.0, max_value=50.0, value=10.0, step=0.5
        )
        capex = st.number_input(
            "资本性支出 / EBIT（%）", min_value=0.0, max_value=100.0, value=12.0, step=0.5
        )
        nwc = st.number_input(
            "营运资本增加 / EBIT（%）", min_value=0.0, max_value=50.0, value=3.0, step=0.5
        )

    with col3:
        st.markdown("**③ 折现与永续期**")
        wacc_pct = st.number_input(
            "WACC（%）", min_value=0.1, max_value=50.0, step=0.1, key="fcff_wacc"
        )
        terminal_growth = st.number_input(
            "永续增长率 g（%）", min_value=-5.0, max_value=10.0, value=2.0, step=0.1
        )
        years = st.number_input(
            "预测期（年）", min_value=1, max_value=15, value=5, step=1
        )

    # ---------------- 计算：参数非法时给出友好提示 ----------------
    try:
        assumptions = Assumptions(
            ebit_base=float(ebit),
            ebit_growth=growth / 100.0,
            tax_rate=tax / 100.0,
            da_ratio=da / 100.0,
            capex_ratio=capex / 100.0,
            nwc_ratio=nwc / 100.0,
            wacc=wacc_pct / 100.0,
            terminal_growth=terminal_growth / 100.0,
            forecast_years=int(years),
        )
        valuation = run_valuation(assumptions)
    except ValueError as exc:
        st.error(f"参数校验未通过：{exc}")
        return

    ev = valuation.enterprise_value

    # ---------------- 关键结果 ----------------
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("企业价值 EV（万元）", f"{ev:,.2f}")
    m2.metric("预测期现值（万元）", f"{valuation.pv_explicit:,.2f}")
    m3.metric("终值现值（万元）", f"{valuation.pv_terminal:,.2f}")
    m4.metric("终值占 EV 比重", f"{valuation.pv_terminal / ev:.1%}")

    # ---------------- 预测期明细表 ----------------
    st.markdown("**预测期明细（单位：万元）**")
    table = pd.DataFrame(
        [
            {
                "年份": f"第 {r.year} 年",
                "EBIT": f"{r.ebit:,.2f}",
                "EBIT×(1-t)": f"{r.nopat:,.2f}",
                "折旧摊销": f"{r.da:,.2f}",
                "资本性支出": f"{r.capex:,.2f}",
                "营运资本增加": f"{r.nwc_increase:,.2f}",
                "FCFF": f"{r.fcff:,.2f}",
                "折现因子": f"{r.discount_factor:.4f}",
                "现值 PV": f"{r.pv:,.2f}",
            }
            for r in valuation.rows
        ]
    )
    st.dataframe(table, hide_index=True)

    # ---------------- 终值与 Excel 导出 ----------------
    with st.expander("查看终值计算与导出 Excel"):
        st.markdown(
            f"""
            - 第 {assumptions.forecast_years} 年 FCFF：**{valuation.rows[-1].fcff:,.2f} 万元**
            - 第 {assumptions.forecast_years + 1} 年 FCFF = FCFF_n × (1+g)：**{valuation.fcff_next:,.2f} 万元**
            - 终值 TV = FCFF_(n+1) / (WACC − g)：**{valuation.terminal_value:,.2f} 万元**
            - 终值现值 PV(TV)：**{valuation.pv_terminal:,.2f} 万元**
            """
        )

        # 在内存中生成工作簿字节流，避免依赖服务器临时目录
        try:
            excel_data = excel_bytes(valuation)
        except Exception as exc:  # 生成失败不影响页面其余部分
            st.warning(f"Excel 生成失败：{exc}")
        else:
            st.download_button(
                "⬇️ 下载 Excel（预测期明细 + 估值汇总）",
                data=excel_data,
                file_name="FCFF_valuation_result.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="fcff_excel_download",
            )


# ===========================================================================
# 模块二：WACC 加权平均资本成本计算器
# ===========================================================================
def compute_wacc(
    rf: float,
    mrp: float,
    beta_u: float,
    d_weight: float,
    e_weight: float,
    rd: float,
    tax: float,
) -> dict:
    """按目标资本结构重新加杠杆，并计算 WACC。

    全部入参均为「小数」形式（3% 请传 0.03），返回值同样为小数。
    计算步骤：
        1. 归一化资本结构，得到 D/V、E/V、D/E；
        2. βl = βu × [1 + (1 - T) × D/E]；
        3. Ke = Rf + βl × MRP；
        4. 税后债务成本 = Rd × (1 - T)；
        5. WACC = E/V × Ke + D/V × Rd × (1 - T)。
    """
    if d_weight < 0 or e_weight < 0:
        raise ValueError("资本结构比例不能为负数")
    if not 0.0 <= tax <= 1.0:
        raise ValueError("企业所得税率必须在 0%~100% 之间")
    if beta_u < 0:
        raise ValueError("βu 不能为负数")

    total = d_weight + e_weight
    if total <= 0:
        raise ValueError("D/V 与 E/V 之和必须大于 0")
    d = d_weight / total  # 归一化：即使输入 30%+60%，也按 1/3 与 2/3 计算
    e = e_weight / total
    if e <= 0:
        raise ValueError("权益占比 E/V 必须大于 0，否则 D/E 无意义")

    de = d / e                                     # 债务 / 权益
    beta_l = beta_u * (1.0 + (1.0 - tax) * de)     # 重新加杠杆
    ke = rf + beta_l * mrp                         # CAPM
    kd_after_tax = rd * (1.0 - tax)                # 税后债务成本
    wacc = e * ke + d * kd_after_tax               # 加权平均

    return {
        "d_weight": d,
        "e_weight": e,
        "de": de,
        "beta_l": beta_l,
        "ke": ke,
        "kd": kd_after_tax,
        "wacc": wacc,
    }


def render_wacc_tab() -> None:
    """第二个标签页：WACC 计算器（表单输入 + 大号结果 + 图表）。"""
    st.subheader("WACC 加权平均资本成本计算器")
    st.caption(
        "βl = βu × [1 + (1−T) × D/E]　→　Ke = Rf + βl × MRP　→　"
        "WACC = (E/V) × Ke + (D/V) × Rd × (1−T)"
    )

    # ---------------- 输入区（用表单批量提交，避免边输入边刷新） ----------------
    with st.form("wacc_form"):
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("**市场与公司风险参数**")
            rf_pct = st.number_input(
                "无风险利率 Rf（%）",
                min_value=0.0, max_value=20.0, value=3.0, step=0.1, format="%.2f",
            )
            mrp_pct = st.number_input(
                "市场风险溢价 MRP（%）",
                min_value=0.0, max_value=30.0, value=6.0, step=0.1, format="%.2f",
            )
            beta_u = st.number_input(
                "可比公司去杠杆 Beta（βu）",
                min_value=0.0, max_value=5.0, value=0.8, step=0.05, format="%.2f",
            )

        with col2:
            st.markdown("**资本结构与债务成本**")
            d_pct = st.number_input(
                "目标债务占比 D/V（%）",
                min_value=0.0, max_value=100.0, value=30.0, step=1.0,
            )
            e_pct = st.number_input(
                "目标权益占比 E/V（%）",
                min_value=0.0, max_value=100.0, value=70.0, step=1.0,
            )
            rd_pct = st.number_input(
                "税前债务成本 Rd（%）",
                min_value=0.0, max_value=30.0, value=5.0, step=0.1, format="%.2f",
            )
            tax_pct = st.number_input(
                "企业所得税率 T（%）",
                min_value=0.0, max_value=100.0, value=25.0, step=1.0,
            )

        submitted = st.form_submit_button("计算 WACC", type="primary")

    # ---------------- 提交后计算并缓存结果 ----------------
    if submitted:
        try:
            result = compute_wacc(
                rf=rf_pct / 100.0,
                mrp=mrp_pct / 100.0,
                beta_u=beta_u,
                d_weight=d_pct / 100.0,
                e_weight=e_pct / 100.0,
                rd=rd_pct / 100.0,
                tax=tax_pct / 100.0,
            )
        except ValueError as exc:
            st.session_state.pop("wacc_result", None)
            st.error(f"参数校验未通过：{exc}")
        else:
            st.session_state["wacc_result"] = result
            # 记录本次输入，供「计算过程」展示
            st.session_state["wacc_note"] = {
                "rf": rf_pct / 100.0,
                "mrp": mrp_pct / 100.0,
                "beta_u": beta_u,
                "rd": rd_pct / 100.0,
                "tax": tax_pct / 100.0,
                "d_pct": d_pct,
                "e_pct": e_pct,
            }

    result = st.session_state.get("wacc_result")
    note = st.session_state.get("wacc_note", {})

    if not result:
        st.info("填写上方参数后点击「计算 WACC」按钮，结果将显示在这里。")
        return

    # 资本结构之和不为 100% 时给出提示（计算时已自动归一化）
    if abs(note.get("d_pct", 0) + note.get("e_pct", 0) - 100.0) > 1e-6:
        st.warning(
            f"D/V 与 E/V 之和为 {note['d_pct'] + note['e_pct']:.2f}%，不等于 100%，"
            "已按两者比例归一化后计算。"
        )

    # ---------------- 醒目的大号 WACC ----------------
    st.markdown(
        f"""
        <div class="wacc-card">
            <div class="label">加权平均资本成本 WACC</div>
            <div class="value">{result['wacc']:.2%}</div>
            <div class="formula">
                = {result['e_weight']:.2%} × {result['ke']:.2%}
                &nbsp;+&nbsp; {result['d_weight']:.2%} × {result['kd']:.2%}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ---------------- 中间变量 ----------------
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("杠杆后 Beta（βl）", f"{result['beta_l']:.3f}")
    k2.metric("股权资本成本 Ke", f"{result['ke']:.2%}")
    k3.metric("税后债务成本", f"{result['kd']:.2%}")
    k4.metric("D/E（债务 / 权益）", f"{result['de']:.2%}")

    st.divider()

    # ---------------- 图表 + 构成明细 ----------------
    chart_col, table_col = st.columns([3, 2])

    with chart_col:
        st.markdown("**资本权重 vs. 资本成本率（单位：%）**")
        # 两行（股权 / 债务）× 两列（权重 / 成本率），Streamlit 会自动画成分组柱状图
        chart_df = pd.DataFrame(
            {
                "资本权重": [result["e_weight"] * 100, result["d_weight"] * 100],
                "资本成本率": [result["ke"] * 100, result["kd"] * 100],
            },
            index=["股权", "债务"],
        )
        st.bar_chart(chart_df, height=340)
        st.caption(
            "柱高对比：权重反映资本结构占比，成本率反映该项资本的价格；"
            "两者相乘即该项资本对 WACC 的贡献。"
        )

    with table_col:
        st.markdown("**WACC 构成明细**")
        build_up = pd.DataFrame(
            [
                {
                    "资本类型": "股权",
                    "权重": f"{result['e_weight']:.2%}",
                    "成本率": f"{result['ke']:.2%}",
                    "加权贡献": f"{result['e_weight'] * result['ke']:.2%}",
                },
                {
                    "资本类型": "债务（税后）",
                    "权重": f"{result['d_weight']:.2%}",
                    "成本率": f"{result['kd']:.2%}",
                    "加权贡献": f"{result['d_weight'] * result['kd']:.2%}",
                },
                {
                    "资本类型": "合计",
                    "权重": "100.00%",
                    "成本率": "—",
                    "加权贡献": f"{result['wacc']:.2%}",
                },
            ]
        )
        st.dataframe(build_up, hide_index=True)

    # ---------------- 计算过程 ----------------
    with st.expander("查看计算过程（逐步展开）"):
        st.markdown(
            f"""
            1. **归一化资本结构**：D/V = {result['d_weight']:.2%}，E/V = {result['e_weight']:.2%}，
               因此 D/E = {result['de']:.4f}
            2. **重新加杠杆**：βl = βu × [1 + (1 − T) × D/E]
               = {note.get('beta_u', 0.0):.2f} × [1 + (1 − {note.get('tax', 0.0):.2%}) × {result['de']:.4f}]
               = **{result['beta_l']:.4f}**
            3. **股权成本（CAPM）**：Ke = Rf + βl × MRP
               = {note.get('rf', 0.0):.2%} + {result['beta_l']:.4f} × {note.get('mrp', 0.0):.2%}
               = **{result['ke']:.2%}**
            4. **税后债务成本**：Rd × (1 − T)
               = {note.get('rd', 0.0):.2%} × (1 − {note.get('tax', 0.0):.2%})
               = **{result['kd']:.2%}**
            5. **加权求和**：WACC = {result['e_weight']:.2%} × {result['ke']:.2%}
               + {result['d_weight']:.2%} × {result['kd']:.2%}
               = **{result['wacc']:.2%}**
            """
        )

    # ---------------- 回填到 FCFF 模块 ----------------
    st.button(
        "↗️ 把该 WACC 应用到「FCFF 估值」模块",
        on_click=_apply_wacc_to_fcff,
        help="点击后切到 FCFF 标签页，折现率输入框会自动更新为本次计算结果",
    )


# ===========================================================================
# 主程序：用 st.tabs 组织两个模块
# ===========================================================================
def main() -> None:
    st.title("📊 企业价值评估工作台")
    st.caption("模块一：FCFF 两阶段折现估值　｜　模块二：WACC 加权平均资本成本计算器")

    fcff_tab, wacc_tab = st.tabs(["📈 FCFF 估值", "🧮 WACC 计算器"])
    with fcff_tab:
        render_fcff_tab()
    with wacc_tab:
        render_wacc_tab()

    st.divider()
    st.caption("本工具仅用于教学演示与内部测算，不构成投资建议。")


if __name__ == "__main__":
    main()
