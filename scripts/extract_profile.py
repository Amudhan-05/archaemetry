"""Stage 3 - automated profile extraction from a (near-)rotationally-symmetric
vessel or sherd mesh.  Replaces the GigaMesh GUI step for plain profiles.

Method (same principle GigaMesh uses):
  1. Seed the symmetry axis with PCA (longest extent for a tall vessel).
  2. Refine by the circle-centers method: slice perpendicular to the axis,
     robustly fit a circle to each slice (outlier rejection so a handle / broken
     edge does not bias the centre), then re-fit the axis through the centres.
     Iterate.
  3. Express every vertex in cylindrical coords (h along axis, r from axis).
  4. Per height band, take a robust radius (median over angle => ignores the
     handle, which is a minority of the circumference) -> exterior profile r(h).
  5. Emit an SVG profile (mirrored to show the full outline) + a validation
     overlay PNG + a JSON confidence report.

Usage:
  python extract_profile.py IN.(ply|obj) OUTDIR [--bands N] [--assume-mm-per-unit K]
"""
import argparse
import json
import os
import sys
import numpy as np
import open3d as o3d


# ---------- geometry helpers ----------
def robust_circle_fit(P2, n_iter=3, k=2.5):
    """Algebraic (Kasa) circle fit with iterative outlier rejection.
    P2: (N,2). Returns center(2,), radius, inlier_fraction."""
    idx = np.ones(len(P2), dtype=bool)
    cx = cy = r = 0.0
    for _ in range(n_iter):
        p = P2[idx]
        if len(p) < 8:
            break
        u, v = p[:, 0], p[:, 1]
        A = np.column_stack([u, v, np.ones_like(u)])
        b = -(u**2 + v**2)
        sol, *_ = np.linalg.lstsq(A, b, rcond=None)
        D, E, F = sol
        cx, cy = -D / 2, -E / 2
        r = np.sqrt(max(cx**2 + cy**2 - F, 1e-12))
        d = np.abs(np.sqrt((P2[:, 0] - cx)**2 + (P2[:, 1] - cy)**2) - r)
        mad = np.median(d) + 1e-9
        idx = d < k * mad
    return np.array([cx, cy]), r, float(idx.mean())


def basis_from_dir(d):
    """Orthonormal (e1,e2) spanning the plane perpendicular to unit vector d."""
    d = d / np.linalg.norm(d)
    a = np.array([1.0, 0, 0]) if abs(d[0]) < 0.9 else np.array([0, 1.0, 0])
    e1 = np.cross(d, a); e1 /= np.linalg.norm(e1)
    e2 = np.cross(d, e1)
    return e1, e2, d


def fit_axis(V, n_bands=40, n_refine=4):
    """Return (point_on_axis, unit_dir, per-slice residual)."""
    c = V.mean(0)
    cov = np.cov((V - c).T)
    evals, evecs = np.linalg.eigh(cov)
    d = evecs[:, np.argmax(evals)]          # PCA seed = major axis
    p0 = c.copy()
    resid = np.nan
    for _ in range(n_refine):
        e1, e2, d = basis_from_dir(d)
        h = (V - p0) @ d
        lo, hi = np.percentile(h, [5, 95])   # trim caps
        edges = np.linspace(lo, hi, n_bands + 1)
        centers3d, resids = [], []
        for i in range(n_bands):
            m = (h >= edges[i]) & (h < edges[i + 1])
            if m.sum() < 30:
                continue
            Pw = V[m] - p0
            P2 = np.column_stack([Pw @ e1, Pw @ e2])
            ctr2, r, inl = robust_circle_fit(P2)
            hb = h[m].mean()
            c3 = p0 + ctr2[0] * e1 + ctr2[1] * e2 + hb * d
            centers3d.append(c3)
            resids.append(r)
        centers3d = np.array(centers3d)
        if len(centers3d) < 4:
            break
        # refit axis as best line through the circle centres
        cc = centers3d.mean(0)
        _, _, Vt = np.linalg.svd(centers3d - cc)
        d = Vt[0]
        p0 = cc
        # residual = how far the circle centres deviate from the fitted line
        proj = (centers3d - cc) @ d
        line_pts = cc + np.outer(proj, d)
        resid = float(np.sqrt(((centers3d - line_pts)**2).sum(1)).mean())
    return p0, d / np.linalg.norm(d), resid


def profile_from_axis(V, p0, d, n_bands=300):
    e1, e2, d = basis_from_dir(d)
    Pw = V - p0
    h = Pw @ d
    u = Pw @ e1
    v = Pw @ e2
    r = np.sqrt(u**2 + v**2)
    lo, hi = h.min(), h.max()
    edges = np.linspace(lo, hi, n_bands + 1)
    hs, r_med, r_max, cover = [], [], [], []
    for i in range(n_bands):
        m = (h >= edges[i]) & (h < edges[i + 1])
        if m.sum() < 10:
            continue
        ang = np.arctan2(v[m], u[m])
        # angular coverage: fraction of 24 sectors that contain a point
        filled = len(np.unique(np.floor((ang + np.pi) / (2 * np.pi) * 24).astype(int)))
        hs.append(0.5 * (edges[i] + edges[i + 1]))
        r_med.append(np.median(r[m]))       # robust wall radius (ignores handle)
        r_max.append(np.percentile(r[m], 98))
        cover.append(filled / 24.0)
    return (np.array(hs), np.array(r_med), np.array(r_max), np.array(cover))


