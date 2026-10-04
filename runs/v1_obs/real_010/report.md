# Lab report: real_010

## The lab's conclusion

This notice was for results I had already read, so the inbox is now empty and nothing has changed. The run ended as **unresolved**:

- **Secure:** one planet at 2.22 days, with an amplitude of about 204 m/s and a nearly circular orbit.
- **Not settled:** whether the weak signals at 3.8 and 5.65 days are planets or starspots on a star rotating every ~11.5 days.
- **Budget:** one submission was used and 9 of the 10 remain. No new observations can be taken for this real-data target.

## Research log

### 1. Evidence: One periodic signal is real: about 2.213 days, very strong (likely a hot Jupiter); everything else in the raw periodogram is its alias or noise.

- 2.2131 d: power 0.993, false-alarm probability 1.4e-31 (threshold 1e-3). The data run from -244 to +165 m/s against 3.4 m/s median errors, so the semi-amplitude is roughly 200 m/s. This is a raw-range estimate only; the fit sets the real value. The uneven range hints at some eccentricity.
- 1.818 d (false-alarm probability 1e-5) is the 1-day alias of 2.213 d (1/1.818 + 1/2.213 ≈ 1.00 per day). The window function peaks at 0.999 d with strength 0.65. I favour 2.213 d because it has far more power (0.99 vs 0.64). The other 1-day alias is 0.688 d. Treat both as alternatives only if the fit at 2.213 d leaves structure.
- 2.953 d (false-alarm probability 0.07) and 1.501 d (0.16) are a harmonic pair. Both are above the 1% threshold, so not credible. The same goes for 1.900 d and 2.102 d (0.36, 0.42), which are 1-day aliases of each other. These may simply be leakage from the dominant signal. No residual periodogram exists yet (no fit ID); recheck these after the 2.213 d orbit is removed.
- All periods are well inside the 41.96-day baseline. No long-period peak was found, so there is no sign of a trend in the raw data; check the fit residuals for a slope. A ~200 m/s amplitude is far above stellar activity levels for a 0.82 solar-mass star, so activity is not a concern for the main signal.
- Minimum: 1 planet. A second planet would need a peak in the residual periodogram (for example near 2.95 d or 1.50 d) that falls below 1% false-alarm probability.

### 2. Hypothesis: H1: 1 planet (2.2 d)

Single planet at the dominant 2.213 d peak (false-alarm probability 1.4e-31).

*Agent-generated hypothesis.*

### 3. Hypothesis: H2: 1 planet (1.8 d)

One-day alias alternative: single planet at 1.818 d.

*Agent-generated hypothesis.*

### 4. Hypothesis: H3: 2 planets (2.2 d, 3.0 d)

Two planets: 2.213 d plus the weak 2.95 d peak (false-alarm probability 0.07), tests planet count.

*Agent-generated hypothesis.*

### 5. Plan: We test whether the star hosts one planet at 2.213 days, its 1-day alias at 1.818 days, or a second planet near 2.95 days, and we fit all three in parallel.

- H1 (one planet, 2.213 d): this is the leading candidate. A fit takes about 1 investigator run and no submissions. It tells us whether one orbit brings the scatter down to the 5.1 m/s limit (1.5 × 3.4 m/s).
- H2 (one planet, 1.818 d alias): costs 1 run. The BIC comparison (lower is better; 10 or more is decisive) between H1 and H2 settles which alias is real.
- H3 (two planets, 2.213 d + 2.95 d): costs 1 run. It tests the planet count. Its 2.95 d peak is weak (false-alarm probability 0.07), so we expect H1 to win.
- Not chosen: the 0.688 d alias and the 1.90/2.10 d noise pair. Their false-alarm probabilities are 0.36–0.42, so a fit is unlikely to teach us anything.
- Chosen: H1, H2 and H3, run in parallel because together they cost about a third of the time. Then the critic reviews the leader and we go to the decision tool.

### 6. Fit: F1 for H1: 1 planet, scatter 8.12 m/s ✗

| Planet | Period (d) | Amplitude (m/s) | Eccentricity | Signal ÷ noise |
|---|---|---|---|---|
| 1 | 2.22 | 201.61 | 0.02 | 241 |

Scatter around the model: **8.12 m/s** (limit 5.10 m/s, does not fit). BIC 345.9 (lower is better).

