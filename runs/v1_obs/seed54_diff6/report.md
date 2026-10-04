# Lab report: seed54_diff6

## The lab's conclusion

- **Result:** Concluded. The star has one planet with a period of about 2.99 days. The fit passed all four submission checks on the first try, using no follow-up observations.

**System:**

| Period | Amplitude | Eccentricity |
|---|---|---|
| 2.989 days | 19.8 m/s | 0.04 (nearly circular) |

**Evidence:**
- The periodogram of the original data has one strong signal at about 3.02 days, with a false-alarm probability of 7×10⁻⁷⁴. The fitted period settled at 2.989 days.
- With this one planet, the scatter left around the model is 0.91 m/s, under the limit of 1.12 m/s (1.5 times the 0.75 m/s typical measurement error). After removing it, the strongest leftover peak (1.29 days) has a false-alarm probability of 0.22, far above the 1% threshold.
- Adding a second planet near 1.9 days made the model worse by 6.9 in BIC (lower is better; 10 or more is decisive). That second planet came out at 0.96 m/s and exactly 2.00 days, with its eccentricity stuck at the 0.8 limit, which points to fitting noise rather than a planet.
- The critic approved the one-planet fit, and the decision tool returned "conclude" on its first round. The submission passed the scatter, BIC, planet-count and orbital-parameter checks.

**Uncertain:**
- The data cover only 7.05 days, about 2.3 orbits, so the period is known only roughly.
- The scatter is somewhat larger than the measurement errors explain (reduced χ² 1.63, where 1 means a perfect match). This could be noise from the star itself, or a very weak signal near 1.3 or 1.9 days that these data cannot detect.
- Longer-period companions can't be tested with such a short window.

**Next experiment:** Take observations over several weeks. That would pin down the 2.99-day period, test whether the leftover scatter is a weak signal, and allow a search for outer planets.

## Research log

### 1. Evidence: The data contain one clear periodic signal at about 3.02 days; nothing else passes the significance threshold.

- 3.023 d: false-alarm probability 7e-74, far below the 1% threshold. It explains 99.2% of the variance. Its amplitude is about 21 m/s, estimated from the RV range of -20.6 to +21.0 m/s. The tool flags no aliases or harmonics, and the window function has no peaks. The 7.05-day baseline covers only about 2.3 cycles, so the period is constrained but not tightly. Confidence: high.
- 1.902 d: false-alarm probability 0.11, above the 1% threshold, so it is not credible. It is not a harmonic of 3.02 d (half of 3.02 d is 1.51 d) and not a 1-day alias of it. Treat it only as something to check in the residuals.
- 1.292 d: false-alarm probability 0.88. This is noise.
- I could not run a residual periodogram because no fit exists yet. If 0.8% of the variance is left after a sinusoid, the residual RMS would be roughly 1.3 m/s, against a median error of 0.75 m/s. That excess could come from eccentricity, stellar jitter or a weak second signal. The 1.9 d peak is the first one to recheck once the investigators fit the 3.02 d orbit.
- Minimum planet count: 1. A second planet would be supported if, after fitting the 3.02 d orbit, a residual peak (for example near 1.9 d) reaches a false-alarm probability below 1%. Adding follow-up points (30 available) would also help pin down the 3.02 d period.

### 2. Hypothesis: H1: 1 planet (3.0 d)

Single planet at the dominant 3.02 d signal (false-alarm probability 7e-74).

*Agent-generated hypothesis.*

### 3. Hypothesis: H2: 2 planets (3.0 d, 1.9 d)

Two planets: 3.02 d plus the weak 1.90 d peak (false-alarm probability 0.11) that may strengthen after removing the 3.02 d orbit.

*Agent-generated hypothesis.*

### 4. Plan: We will fit one planet (H1, 3.02 d) and two planets (H2, 3.02 d + 1.90 d) in parallel, because the data can decide between them by BIC.

