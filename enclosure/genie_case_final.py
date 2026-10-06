#!/usr/bin/env python3
"""
GENIE enclosure -- Rev J "SLIDE"  (two variants: WITH / WITHOUT ToF holes)
7 x 7 x 7 in (177.8 mm) clear acrylic cube, 3 mm, with a VERTICALLY SLIDING
removable BACK panel running in glued acrylic guide rails.

One CFG dict drives everything.  Outputs, written next to this script:
    DESIGN_B_NO_TOF/GENIE_NO_TOF.dxf            ACI 1 = CUT, ACI 5 = ENGRAVE
    DESIGN_B_NO_TOF/GENIE_NO_TOF_blackred.dxf   ACI 7 = CUT, ACI 1 = ENGRAVE
    DESIGN_A_WITH_TOF_HOLES/GENIE_WITH_TOF*.dxf fallback with ToF apertures
    geometry check report on stdout

Previews: render_final.py.  Partial re-cuts: make_partial.py.
Independent audit before every cut: verify_dxf.py <file>.

Author: Arman Adil Mangat. First generated 28-08-2026, Rev J 30-08-2026.
"""
import math
import ezdxf
from strokefont import stroke_text

# ----------------------------------------------------------------------------
# CFG -- change here, nowhere else
# ----------------------------------------------------------------------------
CFG = dict(
    T            = 3.0,        # material thickness, nominal
    S            = 177.8,      # external cube edge = 7.000 in
    KERF         = 0.178,      # measured 0.007 in -- DOCUMENTED, NOT APPLIED
    R_CORNER     = 2.0,        # all sensor cutout corners
    R_SLOT       = 0.5,        # joint mortise corners
    SLIDE_CLEAR  = 0.4,        # channel is T + this  -> 3.4 mm
    PANEL_CLEAR  = 0.8,        # sliding panel is IN - this, both axes-ish
    RAIL_W       = 6.0,        # guide rail strip width (in Y)
    N_TABS       = 5,
    TAB_INSET    = 12.0,
    # --- measured parts (ENCLOSURE.md, 27-08-2026) ---
    TFT_W        = 63.0, TFT_H = 45.0,
    DHT_W        = 18.0, DHT_H = 14.0,     # module 17x13 + clearance
    # rev H: measured off the module photo.  Board 32.5 x 15; blue sensor body
    # 15.5 wide at the RIGHT end; red LED 14.2 mm to the LEFT of the sensor
    # centre and about 4.3 mm off the board centreline.  A round hole cannot
    # absorb that 4.3 -- and it flips if the module is turned round -- so the
    # port is a SLOT running across the board, which catches the LED either way.
    # rev J: the 4.5 slot caught the LED but left the 3-pin header and its
    # dupont shells with nowhere to go.  One relief opening now clears the
    # LED *and* the connector; a 3.5 mm bridge is left to the sensor window.
    DHT_LED_W    = 12.5,
    DHT_LED_H    = 12.0,
    DHT_LED_DX   = -18.75,                 # LEFT of the window centre
    MIC_PORT_D   = 4.0,                    # acoustic port (unused, kept for ref)
    # rev G: the INMP441 round breakout is ~11 mm across and has to SIT IN the
    # hole, not behind it.  9 mm was too small to pass the module at all.
    MIC_MOD_D    = 11.0,
    # rev H: MEASURED off the real driver (29-08).  Body that passes through
    # the panel = 44.0.  Steel flange = 50 square.  Bolt centres 5.7 cm on the
    # DIAGONAL, i.e. a 40 x 40 square (40 x sqrt2 = 56.6).  So the hole is 46 --
    # 1 mm of relief round a 44 body -- NOT 53, which is wider than the flange
    # across its flats and would leave the driver hanging on its bolts.
    SPK_CUT_D    = 46.0,
    SPK_BOLT_PITCH = 40.0,                 # centre-to-centre, both axes
    SPK_FLANGE   = 50.0,                   # square, for clearance checks only
    SMOKE_D      = 20.0,                   # MQ-2  (size is right, do not change)
    SMOKE_A      = 30.0,                   # rev H: moved FORWARD, off the
    SMOKE_V      = 68.0,                   #        speaker flange. Same height.
    TOF_W        = 25.0, TOF_H = 10.0,
    FLAME_D      = 5.5,
    BUTTON_D     = 12.0,
    BUTTON_N     = 3,
    # --- Rev F: mini toggle switches, ESP power on/off (photo 29-08) ---
    # MTS-102 family bushing is M6 x 0.75.  6.4 nominal cuts to about 6.58
    # with the documented 0.178 kerf, which clears both M6 and 1/4 in
    # bushings; the hex nut and its washer cover the slop.  Test both sizes
    # on part 10 with the real switch before the sheet is cut.
    SWITCH_D     = 6.4,
    SWITCH_N     = 6,          # 3 per side of the top panel
    SWITCH_X     = (22.0, 155.8),
    SWITCH_Y     = (78.0, 100.0, 122.0),
    # --- Rev F: back-panel finger slot, replaces the R14 top-edge notch ---
    FINGER_W     = 60.0,
    FINGER_H     = 14.0,
    FINGER_DROP  = 29.0,       # slot bottom, measured DOWN from the top edge
    TOF_CUT      = False,      # True  = cut 25 x 10 ToF apertures (4 off)
                               # False = engraved footprint only, no hole
    # rev J: 15.5.  The DIA 11 test hole would not take the module at all, and
    # 12 would not either -- measured against the DIA 11 slug in the test-cut
    # photo the round INMP441 board is 13.1 - 14.4 mm across, not 11.
    # RULE, learned the hard way: any hole a physical part must ENTER gets
    # real clearance over the MEASURED size, never a nominal match.  There is
    # no second test cut, so this one goes the recoverable way: a hole that is
    # a little large is fixed with foam tape, a hole that is small is not
    # fixable at all.
    MIC_HOLE_D   = 15.5,
    PT_WIRE_D    = 10.0,       # pan-tilt servo wire pass, top panel
    CABLE_SLOT_W = 14.0,       # AC mains entry, U-slot in the slider's bottom edge
    CABLE_SLOT_H = 20.0,
    M3           = 3.2,
    # --- rev G: TFT clamp frame reworked.  The old 66 x 48 window sat right on
    # top of the shield's pin headers and its edge button, so the wires had
    # nowhere to go and the button was pressed permanently.  The frame now
    # grips ONLY the two short edges of the shield; the whole long-edge zone
    # (headers, jumper wires, button) passes through the opening.
    # rev J: the shield MEASURED 65 x 63 -- nearly square, not the landscape
    # board that was assumed.  A 63 x 62 opening left 1 mm of grip per side,
    # i.e. none.  The frame now grips FOUR CORNER PADS only, through a
    # cross-shaped opening, so it does not depend on the board's exact size
    # and every edge-mounted header, wire and the button stays clear.
    # The plate is SQUARE with its four bolts on the axes, so it can be turned
    # 90 degrees without re-drilling the front panel -- that removes the
    # orientation risk.  Two variants are cut because the board's short side
    # is genuinely uncertain: the user read 63 mm, the test-cut photo measures
    # about 52 mm against the frame's own 108 mm edge.  Both are on the sheet;
    # whichever fits is the one that gets bolted, and they are interchangeable.
    FRAME_SIZE   = 100.0,
    FRAME_BOLT_R = 42.0,
    FRAME_PAD    = 8.0,
    FRAME_RELIEF = 2.0,
    TFT_BOARD_A  = (66.0, 52.0),
    TFT_BOARD_B  = (66.0, 63.0),
    # --- sheet ---
    SHEET_W      = 610.0, SHEET_H = 915.0, # 2 x 3 ft acrylic
    GAP          = 12.0, MARGIN = 10.0,
    # --- checks ---
    MIN_FEATURE_GAP = 3.0,
    MIN_EDGE_GAP    = 6.0,
)

T   = CFG['T']
S   = CFG['S']
IN  = S - 2 * T                      # 171.8 internal span
BULGE90 = math.tan(math.pi / 8)      # 0.414213562, CCW quarter arc

