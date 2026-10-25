# build.sh — инструкция

`build.sh` прогоняет все тесты модели ЦАП AD9081. Для каждого сценария и каждой частоты он делает четыре шага:

```
dds_gr_all.v ──Verilator──► libdds.dylib ──GNU Radio (dds.grc)──► *.bin ──sfdr.py──► results.csv
                                                                          └─model_ref.py──► reference.csv
```

В конце `report.py` собирает всё в `results/summary.md` и строит графики.

---

## 1. Что нужно установить

| программа | зачем | проверка |
|---|---|---|
| Verilator | собирает Verilog в библиотеку | `verilator --version` |
| GNU Radio (`grcc`) | запускает `dds.grc` | `grcc --version` |
| Python с numpy, pandas, matplotlib | измерения и отчёт | `python -c "import numpy, pandas, matplotlib"` |

На маке используй Python из radioconda: `conda activate` или `PY=~/radioconda/bin/python`. Системный `python3` не подойдёт, в нём нет numpy.

## 2. Где что лежит

```
<папка проекта>/
├── dds_gr_all.v        модель (DDS + dac_nonlin + dac_jitter)
├── wrapper.cpp         обёртка Verilator → GNU Radio
├── dds.grc             граф GNU Radio (File Sink, тип int)
├── obj_dir/            сюда Verilator кладёт libdds.dylib
└── scripts/
    ├── build.sh        ← запускать отсюда
    ├── sfdr.py         измеритель: SFDR, HD2, HD3, IMD3, SNR, NSD
    ├── model_ref.py    эталон: побитовая копия Verilog на Python
    ├── report.py       таблицы и графики
    └── results/        результаты (создаётся сам)
```

Скрипт сам находит:
- **Python**: сначала пробует `python`, потом `python3`, и берёт тот, где есть numpy;
- **путь File Sink**: читает поле `file:` блока `blocks_file_sink` из `dds.grc`.

Оба значения печатаются в первой строке вывода. Если что-то не так, проверь сначала её.

## 3. Запуск

```bash
cd scripts
./build.sh                                   # всё: 11 сценариев, ~106 точек
QUICK=1 ./build.sh                           # быстро: 3 частоты + 1 двухтон на сценарий
ONLY="ideal full" ./build.sh                 # только перечисленные сценарии
ONLY="ideal jit25 jit50 jit100 jit200 full_jit50" ./build.sh   # только джиттер
QUICK=1 ONLY="ideal" ./build.sh              # проверка, что всё живо (~30 с)
```

Одна точка — это сборка в Verilator плюс прогон GNU Radio, примерно 5–10 секунд. Полный прогон занимает 10–20 минут.

### Переменные окружения

Их задают перед командой: `ИМЯ=значение ./build.sh`.

| переменная | по умолчанию | что задаёт |
|---|---|---|
| `ONLY` | все | список сценариев через пробел |
| `QUICK` | 0 | `1` — урезанный набор частот |
| `SRC` | папка выше `scripts/` | где лежат `dds_gr_all.v`, `wrapper.cpp` |
| `GRC` | `$SRC/dds.grc` | граф GNU Radio |
| `RAW` | из `dds.grc` | файл, который пишет File Sink |
| `MDIR` | `$SRC/obj_dir` | куда собирать библиотеку |
| `LIB` | `libdds.dylib` (macOS) / `libdds.so` | имя библиотеки, которую грузит GNU Radio |
| `PY` | ищется сам | конкретный Python |
| `DTYPE` | `int32` | тип элемента File Sink (`int` в GRC = `int32`) |
| `RES` | `scripts/results` | папка результатов |

## 4. Сценарии

Список задан в массиве `SCENARIOS` внутри `build.sh`, в формате `имя|параметры Verilog`:

| сценарий | что моделирует |
|---|---|
| `ideal` | идеальный ЦАП, только квантование 16 бит (пол модели) |
| `aw14` | идеальный ЦАП, ROM синуса 14 бит (спуры усечения фазы ≈ 80 dBc) |
| `inl2` | INL «дуга» 8 LSB → HD2 |
| `inl3` | INL «S-кривая» 8 LSB → HD3 |
| `dnl` | рассогласование 64 сегментов, DNL 3.5 LSB |
| `full` | всё вместе, INL ≈ 8 LSB + DNL 3.5 LSB (Table 3) |
| `jit25` … `jit200` | идеальный ЦАП + джиттер такта 25/50/100/200 fs rms |
| `full_jit50` | `full` + джиттер 50 fs |
| `dyn` | статика + динамическая (от скорости нарастания) нелинейность, shuffle выключен |
| `shuf_rot_dyn` | условия Table 16: вращение сегментов + динамическая нелинейность |
| `ad9081` | полная модель: статика + вращение + динамика + джиттер 58 fs + тепловой пол |

**Как добавить свой сценарий** — дописать строку в `SCENARIOS`:
```bash
  "big_s|NONLIN=1 INL2_Q=0 INL3_Q=320 DNL_Q=0"      # S-кривая 20 LSB
  "seed3|NONLIN=1 INL2_Q=48 INL3_Q=48 DNL_Q=56 SEED=3"
  "jit60|NONLIN=0 JIT_FS=60"
```

Параметры сценария перекрывают общие. Основные:

| параметр | смысл | единицы |
|---|---|---|
| `NONLIN` | 0 — идеальный ЦАП, 1 — с нелинейностью | — |
| `INL2_Q`, `INL3_Q` | высота дуги и S-кривой | 1/16 LSB (128 = 8 LSB) |
| `DNL_Q` | максимальный DNL сегментов | 1/16 LSB (56 = 3.5 LSB) |
| `SEED` | «какая микросхема»: набор ошибок сегментов | — |
| `JIT_FS` | джиттер такта, rms | фемтосекунды |
| `AW` | разрядность адреса ROM синуса | бит |
| `DYN_A_Q` … `DYN_E_Q` | динамическая нелинейность: члены при \|dx\|, dx·x, dx·x², \|dx\|², dx·\|dx\| | 1/2¹⁶ |
| `DYN_P2_Q`, `DYN_P3_Q` | безынерционное искажение выходного каскада: x², x³ | 1/2¹⁶ |
| `NOISE_Q` | тепловой шумовой пол, rms (115 → −168 dBc/Hz при 0 dBFS) | 1/16 МЗР |
| `FDAC_MHZ` | частота такта ЦАП (масштаб джиттера) | МГц |

Динамическая нелинейность (`dac_dyn`) добавляет к отсчёту

```
e[n] = ( A·|dx| + B·dx·x + C·dx·x² + D·|dx|² + E·dx·|dx| + P2·x² + P3·x³ ) / 2^16,  dx = x[n]−x[n−1]
```

x нормирован на полную шкалу. Члены A…E растут с частотой (`|dx| ≈ 2·sin(πf/fDAC)`), P2/P3 — нет.
Выход модуля комбинационный, поэтому задержка конвейера не меняется и привязка `PIPE`/`DELAY`
для эталона shuffle остаётся прежней.

Если в параметрах есть `JIT_FS`, сценарий считается джиттерным. Для него:
- эталон `model_ref.py` не вызывается (в нём нет модели джиттера);
- двухтон не прогоняется, только однотон (меряем SNR).

## 5. Точки измерений

Частоты взяты из AD9081 Table 16 (fDAC = 12 GSPS). Тон ставится на ближайший нечётный бин M = fOUT·32768/12000:

| режим | частоты, МГц | уровень |
|---|---|---|
| однотон (SFDR, HD2, HD3, SNR) | 70, 100, 500, 900, 1900, 2600, 3700, 4500 | −7 dBFS |
| двухтон (IMD3) | 1900, 2600, 3700; второй тон на 2 бина выше (0.73 МГц) | −6 dBFS на тон |

Изменить можно в начале `build.sh`: `FOUT_1T`, `FOUT_2T`, `SPACING`.

## 6. Результаты

```
results/
├── summary.md           главная таблица + проверка цепочки
├── results.csv          все измерения (одна строка = одна точка)
├── reference.csv        те же точки из model_ref.py
├── sfdr_vs_fout.png     SFDR от частоты vs Table 16
├── stage1_dyn.png       этап 1: SFDR и IMD3 модели с динамикой vs Table 16 ±3 дБ
├── dyn_fit.json         подобранные коэффициенты dac_dyn
├── imd3_vs_fout.png     IMD3 от частоты vs Table 16
├── snr_jitter.png       SNR от частоты для джиттерных сценариев + теория
├── nsd_jitter.png       NSD модели vs Table 16 + подбор σ по даташиту
├── inl_dnl_<сценарий>.png   форма INL/DNL сценария
├── raw/<сценарий>_M<..>.bin сырые записи (можно переизмерить)
├── meas/                текстовый вывод измерителя по каждой точке
└── logs/                логи Verilator и GNU Radio
```

