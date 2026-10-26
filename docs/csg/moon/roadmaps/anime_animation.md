# Anime Animation Roadmap

## Direction

Teach and assist a Japanese anime-style frame-by-frame workflow: storyboard,
layout, key poses, breakdowns, inbetweens, cleanup, color, cel shading, and
compositing. Limited animation is a valid artistic technique, not a deficiency
to be hidden by indiscriminate frame generation.

## Learning features

- Timing, spacing, arcs, anticipation, follow-through, and holds.
- Pose construction and silhouette feedback.
- Onion-skin comparisons and volume/proportion drift analysis.
- Guided key-pose and breakdown exercises.
- Explanations and redlines tied to the current shot.

## Production assistance

- Exposure sheet/timeline and layer-aware frame representation.
- Keypoint, line, region, and optical-flow correspondence.
- Forward/backward consistency and occlusion masks.
- Suggested breakdowns and inbetweens requiring acceptance.
- Motion-aware color and cel-shadow propagation.
- Cleanup, line stabilization, and flicker diagnostics.
- Image-sequence and video export with reproducible settings.

## Existing prototypes

The current same-coordinate 3D sparse propagation cannot represent ordinary
character motion and scales poorly in memory. The binary graph-cut pass blends
same-coordinate neighbors and can ghost under motion. ARAP currently deforms a
wireframe without warping image pixels. Retain these as research baselines;
replace production plans with motion-aware, occlusion-aware, windowed methods.

## Alternative techniques

- Frame-by-frame correspondence and interpolation for core anime instruction.
- Layered cutout rigs for dialogue shots, motion comics, and rapid prototypes.
- ARAP/cage deformation as corrective tools after texture warping exists.
- Optional video diffusion for proposals, never as the only editable format.

## Delivery order

1. Animation lesson and document/timeline schema.
2. Manual key-pose, breakdown, and onion-skin workflow.
3. Motion correspondence evaluation harness.
4. Proportion/arc/spacing tutor.
5. Motion-aware color propagation.
6. Accepted-suggestion inbetweening and cleanup.
7. Secondary cutout/puppeteering workflow.
