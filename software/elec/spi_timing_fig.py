"""SPI signal investigation (2026-11-04): why a late falling DATA edge corrupts the SK9822 brightness byte at 4 MHz but
not at 1 MHz, while 0x00 / 0xFF colour bytes survive. -> docs/img/spi_late_fall.svg/.png
Run: py software/elec/spi_timing_fig.py

Illustration, not a measurement. DATA at the strip's DI pad is drawn two ways that both read field 22 at 4 MHz:
a series resistance (rise = fall, tau = 200 ns, e.g. about 6.8 kohm into about 30 pF, which needs a low switching point
like the 1.5 V drawn) and a weak pull-down (rise 5 ns, fall tau = 200 ns, which reads the same at any switching point;
calc/spi_bit_model.py has the fits). The design path, 68 ohm + the buffer's ~25 ohm into the same 30 pF, has tau ~3 ns:
a vertical edge at this scale. SPI mode 0: DATA changes on the CLK falling edge, the SK9822 samples it on the next
rising edge, half a period later.
"""
import math
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

OUT = os.path.join(os.path.dirname(__file__), "..", "..", "docs", "img")
TAU, TAU_RISE_WEAK, VTH, VDD = 200.0, 5.0, 1.5, 5.0
# the last 4 bits of the 32-bit start frame, the header 0xE4 (field 4), the first 4 bits of B (0x00)
BITS = [0, 0, 0, 0] + [1, 1, 1, 0, 0, 1, 0, 0] + [0, 0, 0, 0]
HDR0 = 4


def waves(period_ns, dt=0.5):
    n = int(len(BITS) * period_ns / dt)
    t, clk, ideal, real, weak = [], [], [], [], []
    v = w = 0.0
    for i in range(n):
        tt = i * dt
        b = BITS[min(int(tt // period_ns), len(BITS) - 1)]
        target = VDD * b
        v += (target - v) * (1 - math.exp(-dt / TAU))
        w += (target - w) * (1 - math.exp(-dt / (TAU_RISE_WEAK if target > w else TAU)))
        t.append(tt / 1000.0)
        clk.append(VDD if (tt % period_ns) >= period_ns / 2 else 0.0)
        ideal.append(target)
        real.append(v)
        weak.append(w)
    return t, clk, ideal, real, weak


def panel(ax, mhz):
    period = 1000.0 / mhz
    t, clk, ideal, real, weak = waves(period)
    off = 6.5
    ax.plot(t, [c + off for c in clk], color="#c9a400", lw=1.6, label="CLK at CI")
    ax.plot(t, ideal, color="#999", lw=1.0, ls="--", label="DATA as sent (and with 68 ohm: tau ~3 ns)")
    ax.plot(t, real, color="#e06000", lw=2.0, label="DATA at DI, series R (rise = fall, tau 200 ns)")
    ax.plot(t, weak, color="#7a0000", lw=1.4, ls=(0, (4, 2)), label="DATA at DI, weak pull-down (rise 5 ns, fall tau 200 ns)")
    ax.axhline(VTH, color="#2060a0", lw=0.9, ls=":", label="switching point 1.5 V")
    read = []
    for i, b in enumerate(BITS):
        ts = (i + 0.5) * period
        k = int(ts / 0.5)
        r = 1 if real[min(k, len(real) - 1)] > VTH else 0
        assert r == (1 if weak[min(k, len(weak) - 1)] > VTH else 0), "the two DATA shapes should read alike at 1.5 V"
        read.append(r)
        x = ts / 1000.0
        ax.axvline(x, color="#bbb", lw=0.6, zorder=0)
        if HDR0 <= i < HDR0 + 8:
            bad = r != b
            ax.text(x, -1.3, str(r), ha="center", va="center", fontsize=11, weight="bold", color="#c00000" if bad else "#1a1a1a")
            ax.text(x, -2.4, str(b), ha="center", va="center", fontsize=9, color="#666")
    hdr = read[HDR0:HDR0 + 8]
    field = int("".join(map(str, hdr[3:])), 2)
    ax.text(t[-1] * 1.005, -1.3, "read", fontsize=8.5, va="center")
    ax.text(t[-1] * 1.005, -2.4, "sent", fontsize=8.5, va="center", color="#666")
    x0, x1 = HDR0 * period / 1000.0, (HDR0 + 8) * period / 1000.0
    ax.annotate("", xy=(x0, 12.6), xytext=(x1, 12.6), arrowprops=dict(arrowstyle="<->", color="#444", lw=0.9))
    ax.text((x0 + x1) / 2, 13.2, "header byte 0xE4 = 111 + field 00100 (4)", ha="center", fontsize=9)
    verdict = ("read 1111 0110: field %d instead of 4 (%.1fx the current); the 0x00 bytes after it read right" % (field, field / 4.0)
               if field != 4 else "read 1110 0100: field 4, every bit right")
    ax.set_title("%g MHz (half period %g ns between a DATA change and the sampling edge): %s" % (mhz, period / 2, verdict),
                 fontsize=10, loc="left")
    ax.set_ylim(-3.0, 14.2)
    ax.set_yticks([0, VTH, VDD, off, off + VDD])
    ax.set_yticklabels(["0", "1.5", "5 V", "CLK 0", "5 V"], fontsize=8)
    ax.set_xlim(0, t[-1])
    ax.set_xlabel("time, us", fontsize=9)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    return ax


fig, axes = plt.subplots(2, 1, figsize=(12.5, 8.6))
panel(axes[0], 4)
panel(axes[1], 1)
handles, labels = axes[0].get_legend_handles_labels()
fig.legend(handles, labels, loc="upper left", bbox_to_anchor=(0.01, 0.955), ncol=3, frameon=False, fontsize=8.5)
fig.suptitle("A late falling DATA edge flips only the bits right after a 1-to-0 step: the brightness field, not the 0x00/0xFF colours",
             fontsize=11.5, weight="bold", x=0.01, ha="left")
fig.text(0.01, 0.005, "Illustration: both DATA shapes read these bits at a 1.5 V switching point; the weak pull-down reads the same at any switching point, "
         "the series R only at about 2.2 V or below. fig. spi_late_fall, 2026-11-04, software/elec/spi_timing_fig.py",
         fontsize=7.5, color="#666")
fig.tight_layout(rect=(0, 0.02, 1, 0.91))
os.makedirs(OUT, exist_ok=True)
for ext in ("svg", "png"):
    fig.savefig(os.path.join(OUT, "spi_late_fall." + ext), dpi=130)
print("wrote", os.path.join(OUT, "spi_late_fall.png"))
