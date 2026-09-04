# 3D Pottery Sherd Documentation — Project Handoff

## Project Goal

Build a low-cost, field-portable photogrammetry (SfM/MVS) pipeline to digitise archaeological pottery sherds as proof of concept for a funding application. The end deliverable per sherd is a metrically accurate 3D mesh, a publication-standard profile drawing (cross-section), and — for decorated ware — a flattened surface rollout showing the full decorative programme. The pipeline is being validated cheaply first (consumer camera, DIY light tent, free/low-cost software) with the explicit intention of scaling up hardware and software once funded.

Benchmark reference: a real museum dataset (Swedish National Historical Museums, Pitted Ware Culture rim fragment, 149 images, Canon 5DS R, RealityCapture, 2,598,096 polygons) is being used to validate that this budget pipeline can approach professional output quality.

---

## Current Hardware

| Component | Spec |
|---|---|
| Camera | Nikon Coolpix AW100 (16MP, small sensor, sensor width 6.17mm) — acceptable for proof of concept only |
| Laptop | AMD Ryzen 7 5000 series, Nvidia RTX 3050 (4GB VRAM) |
| Note | AW100 has wide-angle distortion and no RAW — fine for proving the pipeline, not for final accuracy. Upgrade path: mirrorless + 50mm macro lens (e.g. Sony A6000-series) |

---

## Capture Setup (Built)

**Light tent (DIY cardboard):**
- Interior ~60cm (W) x 50cm (D) x 50cm (H)
- Left and right side panels only are cut open and covered with white diffusion fabric (thin cotton/dupatta or tracing paper)
- Back wall and top are solid, lined inside with white chart paper to bounce light
- Front fully open for camera
- Floor lined with matte white/grey chart paper

**Lighting:**
- Two identical PAR20 LED bulbs, 7–8W, 6500K daylight, dimmable, in clamp lamp holders
- Each wired through an inline LED-compatible rotary dimmer (Havells/Anchor, plug-and-play or self-wired — live wire passes through dimmer, neutral/earth bypass it)
- Positioned ~20–30cm from diffusion panels, ~45° elevation, fixed permanently using cardboard cones/sleeves attached to the tent exterior so angle/distance never drift between sessions
- Both lamps must be identical model/batch — mismatched colour temperature ruins texture reconstruction
- For sherds with slip/gloss: cross-polarised lighting (polarising filters on lights + rotated circular polariser on lens) eliminates specular reflections

**Turntable:**
- Manual lazy susan (e.g. Ikea Snudda), ~30cm diameter
- Marked in 10° increments
- Matte white/grey surface (add chart paper if needed)

**Sherd support:**
- Grey/brown modelling clay to stabilise and angle the sherd (no 3D printing needed at PoC stage)
- Sand tray as a faster alternative for batches
- For underside capture: second session with sherd propped ~45° on clay, meshes merged later in MeshLab

**Scale reference (ArUco markers):**
- 6–10 markers minimum, printed matte (never glossy), 3–5cm each
- 4 flat on turntable at 12/3/6/9 o'clock around sherd
- 2 on angled card tents for mid/high elevation visibility
- Distances between specific marker pairs measured with a digital calliper and recorded — this is the source of all dimensional accuracy downstream

**Reproducible lighting (grey card protocol):**
- One physical 18% grey card (printed once, never reprinted, stored flat away from light) or your own first-session shot as reference
- Shoot it at the start of every session before placing the sherd
- Check R=G=B (colour neutrality) and match absolute brightness to your recorded reference values (e.g. R142 G142 B142)
- Adjust dimmer to match before removing the card and placing the sherd
- Camera white balance must be locked manually (Daylight/Cloudy) — never Auto

**Camera settings:**
- Lowest ISO, fixed wide-angle zoom (never changed mid-session), 2-second self-timer or ML-L3 IR remote (if AW100 supports it) to avoid shake

---

## Shooting Protocol