- H1 fit: expected learning = whether one orbit brings scatter down to the limit (1.5 x 0.75 = 1.12 m/s); cost ~2 min, 0 submissions.
- H2 fit: expected learning = whether the 1.90 d peak (false-alarm probability 0.11 now) is real, judged by BIC (lower is better; 10 or more is decisive); cost ~2 min, 0 submissions.
- Not chosen: eccentric-only variants or extra alias tests; the analyst found no alias for 3.02 d.
- Chosen: both, run in parallel, then critic on the leader and the decision tool.

### 5. Fit: F1 for H1: 1 planet, scatter 0.91 m/s ✓

| Planet | Period (d) | Amplitude (m/s) | Eccentricity | Signal ÷ noise |
|---|---|---|---|---|
| 1 | 2.99 | 19.82 | 0.04 | 160 |

Scatter around the model: **0.91 m/s** (limit 1.12 m/s, fits). BIC 226.2 (lower is better).

### 6. Fit: F2 for H2: 2 planets, scatter 0.85 m/s ✓

| Planet | Period (d) | Amplitude (m/s) | Eccentricity | Signal ÷ noise |
|---|---|---|---|---|
| 1 | 2.99 | 19.90 | 0.03 | 161 |
| 2 | 2.00 | 0.96 | 0.80 | 8 |

Scatter around the model: **0.85 m/s** (limit 1.12 m/s, fits). BIC 233.1 (lower is better).

- ⚠ planet 2: eccentricity at the upper limit 0.8; often a sign of a missing planet or a wrong period

### 7. Critic: Critic approved F1

Approve: one planet at 2.99 days explains the data down to the noise level, and adding a second planet makes the fit worse.
- Residual scatter is 0.91 m/s, under the 1.12 m/s limit. The planet's amplitude signal-to-noise (K_over_sigma_sqrtN) is 160, far above the threshold of about 5. BIC (lower is better; 10 or more is decisive) beats no planet by about 27,200.
- The two-planet rival F2 has a BIC of 233.1, which is 6.9 worse than F1's 226.2. Its second planet (2.00 days, K=0.96 m/s) has eccentricity stuck at the 0.8 limit, a sign it is fitting noise.
- The residual periodogram is clean. The strongest peak (1.29 days) has a false-alarm probability of 0.22, and the earlier 1.9-day candidate now sits at 0.43. Both are well above the 1% threshold.
- The orbit is physically plausible: eccentricity 0.037, and the period (2.99 days) is well inside the 7.05-day baseline. No aliases or harmonics are flagged. The fitted period is 0.034 days from the periodogram peak at 3.02 days, inside the 0.1-day tolerance. There has been no earlier submission feedback to address.

### 8. Decision: Decision: conclude with F1

The data decide the question: F1 (1 planet(s)) fits, leaves no signal, beats every simpler model decisively, and no larger model is needed. Submit it.

- ✓ Scatter around the model is 0.91 m/s; the limit is 1.12 m/s.
- ✓ No significant periodicity is left after subtracting the model.
- ✓ The optimiser converged inside its search range.
- ✓ The critic has not rejected this fit.
- ✓ Every model with fewer planets is worse by at least 10 in BIC.
- ✓ Alternative periods with the same planet count are clearly worse.
- ✓ The weakest planet's signal is 160.3× the noise (needs at least 5).
- ✓ The longest period (3.0 d) is 0.42× the 7.1 d observing span (allowed up to 1.5×).
- ✓ No submission of this configuration has failed.

### 9. Submission: Submitted F1: passed

- ✓ scatter within the limit
- ✓ better than no planets
- ✓ right number of planets
- ✓ orbits match the true ones

All criteria passed.

### 10. PI note: The one-planet fit at 2.99 days (F1) passed all four submission checks, so the run is finished.

- Scatter 0.91 m/s, limit 1.12 m/s; the two-planet model's BIC was 6.9 worse (lower is better; 10 or more is decisive).
- The checks for planet count and orbital parameters passed. We used 1 submission and no follow-up points.
