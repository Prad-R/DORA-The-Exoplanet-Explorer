"""Turn the research record into something a person can read.

``describe`` gives each ledger entry a plain-language title and a short
markdown body; ``render_report`` assembles a run's report. Standard library
only, so the UI can import it without the scientific stack.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

CRITERIA = {
    "ok_rms": "scatter within the limit",
    "ok_delta_bic": "better than no planets",
    "ok_count": "right number of planets",
    "ok_match": "orbits match the true ones",
}


def _days(periods) -> str:
    return ", ".join(f"{float(p):.1f} d" for p in periods) or "no planets"


def _split(text: str) -> tuple[str, str]:
    """First sentence as a headline, the rest as detail."""
    text = (text or "").strip()
    m = re.match(r"(.{20,220}?[.!?])(\s+|$)(.*)", text, re.S)
    if m:
        return m.group(1).strip(), m.group(3).strip()
    first, _, rest = text.partition("\n")
    return first[:220], rest.strip()


def _fit_table(planets: List[Dict[str, Any]]) -> str:
    # Fit order, numbered from 1, so the fitter's flags ("planet 2: ...") point at the right row.
    rows = ["| Planet | Period (d) | Amplitude (m/s) | Eccentricity | Signal ÷ noise |", "|---|---|---|---|---|"]
    for i, p in enumerate(planets, 1):
        rows.append(f"| {i} | {p['P_days']:.2f} | {p['K_ms']:.2f} | {p['e']:.2f} | "
                    f"{p.get('K_over_sigma_sqrtN', 0):.0f} |")
    return "\n".join(rows)


def describe(r: Dict[str, Any]) -> Dict[str, str]:
    """Return {'label', 'title', 'body', 'tone'} for one ledger entry. Tone: info, good, bad, warn."""
    kind = r.get("kind")
    if kind == "hypothesis":
        n = len(r.get("periods_days", []))
        return {"label": "Hypothesis", "tone": "info",
                "title": f"{r['id']}: {n} planet{'s' if n != 1 else ''} ({_days(r.get('periods_days', []))})",
                "body": f"{r.get('rationale', '')}\n\n*Agent-generated hypothesis.*"}
    if kind == "fit":
        n = r.get("n_planets", len(r.get("planets", [])))
        ok = r.get("rms_ok")
        lines = [_fit_table(r["planets"])] if r.get("planets") else []
        lines.append(f"Scatter around the model: **{r['rms_ms']:.2f} m/s** (limit {r['rms_limit_ms']:.2f} m/s, "
                     f"{'fits' if ok else 'does not fit'}). BIC {r['bic']:.1f} (lower is better).")
        if r.get("refit_of"):
            lines.append(f"Refit of {r['refit_of']} after new observations ({r.get('n_obs', '?')} points).")
        if r.get("flags"):
            lines.append("\n".join(f"- ⚠ {f}" for f in r["flags"]))
        source = f" for {r['hypothesis_id']}" if r.get("hypothesis_id") else ""
        return {"label": "Fit", "tone": "good" if ok else "bad",
                "title": f"{r['id']}{source}: {n} planet{'s' if n != 1 else ''}, "
                         f"scatter {r['rms_ms']:.2f} m/s {'✓' if ok else '✗'}",
                "body": "\n\n".join(lines)}
    if kind == "verdict":
        approved = r.get("verdict") == "approve"
        return {"label": "Critic", "tone": "good" if approved else "bad",
                "title": f"Critic {'approved' if approved else 'rejected'} {r['fit_id']}",
                "body": r.get("reasons", "")}
    if kind == "submission":
        crit = r.get("criteria", {})
        lines = [f"- {'✓' if crit.get(k) else '✗'} {label}" for k, label in CRITERIA.items() if k in crit]
        return {"label": "Submission", "tone": "good" if r.get("success") else "bad",
                "title": f"Submitted {r['fit_id']}: {'passed' if r.get('success') else 'failed'}",
                "body": "\n".join(lines + ["", r.get("implication", "")])}
    if kind == "decision" and "status" in r:
        status = r["status"]
        title = {
            "conclude": f"Decision: conclude with {r.get('leader')}",
            "needs_review": f"Decision: {r.get('leader')} needs a critic review first",
            "refine": f"Decision: more analysis needed on {r.get('leader')}",
            "observe": f"Decision: observe {len(r.get('observations', []))} new points",
            "unresolved": "Decision: unresolved",
        }.get(status, f"Decision: {status}")
        lines = [r.get("summary", r.get("reason", ""))]
        checks = r.get("checks") or []
        if checks:
            lines.append("\n".join(f"- {'✓' if c['passed'] else '✗'} {c['explanation']}" for c in checks))
        if r.get("refits"):
            lines.append("Refitted: " + ", ".join(f"{a} → {b}" for a, b in r["refits"].items()))
        tone = {"conclude": "good", "observe": "warn", "refine": "warn", "unresolved": "bad"}.get(status, "info")
        return {"label": "Decision", "tone": tone, "title": title, "body": "\n\n".join(x for x in lines if x)}
    # Free-text notes written by agents.
    label = {"evidence": "Evidence", "plan": "Plan", "decision": "PI note"}.get(kind, str(kind).title())
    title, body = _split(r.get("text", ""))
    return {"label": label, "tone": "info", "title": title, "body": body}


def render_report(task_id: str, ledger: List[Dict[str, Any]], final_report: Optional[str]) -> str:
    out = [f"# Lab report: {task_id}", ""]
    out += ["## The lab's conclusion", "", final_report or "*The lab did not write a final report.*", ""]
    out += ["## Research log", ""]
    for i, r in enumerate(ledger, 1):
        d = describe(r)
        out += [f"### {i}. {d['label']}: {d['title']}", "", d["body"], ""]
    return "\n".join(out)