### Как читать `summary.md`

1. **Строка `Chain check`** — главная проверка. Измерение после GNU Radio сравнивается с эталоном:
   - `0.000 dB (OK)` — цепочка Verilog → Verilator → GNU Radio → файл ничего не искажает;
   - `MISMATCH` — что-то не так в обёртке, File Sink или `SKIP` (см. раздел 8).

   Джиттерные сценарии в проверке не участвуют.
2. **Однотон / двухтон** — SFDR, HD2, HD3, IMD3 рядом со значениями Table 16.
3. **Clock jitter** — для каждой σ и частоты:
   - `SNR` — измерено;
   - `theory` — −20·lg(2πfσ·sinc) вместе с шумом квантования;
   - `Δ` — разница, должна быть около 0;
   - `σ from SNR` — σ, восстановленная из измерения, должна совпасть с заданной;
   - внизу — σ, подобранная по NSD из даташита (≈ 58 fs).

### Ориентиры (если числа другие — что-то сломано)

| что | ожидается |
|---|---|
| `ideal`: SFDR / SNR | 119.1 dBc / 91.1 дБ на всех частотах |
| `aw14`: SFDR | 80.4 dBc |
| `inl2`: HD2 | −85.3 dBc |
| `inl3`: HD3 / IMD3 | −90.0 / −78.5 dBc |
| `jit50`: SNR на 70 / 900 / 3700 МГц | 89.0 / 71.0 / 60.1 дБ |

## 7. Отдельные инструменты

```bash
# подобрать коэффициенты dac_dyn под Table 16 (секунды: ошибка линейна по коэффициентам)
python fit_dyn.py --json results/dyn_fit.json

# собрать итоговый отчёт в PDF из results/summary.md и графиков
python make_report.py results -o ../REPORT.pdf
```


```bash
# переизмерить одну запись
python sfdr.py results/raw/full_M2457.bin --m 2457
python sfdr.py results/raw/full_M5189_M5191.bin --m 5189 --m2 5191

# ожидаемый результат точки без GNU Radio (эталон)
python model_ref.py --params "NONLIN=1" --m 2457

# реальные INL/DNL сценария + график
python model_ref.py --params "NONLIN=1 SEED=3" --inl-dnl --plot inl.png

# пересобрать отчёт по уже готовым results/
python report.py results
```

## 8. Если что-то пошло не так

| симптом | причина и что делать |
|---|---|
| `No module named 'numpy'` | не тот Python → `conda activate` или `PY=~/radioconda/bin/python ./build.sh` |
| `...f32_IMD3.bin was not written` | граф не отработал. Скрипт печатает хвост лога GNU Radio — смотри туда. Частая причина — блок с неправильным значением (например, `Vector Source` типа int с комплексным вектором: поставь `(0,)`) |
| `File Sink path not found in dds.grc` | в `dds.grc` нет `blocks_file_sink` с полем `file:` → задай `RAW=/путь/к/файлу ./build.sh` |
| `verilator failed (<id>)` | ошибка в Verilog. Подробности в `results/logs/build_<id>.log` |
| `unknown parameter ...` от `model_ref.py` | в сценарии параметр, которого нет в эталоне. Для джиттера уже обрабатывается; для новых параметров добавь их в `DEFAULTS` в `model_ref.py` или пропусти эталон |
| `Chain check ... MISMATCH` | выход GNU Radio не совпадает с моделью: проверь тип File Sink (`int`), что `wrapper.cpp` пишет `io_out` целиком, и `SKIP` |
| `WARNING ... leakage around bin` | запись не когерентна: в начале остался переходный процесс (увеличь `SKIP`) или неверный `M` |
| `WARNING ... samples at full scale` | клиппинг или неверный `--bits` (должно быть `DW−1+FRAC` = 19) |