### 7. Fit: F2 for H2: 1 planet, scatter 90.59 m/s ✗

| Planet | Period (d) | Amplitude (m/s) | Eccentricity | Signal ÷ noise |
|---|---|---|---|---|
| 1 | 1.81 | 166.07 | 0.02 | 198 |

Scatter around the model: **90.59 m/s** (limit 5.10 m/s, does not fit). BIC 22831.2 (lower is better).

### 8. Fit: F3 for H3: 2 planets, scatter 6.43 m/s ✗

| Planet | Period (d) | Amplitude (m/s) | Eccentricity | Signal ÷ noise |
|---|---|---|---|---|
| 1 | 2.22 | 202.03 | 0.03 | 241 |
| 2 | 2.84 | 12.36 | 0.72 | 15 |

Scatter around the model: **6.43 m/s** (limit 5.10 m/s, does not fit). BIC 295.2 (lower is better).

### 9. Evidence: H1 (one planet) captures the main signal but does not fully explain the data: fit F1 leaves 8.12 m/s of scatter, above the 5.1 m/s limit.

- F1: P = 2.21921 d, K = 201.6 m/s, e = 0.024 (close to circular), omega = 5.84 rad. The period moved 0.27% from the starting value of 2.2131 d and is not stuck on the ±10% search bound. The fit raised no flags.
- RMS 8.12 m/s, limit 5.1 m/s (fails). Reduced chi2 is 6.75. BIC 345.9, lower is better; it beats the no-planet model by 62,395.
- Residual periodogram: the strongest peak is 3.829 d (FAP 0.011), then 5.625 d (FAP 0.014) and 14.18 d (FAP 0.087). None is below the 1e-3 detection threshold, and none is near 2.95 d, so this does not support H3's 2.95 d peak. 3.83 d and 5.63 d are near the 1% level and should be watched. The leftover scatter could also be stellar jitter.

### 10. Evidence: H2 (a single planet at the 1.818 d alias) does not explain the data: its fit F2 leaves about 18 times the allowed scatter, and the real 2.213 d signal is still in the residuals.

- F2: P = 1.81476 d, K = 166.1 m/s, e = 0.022. RMS 90.59 m/s (limit 5.1 m/s, failed). Reduced chi2 839.5. BIC 22831.2 (lower is better), compared with 345.9 for F1/H1. Delta BIC is about 22485 in favour of H1, far past the 10-point decisive threshold. No flags were raised and the period did not hit its bound.
- Strongest residual peak: 2.2278 d, power 0.53, false-alarm probability 5.1e-4 (threshold 1e-3). This is the 2.213 d signal that the 1.818 d alias fit leaves behind. All other residual peaks have false-alarm probability above 0.8 (2.953 d is at 0.83).
- Conclusion: reject the 1.818 d alias. 2.213 d (H1) is the true period.

### 11. Hypothesis: H4: 2 planets (2.2 d, 3.8 d)

F1 residual scatter 8.1 m/s exceeds 5.1 m/s limit; strongest residual peak 3.829 d (false-alarm probability 0.011).

*Agent-generated hypothesis.*

### 12. Hypothesis: H5: 2 planets (2.2 d, 5.6 d)

Competing second-planet period: residual peak 5.625 d (false-alarm probability 0.014).

*Agent-generated hypothesis.*

### 13. Fit: F4 for H4: 2 planets, scatter 5.52 m/s ✗

| Planet | Period (d) | Amplitude (m/s) | Eccentricity | Signal ÷ noise |
|---|---|---|---|---|
| 1 | 2.22 | 203.33 | 0.02 | 243 |
| 2 | 3.79 | 10.26 | 0.38 | 12 |

Scatter around the model: **5.52 m/s** (limit 5.10 m/s, does not fit). BIC 265.6 (lower is better).

### 14. Fit: F5 for H5: 2 planets, scatter 5.29 m/s ✗

| Planet | Period (d) | Amplitude (m/s) | Eccentricity | Signal ÷ noise |
|---|---|---|---|---|
| 1 | 2.22 | 203.51 | 0.02 | 243 |
| 2 | 5.65 | 10.11 | 0.50 | 12 |

Scatter around the model: **5.29 m/s** (limit 5.10 m/s, does not fit). BIC 259.3 (lower is better).

