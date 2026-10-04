# Lab report: seed96_diff3

## The lab's conclusion

- **Result:** Concluded. The star has two planets. The fit we submitted (F3) passed every criterion on its first attempt, using 1 of 5 submissions and no follow-up observations.
- **System:**

| Planet | Period | Amplitude | Eccentricity |
|---|---|---|---|
| b | 116.6 d | 29.3 m/s | 0.25 |
| c | 31.1 d | 14.0 m/s | 0.02 |

- **Evidence:**
  - The analyst found two strong signals: about 111 d (false-alarm probability 9×10⁻²⁴) and about 32 d (false-alarm probability 9×10⁻⁶). Both are far below the 1×10⁻³ threshold, and neither is a harmonic of the other.
  - The two-planet fit leaves 1.13 m/s of scatter, under the 1.58 m/s limit (1.5 × the 1.05 m/s typical error).
  - No one-planet fit works. Each left about 9.2 m/s of scatter and a 30.8 d signal behind (false-alarm probability 3×10⁻²⁷), and its period kept running into the edge of its search range. Its best BIC was 5830, against 278.8 for the two-planet fit (lower is better; a gap of 10 or more is decisive).
  - Nothing significant is left after the two-planet fit. The strongest leftover peak is at 1.27 d with a false-alarm probability of 0.022, above the 1×10⁻³ threshold. The critic approved the fit: the orbits are well separated and neither eccentricity is extreme.
- **Uncertain:** The outer planet's period, 116.6 d, is longer than the 106.7-day observing span, so less than one full orbit has been seen. Its period, and therefore its eccentricity, are uncertain by perhaps tens of days. A weaker 58 d peak appeared after the one-planet fit but not after the two-planet fit, so it was most likely a side effect of fitting one planet only.
- **Next experiment:** Extend the observations past about 220 days, two full orbits of the outer planet. That would pin down its period and eccentricity and show whether a long-term trend or a more distant companion is hiding in the outer signal.

## Research log

### 1. Evidence: Two periodic signals are real: about 111 days and about 32 days.

The 111-day period is longer than the 106.7-day baseline, so its exact value is poorly pinned down.
- 111.3 d: power 0.80, false-alarm probability 9e-24 (threshold 1e-3). Real signal, high confidence. It is longer than the 106.7-day baseline (less than one full cycle observed), so the true period could plausibly be anywhere from about 100 days to a few hundred days, or the signal could be part of a longer trend. No sampling aliases or harmonics flagged.
- 32.0 d: power 0.36, false-alarm probability 9e-6 (threshold 1e-3). Real signal, high confidence. No aliases flagged, and it is not an integer harmonic of 111 d (111/3 = 37 d, 111/4 = 28 d).
- All other peaks (3.35, 1.20, 1.88, 2.11, 4.21, 3.56 d) have false-alarm probability 0.93 or higher, so they are noise. Pairs 1.20/3.56 d and 2.11/4.21 d are harmonics of each other, which confirms they are not independent signals.
- Amplitudes: the periodogram does not give semi-amplitudes, and fitting is left to the investigators. The RV range of -34 to +51 m/s (median error 1.05 m/s) points to a large amplitude (tens of m/s) for the 111-day signal.
- Minimum planet count: 2. Signs of more would be a significant peak (false-alarm probability below 1e-3) in the residuals of a 2-planet fit, or residual RMS above 1.5 x 1.05 m/s. Follow-up data that extend the baseline past about 220 days (two cycles) would pin down the 111-day period. No follow-up data have been taken yet (0 points).

### 2. Hypothesis: H1: 1 planet (111.3 d)

One planet: only the dominant 111.3 d signal (false-alarm probability 9e-24) is real; 32 d is an artefact of fitting a poorly sampled long orbit.

*Agent-generated hypothesis.*

### 3. Hypothesis: H2: 2 planets (111.3 d, 32.0 d)

Two planets: 111.3 d (FAP 9e-24) and 32.0 d (FAP 9e-6), not harmonically related.

*Agent-generated hypothesis.*

### 4. Plan: We will fit both the one-planet (111 d) and two-planet (111 d + 32 d) hypotheses in parallel and let BIC decide the planet count.

- Test H1 (111 d only): expected learning = whether 32 d survives as leftover signal; cost ~2 min, 0 submissions.
- Test H2 (111 d + 32 d): expected learning = whether scatter reaches the 1.58 m/s limit (1.5 x 1.05 m/s) and BIC improves by 10 or more over H1; cost ~2 min, 0 submissions.
- Not chosen now: a 3-planet search — only if H2 residuals show a peak below false-alarm probability 1e-3.
- Chosen: H1 and H2 together, since they are cheap, parallel, and directly decide the planet count.

### 5. Fit: F1 for H1: 1 planet, scatter 9.29 m/s ✗

| Planet | Period (d) | Amplitude (m/s) | Eccentricity | Signal ÷ noise |
|---|---|---|---|---|
| 1 | 144.69 | 35.05 | 0.45 | 204 |

