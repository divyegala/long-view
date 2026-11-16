# Long View

A local cycling dashboard built around one question: **Am I becoming a better rider?**

Track sustained power, repeated work, and useful power after accumulated load. Compare each ride with personal history rather than judging progress through one FTP number.

## Run

Requires Python 3.10+. The interface needs no JavaScript build or external chart service.

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
export LONG_VIEW_TIMEZONE=America/Los_Angeles  # use your timezone
.venv/bin/python server.py --open
```

Open <http://127.0.0.1:8765>. On Windows use `.venv\Scripts\python`. The macOS launcher is `Start Long View.command`.

Import FIT/ZIP recordings or connect directly to Intervals.icu through **Data & downloads**. An agent can also fetch permitted data through any ride-data MCP and use the [neutral import contract](docs/data-sources.md). Built-in direct access covers Intervals.icu; other MCP connections are used by the agent, not by the browser.

For a complete synthetic demo:

```sh
.venv/bin/python examples/make_demo.py
.venv/bin/python import_rides.py data/demo-bundle.json --data-dir data/demo
LONG_VIEW_DATA_DIR=data/demo .venv/bin/python server.py --port 8766 --open
```

## Philosophy

- **A power curve has depth.** One peak misses the ability to repeat work and sustain power late.
- **Compare like opportunities.** Routes, intent, duration, cooling and preceding work affect performance. An easy ride does not test maximal capacity.
- **Keep watts real.** Indoor and outdoor rides share a history. Their FTP references can differ for workload cost; measured aerobic watts are never scaled by an FTP ratio.
- **Keep recovery visible.** Confirmed recording gaps remain zero-power stops on the elapsed clock. Missing power at a recorded timestamp stays unknown.
- **Show evidence.** These are descriptive measures and experimental workload proxies, not measured physiological fatigue or an automatic FTP diagnosis.

## Reading the charts

Choose **3, 5, 8, 10, 15, 20, 30, 45 or 60 minutes**. Selection updates power and late-power cards, their trends, and Power later in the ride. The duration comparison shows all nine. **Late starts** selects after 1h, 2h, 3h, etc. and updates the late-power cards and trends together.

All examples below are hypothetical. Percentages in the duration bars compare with the median of earlier rides under the same conditions.

| View | Meaning | Example |
| --- | --- | --- |
| **Best** | Highest complete rolling average power at each duration. | Your strongest 20-minute average is 200 W; the prior-ride median is 180 W. The bar shows **+11%**. |
| **Repeated** | Mean of the strongest three greedily selected, non-overlapping blocks. All three must exist; they can be pieces of one longer effort. | Three 10-minute blocks at 210, 200 and 190 W give **200 W**. With only two available blocks, Repeated is unavailable. |
| **Late** | Best complete effort starting at the selected elapsed hour or later. Default: after 1h. | For 20 minutes after 2h, a 185 W block from 2:10–2:30 qualifies. A 210 W block at 0:40 does not. A 45-minute effort after 2h needs at least 2h45 of recording. |
| **Under load** | Three panels show best efforts beginning at low, moderate and high modeled burden. Each compares against prior efforts beginning in the same band. | High-load 20-minute power of 190 W versus a prior high-load median of 180 W shows **+6%** in the high panel. It is not compared with fresh efforts, and high-load starts are never discarded. |
| **Power later in the ride — By elapsed hour** | Best full effort after each hour cutoff, divided by that ride's overall best at the same duration. | Best 20-minute power is 200 W overall, 190 W after 1h and 180 W after 2h: points are **100%, 95%, 90%**. |
| **Power later in the ride — By modeled load** | Power retained in each starting-load band, divided by that ride's overall best at the chosen duration. | Best 20-minute power is 200 W; best high-load power is 180 W. The high-load point is **90%**. |
| **Work across power levels** | Cumulative minutes at or above each wattage per moving hour. Above-FTP view uses each environment's reference. | Twelve minutes at or above 200 W in two moving hours gives **6 min/h** at 200 W. |

The **Repeated 3-min power** marker stays fixed at three minutes: blocks at 240, 230 and 220 W give 230 W. **Repeatability** counts all above-FTP minutes per moving hour: twenty hard minutes in two moving hours gives 10 min/h. It does not count intentional intervals.

### What “after an hour” means

These are cumulative start cutoffs: **after 1h** searches from 1:00 onward, **after 2h** from 2:00 onward, and so on. They are not separate 1:00–2:00 buckets. Every second of the selected effort must fit in the recording; unavailable efforts remain missing rather than zero. On a 2h15 ride, after-2h power can exist for a 10-minute effort but not for a 20-minute effort.

The clock is **elapsed time**, including stops. A 30-minute stop advances the hour marker and permits modeled recovery. Hour markers match time into a ride, not equal fatigue. Use Under load alongside them to inspect the effect of preceding intensity and recovery.

### What “under load” means

The model evaluates burden **at the effort's start**: low below 1, moderate from 1 to below 2, high at least 2. Every band is shown on the same percentage scale. Missing bands remain missing. A 45-minute effort can start at low load and accumulate substantial load during the effort; its classification still describes its start.

For example, two efforts may begin two hours into their rides. One follows hard threshold work; the other follows easy riding and a long stop. Their hour cutoff is the same, while the model may assign different starting-load bands. These bands are experimental context, not measurements of physiological fatigue.

### Trend and timeline examples

On a progress trend, **110 against reference 100** means the recorded measure is 10% higher than the reference. The smooth line follows the recent strongest-three median; it does not make a single ride a fitness test.

On the ride timeline, a 30-minute recording stop appears as shaded zero-power time. The slow and fast workload states recover during that interval, and the elapsed clock keeps advancing.

## Comparisons

Long rides default to **120+ moving minutes**, with a 90-minute option. Ride view uses strictly earlier modeled rides in the selected 42-day, 90-day or entire-history window. Let *x* be this ride's value and *b* the median value of those comparison rides:

```math
\Delta=100\left(\frac{x}{b}-1\right).
```

The overview compares the median of each period's strongest three rides with the preceding equal-length period. “All previous rides” splits the overview into earlier and later halves. Coverage and sample counts matter: catalog-only activities cannot supply power curves.

## Equations

For one-second measured power $P_t$, rolling power and accumulated work are:

```math
\bar{P}_d(s)=\frac{1}{d}\sum_{t=s}^{s+d-1}P_t,
\qquad K(s)=\frac{1}{1000}\sum_{t=0}^{s-1}P_t.
```

Windows containing unknown power are excluded. Stops contribute zero watts.

Experimental workload cost combines shared aerobic reference $A$, environment-specific FTP reference $F$, and exponent $q$:

```math
C_t=(P_t/A)^2+\left[\frac{\max(0,P_t/F-0.8)}{0.2}\right]^q.
```

The slow state accumulates cost and decays exponentially. The fast state accumulates above-FTP work and recovers below FTP:

```math
S_{t+1}=aS_t+\tau_s(1-a)C_t,\qquad a=e^{-1/(60\tau_s)},
```

```math
R_{t+1}=\begin{cases}
R_t+(P_t-F)/1000,&P_t>F,\\
R_t\exp\left[-\frac{1}{\tau_f(1+4(P_t/F)^2)}\right],&P_t\le F.
\end{cases}
\qquad B_t=S_t/30+R_t/5.
```

Here $\tau_s$ is in minutes and $\tau_f$ in seconds. Burden is evaluated **at the effort's start**, with zero initial within-ride load. Constants are exploratory, not fitted physiology. Example settings: indoor/outdoor FTP 185/203 W, aerobic reference 140 W, $q=3$, $\tau_s=240$, $\tau_f=120$. Configure these for the athlete.

## Data and development

Personal recordings, notes, caches, screenshots and credentials are excluded from Git. The server listens only on loopback. A locally entered Intervals key stays in server memory. Timezone defaults to UTC; set `LONG_VIEW_TIMEZONE` for FIT imports. `LONG_VIEW_DATA_DIR` selects a separate store.

Agents: read [AGENTS.md](AGENTS.md) and [the data-source guide](docs/data-sources.md). Core analysis lives in `model.py`; `server.py` serves plain HTML/CSS/JavaScript.

```sh
.venv/bin/python -B -m unittest discover -s tests -v
node --check static/app.js
```