TOP_DEPTH  = 165.0                   # y 3 .. 168.0
BOT_DEPTH  = S - T                   # y 3 .. 177.8 = 174.8
SIDE_DEPTH = S - T                   # a = y-3, 0 .. 174.8
SIDE_HIGH  = IN                      # z 3 .. 174.8

# rail zones, expressed in a = y - 3
RAIL_FRONT_A = (159.4, 165.4)
CHANNEL_A    = (165.4, 165.4 + T + CFG['SLIDE_CLEAR'])   # 165.4 .. 168.8
RAIL_REAR_A  = (168.8, 174.8)

BACK_W = IN - CFG['PANEL_CLEAR']                 # 171.0
BACK_H = IN - 0.6                                # 171.2
RAIL_L = IN                                      # 171.8
STOP_L = IN - 2 * T                              # 165.8, sits between the rails

CUT, ENG, NOTE = 'CUT', 'ENGRAVE', 'NOTES'


# ----------------------------------------------------------------------------
# primitives
# ----------------------------------------------------------------------------
class Circle:
    def __init__(self, c, r, layer=CUT):
        self.c, self.r, self.layer = c, r, layer

    def moved(self, dx, dy):
        return Circle((self.c[0] + dx, self.c[1] + dy), self.r, self.layer)


class Poly:
    """points = [(x, y, bulge), ...]"""
    def __init__(self, pts, closed=True, layer=CUT):
        self.pts = [(p[0], p[1], p[2] if len(p) > 2 else 0.0) for p in pts]
        self.closed, self.layer = closed, layer

    def moved(self, dx, dy):
        return Poly([(x + dx, y + dy, b) for (x, y, b) in self.pts],
                    self.closed, self.layer)


def rrect(x0, y0, w, h, r=0.0, layer=CUT):
    """Rounded rectangle, CCW, as a bulge polyline."""
    x1, y1 = x0 + w, y0 + h
    r = min(r, w / 2 - 1e-6, h / 2 - 1e-6) if r > 0 else 0.0
    if r <= 0:
        return Poly([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], True, layer)
    B = BULGE90
    return Poly([
        (x0 + r, y0, 0), (x1 - r, y0, B),
        (x1, y0 + r, 0), (x1, y1 - r, B),
        (x1 - r, y1, 0), (x0 + r, y1, B),
        (x0, y1 - r, 0), (x0, y0 + r, B),
    ], True, layer)


def fillet_poly(pts, turns, r, layer=CUT):
    """Round every 90-degree corner of a CCW polygon.

    turns[i] = +1 for a convex corner (left turn), -1 for a concave one.
    Concave corners take a negative bulge, which is what lets a cross-shaped
    opening carry the same R2 as every other cutout in this design.
    """
    n = len(pts)
    out = []
    for i, (p, t) in enumerate(zip(pts, turns)):
        a, b = pts[i - 1], pts[(i + 1) % n]
        d0 = (p[0] - a[0], p[1] - a[1])
        d1 = (b[0] - p[0], b[1] - p[1])
        l0 = math.hypot(*d0) or 1.0
        l1 = math.hypot(*d1) or 1.0
        u0 = (d0[0] / l0, d0[1] / l0)
        u1 = (d1[0] / l1, d1[1] / l1)
        out.append((p[0] - u0[0] * r, p[1] - u0[1] * r, t * BULGE90))
        out.append((p[0] + u1[0] * r, p[1] + u1[1] * r, 0.0))
    return Poly(out, True, layer)


def cross_opening(cx, cy, A, b, a, B, r=None, layer=CUT):
    """Plus-shaped opening: horizontal arm 2A x 2b, vertical arm 2a x 2B.

    What is left is material at the four CORNERS only -- which is exactly
    where a PCB has no headers, no buttons and no ribbon.
    """
    r = CFG['R_CORNER'] if r is None else r
    P = [(cx - a, cy - B), (cx + a, cy - B), (cx + a, cy - b), (cx + A, cy - b),
         (cx + A, cy + b), (cx + a, cy + b), (cx + a, cy + B), (cx - a, cy + B),
         (cx - a, cy + b), (cx - A, cy + b), (cx - A, cy - b), (cx - a, cy - b)]
    T = [1, 1, -1, 1, 1, -1, 1, 1, -1, 1, 1, -1]
    return fillet_poly(P, T, r, layer)


def round90(pts, r=2.0, layer=CUT):
    """Fillet every 90-degree corner of a rectilinear closed path.

    pts is a CCW list of (x, y).  Returns a bulge Poly.  Used for the
    cross-shaped opening in the TFT clamp frame, which has both convex and
    concave corners -- the sign of the bulge follows the turn direction, so
    the same call rounds both.
    """
    n = len(pts)
    out = []
    for i in range(n):
        a, v, b = pts[i - 1], pts[i], pts[(i + 1) % n]
        ux, uy = v[0] - a[0], v[1] - a[1]
        wx, wy = b[0] - v[0], b[1] - v[1]
        lu = math.hypot(ux, uy); lw = math.hypot(wx, wy)
        ux, uy, wx, wy = ux / lu, uy / lu, wx / lw, wy / lw
        cross = ux * wy - uy * wx
        t = min(r, lu / 2 - 1e-6, lw / 2 - 1e-6)
        out.append((v[0] - ux * t, v[1] - uy * t, BULGE90 * (1 if cross > 0 else -1)))
        out.append((v[0] + wx * t, v[1] + wy * t, 0.0))
    return Poly(out, True, layer)


def cross_opening(cx, cy, bw, bh, pad, relief):
    """CCW cross that leaves `pad` x `pad` of material on each board corner."""
    hx0, hx1 = cx - bw / 2 - relief, cx + bw / 2 + relief
    hy0, hy1 = cy - bh / 2 + pad,    cy + bh / 2 - pad
    vx0, vx1 = cx - bw / 2 + pad,    cx + bw / 2 - pad
    vy0, vy1 = cy - bh / 2 - relief, cy + bh / 2 + relief
    return [(vx0, vy0), (vx1, vy0), (vx1, hy0), (hx1, hy0), (hx1, hy1),
            (vx1, hy1), (vx1, vy1), (vx0, vy1), (vx0, hy1), (hx0, hy1),
            (hx0, hy0), (vx0, hy0)]


def tof_feature(p, name, x, y, where):
    """The ONLY place a ToF aperture is decided.

    CFG['TOF_CUT'] True  -> 25 x 10 R2 through cut, engraved label.
    CFG['TOF_CUT'] False -> NOTHING is drawn on any layer.  The sensors are
    mounted internally and read through the clear acrylic (user bench-tested
    this 2-3 times, 28-08).
    """
    w, h = CFG['TOF_W'], CFG['TOF_H']
    if not CFG['TOF_CUT']:
        return                      # nothing drawn: no cut, no engrave, no label
    p.cut_rect(name, x, y, w, h)
    p.add(label('TOF ' + where, x + w / 2, y - 8.0, 3.5))
    p.add(label('OPEN APERTURE', x + w / 2, y + h + 5.0, 3.0))


def label(s, x, y, h=4.5, anchor='cm', layer=ENG, rot=0.0):
    ca, sa = math.cos(math.radians(rot)), math.sin(math.radians(rot))
    out = []
    for seg in stroke_text(s, 0.0, 0.0, h=h, anchor=anchor):
        out.append(Poly([(x + px * ca - py * sa, y + px * sa + py * ca, 0)
                         for (px, py) in seg], False, layer))
    return out


# ----------------------------------------------------------------------------
# tab pattern
# ----------------------------------------------------------------------------
def tabs_in(a0, a1, n=None):
    """n tabs alternating with gaps inside [a0, a1]; returns [(start, end), ...]"""
    n = n or CFG['N_TABS']
    span = a1 - a0
    seg = span / (2 * n - 1)
    return [(a0 + 2 * k * seg, a0 + 2 * k * seg + seg) for k in range(n)]


def mirror_iv(ivs, L):
    return [(L - b, L - a) for (a, b) in reversed(ivs)]


