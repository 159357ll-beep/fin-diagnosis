# -*- coding: utf-8 -*-
"""
美的集团 2025 年报分析网站（Streamlit 专用版）
===========================================================================
第一个版本只服务「美的集团 2025 年年度报告」这一份 PDF：
    · 按关键词定位「合并及公司资产负债表」「合并及公司利润表」所在页；
    · 用 pypdf 提取 7 个科目（2025 / 2024 两列合并数）；
    · 做勾稽校验，页面表格可手工修正；
    · 计算毛利率、净利率、周转率、资产负债率、权益乘数、杜邦 ROE；
    · 输出图表、诊断与 Excel 下载。

运行：
    streamlit run midea_app.py

依赖：
    streamlit、pypdf、pandas、openpyxl
"""

from __future__ import annotations

import io
import re
from pathlib import Path

import pandas as pd
import streamlit as st

from midea_2025_financial_analysis import (
    DATA,
    DEBT_DETAIL,
    ROE_EXCELLENT,
    DEBT_ALERT,
    calc_metrics,
    dupont_attribution,
)

try:
    from pypdf import PdfReader
except ImportError:  # 允许在没装 pypdf 时仍能打开页面（用内置数据）
    PdfReader = None


# ===========================================================================
# 一、页面配置与样式
# ===========================================================================
st.set_page_config(
    page_title="美的集团 2025 年报分析",
    page_icon="📊",
    layout="wide",
)