- ~80–90 to 150 images per sherd
- Three elevation rings + overhead: Low (~15–20°), Mid (~45°), High (~70°), Overhead (~90°, 1–3 shots)
- 10° rotation increments per ring (36 shots/ring for Low and Mid); reduce to 5° increments if StructureFromMotion later fails due to insufficient overlap
- Camera stays fixed per ring; only the turntable rotates
- 60–70% image overlap required between adjacent shots
- Legible label/sherd ID photographed as first frame of every set
- RAW cull, ICC colour profile (from a ColorChecker Passport shot), shadow lift (esp. dark/black-slip wares), export to JPG 95+ — done in RawTherapee before Meshroom (skip if AW100, which has no RAW)

---

## Software Pipeline (current, updated with RealityCapture)

### Stage 1 — Photogrammetry: RealityCapture (replaces Meshroom as primary tool)

**Why the switch:** Meshroom was taking 20+ hours on 150 images due to CPU-bound Texturing and suboptimal DepthMap settings. RealityCapture is 5–10x faster on the same hardware (same tool the benchmark museum dataset used) and handles scale-setting and background masking internally, which Meshroom + MeshLab had to do manually.

**Workflow in RealityCapture:**
1. Import images
2. Define scale using ArUco marker calliper measurements (built-in ground control/scale bar tool)
3. Run alignment → dense reconstruction → meshing
4. Apply masking to exclude background before meshing (reduces manual cleanup later)
5. Export textured mesh as OBJ — output is already scaled and largely clean

**Cost:** pay-per-image (~$0.01/image) after a free tier — negligible for proof of concept, budget it as a line item for a funded/production phase.