IST = CFG['TAB_INSET']
FRONT_TABS_Z = tabs_in(IST, SIDE_HIGH - IST)          # side panel -> front panel
BL_TABS_A    = tabs_in(IST, BOT_DEPTH - IST)          # side panel -> bottom panel
TOPEDGE_A    = tabs_in(IST, TOP_DEPTH - IST)          # side panel -> top panel
FB_TABS_X    = tabs_in(IST, S - IST)                  # top/bottom panel -> front


# ----------------------------------------------------------------------------
# outline with tabs
# ----------------------------------------------------------------------------
def outline(w, h, tabs=None, notches=None, finger=None, slot_bottom=None):
    """CCW outline.

    tabs    = {'B'|'R'|'T'|'L': [(a, b), ...]}  material sticking OUT by T
    notches = same, material cut IN by T -- the female half of a joint.
              A female edge MUST be drawn this way, never as a separate closed
              rectangle sitting on the panel edge: that puts two cut paths on
              the same line and the laser cuts the edge twice.
    finger  = (centre, radius) semicircular grip notch on the top edge.
    """
    tabs, notches = tabs or {}, notches or {}
    # slot_bottom = (centre_x, width, depth): open U-slot in the bottom edge,
    # R2 fillets at the two internal corners.  For a cable that must not trap
    # the sliding panel -- the panel lifts off the cable instead.

    def ev(edge, rev=False):
        e = [(a, b, 1) for a, b in tabs.get(edge, ())] + \
            [(a, b, -1) for a, b in notches.get(edge, ())]
        return sorted(e, reverse=rev)

    P = [(0.0, 0.0, 0.0)]
    if slot_bottom:
        scx, sw, sd = slot_bottom
        r = 2.0
        P += [(scx - sw / 2, 0, 0), (scx - sw / 2, sd - r, -BULGE90),
              (scx - sw / 2 + r, sd, 0), (scx + sw / 2 - r, sd, -BULGE90),
              (scx + sw / 2, sd - r, 0), (scx + sw / 2, 0, 0)]
    for a, b, s in ev('B'):                       # left -> right along y = 0
        d = -T if s > 0 else T
        P += [(a, 0, 0), (a, d, 0), (b, d, 0), (b, 0, 0)]
    P += [(w, 0, 0)]
    for a, b, s in ev('R'):                       # bottom -> top along x = w
        d = w + T if s > 0 else w - T
        P += [(w, a, 0), (d, a, 0), (d, b, 0), (w, b, 0)]
    P += [(w, h, 0)]
    if finger:
        cx, r = finger
        P += [(cx + r, h, -1.0), (cx - r, h, 0.0)]   # CW half turn into the panel
    for a, b, s in ev('T', rev=True):             # right -> left along y = h
        d = h + T if s > 0 else h - T
        P += [(b, h, 0), (b, d, 0), (a, d, 0), (a, h, 0)]
    P += [(0.0, h, 0.0)]
    for a, b, s in ev('L', rev=True):             # top -> bottom along x = 0
        d = -T if s > 0 else T
        P += [(0, b, 0), (d, b, 0), (d, a, 0), (0, a, 0)]
    return Poly(P, True, CUT)


def slots_v(x, ivs, r=None):
    """vertical column of mortises, x .. x+T, y over each interval"""
    r = CFG['R_SLOT'] if r is None else r
    return [rrect(x, a, T, b - a, r) for (a, b) in ivs]


def slots_h(y, ivs, r=None):
    r = CFG['R_SLOT'] if r is None else r
    return [rrect(a, y, b - a, T, r) for (a, b) in ivs]


# ----------------------------------------------------------------------------
# Part container
# ----------------------------------------------------------------------------
class Part:
    def __init__(self, key, title, w, h, qty=1):
        self.key, self.title, self.w, self.h, self.qty = key, title, w, h, qty
        self.prims = []
        self.feats = []       # ('name', kind, geom) for the checker
        self.org = (0.0, 0.0)
        self.bb = None        # (minx, miny, maxx, maxy) incl. tabs

    def add(self, *p):
        for q in p:
            if isinstance(q, list):
                self.prims.extend(q)
            else:
                self.prims.append(q)

    def feat_rect(self, name, x, y, w, h, joint=False):
        self.feats.append((name, 'rect', (x, y, x + w, y + h), joint))

    def feat_circ(self, name, cx, cy, d, joint=False):
        self.feats.append((name, 'circ', (cx, cy, d / 2.0), joint))

    def cut_rect(self, name, x, y, w, h, r=None, joint=False):
        self.add(rrect(x, y, w, h, CFG['R_CORNER'] if r is None else r))
        self.feat_rect(name, x, y, w, h, joint)

    def cut_circ(self, name, cx, cy, d, joint=False):
        self.add(Circle((cx, cy), d / 2.0))
        self.feat_circ(name, cx, cy, d, joint)


PARTS = []


# ============================================================================
# 01 FRONT  -- 177.8 x 177.8, no tabs, four mortise banks
# ============================================================================
def build_front():
    p = Part('01_FRONT', 'FRONT', S, S)
    side_n = [(T + a, T + b) for (a, b) in FRONT_TABS_Z]
    p.add(outline(S, S, notches={'L': side_n, 'R': side_n,
                                 'B': FB_TABS_X, 'T': FB_TABS_X}))
    for x in (0.0, S - T):
        for (a, b) in side_n:
            p.feat_rect('joint', x, a, T, b - a, joint=True)
    for y in (0.0, S - T):
        for (a, b) in FB_TABS_X:
            p.feat_rect('joint', a, y, b - a, T, joint=True)

    cx = S / 2.0
    # TFT window
    tw, th = CFG['TFT_W'], CFG['TFT_H']
    ty = 92.0
    p.cut_rect('TFT', cx - tw / 2, ty, tw, th)
    p.add(label('TFT 63 X 45', cx, ty - 8.0, 4.0))
    # TFT frame bolts (12_TFT_FRAME clamps the ILI9341 from behind)
    # rev J: 4 bolts on the AXES at +/-42, not at the corners.  A symmetric
    # pattern means the square clamp frame can be turned 90 degrees if the
    # shield turns out to be portrait rather than landscape.
    R = CFG['FRAME_BOLT_R']
    cy0 = ty + th / 2
    for (hx, hy) in ((cx - R, cy0), (cx + R, cy0), (cx, cy0 - R), (cx, cy0 + R)):
        p.cut_circ('TFT-M3', hx, hy, CFG['M3'])
    # rev J: moved down out of the new symmetric TFT bolt pattern
    tof_feature(p, 'TOF-FRONT', 32.5, 73.0, 'FRONT')
    # microphones: one in each UPPER CORNER of the front panel.
    # 133.8 mm apart -- the widest baseline the panel allows, which is what a
    # stereo INMP441 pair wants.
    my = S - 22.0
    for mx in (22.0, S - 22.0):
        # rev H: 11.0.  The INMP441 round board measures 11 mm and now PUSH
        # FITS from behind -- 12.0 let it drop straight through.  The old
        # engraved 11 mm module ring is gone (it fell inside the cut).
        p.cut_circ('MIC', mx, my, CFG['MIC_HOLE_D'])
        p.add(label('MIC 15.5', mx, my - 12.5, 2.6))
        p.add(label('FOAM TAPE BEHIND', mx, my - 17.5, 2.2))
    # rev J: DIA 5.2 cut straight into the panel.  The glue-on reducer ring
    # (old part 11) is gone -- it could not be produced on the machine.
    p.cut_circ('FLAME', cx, 45.0, CFG['FLAME_D'])
    p.add(label('FLAME DIA 5.5 -- DOME SITS IN THIS', cx, 33.0, 3.0))
    p.add(label('01 FRONT', cx, 15.0, 6.0))
    PARTS.append(p)
    return p