### 15. Hypothesis: H6: 2 planets (2.2 d, 1.4 d)

Alias test for H4: 1.352 d is the 1-day alias of the 3.829 d F1 residual peak.

*Agent-generated hypothesis.*

### 16. Hypothesis: H7: 2 planets (2.2 d, 0.8 d)

Alias test for H4: 0.792 d is a 1-day alias of the 3.829 d F1 residual peak.

*Agent-generated hypothesis.*

### 17. Fit: F6 for H6: 2 planets, scatter 6.39 m/s ✗

| Planet | Period (d) | Amplitude (m/s) | Eccentricity | Signal ÷ noise |
|---|---|---|---|---|
| 1 | 2.22 | 200.90 | 0.03 | 240 |
| 2 | 1.34 | 12.41 | 0.80 | 15 |

Scatter around the model: **6.39 m/s** (limit 5.10 m/s, does not fit). BIC 292.2 (lower is better).

- ⚠ planet 2: eccentricity at the upper limit 0.8; often a sign of a missing planet or a wrong period

### 18. Fit: F7 for H7: 2 planets, scatter 6.06 m/s ✗

| Planet | Period (d) | Amplitude (m/s) | Eccentricity | Signal ÷ noise |
|---|---|---|---|---|
| 1 | 2.22 | 200.72 | 0.01 | 240 |
| 2 | 0.84 | 15.00 | 0.80 | 18 |

Scatter around the model: **6.06 m/s** (limit 5.10 m/s, does not fit). BIC 280.1 (lower is better).

- ⚠ planet 2: eccentricity at the upper limit 0.8; often a sign of a missing planet or a wrong period

### 19. Evidence: H5 (2.219 d + 5.65 d) is the best-scoring hypothesis so far, but it still does not bring the scatter under the limit, so it does not fully explain the data.

- Fit F5: planet b P = 2.21958 d, K = 203.5 m/s, e = 0.020, omega = 5.75 rad. Planet c P = 5.6545 d, K = 10.1 m/s, e = 0.502, omega = 5.20 rad. Planet c moved 0.5% from its 5.625 d start and is not on the ±10% bound. No flags were raised.
- RMS 5.29 m/s, limit 5.1 m/s (fails narrowly). Reduced chi2 3.56.
- BIC 259.3, lower is better. That is 86.5 below F1 (345.9), which is decisive (threshold 10). It is only 6.3 below F4/H4 (265.6), which is not decisive, so 5.65 d vs 3.79 d as the second period is not settled.
- Caveats: planet c's K of 10 m/s is about 3 times the 3.4 m/s median error. With 33 points its e of 0.50 is probably poorly constrained. Its source peak in the F1 residuals had FAP 0.014, not below 1e-3.
- F5 residual periodogram: the strongest peak is 6.897 d (FAP 0.037, aliases 0.873/1.168 d), then 3.829 d (FAP 0.13) and 1.167 d (FAP 0.24). None is below 1e-3, so no significant signal is left unexplained. The remaining excess could be jitter.

### 20. Evidence: H4 (2.22 d + 3.79 d) improves a lot on F1 but still does not fully explain the data: fit F4 leaves 5.52 m/s of scatter, just above the 5.1 m/s limit.

- F4: planet b P = 2.22018 d, K = 203.3 m/s, e = 0.019; planet c P = 3.78866 d, K = 10.3 m/s, e = 0.38. No flags; periods not on the ±10% bound.
- RMS 5.52 m/s, limit 5.1 m/s (fails narrowly). Reduced chi2 3.84. BIC 265.6, lower is better: 80.2 below F1 (345.9), well past the 10-point decisive threshold. It also beats F3 (295.2).
- Alias checks for planet c: H6 (1.352 d start) gave F6, which converged to 1.338 d with e at the 0.8 limit, RMS 6.39 m/s, BIC 292.2. H7 (0.792 d start) gave F7, which drifted to 0.842 d with e at the 0.8 limit, RMS 6.06 m/s, BIC 280.1. Both were flagged and both are worse than F4 (by 26.6 and 14.4 BIC). The 3.79 d alias is preferred.
- F4 residual periodogram: strongest peak 3.402 d (FAP 0.35), then 4.21 d (0.65) and 5.63 d (0.75). Nothing is near the 1e-3 detection threshold, so no coherent signal remains. The 0.4 m/s excess over the limit looks like noise or jitter, not a missed planet.
- Caveat: planet c's K/σ√N is 12.3 and the 3.83 d peak in F1's residuals had FAP 0.011, so it is not an independent detection. Its credibility rests on the ΔBIC.

