#!/usr/bin/env python3
"""
REPORT.pdf: final report on the AD9081 DAC model (stages 0 and 1).

    python3 make_report.py [results_dir] [-o ../REPORT.pdf]

The front matter (title, goal, model description, conclusions) is the Russian text below;
the numbers come from results/summary.md, which report.py writes after build.sh, so the
report is never out of date with the measurements.  Markdown is rendered with matplotlib
(DejaVu Sans has Cyrillic): headings, paragraphs, tables and the PNG figures.
"""
import argparse
import os
import re
import textwrap

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.backends.backend_pdf import PdfPages  # noqa: E402
import matplotlib.image as mpimg  # noqa: E402

A4 = (8.27, 11.69)
PDF_DPI = 300   # matplotlib resamples imshow() images to this dpi inside the PDF (default 100 blurs the plots)
L, R, TOP, BOT = 0.09, 0.95, 0.94, 0.07          # page margins in figure units
INK, MUTED, RULE = "#0b0b0b", "#52514e", "#c9c7c2"
FS = dict(h1=15, h2=12, body=8.6, table=7.0, cap=7.5)
LH = dict(h1=0.034, h2=0.026, body=0.0150, table=0.0135)

# Numbered captions, in the order the tables / figures occur in summary.md
TABLE_CAPS = [
    "Однотон, −7 dBFS: SFDR, гармоники, SNR и NSD по сценариям модели в сравнении с Table 16 даташита",
    "Двухтон, −6 dBFS на тон: IMD3 по сценариям модели в сравнении с Table 16 даташита",
    "Этап 1: SFDR, IMD3 и NSD полной модели ad9081, отклонение Δ от Table 16",
    "Однотон, −7 dBFS: SFDR и SNR при выключенном перемешивании, вращении и DWA",
    "Плотность шума по поддиапазонам 0…6 ГГц, тон 900 МГц, dBc/Hz",
    "Разброс характеристик по 20 наборам рассогласования сегментов: медиана (мин…макс)",
    "Влияние джиттера такта: измеренные и теоретические SNR, NSD и SFDR",
]
FIG_CAPS = {
    "sfdr_vs_fout.png": "SFDR всех сценариев модели в зависимости от fOUT; звёзды - Table 16 даташита",
    "imd3_vs_fout.png": "IMD3 всех сценариев модели в зависимости от fOUT; звёзды - Table 16 даташита",
    "stage1_dyn.png": "Этап 1: SFDR и IMD3 при перемешивании вращением без динамики, с динамикой и полной модели ad9081; "
                      "серая полоса - Table 16 ±3 дБ",
    "shuffle_bands.png": "Плотность шума по поддиапазонам при выключенном перемешивании, вращении и DWA",
    "seeds.png": "Разброс SFDR, SNR и IMD3 по 20 наборам рассогласования сегментов; линия - медиана",
    "snr_jitter.png": "SNR в зависимости от fOUT при разном джиттере такта и теоретическая зависимость",
    "nsd_jitter.png": "NSD в зависимости от fOUT при разном джиттере такта; звёзды - Table 16 даташита",
}

TITLE = "Моделирование ЦАП AD9081 в тракте DDS"
SUBTITLE = ("Нелинейность (статическая и динамическая), перемешивание сегментов,\n"
            "джиттер такта и тепловой шум.  Этапы 0 и 1")
AUTHOR = "Романюта М. В."