# ============================================================================
# 03 / 04  SIDE PANELS -- 174.8 (depth) x 171.8 (height)
#   drawn AS SEEN FROM OUTSIDE.  right: u = y-3.  left: u = 174.8-(y-3).
# ============================================================================
def build_side(key, title, is_left):
    W, H = SIDE_DEPTH, SIDE_HIGH
    p = Part(key, title, W, H)

    def U(a):                     # depth-coordinate -> local u
        return (W - a) if is_left else a

    def UIV(ivs):
        return mirror_iv(ivs, W) if is_left else list(ivs)

    tb = {'B': UIV(BL_TABS_A), 'T': UIV(TOPEDGE_A)}
    tb['R' if is_left else 'L'] = list(FRONT_TABS_Z)   # front edge
    p.add(outline(W, H, tabs=tb))

    # speaker: @44 sound hole + @53 engraved driver footprint
    sa, sv = 62.0, 112.0
    # rev H, from the measured driver: 44 body / 50 square flange / bolt
    # centres 56.6 apart on the diagonal.  DIA 46 through -- 1 mm of relief
    # round the body -- plus the four flange bolts on a 40 x 40 square.  The
    # driver bolts on the OUTSIDE face and the flange covers the hole edge.
    p.cut_circ('SPEAKER', U(sa), sv, CFG['SPK_CUT_D'])
    hp = CFG['SPK_BOLT_PITCH'] / 2.0
    for da in (-hp, hp):
        for dv in (-hp, hp):
            p.cut_circ('SPK-M3', U(sa + da), sv + dv, CFG['M3'])
    p.add(label('SPEAKER DIA 46 THROUGH -- BODY IS 44', U(sa), 152.0, 2.8))
    p.add(label('4 X M3 ON A 40 X 40 SQUARE, FLANGE IS 50', U(sa), 147.0, 2.6))
    p.add(label('DRIVER BOLTS ON THE OUTSIDE FACE', U(sa), 142.0, 2.6))
    # MQ-2 -- rev H: moved FORWARD to a 30 so it is nowhere near the 50 mm
    # speaker flange or its bolts.  Same height, same 20 mm hole: the user
    # confirmed the fit is right, only the position moves.
    p.cut_circ('SMOKE', U(CFG['SMOKE_A']), CFG['SMOKE_V'], CFG['SMOKE_D'])
    p.add(label('SMOKE MQ2 DIA 20', U(CFG['SMOKE_A']), 52.5, 3.0))
    ta = 122.0
    tof_feature(p, 'TOF', U(ta) - CFG['TOF_W'] / 2, 107.0,
                'LEFT' if is_left else 'RIGHT')

    # ENGRAVE: guide-rail glue footprints + channel centreline (inner face).
    # rev F: held back 1 mm from the top and bottom edges.  Drawn to y = 0 and
    # y = H these marks lay exactly on the panel outline, which is a cut line --
    # the head would have traced the same path twice and the mark would have
    # read as part of the edge.  The rails themselves still run the full 171.8;
    # it is the two VERTICAL lines you align them to.
    EI = 1.0
    for (a0, a1), nm in ((RAIL_FRONT_A, 'RAIL A'), (RAIL_REAR_A, 'RAIL B')):
        u0, u1 = sorted((U(a0), U(a1)))
        # RAIL B is flush with the rear face, so its footprint would otherwise
        # run right up the panel edge -- which is a cut line.  Clamp it.
        u0, u1 = max(u0, EI), min(u1, W - EI)
        p.add(rrect(u0, EI, u1 - u0, H - 2 * EI, 0.0, ENG))
        p.add(label(nm, (u0 + u1) / 2, H / 2, 4.0, rot=90.0))
    cu = (U(CHANNEL_A[0]) + U(CHANNEL_A[1])) / 2
    p.add(Poly([(cu, EI, 0), (cu, H - EI, 0)], False, ENG))
    p.add(label('3.4 SLIDING CHANNEL', cu, H - 40.0, 3.0, rot=90.0))
    p.add(label('RAILS RUN FULL LENGTH -- MARKS STOP 1 MM SHORT',
                W / 2, 19.0, 2.8))
    p.add(label('GLUE THE 2 RAILS ON THE INNER FACE', W / 2, 12.0, 3.0))

    p.add(label(key.replace('_', ' '), U(85.0), 161.0, 6.0))
    PARTS.append(p)
    return p


# ============================================================================
# 05 TOP -- 177.8 x 165.0.  Rear edge is the sliding-panel exit slot.
# ============================================================================
def build_top():
    p = Part('05_TOP', 'TOP', S, TOP_DEPTH)
    p.add(outline(S, TOP_DEPTH, tabs={'B': FB_TABS_X},
                  notches={'L': TOPEDGE_A, 'R': TOPEDGE_A}))
    for x in (0.0, S - T):
        for (a, b) in TOPEDGE_A:
            p.feat_rect('joint', x, a, T, b - a, joint=True)
    cx = S / 2
    # pan-tilt bracket, front-centre: engraved footprint + 4 x M3 + wire pass.
    # SG90 pan-tilt base pattern NEVER MEASURED -- holes are REF, verify first.
    py = 52.0
    p.add(rrect(cx - 19.0, py - 16.5, 38.0, 33.0, 0.0, ENG))
    for hx in (cx - 16.0, cx + 16.0):
        for hy in (py - 12.5, py + 12.5):
            p.cut_circ('PT-M3', hx, hy, CFG['M3'])
    p.cut_circ('PT-WIRE', cx, py, CFG['PT_WIRE_D'])
    p.add(label('PAN TILT -- M3 REF, MEASURE', cx, py - 24.5, 3.0))
    p.add(label('WIRE DIA 10', cx, py + 20.5, 3.0))
    # 3 buttons in a row
    for i in range(CFG['BUTTON_N']):
        bx = cx + (i - 1) * 35.0
        p.cut_circ('BUTTON', bx, 105.0, CFG['BUTTON_D'])
    p.add(label('3 X BUTTON DIA 12', cx, 93.0, 3.5))
    # rev F: 6 mini toggle switches, 3 per side, ESP power on/off.
    # Kept hard against the side margins so the middle of the lid stays free
    # for the pan-tilt, the buttons and the DHT11.
    n = 0
    for sx in CFG['SWITCH_X']:
        inner = 1.0 if sx < cx else -1.0
        for sy in CFG['SWITCH_Y']:
            n += 1
            p.cut_circ('SWITCH', sx, sy, CFG['SWITCH_D'])
            p.add(label('SW%d' % n, sx + inner * 10.5, sy, 3.0))
        p.add(label('3 X TOGGLE SW DIA 6.4', sx + inner * 19.0,
                    sum(CFG['SWITCH_Y']) / 3.0, 3.0, rot=90.0))
    # DHT11 -- moved from the front (rev E), flush in the window, near the vent
    p.cut_rect('DHT11', cx - CFG['DHT_W'] / 2, 133.0, CFG['DHT_W'], CFG['DHT_H'])
    # rev H: the red LED is 14.2 mm to the LEFT of the sensor body on this
    # module, not the right, and about 4.3 mm off the board centreline -- and
    # that offset flips if the module is fitted the other way round.  A slot
    # across the board catches it in either orientation.
    lw, lh = CFG['DHT_LED_W'], CFG['DHT_LED_H']
    p.cut_rect('DHT-LED', cx + CFG['DHT_LED_DX'] - lw / 2, 140.0 - lh / 2,
               lw, lh, r=lw / 2)
    p.add(label('LED + WIRE RELIEF', cx + CFG['DHT_LED_DX'], 129.0, 2.4))
    p.add(label('DHT11 FLUSH', cx, 152.5, 3.5))
    p.add(label('05 TOP', 40.0, 60.0, 6.0))
    p.add(label('REAR EDGE = SLIDER EXIT SLOT', cx, TOP_DEPTH - 6.5, 3.5))
    p.add(label('FRONT EDGE', cx, 10.0, 4.0))
    PARTS.append(p)
    return p


