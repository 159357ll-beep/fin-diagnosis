# -*- coding: utf-8 -*-
"""
企业自由现金流（FCFF）两阶段折现估值模型
===========================================================================
功能概要
    1. 以基期 EBIT 为起点，按固定增长率滚动预测第 1~5 年的 EBIT；
    2. 逐年计算 FCFF = EBIT×(1-税率) + 折旧摊销 - 资本性支出 - 营运资本增加；
    3. 用 WACC 把各年 FCFF 折现到第 0 年；
    4. 第 5 年末用永续增长模型（Gordon 模型）计算终值 TV，并折现到第 0 年；
    5. 汇总得到企业价值 EV = 预测期现值合计 + 终值现值；
    6. 可选：把第 1~n 年明细（年份、EBIT、FCFF、折现现值）导出为 Excel。

公式
    FCFF_t = EBIT_t × (1 - 税率) + 折旧摊销_t - 资本性支出_t - 营运资本增加_t
    EV     = Σ_{t=1..n} FCFF_t / (1+WACC)^t  +  TV_n / (1+WACC)^n
    TV_n   = FCFF_{n+1} / (WACC - g) = FCFF_n × (1+g) / (WACC - g)

模型约定（重要）
    * 折旧摊销、资本性支出、营运资本增加均按「基期 EBIT 的固定比例」假设，
      因此它们会随 EBIT 同步增长（比例保持不变），便于手工复核；
    * 折现采用「年末折现」惯例，即第 t 年现金流在 t 年末收到；
    * 永续增长率 g 必须小于 WACC，否则终值公式不成立（代码会直接报错）；
    * 预测期增长率 5% 高于永续增长率 2%，隐含「增速逐步回落至永续水平」的
      成熟期假设。严格意义上，稳定期的资本性支出应逐步收敛至折旧摊销水平，
      本脚本为教学演示未做该调整，仅供内部测算参考，不构成投资建议。

运行环境
    Python 3.9+，可直接运行：python fcff_dcf_valuation.py
    核心计算只依赖标准库；导出 Excel 需额外安装：pip install pandas openpyxl
"""

from __future__ import annotations

import io
import sys
import unicodedata
from dataclasses import dataclass, replace
from pathlib import Path


# ===========================================================================
# 一、基础参数（日常只需要修改这一节，其余代码一般无需改动）
#    修改方式二选一：
#      1) 直接改下面各个字段的默认值；
#      2) 在 main() 里用关键字覆盖，例如 Assumptions(wacc=0.09, terminal_growth=0.025)
# ===========================================================================
@dataclass(frozen=True)
class Assumptions:
    """估值假设。金额单位：万元（换成元 / 百万元不影响估值倍数与结论）。"""

    # ---------- 盈利与增长 ----------
    ebit_base: float = 1000.0        # 基期（第 0 年）息税前利润 EBIT
    ebit_growth: float = 0.05        # 预测期（第 1~5 年）EBIT 年增长率，5%
    tax_rate: float = 0.25           # 企业所得税率，25%

    # ---------- 现金流项目（均按 EBIT 的固定比例假设，随 EBIT 同步变动）----------
    da_ratio: float = 0.10           # 折旧摊销 / EBIT = 10%
    capex_ratio: float = 0.12        # 资本性支出 / EBIT = 12%
    nwc_ratio: float = 0.03          # 营运资本增加额 / EBIT = 3%

    # ---------- 折现与永续期 ----------
    wacc: float = 0.10               # 加权平均资本成本 WACC，10%
    terminal_growth: float = 0.02    # 永续增长率 g，2%
    forecast_years: int = 5          # 明确预测期年数，5 年

    def __post_init__(self) -> None:
        """参数合法性校验：把错误挡在计算之前，避免出现无意义的估值结果。"""
        if self.forecast_years < 1:
            raise ValueError("预测期年数 forecast_years 至少为 1 年")
        if not 0.0 <= self.tax_rate <= 1.0:
            raise ValueError(f"税率应在 0~1 之间，当前为 {self.tax_rate}")
        if self.wacc <= 0.0:
            raise ValueError(f"WACC 必须为正数，当前为 {self.wacc}")
        if self.wacc <= self.terminal_growth:
            raise ValueError(
                f"WACC（{self.wacc:.2%}）必须大于永续增长率 g（{self.terminal_growth:.2%}），"
                "否则终值公式分母 ≤ 0，永续增长模型不成立"
            )
        if self.ebit_growth <= -1.0:
            raise ValueError("EBIT 增长率必须大于 -100%")
        for name, value in (
            ("da_ratio", self.da_ratio),
            ("capex_ratio", self.capex_ratio),
            ("nwc_ratio", self.nwc_ratio),
        ):
            if value < 0:
                raise ValueError(f"{name} 不能为负数，当前为 {value}")


