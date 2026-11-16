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

Choose **3, 5, 8, 10, 15, 20, 30, 45 or 60 minutes**. Selection updates power and late-power cards, their trends, and Power after work. The duration comparison shows all nine.

| View | Meaning |
| --- | --- |
| **Exposure** | The 90th percentile of rolling average power. About 10% of valid windows reach that power or higher. Overlapping windows describe exposure, not independent repetitions. |
| **Best** | Highest observed rolling average power at that duration. |
| **Repeated** | Mean of the strongest three greedily selected, non-overlapping blocks. All three must exist; they can be pieces of one longer effort. |
| **Late** | Best window **starting after 500 kJ of recorded mechanical work**. It can include a hard block; it does not necessarily mean the final hour. |
| **Under load** | Best window starting in the experimental **moderate burden band, 1 ≤ B < 2**. Higher-burden starts are excluded from this particular view. |
| **Power after work** | Best power after increasing kJ thresholds, divided by that ride's best at the chosen duration. The alternative shows retention in low, moderate and high modeled-load bands. |
| **Work across power levels** | Cumulative minutes at or above each wattage per moving hour. Above-FTP view uses each environment's reference. |

The separate **Repeated 3-min power** marker stays fixed at three minutes. **Repeatability** counts all minutes above FTP per moving hour; it does not count intentional intervals.

## Comparisons

Long rides default to **120+ moving minutes**, with a 90-minute option. Ride view uses strictly earlier modeled rides in the selected 42-day, 90-day or entire-history window. Percent change uses their median:

$$
\Delta=100\left(\frac{x}{\operatorname{median}(x_{\mathrm{prior}})}-1\right).
$$

The overview compares the median of each period's strongest three rides with the preceding equal-length period. “All previous rides” splits the overview into earlier and later halves. Coverage and sample counts matter: catalog-only activities cannot supply power curves.

## Equations

For one-second measured power $P_t$, rolling power and accumulated work are:

$$
\bar P_d(s)=\frac{1}{d}\sum_{t=s}^{s+d-1}P_t,
\qquad K(s)=\frac{1}{1000}\sum_{t<s}P_t.
$$

Windows containing unknown power are excluded. Stops contribute zero watts.

Experimental workload cost combines shared aerobic reference $A$, environment-specific FTP reference $F$, and exponent $q$:

$$
C_t=(P_t/A)^2+\left[\frac{\max(0,P_t/F-0.8)}{0.2}\right]^q.
$$

The slow state accumulates cost and decays exponentially. The fast state accumulates above-FTP work and recovers below FTP:

$$
S_{t+1}=aS_t+\tau_s(1-a)C_t,\qquad a=e^{-1/(60\tau_s)},
$$

$$
R_{t+1}=\begin{cases}
R_t+(P_t-F)/1000,&P_t>F,\\
R_t\exp\left[-\frac{1}{\tau_f(1+4(P_t/F)^2)}\right],&P_t\le F.
\end{cases}
\qquad B_t=S_t/30+R_t/5.
$$

Here $\tau_s$ is in minutes and $\tau_f$ in seconds. Burden is evaluated **at the effort's start**, with zero initial within-ride load. Constants are exploratory, not fitted physiology. Example settings: indoor/outdoor FTP 185/203 W, aerobic reference 140 W, $q=3$, $\tau_s=240$, $\tau_f=120$. Configure these for the athlete.

## Data and development

Personal recordings, notes, caches, screenshots and credentials are excluded from Git. The server listens only on loopback. A locally entered Intervals key stays in server memory. Timezone defaults to UTC; set `LONG_VIEW_TIMEZONE` for FIT imports. `LONG_VIEW_DATA_DIR` selects a separate store.

Agents: read [AGENTS.md](AGENTS.md) and [the data-source guide](docs/data-sources.md). Core analysis lives in `model.py`; `server.py` serves plain HTML/CSS/JavaScript.

```sh
.venv/bin/python -B -m unittest discover -s tests -v
node --check static/app.js
```