INTRO = [
    ("Задача", """
Проверить, чем в реальном ЦАП AD9081 (fDAC = 12 ГГц, 16 бит) задаются паспортные SFDR и IMD3
(Table 16 даташита), и получить модель DDS-тракта, которая воспроизводит эти числа. Модель
написана на Verilog, собирается Verilator'ом в библиотеку и работает внутри потокового графа
GNU Radio; измерения делает sfdr.py по когерентной записи (БПФ 32768, тон на нечётном бине).
"""),
    ("Модель", """
Тракт: DDS (48-битная фаза, ROM синуса AW=16, RW=20) -> dac_nonlin (полиномиальная INL
"дуга" и "S-кривая" + рассогласование 64 унарных сегментов + перемешивание) -> dac_dyn
(динамическая, зависящая от скорости нарастания нелинейность) -> dac_jitter (белый джиттер
такта) -> dac_noise (тепловой шумовой пол). Выход 20 бит: 16 бит кода и 4 дробных бита, чтобы
не терять доли МЗР ошибки.

Каждая точка считается дважды: через Verilog -> Verilator -> GNU Radio -> файл и побитовой
копией модели на Python (model_ref.py). Их расхождение (строка Chain check) - проверка того,
что цепочка сборки и записи ничего не искажает.
"""),
    ("Что показал этап 0", """
Статическая нелинейность по Table 3 (INL 8 МЗР, DNL 3.5 МЗР) без перемешивания даёт
SFDR 73...86 dBc (медиана 80.5 по 20 вариантам рассогласования сегментов) и IMD3 около
-86 dBc - то есть примерно как в даташите, но совсем не зависит от частоты. Джиттер такта
объясняет паспортную спектральную плотность шума (NSD от -168 до -154 dBc/Hz) при
σ ≈ 58 фс.

Как только включается перемешивание сегментов (а Table 16 измерена именно с ним), спуры от
рассогласования сегментов превращаются в шум: SFDR вырастает до 94 dBc, IMD3 до -87 dBc.
Модель становится на 17...18 дБ чище даташита. Значит, паспортные SFDR и IMD3 AD9081 задаёт
не статика, а динамическая нелинейность - этим и занят этап 1.
"""),
    ("Этап 1: динамическая нелинейность", """
Переключение токовых ячеек на каждом такте теряет заряд, и потеря зависит от того, насколько
и с какого уровня изменился выход. Модель dac_dyn добавляет к отсчёту

    e[n] = ( A·|dx| + B·dx·x + C·dx·x² + D·|dx|² + E·dx·|dx| + P2·x² + P3·x³ ) / 2^16,

где dx = x[n] - x[n-1], а x нормирован на полную шкалу. Такая ошибка растёт с частотой (|dx| ~ 2·sin(πf/fDAC)) -
именно этого не хватало статической модели.

План этапа предполагал только члены A и B. Но dx·x - это 0.5·d(x²)/dt, то есть член второго
порядка: он даёт HD2 и не даёт продукта 2f1-f2, поэтому IMD3 им не задать. Нечётные члены C и
E добавлены именно для IMD3. Кроме того, члены ~|dx| растут с частотой только в 1.9 раза
(5.6 дБ) на диапазоне 70 МГц...4.5 ГГц, а Table 16 требует спада в 12 дБ, поэтому добавлены
члены D и E, квадратичные по скорости нарастания.

Члены P2 и P3 - это безынерционное искажение аналогового выходного каскада, а не ЦАП: все
члены со скоростью обращаются в ноль на низкой частоте, а Table 16 показывает на 70 МГц 80 dBc,
то есть «полку», не зависящую от частоты. Полиномиальной INL по Table 3 (8 МЗР, и та почти
целиком уходит на рассогласование сегментов) для такой полки не хватает: с перемешиванием она
даёт HD2 около -93 dBc. Поэтому полка вынесена в отдельный блок - выходной каскад, который
ни Table 3, ни перемешивание не ограничивают.

Коэффициенты подбираются скриптом fit_dyn.py. Ошибка линейна по каждому коэффициенту, поэтому
подгонка не перезапускает модель: базисные сигналы ошибки считаются один раз, дальше спектр
любого набора коэффициентов - взвешенная сумма. Вместе с коэффициентами подгоняется и доля
полиномиальной INL: члены скорости обращаются в ноль на низкой частоте и не могут дать 80 dBc,
которые Table 16 показывает на 70 МГц, - этот «полочный» уровень задаёт именно гладкая INL,
которую перемешивание не трогает.
"""),
]

OUTRO = [
    ("Выводы", """
1. Статическая нелинейность Table 3 объясняет паспортный SFDR только при выключенном
   перемешивании сегментов. С перемешиванием (условия Table 16) она на 17...18 дБ чище
   даташита и не зависит от частоты.
2. Паспортные SFDR и IMD3 AD9081 задаёт динамическая нелинейность - ошибка переключения,
   пропорциональная шагу выхода, плюс «полка» от выходного каскада на низких частотах.
   Семи членов хватает, чтобы пройти Table 16 по SFDR и IMD3 с запасом: расхождение не
   превышает 2 дБ при критерии ±3 дБ.
3. Перемешивание вращением даёт +13 дБ SFDR на всех вариантах рассогласования ценой -16.6 дБ
   SNR; DWA переносит ошибку к fDAC/2 и для AD9081 не подходит (тон указателя на 31.5/64·fDAC).
4. Джиттер такта σ ≈ 58 фс и тепловой пол -168 dBc/Hz воспроизводят паспортную NSD.
"""),
    ("Ограничения", """
Джиттер белый - фазового шума у несущей в модели нет. Разнос двухтонового сигнала 0.73 МГц
вместо 1 МГц (когерентность БПФ). Значения рис. 30 даташита сняты с графика, ±1 дБ.
Коэффициенты dac_dyn - подгонка под Table 16, а не измерение конкретной микросхемы: они
воспроизводят паспорт, но не выводятся из физики переключения.
"""),
]



