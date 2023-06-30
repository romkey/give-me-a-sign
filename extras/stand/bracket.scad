// SPDX-FileCopyrightText: 2023 John Romkey
//
// SPDX-License-Identifier: MIT

width = 25.4/2;
height = 5;
length = 160 + 25.4; // 180

offset = 25.4/4;

diameter = 4;

module bracket() {
difference() {
  cube([width, length, height]);
  translate([(width)/2, offset + 2.5 +25.4, 0])
    cylinder(height*2, d = diameter, center = true);
  translate([(width)/2, 160 - 25.4/8 - 3 + 25.4, 0])
    cylinder(height*2, d = diameter, center = true);
}

translate([0, 0, height/2])
  rotate([-15, 0, 0])
    cube([width, height, length/2]);
}

module modified_bracket() {
    difference() {
        bracket();
        translate([0, offset + 27.9 + 160/4, 0])
          cube([width, 160/2, height]);
    }

    translate([0, offset + 27.9 + 160/4, 0])
      cube([width, height, 20]);
    translate([0, offset + 27.9 + 3*160/4, 0])
      cube([width, height, 20]);
    translate([0, offset + 27.9 + 160/4, 20-height])
      cube([width, 160/2, height]);
}

modified_bracket();