# 是否在结果末尾附加 WACC × g 的敏感性分析表（True / False）
SHOW_SENSITIVITY = True

# 是否把预测期明细导出为 Excel（需要 pandas + openpyxl）
EXPORT_EXCEL = True
EXCEL_FILENAME = "FCFF_valuation_result.xlsx"


# ===========================================================================
# 二、数据容器
# ===========================================================================
@dataclass(frozen=True)
class YearResult:
    """单一年度的预测与折现结果。"""

    year: int                 # 年份序号 t（第 t 年）
    ebit: float               # 当年 EBIT
    nopat: float              # 息税前利润 × (1 - 税率)，即无杠杆税后利润
    da: float                 # 折旧摊销
    capex: float              # 资本性支出
    nwc_increase: float       # 营运资本增加额
    fcff: float               # 企业自由现金流
    discount_factor: float    # 折现因子 = 1 / (1 + WACC)^t
    pv: float                 # 折现现值 = FCFF × 折现因子


@dataclass(frozen=True)
class Valuation:
    """一次完整估值的结果集合。"""

    assumptions: Assumptions
    rows: list[YearResult]      # 第 1~n 年的明细
    pv_explicit: float          # 预测期现值合计
    fcff_next: float            # 第 n+1 年 FCFF（终值公式分子用）
    terminal_value: float       # 第 n 年末终值 TV
    pv_terminal: float          # 终值折现到第 0 年的现值
    enterprise_value: float     # 企业价值 EV


# ===========================================================================
# 三、核心计算
# ===========================================================================
def build_forecast(a: Assumptions) -> list[YearResult]:
    """滚动预测第 1~n 年 EBIT，并逐年计算 FCFF 及其折现现值。"""
    rows: list[YearResult] = []
    ebit = a.ebit_base  # 从基期 EBIT 出发，逐年复利增长

    for year in range(1, a.forecast_years + 1):
        ebit *= 1.0 + a.ebit_growth                 # 第 t 年 EBIT = 上年 EBIT × (1 + 5%)

        nopat = ebit * (1.0 - a.tax_rate)           # EBIT × (1 - 税率)
        da = ebit * a.da_ratio                      # 折旧摊销（非现金支出，加回）
        capex = ebit * a.capex_ratio                # 资本性支出（现金流出，扣除）
        nwc_increase = ebit * a.nwc_ratio           # 营运资本增加（占用现金，扣除）

        # 经典 FCFF 公式
        fcff = nopat + da - capex - nwc_increase

        # 年末折现：第 t 年现金流折现 t 期
        discount_factor = 1.0 / (1.0 + a.wacc) ** year

        rows.append(
            YearResult(
                year=year,
                ebit=ebit,
                nopat=nopat,
                da=da,
                capex=capex,
                nwc_increase=nwc_increase,
                fcff=fcff,
                discount_factor=discount_factor,
                pv=fcff * discount_factor,
            )
        )

    return rows