# ----------------------------------------------------------------- markdown -> blocks
def plain(t):
    """markdown inline marks are not rendered, so drop them"""
    t = re.sub(r"\*\*(.+?)\*\*", r"\1", t)
    return t.replace("`", "")


def parse_md(path):
    """[('h1'|'h2'|'p'|'table'|'img', payload), ...]"""
    out, rows, para = [], [], []

    def flush_p():
        if para:
            out.append(("p", " ".join(para)))
            para.clear()

    def flush_t():
        if rows:
            out.append(("table", [r for r in rows if not re.fullmatch(r"[-| :]+", "|".join(r))]))
            rows.clear()

    for line in open(path):
        t = line.rstrip("\n")
        if t.startswith("|"):
            flush_p()
            rows.append([plain(c.strip()) for c in t.strip("|").split("|")])
            continue
        flush_t()
        m = re.match(r"!\[.*?\]\((.+?)\)", t)
        if m:
            flush_p(); out.append(("img", m.group(1)))
        elif t.startswith("## "):
            flush_p(); out.append(("h2", plain(t[3:])))
        elif t.startswith("# "):
            flush_p(); out.append(("h1", plain(t[2:])))
        elif t.strip():
            para.append(plain(t.strip()))
        else:
            flush_p()
    flush_p(); flush_t()
    return out


# ----------------------------------------------------------------- page machinery
class Book:
    png_dir = None

    def __init__(self, pdf):
        self.pdf, self.ax, self.y, self.n = pdf, None, 0.0, 0
        self.new_page()

    def new_page(self):
        if self.ax is not None:
            self._emit()
        fig = plt.figure(figsize=A4)
        self.ax = fig.add_axes([0, 0, 1, 1]); self.ax.axis("off")
        self.ax.set_xlim(0, 1); self.ax.set_ylim(0, 1)
        self.y, self.n = TOP, self.n + 1

    def need(self, h):
        if self.y - h < BOT:
            self.new_page()

    def text(self, s, kind="body", color=INK, weight="normal", indent=0.0):
        self.need(LH[kind] * 1.4)
        self.ax.text(L + indent, self.y, s, fontsize=FS[kind], color=color, weight=weight,
                     va="top", ha="left", family="DejaVu Sans")
        self.y -= LH[kind]

    def heading(self, s, kind="h2"):
        self.need(0.09)
        self.y -= 0.012
        for ln in textwrap.wrap(s, 62 if kind == "h2" else 50):   # long headings must not run off
            self.text(ln, kind, weight="bold")
        if kind == "h2":
            self.ax.plot([L, R], [self.y + 0.006] * 2, color=RULE, lw=0.7)
        self.y -= 0.010

    def para(self, s, width=96):
        for block in s.strip("\n").split("\n\n"):
            if block.lstrip().startswith(("e[n]", "    ")):          # formula / preformatted
                for ln in block.split("\n"):
                    self.text(ln, "body", color=MUTED)
                self.y -= 0.008
                continue
            # a numbered list keeps one item per paragraph, with a hanging indent
            lst = re.match(r"\s*\d+\. ", block) is not None
            items = re.split(r"\n(?=\d+\. )", block) if lst else [block]
            for it in items:
                for i, ln in enumerate(textwrap.wrap(" ".join(it.split()), width)):
                    self.text(ln, "body", indent=0.016 if (lst and i) else 0.0)
                self.y -= 0.004
            self.y -= 0.006

    def caption(self, s, center=False):
        lines = textwrap.wrap(s, 104)
        for ln in lines:
            self.need(LH["body"] * 1.4)
            if center:
                self.ax.text((L + R) / 2, self.y, ln, fontsize=FS["cap"], color=MUTED, va="top", ha="center")
            else:
                self.ax.text(L, self.y, ln, fontsize=FS["cap"], color=MUTED, va="top", ha="left")
            self.y -= LH["body"]

    def table(self, rows, caption=None):
        if not rows:
            return
        ncol = max(len(r) for r in rows)
        rows = [r + [""] * (ncol - len(r)) for r in rows]
        w = [max(len(r[c]) for r in rows) for c in range(ncol)]
        scale = min(1.0, 96.0 / max(1, sum(w) + 3 * ncol))
        ncap = len(textwrap.wrap(caption, 104)) if caption else 0
        self.need(LH["table"] * (len(rows) + 2) + LH["body"] * (ncap + 1))
        if caption:
            self.caption(caption)
            self.y -= 0.004
        x0 = L
        xs, tot = [], sum(w) + 2 * ncol
        for c in range(ncol):
            xs.append(x0)
            x0 += (R - L) * (w[c] + 2) / tot
        fs = FS["table"] * max(scale, 0.72)

        def row(r, head):
            for c in range(ncol):
                self.ax.text(xs[c], self.y, r[c], fontsize=fs, color=INK if head else MUTED,
                             weight="bold" if head else "normal", va="top", ha="left")
            self.y -= LH["table"]
            if head:                                   # rule under the header
                self.ax.plot([L, R], [self.y + 0.004] * 2, color=RULE, lw=0.6)
                self.y -= 0.004

        row(rows[0], True)
        for r in rows[1:]:
            if self.y - LH["table"] < BOT:
                self.new_page()
                row(rows[0], True)                     # a table split over pages repeats its header
            row(r, False)
        self.y -= 0.010

    def image(self, path, caption=""):
        if not os.path.exists(path):
            return
        im = mpimg.imread(path)
        aspect = im.shape[0] / im.shape[1]
        w = R - L
        h = w * aspect * A4[0] / A4[1]
        ncap = len(textwrap.wrap(caption, 104)) if caption else 0
        if self.y - h - LH["body"] * ncap < BOT:
            self.new_page()
        ax = self.ax.figure.add_axes([L, self.y - h, w, h])
        ax.imshow(im); ax.axis("off")
        self.y -= h + 0.006
        if caption:
            self.caption(caption, center=True)
        self.y -= 0.012

    def _emit(self):
        f = self.ax.figure
        self.ax.text(0.5, 0.035, str(self.n), ha="center", fontsize=7, color=MUTED)
        self.pdf.savefig(f, dpi=PDF_DPI)
        if Book.png_dir:
            f.savefig(os.path.join(Book.png_dir, f"page_{self.n + 1}.png"), dpi=150)
        plt.close(f)

    def close(self):
        self._emit()