### 21. Decision: Decision: F5 needs a critic review first

F5 (2 planet(s)) is the leading model: no larger model beats it by 10 or more in BIC. Ask the critic to review F5, then decide again.

### 22. Critic: Critic rejected F5

Reject: with e = 0.50, the 5.65-day orbit of planet c dips inside the orbit of the roughly 1.1 Jupiter-mass planet b, so the system is dynamically unstable as fitted, and the second period is not yet distinguished from 3.79 days.
- Stability: the period ratio of 2.55 gives a semi-major-axis ratio of 1.87. Planet c's closest approach is 1.87 × (1 − 0.50) = 0.93 times planet b's orbit, below 1.0, so the orbits cross. Planet b's minimum mass is about 1.1 Jupiter masses (K = 203.5 m/s, star 0.82 solar masses), so a 24-Earth-mass planet c on that orbit would not survive. F4's e = 0.38 orbit also crosses (0.88). The eccentricity is the likely problem: with K/σ√N = 12 and only 33 points it is poorly constrained.
- Planet count: BIC (lower is better; 10 or more is decisive) is 259.3 for F5, compared with 345.9 for one planet (F1). The 86.5 improvement is decisive, so a second signal is supported. No three-planet fit has been run yet.
- Alias or period choice: F5 beats F4 (2.22 + 3.79 d, BIC 265.6) by only 6.3, below the decisive 10. The 3.83-day peak is still in F5's residuals (false-alarm probability 0.13), and 5.63 d is gone from F4's residuals (0.75). The two fits may be modelling the same residual structure, so the second period is not settled.
- Residuals and fit quality: RMS is 5.29 m/s against the 5.1 m/s limit (fails narrowly). The strongest residual peak is 6.90 days with false-alarm probability 0.037, above the 1e-3 detection threshold, so no planet is clearly missing.
Next test: refit H5 and H4 with planet c on a circular orbit (e fixed at 0), check that the orbits no longer cross, and compare BIC. Also run one three-planet fit (2.22 + 3.79 + 5.65 d).

### 23. Hypothesis: H8: 3 planets (2.2 d, 3.8 d, 5.7 d)

F4 and F5 each absorb part of the leftover structure, and both have crossing orbits; test three planets at 2.22, 3.79, 5.65 d.

*Agent-generated hypothesis.*

### 24. Hypothesis: H9: 2 planets (2.2 d, 5.7 d)

Critic rejected F5 for orbit crossing (e=0.50); refit 2.22 + 5.65 d with planet c circular / low eccentricity.

*Agent-generated hypothesis.*

### 25. Hypothesis: H10: 2 planets (2.2 d, 3.8 d)

F4 also has crossing orbits (e=0.38); refit 2.22 + 3.79 d with planet c circular / low eccentricity.

*Agent-generated hypothesis.*

### 26. Fit: F8 for H8: 3 planets, scatter 3.26 m/s ✓

| Planet | Period (d) | Amplitude (m/s) | Eccentricity | Signal ÷ noise |
|---|---|---|---|---|
| 1 | 2.22 | 204.09 | 0.02 | 244 |
| 2 | 3.80 | 9.83 | 0.45 | 12 |
| 3 | 5.68 | 14.18 | 0.76 | 17 |

Scatter around the model: **3.26 m/s** (limit 5.10 m/s, fits). BIC 229.0 (lower is better).

### 27. Fit: F9 for H10: 2 planets, scatter 5.52 m/s ✗

| Planet | Period (d) | Amplitude (m/s) | Eccentricity | Signal ÷ noise |
|---|---|---|---|---|
| 1 | 2.22 | 203.33 | 0.02 | 243 |
| 2 | 3.79 | 10.26 | 0.38 | 12 |

Scatter around the model: **5.52 m/s** (limit 5.10 m/s, does not fit). BIC 265.6 (lower is better).

### 28. Fit: F10 for H9: 2 planets, scatter 5.29 m/s ✗