# ---------- output ----------
def write_svg(hs, rs, path, mm, stroke=0.3):
    h0 = hs.min()
    H = (hs - h0) * mm
    R = rs * mm
    Rmax = R.max()
    # archaeological convention: profile line on the right, mirror on the left
    total_h = H.max()
    pad = 5
    W = 2 * Rmax + 2 * pad
    def pt(r, h, sign):
        x = Rmax + sign * r + pad
        y = total_h - h + pad
        return f"{x:.2f},{y:.2f}"
    right = " ".join(pt(r, h, +1) for r, h in zip(R, H))
    left = " ".join(pt(r, h, -1) for r, h in zip(R[::-1], H[::-1]))
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W:.1f}mm" height="{total_h+2*pad:.1f}mm" viewBox="0 0 {W:.1f} {total_h+2*pad:.1f}">
<polyline fill="none" stroke="black" stroke-width="{stroke}" points="{right}"/>
<polyline fill="none" stroke="black" stroke-width="{stroke}" points="{left}"/>
<line x1="{Rmax+pad:.1f}" y1="{pad}" x2="{Rmax+pad:.1f}" y2="{total_h+pad:.1f}" stroke="black" stroke-width="0.1" stroke-dasharray="2,2"/>
</svg>'''
    with open(path, "w") as f:
        f.write(svg)


def write_overlay(hs, r_med, r_max, cover, path, mm):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    H = (hs - hs.min()) * mm
    fig, ax = plt.subplots(1, 2, figsize=(9, 7), gridspec_kw={"width_ratios": [2, 1]})
    ax[0].plot(r_med * mm, H, "-k", lw=1.2, label="exterior r_median")
    ax[0].plot(-r_med * mm, H, "-k", lw=1.2)
    ax[0].plot(r_max * mm, H, ":", color="tab:red", lw=0.8, label="r_98pct (handle/bulges)")
    ax[0].set_aspect("equal"); ax[0].set_title("Extracted profile"); ax[0].legend(fontsize=7)
    ax[0].set_xlabel("radius (mm)"); ax[0].set_ylabel("height (mm)")
    ax[1].plot(cover, H, "-", color="tab:blue"); ax[1].set_xlim(0, 1)
    ax[1].set_title("angular coverage\n(1.0 = full ring)"); ax[1].set_xlabel("fraction")
    fig.tight_layout(); fig.savefig(path, dpi=110); plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("inp")
    ap.add_argument("outdir")
    ap.add_argument("--bands", type=int, default=300)
    ap.add_argument("--assume-mm-per-unit", type=float, default=1.0,
                    help="scale factor unit->mm (1.0 if mesh already in mm)")
    args = ap.parse_args()
    os.makedirs(args.outdir, exist_ok=True)

    mesh = o3d.io.read_triangle_mesh(args.inp)
    V = np.asarray(mesh.vertices)
    ext = V.max(0) - V.min(0)
    print(f"loaded {len(V):,} verts, bbox={ext.round(3)}")

    p0, d, resid = fit_axis(V)
    print(f"axis dir={d.round(3)}  circle-center residual={resid:.4g} units")

    hs, r_med, r_max, cover = profile_from_axis(V, p0, d, args.bands)
    mm = args.assume_mm_per_unit
    height_mm = (hs.max() - hs.min()) * mm
    maxr_mm = r_med.max() * mm
    print(f"profile: {len(hs)} bands, height={height_mm:.2f}mm, max radius={maxr_mm:.2f}mm")
    print(f"mean angular coverage={cover.mean():.2f}  (1.0=full vessel, <0.5=partial sherd)")

    svg = os.path.join(args.outdir, "profile.svg")
    png = os.path.join(args.outdir, "profile_overlay.png")
    write_svg(hs, r_med, svg, mm)
    write_overlay(hs, r_med, r_max, cover, png, mm)

    report = {
        "input": args.inp,
        "axis_dir": [round(float(x), 4) for x in d],
        "axis_residual_units": round(float(resid), 5),
        "bbox_units": [round(float(x), 4) for x in ext],
        "n_bands": int(len(hs)),
        "height_mm": round(height_mm, 3),
        "max_radius_mm": round(maxr_mm, 3),
        "mean_angular_coverage": round(float(cover.mean()), 3),
        "min_angular_coverage": round(float(cover.min()), 3),
    }
    with open(os.path.join(args.outdir, "profile_report.json"), "w") as f:
        json.dump(report, f, indent=2)
    print("\nreport:", json.dumps(report, indent=2))
    print("wrote:", svg, png)


if __name__ == "__main__":
    main()