# ============================================================================
# 06 BOTTOM -- 177.8 x 174.8
# ============================================================================
def build_bottom():
    p = Part('06_BOTTOM', 'BOTTOM', S, BOT_DEPTH)
    p.add(outline(S, BOT_DEPTH, tabs={'B': FB_TABS_X},
                  notches={'L': BL_TABS_A, 'R': BL_TABS_A}))
    for x in (0.0, S - T):
        for (a, b) in BL_TABS_A:
            p.feat_rect('joint', x, a, T, b - a, joint=True)
    # M3 deck mounts, 20 mm grid corners
    for hx in (44.0, S - 44.0):
        for hy in (44.0, BOT_DEPTH - 54.0):
            p.cut_circ('DECK-M3', hx, hy, CFG['M3'])
    # ENGRAVE: rear stop strip footprint + rail feet.
    # rev F: the rear zone ends at 174.8, which IS the panel's rear edge, so
    # these marks are held 1 mm short of it -- otherwise blue sits on red and
    # the head traces the rear edge twice.  Part 08 still goes flush.
    EI = 1.0
    RW = CFG['RAIL_W'] - EI
    p.add(rrect(2 * T, RAIL_REAR_A[0], STOP_L, RW, 0.0, ENG))
    p.add(label('GLUE PART 08 HERE -- FLUSH WITH THE REAR EDGE',
                S / 2, RAIL_REAR_A[0] + 2.5, 3.0))
    # the OUTER edge of each rail foot would land on x = 3 / 174.8, which is
    # the inner face of the side-panel mortises -- a cut line.  Trimmed 0.6 mm.
    for x0, xs in ((T, T + 0.6), (S - 2 * T, S - 2 * T)):
        p.add(rrect(xs, RAIL_FRONT_A[0], T - 0.6, CFG['RAIL_W'], 0.0, ENG))
        p.add(rrect(xs, RAIL_REAR_A[0], T - 0.6, RW, 0.0, ENG))
    p.add(label('RAIL FEET', 28.0, RAIL_FRONT_A[0] - 6.0, 3.0))
    p.add(label('RAIL FEET', S - 28.0, RAIL_FRONT_A[0] - 6.0, 3.0))
    p.add(label('06 BOTTOM', S / 2, 100.0, 6.0))
    p.add(label('FRONT EDGE', S / 2, 10.0, 4.0))
    PARTS.append(p)
    return p


# ============================================================================
# 02 BACK -- the sliding panel.  171.0 x 171.2 + finger notch.
# ============================================================================
def build_back():
    p = Part('02_BACK_SLIDER', 'BACK SLIDER', BACK_W, BACK_H)
    # rev F: NO notch in the top edge any more.  When the panel is seated its
    # top edge sits 0.6 mm under the lid, behind a 3.4 mm slot -- a notch there
    # cannot be reached by a finger, which is exactly what went wrong on the
    # first build.  The grip is now a through slot lower down, reachable from
    # OUTSIDE the box: hook two fingers in and lift.
    p.add(outline(BACK_W, BACK_H,
                  slot_bottom=(BACK_W / 2, CFG['CABLE_SLOT_W'], CFG['CABLE_SLOT_H'])))
    cx = BACK_W / 2
    fw, fh = CFG['FINGER_W'], CFG['FINGER_H']
    fy = BACK_H - CFG['FINGER_DROP']                     # 142.2 .. 156.2
    p.cut_rect('FINGER-SLOT', cx - fw / 2, fy, fw, fh, r=fh / 2)
    tof_feature(p, 'TOF-REAR', cx - CFG['TOF_W'] / 2, 112.0, 'REAR')
    p.add(label('02 BACK -- SLIDING PANEL', cx, 85.0, 6.0))
    p.add(label('SLIDE UP = OPEN', cx, 72.0, 4.5))
    p.add(label('AC CABLE SLOT -- PANEL LIFTS OFF THE CABLE', cx, 34.0, 3.0))
    p.add(label('FIT A GROMMET', cx, 26.5, 3.0))
    p.add(label('FINGER SLOT -- HOOK 2 FINGERS AND LIFT', cx, BACK_H - 8.0, 3.2))
    p.add(label('LIFT', cx, fy - 8.0, 4.0))
    PARTS.append(p)
    return p


# ============================================================================
# 07 RAIL x4 and 08 REAR STOP STRIP x1 -- 6 mm wide
# ============================================================================
def build_strips():
    r = Part('07_RAIL', 'GUIDE RAIL', CFG['RAIL_W'], RAIL_L, qty=4)
    r.add(outline(CFG['RAIL_W'], RAIL_L))
    r.add(label('07 GUIDE RAIL X4', CFG['RAIL_W'] / 2, RAIL_L / 2, 4.0, rot=90.0))
    PARTS.append(r)

    s = Part('08_STOP', 'REAR STOP STRIP', CFG['RAIL_W'], STOP_L, qty=1)
    s.add(outline(CFG['RAIL_W'], STOP_L))
    s.add(label('08 REAR STOP STRIP X1', CFG['RAIL_W'] / 2, STOP_L / 2, 4.0, rot=90.0))
    PARTS.append(s)
    return r, s


# ============================================================================
# 09 TFT FRAME  (carried over from Rev C.1)
# ============================================================================
def build_tft_frame(key, board, title):
    """Rev J: four-corner clamp on a square, rotatable plate.

    The shield has pin headers down both long edges and a button on a third,
    so a straight-edge clamp always lands on a connector.  This one touches
    only the four corners of the board, through a cross-shaped opening.  The
    plate is square and its four bolts sit on the axes, so it can be turned 90
    degrees without re-drilling the front panel.
    """
    W = CFG['FRAME_SIZE']
    p = Part(key, title, W, W)
    p.add(outline(W, W))
    bw, bh = board
    pts = cross_opening(W / 2, W / 2, bw, bh, CFG['FRAME_PAD'], CFG['FRAME_RELIEF'])
    p.add(round90(pts, CFG['R_CORNER']))
    xs = [q[0] for q in pts]; ys = [q[1] for q in pts]
    p.feat_rect('OPENING', min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))
    R = CFG['FRAME_BOLT_R']
    for (hx, hy) in ((W / 2 - R, W / 2), (W / 2 + R, W / 2),
                     (W / 2, W / 2 - R), (W / 2, W / 2 + R)):
        p.cut_circ('M3', hx, hy, CFG['M3'])
    # labels live only in the corner blocks and the bottom band -- never over
    # the cross opening and never inside a bolt hole
    p.add(label(key[:3], 12.0, 22.0, 3.2))
    p.add(label('FOR A %.0f X %.0f BOARD' % (bw, bh), W / 2, 12.5, 2.4))
    p.add(label('GRIPS 4 CORNERS -- SQUARE, CAN TURN 90 DEG', W / 2, 4.5, 2.2))
    PARTS.append(p)
    return p