**Fallback/comparison tools:**
- **Meshroom** (free, AliceVision) — still useful, and free forever, but slow on 4GB VRAM. If used, key settings for max quality: FeatureExtraction preset=high, DepthMap downscale=1 (try) or 2 (safe fallback), Meshing MaxPoints=10,000,000, MeshFiltering smooth iterations=0 (don't erase real surface detail), Texturing 8192/LSCM. Expect ~3–5 hrs on RTX 3050 at downscale 2. If GPU util is low (~10%) during Texturing, that's normal — Texturing is CPU-bound in Meshroom by design; the real target for speed fixes is DepthMap and image count.
- **Metashape** — faster than Meshroom, slower than RealityCapture, 30-day free trial, ~₹9–12k academic licence, more reliable on difficult (dark/glossy) surfaces.
- **Google Colab (free/cheap GPU)** or **Vast.ai (~$0.20–0.40/hr GPU rental)** — ways to run Meshroom on much better GPUs than the local RTX 3050 if staying free-tool-only.

### Stage 2 — MeshLab (reduced role when using RealityCapture)

With RealityCapture doing scale + rough masking internally, MeshLab is now a ~10 minute finishing step, not a 30–45 minute processing stage:
- Residual background cleanup (Select Faces in Rectangular Region → Delete Selected Faces and Vertices) — RealityCapture's auto-mask is rarely perfect
- Orientation: align vessel rotation axis to Y axis (Transform: Rotate) — required for GigaMesh's axis detection to work
- Hole fill: underside contact point gap (Close Holes) — RealityCapture doesn't solve this
- **Dual OBJ export — critical, unchanged regardless of upstream tool:**
  - `sherd_ID_raw.obj` — cleaned/scaled/oriented, before any geometry repair (primary unedited archaeological record)
  - `sherd_ID_clean.obj` — the working version with holes filled etc.
  - Never overwrite the raw version

**Do not simplify or smooth the mesh before GigaMesh** — full resolution gives more accurate profiles; smoothing erases real surface detail (e.g. impressed decoration) and directly degrades thickness measurements. Only simplify after profile/rollout extraction if performance is genuinely unusable.

### Stage 3 — GigaMesh (replaces PyPotteryLens + PyPotteryInk — current standard tool)

Free, open-source, purpose-built for rotationally symmetric vessels — does axis detection, profile extraction, AND rollout in one tool.

- Input: `sherd_ID_clean.obj`
- Axis detection: automatic, uses the *inner* surface by default (outer surfaces with decoration/relief break rotational symmetry). If axis detection is wrong, re-orient more carefully in MeshLab first — don't try to fix it in GigaMesh.
- **Profile output:** metrically calibrated SVG cross-section, interior/exterior wall lines separated, wall thickness extractable at intervals
- **Rollout output** (decorated/fine ware only, not needed for plain utility ware): projects coloured 3D surface onto frustum sections fitted to vessel profile, unrolls into flat to-scale image. Requires: clean evenly-lit texture (why cross-polarised lighting + shadow-lift matter), full 360° exterior coverage in the mesh, correct axis alignment.

> Note: PyPotteryLens/PyPotteryInk are legacy references from earlier in this project — GigaMesh has since superseded both for this pipeline.

### Stage 4 — Inkscape (unchanged)

Final manual adjustments per CVA publication conventions:
- Line weight 0.3mm standard
- Scale bar in centimetres
- Add hatching to section cut if GigaMesh hasn't already
- Manually complete internal profile by hand if inner surface data was sparse, using GigaMesh's exterior line as reference

---

## Folder Structure

```
pottery-sfm/
  sherd_ID/
    raw_images/          <- original camera files, never modified
    processed_images/    <- JPGs from RawTherapee (if RAW-capable camera used)
    realitycapture_project/  (or meshroom_project/)
    meshlab/
      sherd_ID_raw.obj    <- unedited primary record
      sherd_ID_clean.obj  <- cleaned working version
    gigamesh/
      sherd_ID_profile.svg
      sherd_ID_rollout.svg   (if applicable)
    output/
      sherd_ID_drawing.svg   <- final Inkscape output
    notes.txt             <- session notes, grey card RGB values, marker calliper measurements
  reference/
    grey-card-reference.jpg
    aruco-markers/
    marker-measurements.csv
```

---

## Error/Uncertainty Reporting (for eventual publication)

- Take ≥3 independent photo sets of the same sherd, repositioning sherd/scale bar/targets slightly between sets
- Extract thickness at the same 5–10 points across all models
- Compare to calibrated digital calliper measurements (0.01mm accuracy) at the same points
- Report mean difference and standard deviation as method error — this separates repeatability (same session) from reproducibility (different sessions) and gives defensible accuracy figures for a methods section

---

## Archiving / Data Management

- Keep RAW files forever if camera supports RAW — they are the primary record, never delete after JPG export
- The unedited `_raw.obj` is equivalent to a site photograph — permanent record
- For publication/sharing: upload OBJ + texture to Zenodo (free DOI) or Sketchfab (best web viewer, PBR support)
- Default licensing: CC BY-NC-SA 4.0 unless institution/museum specifies otherwise

---

## Budget Snapshot (proof of concept, India, approximate)

| Item | Cost |
|---|---|
| Turntable | ₹900 |
| DIY light tent (cardboard + fabric) | ₹150–300 |
| 2x PAR20 7W 6500K dimmable bulbs | ₹400–700 |
| 2x clamp lamp holders | ₹200–400 |
| 2x inline LED dimmers | ₹300–600 |
| Chart paper, clay, misc | ₹200–300 |
| ArUco markers (printed) | ₹0–50 |
| USB card reader + spare microSD | ₹450–600 |
| Digital calliper | ₹300–500 |
| **Hardware total** | **~₹3,000–4,300** |
| RealityCapture (per-image, PoC scale) | negligible |
| Metashape (optional, 30-day trial) | free trial / ₹9–12k academic |

All core pipeline software (MeshLab, GigaMesh, Inkscape) is free.

---

## Open Threads / Next Steps

1. Validate RealityCapture output against the Swedish museum benchmark dataset (target ~2.6M polygons on 149 images) to confirm pipeline equivalence for the funding writeup.
2. Test whether AW100's wide-angle distortion causes usable-but-imperfect meshes, or whether a camera upgrade is needed before shooting real sherds (as opposed to the benchmark dataset).
3. Run the 3-session error/reproducibility protocol once one sherd clears the full pipeline, to generate defensible accuracy figures for the methods section.
4. Decide production-scale processing path (local GPU rental via Vast.ai vs. RealityCapture per-image cost vs. Metashape licence) once funded.
5. A full Word-formatted version of the setup/workflow (with tables) was drafted earlier in this project as `sfm_pottery_setup_workflow.docx` — regenerate/update it from this handoff if a formatted deliverable is needed again.
