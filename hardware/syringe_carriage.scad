// Parametric plunger carriage for a disposable syringe.
// The printed part never enters the fluid path.
// Check every dimension against the syringe and the leadscrew nut you bought.
// Units: millimeters.

syringe_body_od = 17.0;     // measure the barrel, not the catalog "10 mL"
plunger_flange_mm = 22.0;
leadscrew_nut_w = 22.0;     // T8 brass nut across flats, typical; measure yours
leadscrew_nut_h = 16.0;
wall = 4.0;
$fn = 48;

module clamp_ring(id, od, h) {
    difference() {
        cylinder(h = h, d = od);
        translate([0, 0, -1]) cylinder(h = h + 2, d = id);
        // slit so it can close on the barrel with a screw, not a glue joint
        translate([-1, 0, -1]) cube([od, 2, h + 2]);
    }
}

module carriage() {
    difference() {
        union() {
            cube([plunger_flange_mm + 16, 28, 12]);
            translate([8, 14, 12])
                clamp_ring(syringe_body_od + 0.6, syringe_body_od + 2 * wall, 18);
        }
        // pocket for the leadscrew nut
        translate([plunger_flange_mm + 16 - leadscrew_nut_w - 2, 14 - leadscrew_nut_w / 2, 2])
            cube([leadscrew_nut_w, leadscrew_nut_w, leadscrew_nut_h]);
        // plunger flange slot
        translate([4, 6, -1]) cube([plunger_flange_mm, 16, 8]);
    }
}

carriage();
