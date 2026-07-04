"""Statistical analysis: which 15m features change first before 1H breakouts.

Primary comparison: SUCCESSFUL breakout events vs matched non-breakout
compression controls, per feature per 15m offset.

Per feature we report:
  * direction          – sign of the effect (from pooled AUC at offsets -8..-1)
  * auc_late / auc_early / auc_very_early – pooled AUC in offset bands
  * earliest_sig_offset / lead_minutes – earliest offset from which the
      feature stays significant (BH-FDR q<0.05, one gap allowed) up to -1
  * changes_before (one-sample)        – earliest offset where the event
      population's own z-scores differ from 0 (Wilcoxon, q<0.05, sustained)
  * hit_rate / fpr / median_lead_min   – per-event trigger rule: signed
      z >= 2 on two consecutive bars within offsets -32..-1
  * symbol_consistency – share of symbols (>=5 events) whose own pooled AUC
      agrees with the global direction
  * succ_vs_fail_auc   – does the feature also separate successful from
      failed breakouts?
  * recommendation     – KEEP / TEST FURTHER / DISCARD

Lead-time convention: the 1H breakout becomes *visible* when the breakout
1H candle closes. A 15m bar at offset k closes (45 - 15k) minutes before
that (offset -1 -> 60 min, offset -32 -> 525 min, offset +3 -> 0 min).
"""
import os
import pickle

import numpy as np
import pandas as pd
from scipy.stats import mannwhitneyu, wilcoxon

from config import RESULTS_DIR

Z_TRIGGER = 2.0
TRIGGER_CONSEC = 2
PRE_HOUR = -1          # last offset strictly before the breakout hour
AUC_MIN_SIG = 0.54     # minimum signed AUC for an offset to count


def lead_minutes(offset):
    return 45 - 15 * offset


def bh_fdr(pvals):
    p = np.asarray(pvals, dtype=float)
    ok = np.isfinite(p)
    q = np.full_like(p, np.nan)
    if ok.sum() == 0:
        return q
    ps = p[ok]
    n = len(ps)
    order = np.argsort(ps)
    ranked = ps[order] * n / (np.arange(n) + 1)
    ranked = np.minimum.accumulate(ranked[::-1])[::-1]
    out = np.empty(n)
    out[order] = np.clip(ranked, 0, 1)
    q[ok] = out
    return q


def auc_from_mw(a, b):
    """AUC that a > b, ignoring NaNs."""
    a = a[np.isfinite(a)]
    b = b[np.isfinite(b)]
    if len(a) < 10 or len(b) < 10:
        return np.nan, np.nan
    u, p = mannwhitneyu(a, b, alternative="two-sided")
    return u / (len(a) * len(b)), p


def sustained_earliest(sig_mask, offsets, upto=PRE_HOUR, max_gap=1):
    """Earliest offset e such that from e to `upto` the mask is True with at
    most `max_gap` total gaps. Returns None if `upto` itself is not sig."""
    idx = {o: i for i, o in enumerate(offsets)}
    if upto not in idx or not sig_mask[idx[upto]]:
        return None
    earliest = upto
    gaps = 0
    o = upto - 1
    while o in idx:
        if sig_mask[idx[o]]:
            earliest = o
        else:
            gaps += 1
            if gaps > max_gap:
                break
        o -= 1
    return earliest