st.markdown(
    """
    <style>
    .block-container { padding-top: 1.6rem; }
    .source-box {
        background: #f7f9fc; border-left: 4px solid #4472c4;
        padding: 10px 14px; border-radius: 4px; font-size: 0.86rem; color: #4a5a75;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

ITEMS = ["营业收入", "营业成本", "净利润", "应收账款", "存货", "总资产", "所有者权益"]
DEFAULT_PDF = Path.home() / "Desktop" / "美的.pdf"


# ===========================================================================
# 二、PDF 解析（美的专用）
# ===========================================================================
REF = re.compile(r"[一二三四五六七八九十百]+\(\d+\)")      # 附注编号，如 四(5)、十八(3)
NUM = re.compile(r"\(?-?\d[\d,]*(?:\.\d+)?\)?")            # 数字，支持 (123) 负数


def _numbers_after(text: str, pattern: str) -> list[float]:
    """在文本中按行匹配标签，返回该行标签之后的数字列表（合并列在前）。"""
    rx = re.compile(pattern)
    for line in text.splitlines():
        s = line.strip()
        m = rx.match(s)
        if not m:
            continue
        rest = REF.sub(" ", s[m.end():])       # 去掉「四(5)」这类附注编号
        values: list[float] = []
        for token in NUM.findall(rest):
            if not any(ch.isdigit() for ch in token):
                continue
            negative = token.startswith("(") and token.endswith(")")
            number = float(token.strip("()").replace(",", ""))
            values.append(-number if negative else number)
        if values:
            return values
    return []


def _collect_pages(reader) -> dict[str, tuple[int, str]]:
    """定位三张关键报表页：资产页、权益页、利润表页。

    先扫描 115~160 页（年报财务报表通常在此区间），找不到再全量回退。
    """
    found: dict[str, tuple[int, str]] = {}

    def scan(indices):
        for i in indices:
            text = reader.pages[i].extract_text(extraction_mode="layout") or ""
            if "合并及公司资产负债表" in text:
                if "资产总计" in text and "assets" not in found:
                    found["assets"] = (i + 1, text)
                if "股东权益合计" in text and "equity" not in found:
                    found["equity"] = (i + 1, text)
            if "合并及公司利润表" in text and "四、净利润" in text:
                if "income" not in found:
                    found["income"] = (i + 1, text)

    scan(range(115, min(len(reader.pages), 160)))
    if len(found) < 3:  # 回退：全量扫描
        scan(range(len(reader.pages)))
    return found


def extract_financials(source) -> tuple[dict[str, dict[str, float]], dict[str, int]]:
    """从美的年报 PDF 中抽取 7 个科目（单位：千元）。

    返回 (数据字典, 用到的页码)。
    """
    if PdfReader is None:
        raise RuntimeError("缺少 pypdf，请先执行：pip install pypdf")

    reader = PdfReader(source)
    pages = _collect_pages(reader)
    missing = {"assets", "equity", "income"} - set(pages)
    if missing:
        raise ValueError(f"未能定位报表页：{missing}，请检查 PDF 是否为美的集团年报")

    assets_text = pages["assets"][1]
    equity_text = pages["equity"][1]
    income_text = pages["income"][1]

    rules = {
        "营业收入": (income_text, r"其中：营业收入"),
        "营业成本": (income_text, r"减：营业成本"),
        "净利润": (income_text, r"四、净利润"),
        "应收账款": (assets_text, r"应收账款(?=\s)"),
        "存货": (assets_text, r"存货(?=\s)"),
        "总资产": (assets_text, r"资产总计(?=\s)"),
        "所有者权益": (equity_text, r"股东权益合计(?=\s)"),
    }

    result: dict[str, dict[str, float]] = {"2025": {}, "2024": {}}
    for item, (text, pattern) in rules.items():
        nums = _numbers_after(text, pattern)
        if len(nums) < 2:
            raise ValueError(f"「{item}」解析失败，未找到 2025/2024 两列数字")
        # 利润表把营业成本列在「减：」项下并以 (xxx) 表示，这里统一转成正数
        cost_2025, cost_2024 = nums[0], nums[1]
        if item == "营业成本":
            cost_2025, cost_2024 = abs(cost_2025), abs(cost_2024)
        result["2025"][item] = cost_2025   # 第一列：2025 年合并
        result["2024"][item] = cost_2024   # 第二列：2024 年合并

    # 勾稽校验：资产 = 负债 + 所有者权益
    liabilities = _numbers_after(equity_text, r"负债合计(?=\s)")
    if liabilities:
        diff = abs(result["2025"]["总资产"] - liabilities[0] - result["2025"]["所有者权益"])
        if diff / result["2025"]["总资产"] > 0.001:
            raise ValueError("勾稽校验未通过：资产 ≠ 负债 + 所有者权益，请人工核对")

    page_info = {k: v[0] for k, v in pages.items()}
    return result, page_info


# ===========================================================================
# 三、数据编辑与计算
# ===========================================================================
def to_editor_df(data: dict[str, dict[str, float]]) -> pd.DataFrame:
    """把千元数据转成「亿元」的编辑表（保留 4 位小数，精度到千元）。"""
    frame = pd.DataFrame(
        {year: {item: data[year][item] / 100_000.0 for item in ITEMS} for year in ("2025", "2024")}
    )
    frame.index.name = "科目（亿元）"
    return frame


def from_editor_df(frame: pd.DataFrame) -> dict[str, dict[str, float]]:
    """把编辑表还原为千元整数。"""
    return {
        year: {item: round(float(frame.loc[item, year]) * 100_000) for item in ITEMS}
        for year in ("2025", "2024")
    }


def diagnose(m25: dict, m24: dict, interest_ratio: float) -> list[tuple[str, str]]:
    """生成诊断条目（级别, 文案），供页面用不同颜色展示。"""
    messages: list[tuple[str, str]] = []

    roe = m25["ROE"]
    if roe >= ROE_EXCELLENT:
        messages.append(("success", f"ROE {roe:.2%} ≥ 15%，盈利能力优秀"))
    elif roe >= 0.10:
        messages.append(("info", f"ROE {roe:.2%} 介于 10%~15%，盈利能力良好"))
    else:
        messages.append(("warning", f"ROE {roe:.2%} < 10%，盈利能力偏弱"))

    debt_ratio = m25["资产负债率"]
    if debt_ratio > DEBT_ALERT:
        if interest_ratio < 0.15:
            messages.append(
                (
                    "warning",
                    f"资产负债率 {debt_ratio:.2%} > 60%，触发债务风险预警；"
                    f"但有息负债率仅 {interest_ratio:.2%}，负债以经营性占款为主，"
                    "建议降级为「关注」",
                )
            )
        else:
            messages.append(("error", f"资产负债率 {debt_ratio:.2%} > 60%，且杠杆偏高，注意偿债风险"))
    else:
        messages.append(("success", f"资产负债率 {debt_ratio:.2%}，资本结构处于安全区间"))

    messages.append(
        (
            "info",
            f"毛利率 {m25['毛利率']:.2%}（同比 {m25['毛利率'] - m24['毛利率']:+.2%}），"
            f"净利率 {m25['净利率']:.2%}",
        )
    )
    messages.append(
        (
            "info",
            f"存货周转 {m25['存货周转率']:.2f} 次（{m25['存货周转天数']:.0f} 天），"
            f"应收周转 {m25['应收账款周转率']:.2f} 次（{m25['应收账款周转天数']:.0f} 天）",
        )
    )
    return messages


# ===========================================================================
# 四、页面主体
# ===========================================================================
if "fin" not in st.session_state:
    st.session_state["fin"] = {year: dict(DATA[year]) for year in ("2025", "2024")}
if "version" not in st.session_state:
    st.session_state["version"] = 0
if "source" not in st.session_state:
    st.session_state["source"] = "内置数据（已人工核对）"

st.title("📊 美的集团 2025 年报分析")
st.caption("上传年报 PDF → 自动抽取合并报表科目 → 指标 / 杜邦 / 诊断 → 下载 Excel")

# ---------------- 侧边栏：数据源 ----------------
with st.sidebar:
    st.header("数据源")
    uploaded = st.file_uploader("上传年报 PDF", type=["pdf"])
    path_text = st.text_input("或输入本地 PDF 路径", value=str(DEFAULT_PDF))

    col_a, col_b = st.columns(2)
    parse_clicked = col_a.button("解析 PDF", type="primary", width="stretch")
    reset_clicked = col_b.button("用内置数据", width="stretch")

    st.divider()
    st.caption("解析只读取合并报表的前两列（2025 / 2024），不会上传到任何服务器。")

if parse_clicked:
    source = uploaded if uploaded is not None else Path(path_text)
    try:
        with st.spinner("正在解析 PDF …"):
            if uploaded is not None:
                uploaded.seek(0)
            data, pages = extract_financials(source)
        st.session_state["fin"] = data
        st.session_state["version"] += 1
        st.session_state["source"] = (
            f"PDF 解析（资产页 P{pages.get('assets')}、权益页 P{pages.get('equity')}、"
            f"利润表 P{pages.get('income')}）"
        )
        st.sidebar.success("解析完成，请在下方表格核对")
    except Exception as exc:  # 解析失败不崩溃，保留原有数据
        st.sidebar.error(f"解析失败：{exc}")

if reset_clicked:
    st.session_state["fin"] = {year: dict(DATA[year]) for year in ("2025", "2024")}
    st.session_state["version"] += 1
    st.session_state["source"] = "内置数据（已人工核对）"

# ---------------- 数据确认表 ----------------
st.subheader("① 基础数据（单位：亿元）")
st.caption("解析结果可能有误差，请对照年报核对后再看指标；可直接在表格里修改。")

editor_df = to_editor_df(st.session_state["fin"])
edited = st.data_editor(
    editor_df,
    key=f"editor_{st.session_state['version']}",
    num_rows="fixed",
    width="stretch",
    column_config={
        "2025": st.column_config.NumberColumn("2025 年", format="%.4f"),
        "2024": st.column_config.NumberColumn("2024 年", format="%.4f"),
    },
)
data = from_editor_df(edited)

# 计算指标
m25 = calc_metrics(data["2025"], data["2024"], "2025")
m25_end = calc_metrics(data["2025"], None, "2025")
m24 = calc_metrics(data["2024"], None, "2024")

interest_2025 = sum(DEBT_DETAIL["2025"].values())
interest_2024 = sum(DEBT_DETAIL["2024"].values())
interest_ratio = interest_2025 / m25["总资产"] if m25["总资产"] else 0.0

# ---------------- 关键卡片 ----------------
st.subheader("② 核心结果")
c1, c2, c3, c4 = st.columns(4)
c1.metric("营业收入", f"{data['2025']['营业收入'] / 100_000:,.2f} 亿元")
c2.metric("净利润", f"{data['2025']['净利润'] / 100_000:,.2f} 亿元")
c3.metric("ROE（平均口径）", f"{m25['ROE']:.2%}")
c4.metric("资产负债率", f"{m25['资产负债率']:.2%}")

# ---------------- 指标表 ----------------
st.subheader("③ 财务指标")
metric_rows = [
    ["毛利率", f"{m25['毛利率']:.2%}", f"{m25_end['毛利率']:.2%}", f"{m24['毛利率']:.2%}"],
    ["净利率", f"{m25['净利率']:.2%}", f"{m25_end['净利率']:.2%}", f"{m24['净利率']:.2%}"],
    ["存货周转率", f"{m25['存货周转率']:.2f} 次", f"{m25_end['存货周转率']:.2f} 次", f"{m24['存货周转率']:.2f} 次"],
    ["应收账款周转率", f"{m25['应收账款周转率']:.2f} 次", f"{m25_end['应收账款周转率']:.2f} 次", f"{m24['应收账款周转率']:.2f} 次"],
    ["总资产周转率", f"{m25['总资产周转率']:.2f} 次", f"{m25_end['总资产周转率']:.2f} 次", f"{m24['总资产周转率']:.2f} 次"],
    ["资产负债率", f"{m25['资产负债率']:.2%}", f"{m25_end['资产负债率']:.2%}", f"{m24['资产负债率']:.2%}"],
    ["权益乘数", f"{m25['权益乘数']:.2f}", f"{m25_end['权益乘数']:.2f}", f"{m24['权益乘数']:.2f}"],
    ["ROE", f"{m25['ROE']:.2%}", f"{m25_end['ROE']:.2%}", f"{m24['ROE']:.2%}"],
]
st.dataframe(
    pd.DataFrame(metric_rows, columns=["指标", "2025（平均）", "2025（期末）", "2024（期末）"]),
    hide_index=True,
    width="stretch",
)
st.caption("2024 年缺 2023 年末余额，周转率与 ROE 按期末余额计算；2025 年同时给出平均、期末两种口径。")

# ---------------- 杜邦 ----------------
st.subheader("④ 杜邦分析")
st.latex(r"ROE = \text{净利率} \times \text{总资产周转率} \times \text{权益乘数}")
st.write(
    f"{m25['净利率']:.2%} × {m25['总资产周转率']:.2f} × {m25['权益乘数']:.2f} "
    f"= **{m25['ROE']:.2%}**（2025 平均口径）"
)
attribution = dupont_attribution(m25_end, m24)
st.write(
    f"2025 vs 2024（期末口径）：净利率贡献 {attribution['净利率贡献'] * 100:+.2f}pp、"
    f"周转率贡献 {attribution['周转率贡献'] * 100:+.2f}pp、"
    f"杠杆贡献 {attribution['杠杆贡献'] * 100:+.2f}pp。"
)

# ---------------- 图表 ----------------
st.subheader("⑤ 规模与盈利趋势（亿元）")
chart_df = pd.DataFrame(
    {
        "营业收入": [data["2025"]["营业收入"] / 100_000, data["2024"]["营业收入"] / 100_000],
        "净利润": [data["2025"]["净利润"] / 100_000, data["2024"]["净利润"] / 100_000],
    },
    index=["2025", "2024"],
)
st.bar_chart(chart_df, height=320)

# ---------------- 诊断 ----------------
st.subheader("⑥ 智能诊断")
for level, text in diagnose(m25, m24, interest_ratio):
    if level == "success":
        st.success(text)
    elif level == "warning":
        st.warning(text)
    elif level == "error":
        st.error(text)
    else:
        st.info(text)

# ---------------- 下载 ----------------
st.subheader("⑦ 导出")
buffer = io.BytesIO()
with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
    pd.DataFrame(data).to_excel(writer, sheet_name="基础数据（千元）")
    pd.DataFrame(metric_rows, columns=["指标", "2025平均", "2025期末", "2024期末"]).to_excel(
        writer, sheet_name="财务指标", index=False
    )
st.download_button(
    "⬇️ 下载 Excel",
    data=buffer.getvalue(),
    file_name="美的集团2025财务分析.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
)

# ---------------- 来源与免责声明 ----------------
st.markdown(
    f"""
    <div class="source-box">
      数据来源：美的集团股份有限公司《2025 年年度报告》合并资产负债表、合并利润表，
      巨潮资讯网，2026 年 3 月。当前数据：{st.session_state['source']}。<br>
      免责声明：本页面仅用于个人学习与交流，不构成任何投资建议；数据请以公司公告为准。
    </div>
    """,
    unsafe_allow_html=True,
)