def run_valuation(a: Assumptions) -> Valuation:
    """执行完整估值：预测期折现 + 永续期终值折现 + 企业价值汇总。"""
    rows = build_forecast(a)
    pv_explicit = sum(r.pv for r in rows)

    last = rows[-1]                                        # 预测期最后一年
    n = a.forecast_years

    # 永续期第一年现金流：第 n 年 FCFF 按永续增长率 g 增长一年
    fcff_next = last.fcff * (1.0 + a.terminal_growth)

    # 第 n 年末终值（Gordon 永续增长模型）
    terminal_value = fcff_next / (a.wacc - a.terminal_growth)

    # 终值折现到第 0 年：与第 n 年现金流使用同一个折现因子
    pv_terminal = terminal_value / (1.0 + a.wacc) ** n

    enterprise_value = pv_explicit + pv_terminal

    return Valuation(
        assumptions=a,
        rows=rows,
        pv_explicit=pv_explicit,
        fcff_next=fcff_next,
        terminal_value=terminal_value,
        pv_terminal=pv_terminal,
        enterprise_value=enterprise_value,
    )


# ===========================================================================
# 四、控制台输出（按字符显示宽度对齐，中英文混排不会错位）
# ===========================================================================
def _text_width(text: str) -> int:
    """计算字符串在终端中的显示宽度：中日韩全角字符按 2 列计。"""
    return sum(
        2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1 for ch in text
    )


def _pad(text: str, width: int, align: str = "left") -> str:
    """按显示宽度补空格，支持左对齐 / 右对齐 / 居中。"""
    gap = max(0, width - _text_width(text))
    if align == "right":
        return " " * gap + text
    if align == "center":
        left = gap // 2
        return " " * left + text + " " * (gap - left)
    return text + " " * gap


def _kv(label: str, value: str, width: int = 40) -> str:
    """输出一行「标签 : 数值」，标签按显示宽度对齐。"""
    return f"  {_pad(label, width)}: {value}"


def _print_table(headers: list[str], rows: list[list[str]], aligns: list[str]) -> None:
    """打印等宽表格。"""
    widths = [
        max(_text_width(headers[i]), *(_text_width(row[i]) for row in rows))
        for i in range(len(headers))
    ]
    separator = "─" * (sum(widths) + 2 * (len(widths) - 1))

    print("  ".join(_pad(h, w, "center") for h, w in zip(headers, widths)))
    print(separator)
    for row in rows:
        print("  ".join(_pad(c, w, a) for c, w, a in zip(row, widths, aligns)))
    print(separator)