def main():
    with open(os.path.join(RESULTS_DIR, "windows.pkl"), "rb") as f:
        W = pickle.load(f)

    # merge derivatives windows if built (aligned by symbol + bar open time)
    dpath = os.path.join(RESULTS_DIR, "deriv_windows.pkl")
    if os.path.exists(dpath):
        with open(dpath, "rb") as f:
            D = pickle.load(f)

        def keyed(meta):
            return list(zip(meta["symbol"], meta["t_open_ms"]))

        for side, zkey in (("ev", "ev_z"), ("ct", "ct_z")):
            src_idx = {k: i for i, k in enumerate(keyed(D[f"{side}_meta"]))}
            rows = [src_idx.get(k, -1) for k in keyed(W[f"{side}_meta"])]
            rows = np.array(rows)
            ok = rows >= 0
            for feat in D["features"]:
                M = np.full((len(rows), len(W["offsets"])), np.nan)
                M[ok] = D[zkey][feat][rows[ok]]
                W[zkey][feat] = M
        W["features"] = W["features"] + D["features"]
        print(f"merged {len(D['features'])} derivatives features")

    offsets = list(W["offsets"])
    oi = {o: i for i, o in enumerate(offsets)}
    ev_meta, ct_meta = W["ev_meta"], W["ct_meta"]
    succ = ev_meta["success"].values.astype(bool)
    print(f"{len(ev_meta)} events ({succ.sum()} successful), "
          f"{len(ct_meta)} controls\n")

    pre = [o for o in offsets if o <= PRE_HOUR]
    band_late = [oi[o] for o in range(-4, 0)]
    band_early = [oi[o] for o in range(-16, -8)]
    band_very_early = [oi[o] for o in range(-32, -16)]
    band_dir = [oi[o] for o in range(-8, 0)]

    rows, offset_rows = [], []
    all_p2, all_p1, keys = [], [], []

    for feat in W["features"]:
        E = W["ev_z"][feat][succ]          # successful events only
        C = W["ct_z"][feat]
        Ef = W["ev_z"][feat][~succ]        # failed breakouts

        # direction from pooled late-band AUC
        a_dir, _ = auc_from_mw(E[:, band_dir].ravel(), C[:, band_dir].ravel())
        d = 1.0 if (np.isnan(a_dir) or a_dir >= 0.5) else -1.0

        # per-offset two-sample & one-sample tests
        for o in offsets:
            j = oi[o]
            auc, p2 = auc_from_mw(E[:, j], C[:, j])
            ez = E[:, j]
            ez = ez[np.isfinite(ez)]
            try:
                p1 = wilcoxon(ez).pvalue if len(ez) >= 20 else np.nan
            except ValueError:
                p1 = np.nan
            offset_rows.append({"feature": feat, "offset": o, "auc": auc,
                                "p_two_sample": p2, "p_one_sample": p1,
                                "median_event_z": float(np.nanmedian(E[:, j])),
                                "median_control_z":
                                    float(np.nanmedian(C[:, j]))})
            all_p2.append(p2)
            all_p1.append(p1)
            keys.append((feat, o))

    q2 = bh_fdr(all_p2)
    q1 = bh_fdr(all_p1)
    odf = pd.DataFrame(offset_rows)
    odf["q_two_sample"] = q2
    odf["q_one_sample"] = q1

    per_symbol_min = 5
    for feat in W["features"]:
        E = W["ev_z"][feat][succ]
        C = W["ct_z"][feat]
        Ef = W["ev_z"][feat][~succ]
        sub = odf[odf.feature == feat].set_index("offset")
        a_dir = np.nan
        av, _ = auc_from_mw(E[:, band_dir].ravel(), C[:, band_dir].ravel())
        a_dir = av
        d = 1.0 if (np.isnan(a_dir) or a_dir >= 0.5) else -1.0

        def band_auc(band):
            a, _ = auc_from_mw(E[:, band].ravel(), C[:, band].ravel())
            return a

        # sustained earliest significant offset (two-sample, direction-aware)
        signed_auc = d * (sub.loc[pre, "auc"].values - 0.5) + 0.5
        sig2 = ((sub.loc[pre, "q_two_sample"].values < 0.05)
                & (signed_auc >= AUC_MIN_SIG))
        e2 = sustained_earliest(sig2, pre)
        sig1 = (sub.loc[pre, "q_one_sample"].values < 0.05)
        e1 = sustained_earliest(sig1, pre)

        # per-event trigger: statistic = max over the -32..-1 window of the
        # 2-bar running minimum of signed z. Threshold set on CONTROLS at the
        # 90th percentile -> FPR fixed at 10% for every feature, so hit rates
        # and leads are directly comparable across features.
        pre_idx = [oi[o] for o in pre]

        def run_min2(M):
            Z = d * M[:, pre_idx]
            Zprev = np.roll(Z, 1, axis=1)
            Zprev[:, 0] = np.nan
            return np.fmin(Z, Zprev)          # (n, n_pre) 2-bar min

        S_e, S_c = run_min2(E), run_min2(C)
        stat_c = np.nanmax(S_c, axis=1)
        thr = np.nanpercentile(stat_c[np.isfinite(stat_c)], 90)
        cross_e = S_e >= thr
        hit_e = cross_e.any(axis=1)
        first_e = np.full(len(S_e), np.nan)
        idx_first = np.argmax(cross_e, axis=1)
        first_e[hit_e] = np.array(pre)[idx_first[hit_e]]
        hit_c = (S_c >= thr).any(axis=1)
        leads = np.array([lead_minutes(o) for o in first_e[hit_e]])

        # symbol consistency
        sym_e = ev_meta.loc[succ, "symbol"].values
        sym_c = ct_meta["symbol"].values
        agree, total = 0, 0
        for s in np.unique(sym_e):
            me, mc = sym_e == s, sym_c == s
            if me.sum() < per_symbol_min or mc.sum() < per_symbol_min:
                continue
            a_s, _ = auc_from_mw(E[me][:, band_dir].ravel(),
                                 C[mc][:, band_dir].ravel())
            if np.isnan(a_s):
                continue
            total += 1
            if (a_s - 0.5) * (a_dir - 0.5) > 0:
                agree += 1
        consistency = agree / total if total else np.nan

        a_sf, _ = auc_from_mw(E[:, band_dir].ravel(),
                              Ef[:, band_dir].ravel()) if len(Ef) else (np.nan,
                                                                        np.nan)

        hit_rate = float(hit_e.mean())
        fpr = float(hit_c.mean())          # ~0.10 by construction
        auc_late = band_auc(band_late)
        auc_early = band_auc(band_early)
        signed_late = d * (auc_late - 0.5) + 0.5
        signed_early = d * (auc_early - 0.5) + 0.5
        # --- quality tier (redundancy handled after the loop) ---
        strong_late = (e2 is not None and e2 <= -4 and signed_late >= 0.58
                       and (np.isnan(consistency) or consistency >= 0.85))
        strong_early = (e2 is not None and e2 <= -16 and signed_early >= 0.55
                        and (np.isnan(consistency) or consistency >= 0.80))
        if strong_late or strong_early:
            rec = "KEEP"
        elif (e2 is not None and signed_late >= 0.55
              and (np.isnan(consistency) or consistency >= 0.70)):
            rec = "TEST FURTHER"
        else:
            rec = "DISCARD"

        rows.append({
            "feature": feat,
            "direction": "+" if d > 0 else "-",
            "auc_late_-4..-1": auc_late,
            "auc_early_-16..-9": band_auc(band_early),
            "auc_veryearly_-32..-17": band_auc(band_very_early),
            "earliest_sig_offset": e2,
            "lead_min_vs_1h_close": lead_minutes(e2) if e2 is not None
                                    else np.nan,
            "onesample_earliest_offset": e1,
            "onesample_lead_min": lead_minutes(e1) if e1 is not None
                                  else np.nan,
            "hit_rate_fpr10": hit_rate,
            "fpr": fpr,
            "median_trigger_lead_min": float(np.median(leads)) if len(leads)
                                       else np.nan,
            "symbol_consistency": consistency,
            "n_symbols": total,
            "succ_vs_fail_auc": a_sf,
            "recommendation": rec,
        })

    stats = pd.DataFrame(rows)
    stats["signed_auc_late"] = np.where(
        stats["direction"] == "+", stats["auc_late_-4..-1"],
        1 - stats["auc_late_-4..-1"])

    # ---- redundancy pass: among KEEP candidates, greedily accept by signed
    # late AUC; a candidate correlated >0.7 (|rho| of mean z over -8..-1,
    # successful events) with an accepted feature is downgraded.
    band_mean = {}
    for feat in W["features"]:
        band_mean[feat] = np.nanmean(W["ev_z"][feat][succ][:, band_dir],
                                     axis=1)
    stats["redundant_with"] = ""
    cand = stats[stats.recommendation == "KEEP"] \
        .sort_values("signed_auc_late", ascending=False)
    accepted = []
    for _, r in cand.iterrows():
        f = r.feature
        dup = None
        for a in accepted:
            x, y = band_mean[f], band_mean[a]
            ok = np.isfinite(x) & np.isfinite(y)
            if ok.sum() > 50 and abs(np.corrcoef(x[ok], y[ok])[0, 1]) > 0.7:
                dup = a
                break
        if dup is None:
            accepted.append(f)
        else:
            stats.loc[stats.feature == f, "recommendation"] = "TEST FURTHER"
            stats.loc[stats.feature == f, "redundant_with"] = dup

    order = {"KEEP": 0, "TEST FURTHER": 1, "DISCARD": 2}
    stats = stats.sort_values(
        ["recommendation", "signed_auc_late"],
        ascending=[True, False],
        key=lambda s: s.map(order) if s.name == "recommendation" else s)
    stats.to_csv(os.path.join(RESULTS_DIR, "feature_stats.csv"), index=False)
    odf.to_csv(os.path.join(RESULTS_DIR, "offset_stats.csv"), index=False)
    with pd.option_context("display.width", 250, "display.max_columns", 50):
        print(stats.to_string(index=False))


if __name__ == "__main__":
    main()