# ============================================================================
# 10 FIT COUPON -- cut this FIRST on scrap
# ============================================================================
def build_coupon():
    """Rev H: now also gauges the speaker bolt pattern and the mic fit."""
    W, H = 92.0, 134.0
    p = Part('10_FIT_COUPON', 'FIT / KERF COUPON', W, H)
    p.add(outline(W, H))
    # --- row 1, y 22..46 : joint and channel slots
    for i, sw in enumerate((2.85, 3.00, 3.15)):
        x = 10.0 + i * 16.0
        p.add(rrect(x, 22.0, sw, 24.0, CFG['R_SLOT']))
        p.feat_rect('coupon-slot', x, 22.0, sw, 24.0, joint=True)
        p.add(label(('%.2f' % sw), x + sw / 2, 15.0, 3.0))
    p.add(rrect(62.0, 22.0, 3.4, 24.0, CFG['R_SLOT']))
    p.feat_rect('coupon-slot', 62.0, 22.0, 3.4, 24.0, joint=True)
    p.add(label('3.40', 63.7, 15.0, 3.0))
    p.add(rrect(78.0, 22.0, 3.6, 24.0, CFG['R_SLOT']))
    p.feat_rect('coupon-slot', 78.0, 22.0, 3.6, 24.0, joint=True)
    p.add(label('3.60', 79.8, 15.0, 3.0))
    p.add(label('10 FIT COUPON -- CUT FIRST', W / 2, 6.0, 2.8))
    # --- row 2, y 51..58 : engrave power patches.  These MUST come out as a
    # mark.  If one goes through, the blue layer is set up as a cut.
    for i in range(3):
        p.add(rrect(10.0 + i * 14.0, 51.0, 10.0, 7.0, 0.0, ENG))
    p.add(label('ENG PATCH', 70.0, 57.0, 3.0))
    p.add(label('MUST NOT CUT', 70.0, 51.0, 3.0))
    # --- row 3, y 68 : toggle bushing and microphone gauges
    for hx, hd in ((12.0, 6.2), (30.0, 6.4)):
        p.cut_circ('SW-GAUGE', hx, 68.0, hd)
        p.add(label('%.1f' % hd, hx, 76.5, 2.6))
    for hx, hd in ((52.0, 15.0), (75.0, 15.5)):
        p.cut_circ('MIC-GAUGE', hx, 70.0, hd)
        p.add(label('%.1f' % hd, hx, 81.0, 2.6))
    p.add(label('SW', 21.0, 61.0, 2.6))
    # --- row 4 : speaker flange bolt gauge, 40 x 40 centre-to-centre.
    # Lay the real driver on this before the sheet is cut.  If its bolts do
    # not drop into all four holes the pitch in CFG is wrong -- one line.
    for bx in (26.0, 66.0):
        for by in (86.0, 126.0):
            p.cut_circ('SPK-GAUGE', bx, by, CFG['M3'])
    p.cut_circ('FLAME-GAUGE', 82.0, 114.0, CFG['FLAME_D'])
    p.add(label('F5.5', 82.0, 121.0, 2.4))
    p.add(label('SPEAKER BOLT GAUGE 40 X 40', W / 2, 106.0, 2.6))
    p.add(label('LAY THE DRIVER ON THESE FOUR', W / 2, 100.0, 2.8))
    p.add(label('BEFORE THE SHEET IS CUT', W / 2, 94.0, 2.8))
    PARTS.append(p)
    return p



# ----------------------------------------------------------------------------
# NOTES layer -- title block, key and component index.  ACI 8, output OFF.
# ----------------------------------------------------------------------------
def note_lines(x, y, rows, h=4.6, lead=8.0):
    """rows = list of strings, drawn downward from y"""
    out = []
    for i, r in enumerate(rows):
        if r:
            out += label(r, x, y - i * lead, h, anchor='lb', layer=NOTE)
    return out


NOTES_PRIMS = []


def build_notes():
    P = []
    W, H = CFG['SHEET_W'], CFG['SHEET_H']
    C1, C2 = 14.0, 308.0
    HD, LD = 4.0, 7.0
    P.append(rrect(0, 0, W, H, 0.0, NOTE))                 # sheet outline
    P.append(rrect(6, 574, W - 12, H - 580, 0.0, NOTE))    # title block frame
    variant = 'WITH TOF HOLES' if CFG['TOF_CUT'] else 'NO TOF -- NOTHING CUT OR MARKED'
    P += label('GENIE ENCLOSURE  REV J  -- SLIDE  -- ' + variant,
               C1, 893, 8.4, anchor='lb', layer=NOTE)
    P += note_lines(C1, 876, [
        '177.8 MM CUBE / 3.0 MM CLEAR CAST ACRYLIC / ALL DIMENSIONS MM / 29-08-2026',
        'VERTICALLY SLIDING REMOVABLE BACK PANEL IN GLUED 6 MM GUIDE RAILS',
    ], 4.2, 7.4)

    # ---- left column ----
    P += label('LAYER KEY', C1, 852, 5.5, anchor='lb', layer=NOTE)
    P += note_lines(C1, 841, [
        'RED   ACI 1  CUT      THROUGH CUT',
        'BLUE  ACI 5  ENGRAVE  SURFACE MARKS AND LABELS, LOW POWER',
        'GREY  ACI 8  NOTES    THIS TEXT AND THE BORDER.',
        '                      SET OUTPUT OFF. DO NOT CUT THE GREY LAYER.',
    ], HD, LD)
    P += label('PART LIST -- 13 PIECES, 10 UNIQUE', C1, 806, 5.5, anchor='lb', layer=NOTE)
    P += note_lines(C1, 795, [
        'NO  PART            SIZE MM        QTY  NOTE',
        '01  FRONT           177.8 X 177.8   1   TFT, 2 MIC DIA 12, FLAME DIA 5.2.',
        '02  BACK SLIDER     171.0 X 171.2   1   AC CABLE SLOT. SLIDES UP.',
        '03  LEFT            174.8 X 171.8   1   SPEAKER DIA 46 + 4 M3, MQ2.',
        '04  RIGHT           174.8 X 171.8   1   MIRROR OF 03',
        '05  TOP             177.8 X 165.0   1   3 BUTTONS, 6 TOGGLE SW, DHT+LED SLOT.',
        '06  BOTTOM          177.8 X 174.8   1   4 X M3 DECK MOUNTS',
        '07  GUIDE RAIL        6.0 X 171.8   4   2 PER SIDE, INNER FACE',
        '08  REAR STOP STRIP   6.0 X 165.8   1   ON BOTTOM, BETWEEN REAR RAILS',
        '09  TFT CLAMP FRAME 116.0 X 104.0   1   CROSS OPENING, 4 CORNER PADS',
        '10  FIT COUPON       92.0 X 134.0   1   CUT THIS FIRST, ON SCRAP',
    ], HD, LD)
    P += label('BEFORE CUTTING THE SHEET', C1, 702, 5.5, anchor='lb', layer=NOTE)
    P += note_lines(C1, 691, [
        '1  CUT PART 10 ON SCRAP FIRST. SLOTS 2.85 / 3.00 / 3.15 ARE',
        '   FOR THE TAB JOINTS, 3.40 / 3.60 FOR THE SLIDING CHANNEL.',
        '   PUSH A 3 MM OFFCUT INTO EACH ONE.',
        '2  RIGHT FIT = SLIDES TOGETHER UNDER LIGHT THUMB PRESSURE.',
        '   IF TWO FEEL OK, TAKE THE TIGHTER ONE -- CEMENT FILLS A',
        '   TIGHT JOINT BY CAPILLARY ACTION, NOT A LOOSE ONE.',
        '3  PART 10 ALSO GAUGES: TOGGLE BUSHING 6.2 / 6.4, MICROPHONE',
        '   12.0 / 12.5, FLAME 5.2, AND THE SPEAKER BOLTS ON A 40 X 40',
        '   SQUARE. LAY THE REAL DRIVER ON THOSE FOUR HOLES -- IF ITS',
        '   BOLTS DO NOT DROP IN, STOP, THE PITCH IS WRONG.',
        '4  CONFIRM THE 3 BLUE PATCHES COME OUT AS A MARK. IF ONE GOES',
        '   THROUGH, THE BLUE LAYER IS SET UP AS A CUT -- FIX IT.',
        '5  KERF IS NOT COMPENSATED IN THIS FILE. MEASURED 0.178 MM.',
        '6  FILM STAYS ON BOTH FACES UNTIL AFTER CUTTING.',
        '7  CORRECT CUT ON CAST ACRYLIC = CLEAR GLOSSY EDGE.',
        '   FROSTED MEANS THE SETTINGS ARE WRONG.',
    ], HD, LD)

    # ---- right column ----
    P += label('COMPONENT PLACEMENT', C2, 852, 5.5, anchor='lb', layer=NOTE)
    P += note_lines(C2, 841, [
        'ORIGIN = BOTTOM LEFT OF EACH PANEL AS DRAWN, FROM OUTSIDE',
        '',
        '01 FRONT',
        '   TFT WINDOW      63 X 45 R2     CENTRE 88.9 , 114.5',
        '   TFT FRAME BOLTS 4 X DIA 3.2    40.9 / 136.9  X  72.5 / 156.5',
        '   MICROPHONE X2   2 X DIA 12     22.0 AND 155.8 , 155.8',
        '                   UPPER CORNERS, 133.8 APART. INMP441 BOARD',
        '                   MEASURES 11 -- 12.0 IS A SLIP FIT, TAPE IT',
        '                   FROM BEHIND, IT IS NOT A PRESS FIT.',
        '   FLAME           DIA 5.2        CENTRE 88.9 , 45.0',
        '                   FINAL SIZE. NO REDUCER RING ANY MORE.',
        '   TOF: NO HOLES ANY PANEL -- BLUE FOOTPRINTS MARK POSITIONS',
        '',
        '03 LEFT AND 04 RIGHT    A = FROM FRONT, V = HEIGHT',
        '   SPEAKER         DIA 46 THROUGH A 62 , V 112',
        '                   BODY 44, FLANGE 50 SQ, BOLTS 56.6 DIAGONAL',
        '                   4 X M3 AT A 42 / 82 , V 92 / 132',
        '                   DRIVER BOLTS ON THE OUTSIDE FACE.',
        '   SMOKE MQ2       DIA 20         A 30 , V 68  MOVED FORWARD',
        '   TOF ' + ('25 X 10 CUT   A 122 , V 112' if CFG['TOF_CUT'] else 'INTERNAL -- NOTHING CUT OR MARKED'),
        '   BLUE RAIL A     A 159.4 - 165.4    GLUE 6 MM STRIP',
        '   BLUE CHANNEL    A 165.4 - 168.8    3.40, PANEL SLIDES HERE',
        '   BLUE RAIL B     A 168.8 - 174.8    GLUE 6 MM STRIP',
        '',
        ('02 BACK  TOF REAR 25 X 10 CUT, CENTRE 85.5 , 117.0' if CFG['TOF_CUT'] else
         '02 BACK  NO TOF -- SENSOR MOUNTS INSIDE THE PANEL'),
        '         AC CABLE U-SLOT 14 X 20 IN THE BOTTOM EDGE, CENTRE',
        '         FINGER SLOT 60 X 14 R7 THROUGH, CENTRE 85.5 , 149.2',
        '         REV F: THE OLD TOP-EDGE NOTCH IS GONE. THE SLOT IS',
        '         REACHED FROM OUTSIDE THE BOX. FIT A GROMMET IN THE',
        '         CABLE SLOT.',
        '05 TOP   3 X BUTTON DIA 12   53.9 / 88.9 / 123.9 , 105.0',
        '         6 X TOGGLE SW DIA 6.4  X 22.0 AND 155.8,',
        '                                Y 78.0 / 100.0 / 122.0',
        '         SW1-3 LEFT COLUMN, SW4-6 RIGHT COLUMN, ESP POWER',
        '         BUSHING IS M6 X 0.75 -- GAUGE IT ON PART 10 FIRST',
        '         DHT11 18 X 14 R2    CENTRE 88.9 , 140.0  FLUSH',
        '         DHT RELIEF 12.5 X 12   CENTRE 70.2 , 140.0',
        '         CLEARS THE RED LED *AND* THE 3-PIN CONNECTOR.',
        '         3.5 MM BRIDGE TO THE SENSOR WINDOW.',
        '         PAN-TILT: DIA 10 WIRE AT 88.9 , 52.0 + 4 X M3 REF',
        '06 BOTTOM  4 X DIA 3.2   44 / 133.8  X  44 / 120.8',
        '',
        'INTERNAL, NO APERTURE: MPU-6050 X2, VIBRATION X2, ESP BOARDS',
        'NO APERTURE CUT FOR THE IR OBSTACLE SENSOR -- STILL UNDECIDED',
    ], HD, LD)

    NOTES_PRIMS.extend(P)
    return P


