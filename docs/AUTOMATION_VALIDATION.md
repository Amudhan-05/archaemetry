# Automation validation — profile extraction

Empirical validation of the scripted profile pipeline ([`../scripts/`](../scripts/)),
establishing where automation matches GigaMesh-grade output and where it does not yet.
All results are reproducible from open data; no proprietary tools involved.

## Test data

- **Complete vessel (ground truth):** Attic white-ground lekythos, *3D Archaeological
  Greek Pottery* dataset, [Zenodo record 5102757](https://zenodo.org/records/5102757),
  CC-BY-SA-4.0. Mesh is metric (bbox 50 × 114 × 50 mm), ~122k vertices, one handle.
- **Simulated rim sherd:** a 70° angular wedge of the top ~38% (rim + neck + shoulder)
  of the same vessel, cropped with `tools/crop_wedge.py`. Because it is cropped from a
  known vessel, we have exact ground truth for the fragment's true profile.

## Result 1 — Stage 2 cleanup is fully automatable

Input: a raw Meshroom mesh (753k verts) with the sherd fused into turntable, backdrop,
and noise — **710 connected components**. `clean_mesh.py` keeps the largest component
*by face count* and drops the rest:

- 710 components → **1**; turntable (spatially large but face-sparse) and 708 noise
  islands removed; sherd (face-dense) retained. Deterministic, zero manual clicks.
- Confidence report: `kept_fraction 0.88`, `compactness 0.30`, `single_body true`.

The principle: a flat turntable is *few* triangles over a large area, while the
photographed sherd is *many* triangles over a small area — so "largest by face count"
separates them cleanly. (Production guard: pair with a compactness/size sanity check,
since a heavily-textured turntable could rival the sherd's face count.)

## Result 2 — Stage 3 matches the silhouette on a complete vessel

`extract_profile.py` on the lekythos, fully automatic:

![lekythos profile](validation/lekythos_profile_overlay.png)

- **Axis auto-found:** `[0.03, 0.999, 0.01]` — vertical, correct.
- **Profile traces the silhouette:** flared foot, tapering body, sharp shoulder (~75 mm),
  narrowing neck, rim flare — all recovered.
- **Handle robustly rejected:** the median-over-angle radius (black) stays on the true
  wall; the 98th-percentile (red dotted) bulges exactly where the handle is. This is the
  automatable equivalent of GigaMesh ignoring non-symmetric features.
- Metric output in mm; no smoothing (preserves real surface detail per the handoff).

## Result 3 — a partial fragment fails the mm target (axis is the bottleneck)

Same script on the 70° rim sherd, compared to ground truth (`tools/compare_profiles.py`):

![sherd vs truth](validation/rim_sherd_vs_truth.png)

- **Radius error vs truth: RMS 4.4 mm, MAE 3.6 mm, max 10.8 mm** (on a vessel whose max
  radius is only ~22 mm — i.e. ~20% error).
- The confidence report correctly self-flags the fragment: `mean_angular_coverage 0.28`
  (< 0.5 ⇒ partial sherd).
- **Root cause:** the symmetry axis, re-fit from a narrow fragment, tilts ~7°. The
  *shape* extraction is fine; the *axis* is under-constrained, and its tilt propagates
  into radius error that grows with distance from the rim (right panel).

## Interpretation

The specialist-vs-automatable tradeoff resolves to a single technical fact: **for
fragments, robust axis estimation is the whole game**, and it is precisely GigaMesh's
specialist strength (axis from interior-surface circle centres). Plane-sectioning and
handle rejection — the parts that *looked* like they needed a specialist tool — are
readily automatable and already work here.

**Consequence for deployment:**

- **Complete / large-fragment ware** → the automatable lane already produces
  silhouette-accurate profiles.
- **Small rim sherds** → until the `rim_arc` axis method is built and shown to reach
  sub-mm, use the **bookend** deployment: automate SfM + cleanup + publish, keep GigaMesh
  for the profile itself.

## Result 4 — rim-arc axis: fixes direction, but diameter is the real limit

The `rim_arc` axis method (`extract_profile.py --axis-method rim_arc`) isolates the
horizontal circular arcs on the mesh border (rim + clean breaks) using height bands, and
sets the axis from them — the digital rim-chart method.

On the 70° rim wedge it **cut the axis *tilt* from ~7° (PCA) to ~1°** (arc fit residual
0.001). But the profile RMS did **not** improve — because the limiting error on a small
fragment is not axis *direction*, it is the **circle centre / diameter**, which a short
arc under-determines:

- A ~60° arc pins the axis *direction* (plane normal) well, but its *centre* — and hence
  the vessel radius — is highly uncertain. Radius is measured from that centre, so the
  profile inherits the diameter error.
- When two bands are used and they sit close together (a short section), the line through
  their two noisy centres becomes an unstable *direction* too.

This matches archaeological reality: a tiny rim sherd gives an unreliable vessel diameter
no matter how it is measured — you need a sufficient arc of the rim. It is a
**data limitation, not an algorithm bug.**

**Caveat on the numbers:** an angle sweep (60–360°) did not produce a clean
accuracy-vs-arc curve, because the comparison harness (`compare_profiles.py`) aligns full
and fragment by a depth-from-rim heuristic and re-fits both axes — that alone contributes
several mm (a full 360° ring still shows ~5 mm). So absolute RMS from the current harness
is not trustworthy below ~5 mm. A proper oracle should register the fragment into the
known crop frame (the crop transform is known exactly) and measure axis-angle, axis-offset
and radius error directly. That is the next validation task.

## Deployment implication

- **Complete vessels / large fragments with a long rim arc** → the automatable lane is
  viable; axis and diameter are well-constrained.
- **Small rim sherds (short arc)** → diameter is fundamentally uncertain from geometry
  alone; keep the **bookend** deployment (GigaMesh for the profile, with its assisted /
  manual axis + diameter setting), which is exactly why that capability exists. This is a
  defensible, quantified argument for architecture E in the methods section.

## Next validation step

Build a ground-truth-registered oracle (use the known crop transform, not depth-from-rim
alignment) and re-measure axis error + radius error vs arc length. That yields a clean
"minimum rim arc for X mm" curve — a directly useful field guideline and a strong figure
for the funding writeup.
