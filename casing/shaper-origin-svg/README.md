# Cosmic Unicorn - Shaper Origin SVG

All measurements are in millimeters.

Each cut file has a Shaper Custom Anchor at the upper-left board corner `(0,0)`.
The anchor is a red filled right triangle without stroke, following Shaper's recommendation.
Place each SVG against the same board corner so the cuts share the same coordinate system.

## Board

- Board: 220 x 220 x 16
- Outer corners: R4
- Cutter: 6 mm
- Deepest cut: 12 mm, leaving 4 mm of bottom material in 16 mm Valchromat

## Cutting Steps

1. `01_pocket_205x205_depth_5mm.svg`
   - Centered pocket: 205 x 205
   - Corner radius: R3
   - Cut depth: 5 mm
   - Encoded depth: 5 mm
   - This is the level the display rests on.
   - Human-readable label file: `01_pocket_205x205_depth_5mm_LABEL.svg`

2. `02_deep_clearance_205x142_depth_12mm.svg`
   - Deeper clearance pocket for components on the back side.
   - Width: 205
   - Height: 142
   - Cutter: 8 mm
   - Corner radius: R4
   - Position: full width within the pocket, leaving 60 mm at the top and 3 mm at the bottom.
   - Cut depth: 12 mm
   - Encoded depth: 12 mm
   - Human-readable label file: `02_deep_clearance_205x142_depth_12mm_LABEL.svg`

3. `03_outer_profile_220x220_r4.svg`
   - Outer board profile.
   - 220 x 220
   - Corner radius: R4
   - Preferably cut last.
   - Human-readable label file: `03_outer_profile_220x220_r4_LABEL.svg`

Reference helper:

- `04_bottom_center_tongue_reference.svg`
  - Closed reference shape for the small centered bottom tongue/ledge.
  - Not a cut operation.
  - Useful when editing the layout in a vector editor where the remaining tongue needs to be selected as its own object.

- `05_cutout_with_center_tongue_objects.svg`
  - Working/reference SVG with the 5 mm pocket, the 12 mm pocket shaped around the tongue, and the tongue as its own named object.
  - Useful as an import source for Affinity Designer when the tongue needs to be selected or copied separately.

## Margins

- Cosmic Unicorn according to Pimoroni: 204 x 204 x 10.2
- First pocket: 205 x 205
- Clearance: 1 mm total, 0.5 mm per side.

Shaper format references:

- Custom Anchors: https://support.shapertools.com/hc/en-us/articles/4402965445019-custom-anchors
- Encoded cut depth: https://support.shapertools.com/hc/en-us/articles/12946815194011-manual-svg-cut-depth-encoding