| Planet | Period (d) | Amplitude (m/s) | Eccentricity | Signal ÷ noise |
|---|---|---|---|---|
| 1 | 2.22 | 203.51 | 0.02 | 243 |
| 2 | 5.65 | 10.11 | 0.50 | 12 |

Scatter around the model: **5.29 m/s** (limit 5.10 m/s, does not fit). BIC 259.3 (lower is better).

### 29. Evidence: H8 (three planets, 2.22 + 3.80 + 5.68 d) fits the data statistically (F8: RMS 3.26 m/s, limit 5.1 m/s; BIC 229.0), but as fitted it is not physical: both outer orbits are highly eccentric and cross the hot Jupiter's orbi

- F8: b P = 2.22031 d, K = 204.1 m/s, e = 0.020; c P = 3.79699 d, K = 9.8 m/s, e = 0.455; d P = 5.68435 d, K = 14.2 m/s, e = 0.760 (close to the 0.8 cap but not flagged). No flags; no period on the ±10% bound.
- The fit tool has no option to fix or bound eccentricity, so the requested low-e constraint could not be applied.
- BIC 229.0, lower is better: 36.7 below F4 (265.6) and 30.4 below F5 (259.3), both decisive (threshold 10). Reduced chi2 1.79.
- Orbit crossing: c's periastron is a_c/a_b × (1−e) = 1.43 × 0.545 ≈ 0.78; d's is 1.87 × 0.24 ≈ 0.45. Both are below 1, so both cross b (and d also crosses c). A system like that would not survive.
- F8 residual periodogram: strongest peak 14.18 d (FAP 0.83), then 7.04 d (0.87, its harmonic). Nothing approaches 1e-3, so no signal is left.
- Caveat: K/σ√N is about 12 and 17 for c and d with 33 points. The high eccentricities may be soaking up noise, so the BIC gain may partly come from the extra 10 free parameters fitting noise. Circular refits (H9/H10, and a circular H8 if the tool allows) are needed.

### 30. Evidence: H10 was not actually tested as asked: fit_hypothesis cannot fix or bound eccentricity, so fit F9 simply reproduced F4 (planet c e = 0.38, orbits still cross).

