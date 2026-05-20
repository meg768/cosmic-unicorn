# Cosmic Unicorn Casing

Last updated: 2026-05-19

## Purpose

This is the project's human-readable context file.
Read it first to understand the design decisions, measurements, and open questions.

## Goal

Build and route a casing for a Pimoroni Cosmic Unicorn where the display drops into a Valchromat board from above.

The workflow is intended for Shaper Origin, using a 6 mm cutter for the first pocket and an 8 mm cutter for the deeper clearance pocket.

## Material

- Intended material: 16 mm Valchromat.
- The OpenSCAD model is set to a 16 mm board.
- With a 16 mm board and a deepest cut depth of 12 mm, 4 mm of material remains at the bottom.

## Known Cosmic Unicorn Measurements

From Pimoroni's reference material:

- Cosmic Unicorn outline: about 204 x 204 mm.
- Total thickness/depth: about 10.2 mm.
- Display/board corner radius: about R3.
- The Pico W is located at the lower left on the back side.
- USB power cable routing for the Pico W is not solved yet.

## Current Geometry

Board:

- 220 x 220 mm
- R4 outer corners
- OpenSCAD: `board_t = 16`
- With a 12 mm deepest cut, 4 mm of bottom material remains.

Cutters:

- First pocket: 6 mm cutter, internal corners R3.
- Deeper clearance pocket: 8 mm cutter, internal corners R4.

First pocket:

- 205 x 205 mm
- Depth: 5 mm from the top face
- This is the level the display rests on.
- Clearance around the 204 x 204 mm display: 1 mm total, 0.5 mm per side.

Second, deeper pocket:

- 205 x 142 mm
- Depth: 12 mm from the top face
- Cutter: 8 mm
- Corner radius: R4
- Full width, but only leaves resting surfaces at the top and bottom.
- Leaves 60 mm of resting surface at the top on the 5 mm level.
- Leaves 3 mm of resting surface at the bottom on the 5 mm level.
- The left and right sides have no resting ledge because components sit on the back of the display.

## Important Decisions

- "Cut" always means removed material via `difference()`/cutter volume, not added geometry.
- No separate platforms or supports should be modeled.
- Resting surfaces are created by different cut depths.
- Only the top and bottom should support the display.
- The sides should be deeply cleared for component space.
- A cable channel for the Pico W/USB connection is not modeled yet.

## Files

OpenSCAD:

- `board.scad`

Pimoroni reference material:

- `cosmic_unicorn_dimensional_drawing.png`
- `cosmic_unicorn_schematic.pdf`
- `cosmic_unicorn_with_holes.dxf`

Shaper Origin SVG:

- `shaper-origin-svg/01_pocket_205x205_depth_5mm.svg`
- `shaper-origin-svg/02_deep_clearance_205x142_depth_12mm.svg`
- `shaper-origin-svg/03_outer_profile_220x220_r4.svg`

Human-readable label files:

- `shaper-origin-svg/01_pocket_205x205_depth_5mm_LABEL.svg`
- `shaper-origin-svg/02_deep_clearance_205x142_depth_12mm_LABEL.svg`
- `shaper-origin-svg/03_outer_profile_220x220_r4_LABEL.svg`

Overview:

- `shaper-origin-svg/00_reference_layout.svg`

## Shaper Origin Notes

- The SVG files use a 220 x 220 mm coordinate system.
- Each cut file has a Shaper Custom Anchor at the upper-left board corner `(0,0)`.
- The anchor is a red filled right triangle.
- The cut files include `shaper:cutDepth`:
  - 5 mm for the first pocket.
  - 12 mm for the deeper clearance pocket.

## Next Open Question

Power cable routing for the Pico W.

Possible ideas:

- Test with the actual micro-USB cable before committing to a final hole or route.
- Use a 90-degree micro-USB cable.
- Route a local cable/connector pocket from the side or bottom edge once the physical cable has been chosen.

## Good Next Steps

1. Open the SVG files in Shaper Origin.
2. Test-route in scrap material.
3. Test-fit the Cosmic Unicorn and the actual USB cable.
4. Add the cable channel/connector pocket only after test-fitting.