# ----------------------------------------------------------------------------
# bounding boxes + nesting
# ----------------------------------------------------------------------------
def bbox_of(part):
    xs, ys = [], []
    for pr in part.prims:
        if isinstance(pr, Circle):
            xs += [pr.c[0] - pr.r, pr.c[0] + pr.r]
            ys += [pr.c[1] - pr.r, pr.c[1] + pr.r]
        else:
            xs += [q[0] for q in pr.pts]
            ys += [q[1] for q in pr.pts]
    return min(xs), min(ys), max(xs), max(ys)


def nest():
    for p in PARTS:
        p.bb = bbox_of(p)
    by = {p.key: p for p in PARTS}
    G, M = CFG['GAP'], CFG['MARGIN']
    rows = [
        ['01_FRONT', '06_BOTTOM', '05_TOP'],
        ['03_LEFT', '04_RIGHT', '02_BACK_SLIDER'],
    ]
    y = M
    for row in rows:
        x = M
        rh = 0.0
        for k in row:
            p = by[k]
            w = p.bb[2] - p.bb[0]
            h = p.bb[3] - p.bb[1]
            p.org = (x - p.bb[0], y - p.bb[1])
            x += w + G
            rh = max(rh, h)
        y += rh + G
    # strip column + small parts on the last row
    x = M
    rail = by['07_RAIL']
    for i in range(4):
        w = rail.bb[2] - rail.bb[0]
        rail_i = Part('07_RAIL_%d' % (i + 1), rail.title, rail.w, rail.h)
        rail_i.prims = rail.prims
        rail_i.feats = rail.feats
        rail_i.bb = rail.bb
        rail_i.org = (x - rail.bb[0], y - rail.bb[1])
        x += w + 10.0
        RAIL_COPIES.append(rail_i)
    stop = by['08_STOP']
    stop.org = (x - stop.bb[0], y - stop.bb[1])
    x += (stop.bb[2] - stop.bb[0]) + G
    fa = by['09A_TFT_FRAME']
    fa.org = (x - fa.bb[0], y - fa.bb[1])
    fb = by['09B_TFT_FRAME']
    fb.org = (x + (fa.bb[2] - fa.bb[0]) + G - fb.bb[0], y - fb.bb[1])
    cp = by['10_FIT_COUPON']
    cp.org = (x - cp.bb[0], y + (fa.bb[3] - fa.bb[1]) + G - cp.bb[1])


RAIL_COPIES = []


def placed():
    """(part, prims translated onto the sheet) for every instance."""
    out = []
    for p in PARTS:
        if p.key == '07_RAIL':
            continue
        out.append((p, [pr.moved(*p.org) for pr in p.prims]))
    for r in RAIL_COPIES:
        out.append((r, [pr.moved(*r.org) for pr in r.prims]))
    return out


# ----------------------------------------------------------------------------
# geometry check
# ----------------------------------------------------------------------------
def rect_rect_gap(a, b):
    dx = max(a[0] - b[2], b[0] - a[2], 0.0)
    dy = max(a[1] - b[3], b[1] - a[3], 0.0)
    if dx == 0 and dy == 0:
        return -1.0
    return math.hypot(dx, dy)


def circ_rect_gap(c, r):
    cx, cy, cr = c
    nx = min(max(cx, r[0]), r[2])
    ny = min(max(cy, r[1]), r[3])
    return math.hypot(cx - nx, cy - ny) - cr


def feat_gap(f1, f2):
    (_, k1, g1, _), (_, k2, g2, _) = f1, f2
    if k1 == 'rect' and k2 == 'rect':
        return rect_rect_gap(g1, g2)
    if k1 == 'circ' and k2 == 'circ':
        return math.hypot(g1[0] - g2[0], g1[1] - g2[1]) - g1[2] - g2[2]
    if k1 == 'circ':
        return circ_rect_gap(g1, g2)
    return circ_rect_gap(g2, g1)


