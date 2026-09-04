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

## Next validation step

Implement the **rim-arc axis method** (fit the rim's circular edge: axis = rim-plane
normal, diameter = arc radius — the digital form of the archaeological rim chart), then
re-run `tools/compare_profiles.py` on the same wedge. If sherd RMS drops toward sub-mm,
the manual GigaMesh middle can be removed for plain rim sherds. If not, these numbers are
the defensible argument for keeping it (architecture E) in the methods section.