def print_results(v: Valuation) -> None:
    """把估值结果按「假设 → 预测期 → 终值 → 企业价值 → 校验 → 敏感性」分段打印。"""
    a = v.assumptions
    rule = "=" * 78

    print(rule)
    print(_pad("企业自由现金流（FCFF）两阶段折现估值", 78, "center"))
    print(rule)
    print("公式：FCFF = EBIT×(1-税率) + 折旧摊销 - 资本性支出 - 营运资本增加")
    print("      EV   = Σ FCFF_t/(1+WACC)^t + TV_n/(1+WACC)^n")
    print("      TV_n = FCFF_n×(1+g)/(WACC-g)")
    print()

    # ---------------- 一、核心假设 ----------------
    print("【一】核心假设")
    print(_kv("基期 EBIT（第 0 年）", f"{a.ebit_base:,.2f} 万元"))
    print(_kv("预测期 EBIT 年增长率", f"{a.ebit_growth:.2%}"))
    print(_kv("企业所得税率", f"{a.tax_rate:.2%}"))
    print(_kv("折旧摊销 / EBIT", f"{a.da_ratio:.2%}"))
    print(_kv("资本性支出 / EBIT", f"{a.capex_ratio:.2%}"))
    print(_kv("营运资本增加 / EBIT", f"{a.nwc_ratio:.2%}"))
    print(_kv("加权平均资本成本 WACC", f"{a.wacc:.2%}"))
    print(_kv("永续增长率 g", f"{a.terminal_growth:.2%}"))
    print(_kv("明确预测期", f"{a.forecast_years} 年"))
    print()

    # ---------------- 二、预测期明细 ----------------
    print(f"【二】预测期（第 1~{a.forecast_years} 年）FCFF 计算与折现")
    headers = ["年度", "EBIT", "EBIT×(1-t)", "折旧摊销", "资本性支出",
               "营运资本增加", "FCFF", "折现因子", "现值 PV"]
    table_rows = [
        [
            f"第{r.year}年",
            f"{r.ebit:,.2f}",
            f"{r.nopat:,.2f}",
            f"{r.da:,.2f}",
            f"{r.capex:,.2f}",
            f"{r.nwc_increase:,.2f}",
            f"{r.fcff:,.2f}",
            f"{r.discount_factor:.4f}",
            f"{r.pv:,.2f}",
        ]
        for r in v.rows
    ]
    _print_table(headers, table_rows, ["left"] + ["right"] * 8)
    print(_kv("预测期现值合计", f"{v.pv_explicit:,.2f} 万元"))
    print()

    # ---------------- 三、永续期终值 ----------------
    last = v.rows[-1]
    n = a.forecast_years
    print(f"【三】永续期终值（第 {n} 年末，Gordon 永续增长模型）")
    print(_kv(f"第 {n} 年 FCFF", f"{last.fcff:,.2f} 万元"))
    print(_kv(f"第 {n + 1} 年 FCFF = FCFF_{n}×(1+g)", f"{v.fcff_next:,.2f} 万元"))
    print(_kv(f"终值 TV = FCFF_{n + 1}/(WACC-g)", f"{v.terminal_value:,.2f} 万元"))
    print(_kv(f"终值折现因子 = 1/(1+WACC)^{n}", f"{last.discount_factor:.4f}"))
    print(_kv("终值现值 PV(TV)", f"{v.pv_terminal:,.2f} 万元"))
    print()

    # ---------------- 四、企业价值 ----------------
    ev = v.enterprise_value
    print("【四】企业价值（Enterprise Value）")
    print(_kv("预测期现值合计", f"{v.pv_explicit:,.2f} 万元"))
    print(_kv("终值现值", f"{v.pv_terminal:,.2f} 万元"))
    print("  " + "─" * 52)
    print(_kv("企业价值 EV", f"{ev:,.2f} 万元"))
    print()

    # ---------------- 五、结果校验 ----------------
    ebitda_last = last.ebit + last.da
    fcff_margin = (1.0 - a.tax_rate) + a.da_ratio - a.capex_ratio - a.nwc_ratio
    growth_total = (1.0 + a.ebit_growth) ** (a.forecast_years - 1) - 1.0

    print("【五】结果校验与关键比率")
    print(_kv("FCFF / EBIT（各年恒定）", f"{fcff_margin:.2%}"))
    print(_kv(f"第 1~{n} 年 FCFF 累计增长", f"{growth_total:.2%}"))
    print(_kv("终值占企业价值比重", f"{v.pv_terminal / ev:.2%}"))
    print(_kv("预测期现值占企业价值比重", f"{v.pv_explicit / ev:.2%}"))
    print(_kv(f"隐含退出倍数 TV / 第{n}年 EBITDA", f"{v.terminal_value / ebitda_last:.2f}x"))
    print(_kv("隐含 EV / 基期 EBIT", f"{ev / a.ebit_base:.2f}x"))
    print()

    # ---------------- 六、敏感性分析（可选） ----------------
    if SHOW_SENSITIVITY:
        print("【六】敏感性分析：企业价值 EV（万元）")
        print("  横轴为 WACC，纵轴为永续增长率 g；单元格为对应假设下的 EV")
        waccs = [a.wacc + d for d in (-0.02, -0.01, 0.0, 0.01, 0.02)]
        growths = [a.terminal_growth + d for d in (-0.01, 0.0, 0.01)]

        sens_headers = ["g \\ WACC"] + [f"{w:.2%}" for w in waccs]
        sens_rows: list[list[str]] = []
        for g in growths:
            row = [f"{g:.2%}"]
            for w in waccs:
                if w <= g:  # 分母不为正，模型不成立
                    row.append("—")
                else:
                    scenario = run_valuation(
                        replace(a, wacc=w, terminal_growth=g)
                    )
                    row.append(f"{scenario.enterprise_value:,.0f}")
            sens_rows.append(row)
        _print_table(sens_headers, sens_rows, ["left"] + ["right"] * len(waccs))
        print()

    # ---------------- 结论 ----------------
    print("【结论】")
    print(
        f"  在 WACC={a.wacc:.2%}、永续增长率 g={a.terminal_growth:.2%} 的假设下，"
        f"企业价值约为 {ev:,.2f} 万元，"
    )
    print(f"  相当于基期 EBIT 的 {ev / a.ebit_base:.2f} 倍。")
    print(
        "  注：EV 为企业整体价值（股权 + 有息负债）；如需股权价值，"
        "应在此基础上扣减净负债。"
    )
    print(rule)