def check():
    issues = []
    for p in PARTS:
        if p.key.startswith('07_RAIL_'):
            continue
        fs = p.feats
        for i in range(len(fs)):
            for j in range(i + 1, len(fs)):
                if fs[i][3] and fs[j][3]:
                    continue                      # joint vs joint is by design
                # a cut and its own engraved footprint ring are concentric
                if {fs[i][0], fs[j][0]} in ({'MIC', 'MIC-MOD'},
                                            {'SPEAKER', 'SPK-RING'}):
                    continue
                g = feat_gap(fs[i], fs[j])
                if g < CFG['MIN_FEATURE_GAP']:
                    issues.append('%s: %s <-> %s gap %.2f mm'
                                  % (p.key, fs[i][0], fs[j][0], g))
        for (nm, k, g, joint) in fs:
            if joint:
                continue
            if k == 'rect':
                d = min(g[0], g[1], p.w - g[2], p.h - g[3])
            else:
                d = min(g[0] - g[2], g[1] - g[2], p.w - g[0] - g[2], p.h - g[1] - g[2])
            if d < CFG['MIN_EDGE_GAP']:
                issues.append('%s: %s only %.2f mm from panel edge' % (p.key, nm, d))

    # tab / mortise correspondence
    def col(part, x):
        return sorted((round(f[2][1], 3), round(f[2][3], 3))
                      for f in part.feats if f[3] and f[1] == 'rect'
                      and abs(f[2][0] - x) < 1e-6)

    by = {p.key: p for p in PARTS}
    want_front = sorted((round(T + a, 3), round(T + b, 3)) for a, b in FRONT_TABS_Z)
    for x in (0.0, S - T):
        if col(by['01_FRONT'], x) != want_front:
            issues.append('01_FRONT mortise column at x=%.1f does not match side tabs' % x)
    want_bl = sorted((round(a, 3), round(b, 3)) for a, b in BL_TABS_A)
    for x in (0.0, S - T):
        if col(by['06_BOTTOM'], x) != want_bl:
            issues.append('06_BOTTOM mortise column at x=%.1f mismatch' % x)
    want_tp = sorted((round(a, 3), round(b, 3)) for a, b in TOPEDGE_A)
    for x in (0.0, S - T):
        if col(by['05_TOP'], x) != want_tp:
            issues.append('05_TOP mortise column at x=%.1f mismatch' % x)

    # sheet fit + part overlap
    inst = placed()
    boxes = []
    for p, prims in inst:
        xs, ys = [], []
        for pr in prims:
            if isinstance(pr, Circle):
                xs += [pr.c[0] - pr.r, pr.c[0] + pr.r]
                ys += [pr.c[1] - pr.r, pr.c[1] + pr.r]
            else:
                xs += [q[0] for q in pr.pts]
                ys += [q[1] for q in pr.pts]
        boxes.append((p.key, min(xs), min(ys), max(xs), max(ys)))
    for k, x0, y0, x1, y1 in boxes:
        if x0 < 0 or y0 < 0 or x1 > CFG['SHEET_W'] or y1 > CFG['SHEET_H']:
            issues.append('%s falls off the %gx%g sheet' % (k, CFG['SHEET_W'], CFG['SHEET_H']))
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            a, b = boxes[i], boxes[j]
            if rect_rect_gap(a[1:], b[1:]) < 4.0:
                issues.append('nest: %s and %s closer than 4 mm' % (a[0], b[0]))

    # sliding stack sanity
    if abs((CHANNEL_A[1] - CHANNEL_A[0]) - (T + CFG['SLIDE_CLEAR'])) > 1e-9:
        issues.append('sliding channel width wrong')
    if RAIL_REAR_A[1] != BOT_DEPTH:
        issues.append('rear rail is not flush with the rear face')
    if TOP_DEPTH > CHANNEL_A[0] + 3.0:
        issues.append('top panel fouls the sliding panel exit slot')
    if BACK_W >= IN or BACK_H >= IN:
        issues.append('sliding panel will not fit the opening')
    return issues, boxes


# ----------------------------------------------------------------------------
# DXF
# ----------------------------------------------------------------------------
def write_dxf(path, cut_aci, eng_aci, note_aci=8):
    doc = ezdxf.new('R12')
    doc.header['$MEASUREMENT'] = 1
    doc.layers.add(CUT, color=cut_aci)
    doc.layers.add(ENG, color=eng_aci)
    doc.layers.add(NOTE, color=note_aci)
    msp = doc.modelspace()
    n = 0
    for _p, prims in placed() + [(None, NOTES_PRIMS)]:
        for pr in prims:
            aci = {CUT: cut_aci, ENG: eng_aci, NOTE: note_aci}[pr.layer]
            att = {'layer': pr.layer, 'color': aci}
            if isinstance(pr, Circle):
                msp.add_circle(pr.c, pr.r, dxfattribs=att)
            else:
                pl = msp.add_polyline2d(
                    [(x, y, 0.0, 0.0, b) for (x, y, b) in pr.pts],
                    format='xyseb', dxfattribs=att)
                if pr.closed:
                    pl.close(True)
            n += 1
    doc.saveas(path)
    return n


# ----------------------------------------------------------------------------
# flatten for rendering
# ----------------------------------------------------------------------------
def arc_pts(p1, p2, b, n=18):
    if abs(b) < 1e-12:
        return [p2]
    th = 4.0 * math.atan(b)
    ch = math.hypot(p2[0] - p1[0], p2[1] - p1[1])
    if ch < 1e-12:
        return [p2]
    r = ch / (2.0 * math.sin(th / 2.0))
    mx, my = (p1[0] + p2[0]) / 2.0, (p1[1] + p2[1]) / 2.0
    ux, uy = -(p2[1] - p1[1]) / ch, (p2[0] - p1[0]) / ch
    h = r * math.cos(th / 2.0)
    cx, cy = mx + ux * h, my + uy * h
    a1 = math.atan2(p1[1] - cy, p1[0] - cx)
    return [(cx + abs(r) * math.cos(a1 + th * k / n),
             cy + abs(r) * math.sin(a1 + th * k / n)) for k in range(1, n + 1)]


def flatten(poly):
    pts = poly.pts
    out = [(pts[0][0], pts[0][1])]
    seq = list(range(len(pts) - 1)) + ([len(pts) - 1] if poly.closed else [])
    for i in seq:
        p1 = (pts[i][0], pts[i][1])
        p2 = (pts[(i + 1) % len(pts)][0], pts[(i + 1) % len(pts)][1])
        out += arc_pts(p1, p2, pts[i][2])
    return out


def reset():
    del PARTS[:]
    del RAIL_COPIES[:]
    del NOTES_PRIMS[:]


def build_variant(tof_cut, prefix, outdir='.'):
    import os
    CFG['TOF_CUT'] = tof_cut
    reset()
    build_front()
    build_side('03_LEFT', 'LEFT', True)
    build_side('04_RIGHT', 'RIGHT', False)
    build_top()
    build_bottom()
    build_back()
    build_strips()
    build_tft_frame('09A_TFT_FRAME', CFG['TFT_BOARD_A'], 'TFT CLAMP FRAME A')
    build_tft_frame('09B_TFT_FRAME', CFG['TFT_BOARD_B'], 'TFT CLAMP FRAME B')
    build_coupon()
    nest()
    build_notes()
    issues, boxes = check()
    os.makedirs(outdir, exist_ok=True)
    f1 = os.path.join(outdir, prefix + '.dxf')
    f2 = os.path.join(outdir, prefix + '_blackred.dxf')
    n1 = write_dxf(f1, 1, 5)
    n2 = write_dxf(f2, 7, 1)
    ex = max(b[3] for b in boxes); ey = max(b[4] for b in boxes)
    ntof = sum(1 for p in PARTS for f in p.feats if f[0].startswith('TOF')
               and not f[0].endswith('-ENG'))
    print('--- %s ---' % prefix)
    print('    TOF_CUT      : %s   (%d ToF apertures on the CUT layer)'
          % (tof_cut, ntof if tof_cut else 0))
    print('    parts placed : %d' % len(placed()))
    print('    nest extents : %.1f x %.1f mm on a %g x %g sheet'
          % (ex, ey, CFG['SHEET_W'], CFG['SHEET_H']))
    print('    entities     : %d / %d' % (n1, n2))
    print('    GEOMETRY CHECK: %d issue(s)' % len(issues))
    for s in issues:
        print('       !', s)
    return f1, f2


if __name__ == '__main__':
    build_variant(True,  'GENIE_WITH_TOF',    'DESIGN_A_WITH_TOF_HOLES')
    build_variant(False, 'GENIE_NO_TOF', 'DESIGN_B_NO_TOF')