def title_page(pdf, res, png_dir=None):
    fig = plt.figure(figsize=A4)
    for i, ln in enumerate(textwrap.wrap(TITLE, 34)):
        fig.text(L, 0.88 - i * 0.045, ln, fontsize=21, weight="bold", color=INK, va="top")
    fig.text(L, 0.78, SUBTITLE, fontsize=10.5, color=MUTED, va="top", linespacing=1.6)
    fig.add_artist(plt.Line2D([L, R], [0.735] * 2, color=RULE, lw=1, transform=fig.transFigure))
    fig.text(L, 0.715, AUTHOR, fontsize=10, color=INK, va="top")
    fig.text(L, 0.687, "Verilog \u2192 Verilator \u2192 GNU Radio \u2192 sfdr.py;   "
             "AD9081 Rev.0, fDAC = 12 \u0413\u0413\u0446", fontsize=9, color=MUTED, va="top")
    q = os.path.join(res, "sfdr_vs_fout.png")
    if os.path.exists(q):
        im = mpimg.imread(q)
        h = (R - L) * im.shape[0] / im.shape[1] * A4[0] / A4[1]
        a = fig.add_axes([L, 0.60 - h, R - L, h])
        a.imshow(im); a.axis("off")
        fig.text(L, 0.60 - h - 0.02, "SFDR всех сценариев модели рядом с Table 16 даташита",
                 fontsize=8, color=MUTED, va="top")
    pdf.savefig(fig, dpi=PDF_DPI)
    if png_dir:
        fig.savefig(os.path.join(png_dir, "page_1.png"), dpi=150)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("results", nargs="?", default="results")
    ap.add_argument("-o", "--out", default=os.path.join("..", "REPORT.pdf"))
    ap.add_argument("--png", help="also write every page as <dir>/page_N.png (for checking)")
    a = ap.parse_args()
    res = a.results
    md = parse_md(os.path.join(res, "summary.md"))

    if a.png:
        os.makedirs(a.png, exist_ok=True)
        Book.png_dir = a.png
    with PdfPages(a.out) as pdf:
        title_page(pdf, res, a.png)
        b = Book(pdf)
        for h, t in INTRO:
            b.heading(h)
            b.para(t)
        b.new_page()
        b.heading("Результаты измерений", "h1")
        b.para("Ниже - вывод report.py по последнему прогону build.sh: таблицы и графики "
               "по всем сценариям модели рядом со значениями Table 16 даташита.")
        nt = nf = 0
        for kind, payload in md:
            if kind == "h1":
                continue
            if kind == "h2":
                b.heading(payload)
            elif kind == "p":
                b.para(payload)
            elif kind == "table":
                nt += 1
                cap = TABLE_CAPS[nt - 1] if nt <= len(TABLE_CAPS) else ""
                b.table(payload, f"Таблица {nt} - {cap}" if cap else None)
            elif kind == "img":
                nf += 1
                cap = FIG_CAPS.get(payload, "")
                b.image(os.path.join(res, payload), f"Рисунок {nf} - {cap}" if cap else "")
        b.new_page()
        for h, t in OUTRO:
            b.heading(h)
            b.para(t)
        b.close()
    print(f"wrote {a.out}")


if __name__ == "__main__":
    main()