Scatter around the model: **9.29 m/s** (limit 1.58 m/s, does not fit). BIC 5997.7 (lower is better).

- ⚠ planet 1: period 144.690 d sits on its search bound; widen period_tolerance or change the starting period
- ⚠ planet 1: period exceeds the 106.7 d baseline; poorly constrained

### 6. Fit: F2 for H1: 1 planet, scatter 9.23 m/s ✗

| Planet | Period (d) | Amplitude (m/s) | Eccentricity | Signal ÷ noise |
|---|---|---|---|---|
| 1 | 166.95 | 36.10 | 0.49 | 210 |

Scatter around the model: **9.23 m/s** (limit 1.58 m/s, does not fit). BIC 5927.6 (lower is better).

- ⚠ planet 1: period 166.950 d sits on its search bound; widen period_tolerance or change the starting period
- ⚠ planet 1: period exceeds the 106.7 d baseline; poorly constrained

### 7. Fit: F3 for H2: 2 planets, scatter 1.13 m/s ✓

| Planet | Period (d) | Amplitude (m/s) | Eccentricity | Signal ÷ noise |
|---|---|---|---|---|
| 1 | 116.57 | 29.28 | 0.25 | 170 |
| 2 | 31.14 | 13.97 | 0.02 | 81 |

Scatter around the model: **1.13 m/s** (limit 1.58 m/s, fits). BIC 278.8 (lower is better).

- ⚠ planet 1: period exceeds the 106.7 d baseline; poorly constrained

### 8. Hypothesis: H3: 1 planet (250.0 d)

H1 re-centred: one planet; H1 fit pinned on upper bound (167 d at max tolerance 0.5), so start at 250 d to explore 125-375 d.

*Agent-generated hypothesis.*

### 9. Fit: F4 for H3: 1 planet, scatter 9.16 m/s ✗

| Planet | Period (d) | Amplitude (m/s) | Eccentricity | Signal ÷ noise |
|---|---|---|---|---|
| 1 | 375.00 | 40.93 | 0.68 | 238 |

Scatter around the model: **9.16 m/s** (limit 1.58 m/s, does not fit). BIC 5830.2 (lower is better).

- ⚠ planet 1: period 375.000 d sits on its search bound; widen period_tolerance or change the starting period
- ⚠ planet 1: period exceeds the 106.7 d baseline; poorly constrained

### 10. Critic: Critic approved F3

Approve: two planets (116.6 d and 31.1 d) bring the scatter down to the noise level, nothing significant is left in the residuals, and the orbits are physically plausible.
- Fit quality: residual scatter (RMS) is 1.13 m/s, under the 1.58 m/s noise limit. Reduced chi-squared is 1.34. BIC (lower is better; 10 or more is decisive) is 278.8, against 5927.6 for the best one-planet fit (F2) and 5830.2 for the re-centred one-planet fit (F4). That is a drop of more than 5500.
- No missing planet: the strongest residual peak is at 1.27 d with false-alarm probability 0.022. That is well above the 1e-3 threshold, so there is no case for a third planet, and no three-planet fit is needed.
- Plausibility: both amplitudes are strong (K/sigma*sqrt(N) of 170 and 81, far above 5). Eccentricities are 0.25 and 0.02, well below the limit. The period ratio is 3.74, not near-equal, so mutual-Hill stability is no concern at these amplitudes. No fitted period sits on its search bound.
- Caveat: the 116.6 d outer period is longer than the 106.7 d baseline (less than one cycle observed), so its value is uncertain by perhaps tens of days. This is a precision issue, not a sign the model is wrong. The one-planet fits that pushed to longer periods all hit their bounds and still left about 9 m/s of scatter.

### 11. Decision: Decision: conclude with F3

The data decide the question: F3 (2 planet(s)) fits, leaves no signal, beats every simpler model decisively, and no larger model is needed. Submit it.

- ✓ Scatter around the model is 1.13 m/s; the limit is 1.58 m/s.
- ✓ No significant periodicity is left after subtracting the model.
- ✓ The optimiser converged inside its search range.
- ✓ The critic has not rejected this fit.
- ✓ Every model with fewer planets is worse by at least 10 in BIC.
- ✓ Alternative periods with the same planet count are clearly worse.
- ✓ The weakest planet's signal is 81.2× the noise (needs at least 5).
- ✓ The longest period (116.6 d) is 1.09× the 106.7 d observing span (allowed up to 1.5×).
- ✓ No submission of this configuration has failed.

### 12. Submission: Submitted F3: passed

- ✓ scatter within the limit
- ✓ better than no planets
- ✓ right number of planets
- ✓ orbits match the true ones

All criteria passed.

### 13. PI note: The two-planet fit F3 (116.6 d and 31.1 d) was submitted and passed every criterion, so the run is finished.

- Scatter 1.13 m/s, limit 1.58 m/s.
- BIC 278.8, against 5830 for the best one-planet fit (lower is better; 10 or more is decisive).
- No leftover signal with false-alarm probability below 1e-3. The critic approved.
- 1 of 5 submissions used. No follow-up points were taken.
