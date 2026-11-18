// 2-position flip legs for the Stream Deck (glued into the rear rubber-foot recesses).
// Export parts: part = "holder" | "block"; part = "view" with POS = "low" | "high" shows a preview.
// Hardware per leg: M3x25 screw + nylon lock nut.
part="view"; POS="high";
$fn=56;
W=120; D=85; LID=5; pitch=19.05; mode="ext";
// --- holder ---
PW=24; PL=30; PT=3;            // plate (x, y, thickness)
BOSS_D=10.2; BOSS_H=0.8;       // boss that fits the foot recess (dia 10.6 x 1 mm)
CH=3;                          // cheek thickness
PIN_DOWN=10;                   // pivot below the plate
HOLE=3.3;                      // M3
// --- block ---
GAP=0.4; FW=PW-2*CH-2*GAP;     // block width
SHORT=5; LONG=17; HALF=5;      // from the pivot: short end, long end, half thickness
BOSS_Y=PL-9;                   // boss position on the plate (from the plate front)
PIN_Y=PL-5;                    // pivot position (from the plate front)

module plate(){
  difference(){
    union(){
      translate([0,0,-PT]) cube([PW,PL,PT]);
      translate([PW/2,BOSS_Y,0]) cylinder(d=BOSS_D,h=BOSS_H);
      for(x=[0,PW-CH]) translate([x,0,0]) rotate([90,0,90]) linear_extrude(CH)
        hull(){ translate([PIN_Y-8,-PT]) square([16,0.1]); translate([PIN_Y,-PT-PIN_DOWN]) circle(r=5.5); }
    }
    translate([-1,PIN_Y,-PT-PIN_DOWN]) rotate([0,90,0]) cylinder(d=HOLE,h=PW+2);
  }
}
// block in pivot coordinates: pivot = (0,0); low position: long end forward (-y)
module block(){
  difference(){
    rotate([90,0,90]) linear_extrude(FW) offset(r=1) offset(delta=-1) translate([-LONG,-HALF]) square([LONG+SHORT,2*HALF]);
    translate([-1,0,0]) rotate([0,90,0]) cylinder(d=HOLE,h=FW+2);
  }
}
module leg_assembly(pos, a){
  plate();
  translate([CH+GAP,PIN_Y,-PT-PIN_DOWN]) rotate([(pos=="high"?90:0)-a,0,0]) block();
}
module wedge(w,d,hf,hb){ rotate([90,0,90]) linear_extrude(w) polygon([[0,0],[d,0],[d,hb],[0,hf]]); }
module deck(hf, hb, board){  // hf/hb = wall heights (without lid)
  ang=atan((hb-hf)/D); L=D/cos(ang);
  difference(){
    color("#3a3d44") wedge(W,D,hf,hb);
    translate([3,3,2]) wedge(W-6,D-6,hf+20,hb+20);
    if (mode=="cut") translate([-1,-1,-1]) cube([W/2+1,D+2,100]);
  }
  // lid + keys
  translate([0,0,hf]) rotate([ang,0,0]) {
    difference(){
      color("#4a4e57") cube([W,L,LID]);
      ox=(W-4*pitch)/2; oy=(L-3*pitch)/2;
      for(c=[0:3],r=[0:2]) translate([ox+c*pitch+pitch/2-7, oy+r*pitch+pitch/2-7,-1]) cube([14,14,LID+2]);
      if (mode=="cut") translate([-1,-1,-1]) cube([W/2+1,L+2,100]);
    }
    ox=(W-4*pitch)/2; oy=(L-3*pitch)/2;
    lx=ox+4*pitch+(W-ox-4*pitch)/2;
    color("#2f80ff") translate([lx,L/2,LID-0.5]) cylinder(d=5,h=1);
    for(c=[0:3],r=[0:2]) translate([ox+c*pitch+pitch/2, oy+r*pitch+pitch/2,0]){
      if (mode=="ext" || ox+c*pitch+pitch/2 > W/2) {
        color("#d8d8d8") translate([-7,-7,LID-1.5-8.3]) cube([14,14,8.3]);   // switch under the plate
        color("#cfcfcf") translate([-7,-7,LID]) cube([14,14,5]);
        color(r==0 && c==3 ? "#7aa7ff" : "#eeeeee") translate([0,0,LID+5]) hull(){ translate([-9,-9,0]) cube([18,18,0.1]); translate([-6.5,-6.5,7.4]) cube([13,13,0.1]); }
      }
    }
  }
  // electronics
  if (board=="mega") {
    color("#1b8f6e") translate([8,20,2+3]) cube([101.6,53.3,1.6]);
    color("#222") { translate([25,20,6.6]) cube([70,2.5,8.5]); translate([25,71,6.6]) cube([70,2.5,8.5]); }
    color("#bbb") translate([1.5,52,6.6]) cube([16,12,11]);
  } else {
    color("#1b8f6e") translate([W/2-9, D-3-33-2, 2+1]) cube([18,33,1.6]);
    color("#bbb") translate([W/2-4.5, D-3-1.5, 4.6]) cube([9,4,3.2]);
  }
}

HF=23; HB=29;
FOOT_X=[12, W-12]; FOOT_Y=D-12;
LY = FOOT_Y-BOSS_Y+PIN_Y;   // pivot distance from the front edge
PD = PT+PIN_DOWN;
function ang(pos) = atan(PD/LY) + asin((pos=="high"?LONG:HALF)/sqrt(LY*LY+PD*PD));
module deck_with_legs(pos){
  deck(HF,HB,"mega");
  color("#c98b4a") for(fx=FOOT_X) translate([fx-PW/2, FOOT_Y-BOSS_Y, 0]) leg_assembly(pos, ang(pos));
}
if(part=="holder") rotate([0,-90,0]) plate();          // print on its side
else if(part=="block") rotate([0,90,0]) block();      // print on its side
else {
  pos=POS; a=ang(pos); echo(str("ANGLE ",pos,": ",a));
  rotate([a,0,0]) deck_with_legs(pos);
  color("#3b3b3b") translate([-30,-30,-0.5]) cube([W+60,D+60,0.5]);
}
