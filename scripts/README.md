# archaemetry — scripted pipeline

Automation for the pottery-sherd pipeline described in [`../README.md`](../README.md)
and [`../docs/handoff.md`](../docs/handoff.md). This folder turns the manual,
GUI-driven stages into headless, parameter-driven scripts so a field user can set a
few values and run, and so the pipeline can eventually be packaged to run
machine-independently (notebook / container / hosted).

## Architecture: automate *around* the specialist tool

Not every stage should be automated the same way. The pipeline splits into two lanes:

```
                     ┌─────────────── AUTOMATABLE LANE (this folder) ───────────────┐
  capture ─▶ SfM/MVS ─▶ clean_mesh.py ─▶ extract_profile.py ─▶ (Inkscape CLI, TODO) ─▶ profile
  (rig)     COLMAP/     Stage 2          Stage 3                Stage 4
            Meshroom    remove bg,       axis fit +
                        keep sherd       plane-section
                                    │
                                    └──▶ GigaMesh (manual GUI station) ──▶ Inkscape
                                         Stage 3-specialist:
                                         rollout + faint-decoration (MSII)
                                         for DECORATED ware only
```

- **Plain rotationally-symmetric sherds** → fully automatable lane (the scripts here).
- **Decorated / fine ware (rollouts, faint incised decoration)** → GigaMesh's genuinely
  specialist capabilities; keep it as a manual desktop station. Don't package it —
  package *around* it.

**Two deployment shapes, both valid** (pick per accuracy needs):

1. **Bookend** — automate *up to* GigaMesh (SfM + cleanup + rough orientation) and
   *after* GigaMesh (Inkscape publish), leaving the profile/rollout as manual GigaMesh
   clicks. Lowest risk; keeps GigaMesh's axis/profile quality; a human still touches
   every sherd.
2. **Full-auto** — replace GigaMesh's middle with `extract_profile.py` for plain sherds.
   True walk-away, *if* it hits mm accuracy on fragments (see Validation status — the
   rim-arc axis method is the open item that decides this).

## The parameter surface

The entire field-facing configuration is [`config/sherd.example.yaml`](config/sherd.example.yaml).
Most values have defaults; a field user typically edits only `images_dir`, the `scale`
block, and `ware`. Each run also emits a **confidence report** (JSON) —
`axis_residual`, `angular_coverage`, `kept_fraction` — that is what decides whether a
result is trustworthy or should be flagged for human review / routed to the GigaMesh
station.

## Scripts

| Script | Stage | What it does |
|---|---|---|
| `clean_mesh.py` | 2 | Keep the largest connected component (drops turntable + noise islands, deterministically), optional capped hole-fill. Replaces the manual MeshLab crop. Emits `*_report.json`. |
| `extract_profile.py` | 3 | Auto-fit the symmetry axis (PCA seed → circle-centre refinement, robust to handles/broken edges), project to cylindrical coords, emit a metric SVG profile + validation overlay + confidence report. Replaces GigaMesh's profile step for plain ware. |
| `tools/diagnose_components.py` | — | Inspect the connected-component structure of a raw SfM mesh (sherd vs turntable vs noise). |
| `tools/render_mesh.py` | — | Quick PNG render of a mesh for visual checks. |
| `tools/crop_wedge.py` | — | Crop a complete vessel to an angular wedge to *simulate* a rim/body sherd with ground truth. |
| `tools/compare_profiles.py` | — | Quantify sherd-partiality error: fragment profile vs full-vessel ground truth, RMS/max radius error in mm. |

### Usage

```bash
python -m venv .venv && .venv/Scripts/activate       # Windows; use bin/activate on *nix
pip install -r requirements.txt

# Stage 2 — cleanup (zero manual steps)
python clean_mesh.py  in_mesh.obj  out_clean.obj  --report clean_report.json

# Stage 3 — profile extraction
python extract_profile.py  out_clean.obj  out_dir/   --bands 300 --assume-mm-per-unit 1.0
# -> out_dir/profile.svg, profile_overlay.png, profile_report.json
```

Paths with spaces are fragile through some of the CLI tools (GigaMesh in particular);
work under a space-free root.

## Validation status

Measured on the open CC-BY-SA lekythos mesh (Zenodo 5102757), with a cropped wedge used
as a ground-truthed "rim sherd". Full write-up + figures:
[`../docs/AUTOMATION_VALIDATION.md`](../docs/AUTOMATION_VALIDATION.md).

| Case | Result |
|---|---|
| Stage 2 cleanup | 710 components → 1; turntable + noise removed deterministically ✅ |
| Stage 3, complete vessel | Profile matches silhouette; handle auto-rejected; axis auto-found ✅ |
| Stage 3, 70° rim sherd | Runs + self-flags as partial, but **RMS 4.4 mm / max 10.8 mm** vs truth ❌ |

**Open item (the crux):** on a partial fragment the whole error comes from axis
estimation — a narrow sherd under-constrains the PCA fit, tilting the axis ~7°, and that
tilt accumulates into radius error away from the rim. The fix is a **rim-arc axis
method** (fit the rim's circular edge → axis = rim-plane normal, diameter = arc radius),
mirroring archaeological rim-chart practice and GigaMesh's circle-centre approach. Until
that lands, use the **bookend** deployment (keep GigaMesh for the profile) for fragments.

## Not yet built

- Stage 1 wrapper (COLMAP/Meshroom batch + per-image masking + scale from ArUco).
- Stage 4 (Inkscape CLI: line weights, scale bar, hatching, CVA template).
- `rim_arc` / `inner_surface` axis methods in `extract_profile.py`.
- A single `run.py` that reads `sherd.yaml` and drives the whole lane.
- Packaging (Dockerfile / notebook) for machine-independent execution.