- F9: planet b P = 2.22018 d, K = 203.3 m/s, e = 0.019; planet c P = 3.78866 d, K = 10.3 m/s, e = 0.382. Same as F4 to 4+ digits. No flags; periods not on the ±10% bound.
- RMS 5.52 m/s, limit 5.1 m/s (fails). Reduced chi2 3.84. BIC 265.6, same as F4 (265.6); lower is better, delta 0.0.
- Crossing check: period ratio 1.707 gives a semi-major-axis ratio of 1.428. Planet c's periastron is 1.428 × (1 − 0.382) = 0.88 of b's orbit, so the orbits cross. To avoid crossing, e_c must be below about 0.29 (after allowing for b's apastron at e = 0.019).
- F9 residual periodogram: strongest peak 3.402 d (FAP 0.35), then 4.21 d (0.65) and 5.63 d (0.75). None is near 1e-3.
- Needed: an eccentricity-constrained fit (e_c = 0 or e_c < 0.29), which the current tool does not support. Until then, the stable-orbit version of H10 is untested.

### 31. Decision: Decision: F8 needs a critic review first

F8 (3 planet(s)) is the leading model: no larger model beats it by 10 or more in BIC. Ask the critic to review F8, then decide again.

### 32. Critic: Critic approved F8

Approve: three planets at 2.22, 3.80 and 5.68 days are the only model that brings the scatter under the limit, and it is decisively better than both two-planet fits. The fitted eccentricities of c and d are not credible and should be reported as unconstrained.
- Planet count: BIC (lower is better; 10 or more is decisive) is 229.0 for F8, against 259.3 for F5 (2.22 + 5.65 d) and 265.6 for F4 (2.22 + 3.79 d). Those gaps of 30.4 and 36.7 are decisive after the penalty for extra parameters. RMS is 3.26 m/s against the 5.1 m/s limit (the only fit that passes), and reduced chi2 is 1.79. Planets c and d have K/sigma*sqrt(N) of 11.7 and 16.9, both well above the weak-planet threshold of about 5.
- Residuals: the strongest F8 residual peak is 14.18 days (false-alarm probability 0.83), and its harmonic 7.04 days is at 0.87. Both are far above the 1e-3 detection threshold, so no planet is missing. The 1-day aliases of c (1.34 and 0.84 days, F6/F7) were tested and lose by 14 BIC or more, with eccentricity stuck at the 0.8 cap.
- Plausibility: as fitted, c (e = 0.455, periastron 0.78 of b's orbit) and d (e = 0.76, periastron 0.45) cross the orbit of the roughly 1.1 Jupiter-mass planet b, which is not physical. With 33 points and K only 3 to 4 times the 3.4 m/s errors, eccentricity is known to be biased upward and poorly constrained, so these values are most likely noise-driven rather than a sign of wrong periods. The periods themselves are plausible: d/c = 1.497 (near 3:2 resonance), c/b = 1.71, and circular orbits at these spacings would not cross. Planet d's 1-day aliases have not been tested in a three-planet fit; that is the remaining gap.
- Affordability: the fitting tool cannot fix or bound eccentricity (H9/H10 just reproduced F5/F4), so a stable-orbit refit is not possible. F8 is the best available answer, and leaving it unsubmitted scores nothing. Submit the periods and amplitudes, and mark e_c and e_d as unconstrained (physically below about 0.29 and 0.2).

### 33. Decision: Decision: conclude with F8

The data decide the question: F8 (3 planet(s)) fits, leaves no signal, beats every simpler model decisively, and no larger model is needed. Submit it.

- ✓ Scatter around the model is 3.26 m/s; the limit is 5.10 m/s.
- ✓ No significant periodicity is left after subtracting the model.
- ✓ The optimiser converged inside its search range.
- ✓ The critic has not rejected this fit.
- ✓ Every model with fewer planets is worse by at least 10 in BIC.
- ✓ Alternative periods with the same planet count are clearly worse.
- ✓ The weakest planet's signal is 11.7× the noise (needs at least 5).
- ✓ The longest period (5.7 d) is 0.14× the 42.0 d observing span (allowed up to 1.5×).
- ✓ No submission of this configuration has failed.

### 34. Submission: Submitted F8: failed

- ✓ scatter within the limit
- ✓ better than no planets
- ✗ right number of planets
- ✗ orbits match the true ones

The fit is good but the number of planets is wrong: test hypotheses with one more and one fewer planet. Do not resubmit this configuration.

### 35. PI note: Submitting F8 (three planets at 2.220, 3.797 and 5.684 days) failed: the planet count is wrong, even though its scatter (3.26 m/s, limit 5.1 m/s) and its BIC (lower is better) both passed.

- The feedback says to test one more and one fewer planet. Two-planet fits F4 (2.22 + 3.79 d) and F5 (2.22 + 5.65 d) already exist, and no four-planet fit does yet.
- Physical concern: the 2.22 d, ~204 m/s hot Jupiter on a 0.82-solar-mass star resembles a known active K dwarf. Weak signals at 3.8 d and 5.65 d could be rotation harmonics from starspots, not planets. That would also explain why their fitted eccentricities (0.45, 0.76) are high and their orbits cross.
- Next: a four-planet fit (adding the 14.2 d residual peak). We also ask the analyst whether the secondary signals look like stellar activity.

### 36. Hypothesis: H11: 4 planets (2.2 d, 3.8 d, 5.7 d, 14.2 d)

Submission feedback: wrong count for 3 planets; test one more. Fourth period from strongest F8 residual peak (14.18 d).

*Agent-generated hypothesis.*

### 37. Fit: F11 for H11: 4 planets, scatter 2.33 m/s ✓

| Planet | Period (d) | Amplitude (m/s) | Eccentricity | Signal ÷ noise |
|---|---|---|---|---|
| 1 | 2.22 | 201.07 | 0.02 | 240 |
| 2 | 4.03 | 4.63 | 0.26 | 6 |
| 3 | 6.25 | 10.85 | 0.80 | 13 |
| 4 | 14.96 | 10.10 | 0.10 | 12 |

Scatter around the model: **2.33 m/s** (limit 5.10 m/s, fits). BIC 230.1 (lower is better).

- ⚠ planet 3: period 6.252 d sits on its search bound; widen period_tolerance or change the starting period
- ⚠ planet 3: eccentricity at the upper limit 0.8; often a sign of a missing planet or a wrong period

### 38. Fit: F12 for H11: 4 planets, scatter 2.16 m/s ✓

| Planet | Period (d) | Amplitude (m/s) | Eccentricity | Signal ÷ noise |
|---|---|---|---|---|
| 1 | 2.22 | 204.61 | 0.03 | 244 |
| 2 | 3.31 | 9.15 | 0.80 | 11 |
| 3 | 6.05 | 7.62 | 0.74 | 9 |
| 4 | 14.45 | 12.51 | 0.46 | 15 |

Scatter around the model: **2.16 m/s** (limit 5.10 m/s, fits). BIC 228.7 (lower is better).

- ⚠ planet 2: eccentricity at the upper limit 0.8; often a sign of a missing planet or a wrong period

### 39. Evidence: Best supported: two planets at 2.22 days and about 3.8 days (the F4 configuration).

The 5.65-day signal looks like a by-product of the 3.8-day one, and the 14.2-day and 6.9-day peaks are not credible planets.
- Residuals after the one-planet fit (F1, 2.219 d): 3.83 d has false-alarm probability 1.1% and 5.63 d has 1.4%. Both are near the usual 1% threshold, but neither is below 0.1%. 14.2 d has 8.7%, which is not significant. Baseline is 42.0 days and sampling is 33 points, so all of these periods are well constrained.
- Fitting 3.8 d (F4) removes almost all of the 5.63-day power: its false-alarm probability goes from 1.4% to 75%. Nothing left in the F4 residuals is below 35%, so the residuals are flat. Fitting 5.65 d (F5) leaves 3.83 d at 13% and creates a new 6.9-day peak at 3.7%. So 3.8 d explains the data better, and 5.65 d is the dependent signal.
- 3.83 d and 5.63 d are not 1-day aliases of each other. Their frequencies differ by 1/(12.0 d), and 3 x 3.83 = 11.5 d while 2 x 5.63 = 11.3 d. That fits P_rot/3 and P_rot/2 of a star rotating every ~11.3-11.5 days. This cannot be ruled out: 42 days covers only about 3.6 rotations, and there are no activity indicators. The 1-day alias of 3.83 d is 1.35 d, which is much weaker (76%).
- 6.9 d shows up only after the F5 fit and is not among the top 8 peaks of F1, so it is most likely left over from mis-modelling 5.65 d. 14.2 d is not significant in any residuals.
- Minimum count: 2 planets. A 4-planet case has no support, since the F4 residuals are flat. Follow-up spread over 12 days or more would test whether 3.8 d stays coherent (planet) or drifts (rotation).

### 40. Decision: Decision: unresolved

More data is needed (A submission of this configuration already failed, so the current data favour a wrong model; a signal they cannot yet show (for example a longer orbit) is likely.) but none can be taken. Simulated observing is disabled for real-data tasks.

- ✓ Scatter around the model is 3.26 m/s; the limit is 5.10 m/s.
- ✓ No significant periodicity is left after subtracting the model.
- ✓ The optimiser converged inside its search range.
- ✓ The critic has not rejected this fit.
- ✓ Every model with fewer planets is worse by at least 10 in BIC.
- ✓ Alternative periods with the same planet count are clearly worse.
- ✓ The weakest planet's signal is 11.7× the noise (needs at least 5).
- ✓ The longest period (5.7 d) is 0.14× the 42.0 d observing span (allowed up to 1.5×).
- ✗ A submission of this configuration already failed, so the current data favour a wrong model; a signal they cannot yet show (for example a longer orbit) is likely.

### 41. PI note: The decision tool returned "unresolved", so the lab stops: the current data favour a three-planet model that has already failed submission, and no new observations can be taken for this real-data target.

- One planet at 2.22 days (K ≈ 204 m/s, nearly circular) is secure: false-alarm probability 1.4e-31.
- Weak extra signals at 3.8 d and 5.65 d (K ≈ 10 m/s each) improve the fit. Their periods are close to 1/3 and 1/2 of an ~11.5-day period, which fits starspots rotating with the star.
- The three-planet fit at 2.22 + 3.80 + 5.68 d (scatter 3.26 m/s, limit 5.1 m/s) was submitted and failed on planet count. Adding a fourth planet improves BIC by only 0.3, against the 10 needed (lower is better).
- Two-planet fits miss the scatter limit: 5.29 and 5.52 m/s against 5.1 m/s. Their eccentric orbits cross the hot Jupiter's.