# ===========================================================================
# 五、Excel 导出（pandas + openpyxl）
# ===========================================================================
def _require_pandas():
    """延迟导入 pandas，未安装时给出可操作的提示。"""
    try:
        import pandas as pd
    except ImportError as exc:
        raise SystemExit(
            "导出 Excel 需要 pandas 与 openpyxl，请先执行：pip install pandas openpyxl"
        ) from exc
    return pd


def _write_workbook(writer, v: Valuation) -> None:
    """把明细表与汇总表写入已打开的 ExcelWriter，并统一设置格式。

    文件导出（export_to_excel）与内存导出（excel_bytes）共用这段逻辑，
    保证两种方式产出的工作簿完全一致。
    """
    import pandas as pd
    from openpyxl.styles import Alignment, Font, PatternFill

    a = v.assumptions

    # ---------------- 工作表 1：预测期明细 ----------------
    detail = pd.DataFrame(
        {
            "年份": [r.year for r in v.rows],
            "EBIT（万元）": [r.ebit for r in v.rows],
            "FCFF（万元）": [r.fcff for r in v.rows],
            "折现现值（万元）": [r.pv for r in v.rows],
        }
    )

    # ---------------- 工作表 2：估值汇总 ----------------
    summary_rows = [
        ("基期 EBIT（第 0 年）", a.ebit_base, "万元"),
        ("预测期 EBIT 年增长率", a.ebit_growth, "%"),
        ("企业所得税率", a.tax_rate, "%"),
        ("折旧摊销 / EBIT", a.da_ratio, "%"),
        ("资本性支出 / EBIT", a.capex_ratio, "%"),
        ("营运资本增加 / EBIT", a.nwc_ratio, "%"),
        ("加权平均资本成本 WACC", a.wacc, "%"),
        ("永续增长率 g", a.terminal_growth, "%"),
        ("明确预测期", a.forecast_years, "年"),
        ("预测期现值合计", v.pv_explicit, "万元"),
        (f"终值 TV（第 {a.forecast_years} 年末）", v.terminal_value, "万元"),
        ("终值现值 PV(TV)", v.pv_terminal, "万元"),
        ("企业价值 EV", v.enterprise_value, "万元"),
    ]
    summary = pd.DataFrame(summary_rows, columns=["项目", "数值", "单位"])

    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill("solid", fgColor="4472C4")
    center = Alignment(horizontal="center", vertical="center")

    detail.to_excel(writer, sheet_name="预测期明细", index=False)
    summary.to_excel(writer, sheet_name="估值汇总", index=False)

    # ---- 明细表：列宽、千分位、表头样式、冻结首行 ----
    ws = writer.sheets["预测期明细"]
    for col, width in zip("ABCD", (10, 18, 18, 20)):
        ws.column_dimensions[col].width = width
    for cell in ws[1]:
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = center
    for row in ws.iter_rows(min_row=2, min_col=1, max_col=4):
        row[0].alignment = center                      # 年份居中
        for cell in row[1:]:                           # 数值列千分位 + 两位小数
            cell.number_format = "#,##0.00"
    ws.freeze_panes = "A2"

    # ---- 汇总表：按「单位」列决定数字格式 ----
    ws2 = writer.sheets["估值汇总"]
    for col, width in zip("ABC", (28, 18, 8)):
        ws2.column_dimensions[col].width = width
    for cell in ws2[1]:
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = center
    number_formats = {"%": "0.00%", "万元": "#,##0.00", "年": "0"}
    for idx, (_, _, unit) in enumerate(summary_rows, start=2):
        value_cell = ws2.cell(row=idx, column=2)
        value_cell.number_format = number_formats.get(unit, "General")
        value_cell.alignment = Alignment(horizontal="right")
    # 企业价值一行加粗，便于快速查看
    for col in range(1, 4):
        ws2.cell(row=1 + len(summary_rows), column=col).font = Font(bold=True)


