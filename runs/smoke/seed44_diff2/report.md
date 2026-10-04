# Lab report: seed44_diff2

## The lab's conclusion

1) Findings: The star has one planet, and the first submission passed every check (match score 0.954, minimum required 0.8). The fit leaves 2.43 m/s of scatter, which is below the 2.60 m/s typical measurement error, so it fits the data down to the noise.

| Parameter | Value |
|---|---|
| Period | 15.312 d |
| Semi-amplitude K | 78.88 m/s |
| Eccentricity | 0.092 |
| ω | 2.556 rad |
| Mean anomaly M0 at t_ref | 3.646 rad |
| Mean longitude l | 6.202 rad (with Ω = 0) |
| m sin i | 0.864 M_J |
| Systemic velocity γ | 0.35 m/s |

- **Periodogram:** one dominant peak at about 15.3 d (power 0.98).
- **Sine baseline:** P = 15.32 d, K = 78.4 m/s, RMS 5.64 m/s, which is 2.17 × the median uncertainty. That is above the 1.5 threshold, so the gate decision was Kepler=YES.
- **Keplerian fit:** a 6-parameter least-squares fit from 144 starting points converged with reduced χ² = 0.94.
- **Residuals:** the strongest peak has power 0.12, which is noise, so there is no sign of a second planet.

2) Plan/Next: Nothing left to do; the run is finished with 2 of 3 submissions unused.

4) Results: I submitted the single planet above with `rv_offset_ms` = 0.353 and jitter 0.5 m/s, and included `omega_rad`. The grader confirmed one planet, matching the true count. Period, amplitude, eccentricity and phase all came out close to the true values (distance 0.047).

During conversion my automatic argument matching wrongly set Ω equal to ω. I caught it before submitting and re-ran with Ω = 0. My own m sin i calculation from K (0.8646 M_J) agrees with the helper's value.

The claude.ai connectors (Gmail, Notion, Google Calendar and others) can't be used until you authorise them in your claude.ai connector settings. This task didn't need them.

## Research log
