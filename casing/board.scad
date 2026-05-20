// Cosmic Unicorn casing / routing template
// Measurements are in millimeters.
//
// Based on a 220 x 220 x 16 mm board with a centered two-depth pocket.

$fn = 72;

board_w = 220;
board_h = 220;
board_t = 16;
board_corner_r = 4;

display_w = 204;
display_h = 204;

pocket_w = 205;
pocket_h = 205;
pocket_depth = 12;

top_shoulder_h = 60;
bottom_shoulder_h = 3;
shoulder_cut_depth = 5;
shoulder_height = pocket_depth - shoulder_cut_depth;

cutter_d = 6;
corner_r = cutter_d / 2;
deep_cutter_d = 8;
deep_corner_r = deep_cutter_d / 2;

show_requested_footprint = false;
show_display_reference = false;

rim_x = (board_w - pocket_w) / 2;
rim_y = (board_h - pocket_h) / 2;

if (rim_x < 0 || rim_y < 0) {
    echo(str(
        "WARNING: The pocket is larger than the board. Margin X=",
        rim_x,
        " mm, Y=",
        rim_y,
        " mm. Increase the board size or reduce pocket_w/pocket_h."
    ));
}

module rounded_rect_2d(w, h, r) {
    assert(w >= 2 * r, "Width must be at least 2 x the corner radius.");
    assert(h >= 2 * r, "Height must be at least 2 x the corner radius.");

    hull() {
        translate([ w / 2 - r,  h / 2 - r]) circle(r = r);
        translate([-w / 2 + r,  h / 2 - r]) circle(r = r);
        translate([ w / 2 - r, -h / 2 + r]) circle(r = r);
        translate([-w / 2 + r, -h / 2 + r]) circle(r = r);
    }
}

module rounded_box(w, h, z, r) {
    linear_extrude(height = z)
        rounded_rect_2d(w, h, r);
}

module board_blank() {
    rounded_box(board_w, board_h, board_t, board_corner_r);
}

module shoulder_cutter() {
    translate([0, 0, board_t - shoulder_cut_depth])
        rounded_box(pocket_w, pocket_h, shoulder_cut_depth + 0.2, corner_r);
}

module deep_pocket_cutter() {
    inner_w = pocket_w;
    inner_h = pocket_h - top_shoulder_h - bottom_shoulder_h;
    inner_y = (bottom_shoulder_h - top_shoulder_h) / 2;

    translate([0, inner_y, board_t - pocket_depth])
        rounded_box(inner_w, inner_h, pocket_depth + 0.2, deep_corner_r);
}

module milled_board() {
    difference() {
        board_blank();
        shoulder_cutter();
        deep_pocket_cutter();

    }
}

module display_reference() {
    color([0.05, 0.05, 0.05, 0.45])
        translate([0, 0, board_t + 0.4])
            rounded_box(display_w, display_h, 1.2, corner_r);
}

module requested_footprint() {
    color([1, 0.15, 0.05, 0.28])
        translate([0, 0, board_t + 1.8])
            rounded_box(pocket_w, pocket_h, 1.0, corner_r);
}

milled_board();

if (show_display_reference)
    display_reference();

if (show_requested_footprint)
    requested_footprint();