def export_to_excel(v: Valuation, path: str | Path | None = None) -> Path | None:
    """把预测期明细导出为 Excel 文件，并附一张估值汇总表。

    参数
        v    : run_valuation() 返回的估值结果
        path : 目标文件路径；缺省为脚本所在目录下的 FCFF_valuation_result.xlsx

    返回
        实际写入的文件路径；若文件被占用等原因无法写入则返回 None。

    说明
        * 「预测期明细」工作表包含：年份、EBIT、FCFF、折现现值 四列；
        * 「估值汇总」工作表汇总关键假设与 EV，便于直接归档或引用；
        * 表中数值保留原始精度，仅通过单元格格式显示为两位小数。
    """
    pd = _require_pandas()

    target = Path(path) if path else Path(__file__).resolve().parent / EXCEL_FILENAME
    target.parent.mkdir(parents=True, exist_ok=True)

    try:
        with pd.ExcelWriter(target, engine="openpyxl") as writer:
            _write_workbook(writer, v)
    except PermissionError:
        # 常见原因：同名文件正在 Excel 中打开，Windows 会锁定写入
        print(f"\n[警告] 无法写入 {target}：文件可能正被 Excel 打开，请关闭后重新运行。")
        return None

    return target


def excel_bytes(v: Valuation) -> bytes:
    """在内存中生成工作簿字节流（Streamlit 下载按钮、接口返回等场景使用）。

    与 export_to_excel 使用同一套建表与格式逻辑，只是不落盘，因此不依赖临时目录。
    """
    pd = _require_pandas()

    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        _write_workbook(writer, v)
    return buffer.getvalue()


# ===========================================================================
# 六、程序入口
# ===========================================================================
def _force_utf8_stdout() -> None:
    """统一标准输出 / 错误输出编码为 UTF-8。

    Windows 控制台默认代码页可能是 GBK（cp936），在其他 UTF-8 终端或重定向
    到文件时容易出现中文乱码；这里主动切换到 UTF-8，失败则保持原样。
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            if (stream.encoding or "").lower().replace("-", "") != "utf8":
                stream.reconfigure(encoding="utf-8")
        except (AttributeError, OSError, ValueError):
            pass  # 极老版本 Python 或特殊重定向场景，忽略即可


def main() -> None:
    _force_utf8_stdout()

    # 默认参数即文件开头 Assumptions 中的设定：
    # EBIT=1000、税率 25%、EBIT 年增 5%、WACC 10%、g=2%、预测期 5 年
    assumptions = Assumptions()

    # 若想做情景测试，可改成例如：
    #   assumptions = Assumptions(wacc=0.09, terminal_growth=0.025)
    #   assumptions = Assumptions(ebit_base=1500, ebit_growth=0.08)

    valuation = run_valuation(assumptions)
    print_results(valuation)

    # 把屏幕上打印的预测期明细导出为 Excel（EXPORT_EXCEL=False 可关闭）
    if EXPORT_EXCEL:
        saved_path = export_to_excel(valuation)
        if saved_path is not None:
            print(f"\n已导出 Excel：{saved_path}")


if __name__ == "__main__":
    main()
