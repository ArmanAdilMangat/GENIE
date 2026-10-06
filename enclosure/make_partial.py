#!/usr/bin/env python3
"""Rev H partial cuts -- re-cut only the panels that changed.

Geometry is taken verbatim from genie_case_final.py, so anything emitted here
is byte-identical to the audited full sheet; only the nesting differs.
"""
import math, os, ezdxf
import genie_case_final as G

G.CFG['TOF_CUT'] = False
G.reset()
G.build_front(); G.build_side('03_LEFT','LEFT',True); G.build_side('04_RIGHT','RIGHT',False)
G.build_top(); G.build_bottom(); G.build_back(); G.build_strips()
G.build_tft_frame('09A_TFT_FRAME', G.CFG['TFT_BOARD_A'], 'TFT CLAMP FRAME A')
G.build_tft_frame('09B_TFT_FRAME', G.CFG['TFT_BOARD_B'], 'TFT CLAMP FRAME B')
G.build_coupon(); G.nest()
BY = {p.key: p for p in G.PARTS}
for p in G.PARTS:
    p.bb = G.bbox_of(p)

SUBSETS = {
    'SIDE_PANELS_ONLY':  ['03_LEFT', '04_RIGHT'],
    'REPLACEMENT_PANELS':['01_FRONT', '03_LEFT', '04_RIGHT', '05_TOP',
                          '09A_TFT_FRAME', '09B_TFT_FRAME', '10_FIT_COUPON'],
}

def shelf(keys, sheet_w=610.0, M=10.0, GAP=12.0):
    """simple shelf packing, returns (placements, w, h)"""
    x, y, rowh, out = M, M, 0.0, []
    for k in keys:
        p = BY[k]
        w = p.bb[2] - p.bb[0]; h = p.bb[3] - p.bb[1]
        if x + w + M > sheet_w and x > M:
            x = M; y += rowh + GAP; rowh = 0.0
        out.append((p, (x - p.bb[0], y - p.bb[1])))
        x += w + GAP; rowh = max(rowh, h)
    W = max(pl[1][0] + BY[pl[0].key].bb[2] for pl in out) + M
    H = y + rowh + M
    return out, W, H

def note(prims, x, y, rows, h=3.6, lead=6.2):
    for i, r in enumerate(rows):
        if r:
            prims += G.label(r, x, y - i * lead, h, anchor='lb', layer=G.NOTE)

def emit(name, keys, headline):
    pls, W, H = shelf(keys)
    prims = []
    for p, org in pls:
        prims += [pr.moved(*org) for pr in p.prims]
    note(prims, 10.0, H + 34.0, [
        'GENIE ENCLOSURE  REV H  --  ' + headline,
        'PARTIAL CUT. GEOMETRY IDENTICAL TO THE FULL REV H SHEET.',
        'RED ACI 1 = CUT   BLUE ACI 5 = ENGRAVE   GREY ACI 8 = NOTES, OUTPUT OFF',
        'MATERIAL 3.0 MM CLEAR CAST ACRYLIC.  ALL DIMENSIONS MM.',
        'STOCK NEEDED: %d X %d MM' % (math.ceil(W), math.ceil(H)),
    ], 4.0, 6.6)
    doc = ezdxf.new('R12'); doc.header['$MEASUREMENT'] = 1
    for lay, aci in ((G.CUT,1),(G.ENG,5),(G.NOTE,8)):
        doc.layers.add(lay, color=aci)
    msp = doc.modelspace()
    for pr in prims:
        aci = {G.CUT:1, G.ENG:5, G.NOTE:8}[pr.layer]
        att = {'layer': pr.layer, 'color': aci}
        if isinstance(pr, G.Circle):
            msp.add_circle(pr.c, pr.r, dxfattribs=att)
        else:
            pl = msp.add_polyline2d([(x,y,0.0,0.0,b) for (x,y,b) in pr.pts],
                                    format='xyseb', dxfattribs=att)
            if pr.closed: pl.close(True)
    os.makedirs('PARTIAL_CUTS', exist_ok=True)
    path = os.path.join('PARTIAL_CUTS', name + '.dxf')
    doc.saveas(path)
    # png
    import matplotlib; matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(13, 13.0 * (H + 60) / max(W, 1)), dpi=140)
    for pr in prims:
        if isinstance(pr, G.Circle):
            q = [(pr.c[0]+pr.r*math.cos(t), pr.c[1]+pr.r*math.sin(t))
                 for t in [i*2*math.pi/120 for i in range(121)]]
            paths = [q]
        else:
            paths = [G.flatten(pr)]
        c = {G.CUT:'#c0392b', G.ENG:'#1f5fa8', G.NOTE:'#8b8b8b'}[pr.layer]
        for q in paths:
            ax.plot([a[0] for a in q], [a[1] for a in q], color=c,
                    lw=1.25 if pr.layer==G.CUT else 0.5, solid_capstyle='round')
    ax.set_aspect('equal'); ax.axis('off')
    ax.set_title('%s  --  stock %d x %d mm' % (headline, math.ceil(W), math.ceil(H)),
                 fontsize=13, fontweight='bold', pad=12)
    fig.tight_layout(); fig.savefig(os.path.join('PARTIAL_CUTS', name + '.png'),
                                    facecolor='#fff', bbox_inches='tight')
    plt.close(fig)
    # blue-to-red clearance, same test the full-sheet audit uses
    red, blue = [], []
    for pr in prims:
        pts = ([(pr.c[0]+pr.r*math.cos(2*math.pi*k/128), pr.c[1]+pr.r*math.sin(2*math.pi*k/128))
                for k in range(128)] if isinstance(pr, G.Circle) else G.flatten(pr))
        if pr.layer == G.CUT: red.append(pts)
        elif pr.layer == G.ENG: blue.append(pts)
    cell = 4.0
    grid = {}
    for q in red:
        for a in q:
            grid.setdefault((int(a[0]//cell), int(a[1]//cell)), []).append(a)
    mind = 9e9
    for q in blue:
        for b in q:
            gx, gy = int(b[0]//cell), int(b[1]//cell)
            for ddx in (-1,0,1):
                for ddy in (-1,0,1):
                    for a in grid.get((gx+ddx, gy+ddy), ()):
                        d = math.hypot(a[0]-b[0], a[1]-b[1])
                        if d < mind: mind = d
    ncut = sum(1 for pr in prims if pr.layer == G.CUT)
    print('   closest blue-to-red %.2f mm   %s' %
          (mind, 'OK' if mind >= 0.30 else '*** TOO CLOSE ***'))
    print('%-20s  %d parts  stock %d x %d mm  %d cut paths' %
          (name, len(keys), math.ceil(W), math.ceil(H), ncut))

emit('SIDE_PANELS_ONLY', SUBSETS['SIDE_PANELS_ONLY'],
     '03 LEFT + 04 RIGHT ONLY')
emit('REPLACEMENT_PANELS', SUBSETS['REPLACEMENT_PANELS'],
     'EVERYTHING THAT CHANGED SINCE THE FIRST CUT')

# ---------------------------------------------------------------------------
# 12 FEATURE TEST CARD -- every aperture that changed, at true size, on one
# small piece of scrap.  Offer the real components up to it BEFORE cutting a
# full sheet.  Not part of the production nest.
# ---------------------------------------------------------------------------
def build_feature_card():
    W, H = 120.0, 170.0
    p = G.Part('12_TEST_CARD', 'FEATURE TEST CARD', W, H)
    p.add(G.outline(W, H))
    C = G.CFG
    # --- speaker, full size, with its four flange bolts
    sx, sy = 60.0, 95.0
    p.cut_circ('SPEAKER', sx, sy, C['SPK_CUT_D'])
    hp = C['SPK_BOLT_PITCH'] / 2.0
    for dx in (-hp, hp):
        for dy in (-hp, hp):
            p.cut_circ('SPK-M3', sx + dx, sy + dy, C['M3'])
    p.add(G.label('SPEAKER DIA 46 + 4 X M3 ON 40 X 40', sx, 126.0, 3.0))
    p.add(G.label('BODY MUST PASS, FLANGE MUST BOLT', sx, 64.0, 2.6))
    # --- finger slot, full size
    fw, fh = C['FINGER_W'], C['FINGER_H']
    p.cut_rect('FINGER-SLOT', W / 2 - fw / 2, 143.0, fw, fh, r=fh / 2)
    p.add(G.label('FINGER SLOT -- HOOK 2 FINGERS', W / 2, 137.0, 2.6))
    # --- DHT11 window + LED slot, exact spacing
    dx0 = 75.0
    p.cut_rect('DHT11', dx0 - C['DHT_W'] / 2, 45.0 - C['DHT_H'] / 2,
               C['DHT_W'], C['DHT_H'])
    lw, lh = C['DHT_LED_W'], C['DHT_LED_H']
    p.cut_rect('DHT-LED', dx0 + C['DHT_LED_DX'] - lw / 2, 45.0 - lh / 2,
               lw, lh, r=lw / 2)
    p.add(G.label('DHT11 + LED SLOT', dx0 - 4.0, 57.0, 2.8))
    p.add(G.label('LED IS 14.5 LEFT', dx0 - 4.0, 32.5, 2.6))
    # --- microphone
    p.cut_circ('MIC', 25.0, 45.0, C['MIC_HOLE_D'])
    p.add(G.label('MIC 12', 25.0, 54.5, 2.8))
    # --- flame, final size
    p.cut_circ('FLAME', 25.0, 18.0, C['FLAME_D'])
    p.add(G.label('FLAME 5.2', 25.0, 25.0, 2.6))
    # --- one toggle and one button
    p.cut_circ('SWITCH', 62.0, 18.0, C['SWITCH_D'])
    p.add(G.label('SW 6.4', 62.0, 26.0, 2.4))
    p.cut_circ('BUTTON', 90.0, 18.0, C['BUTTON_D'])
    p.add(G.label('BTN 12', 90.0, 28.0, 2.4))
    p.add(G.label('12 FEATURE TEST CARD', W / 2, 163.0, 3.2))
    G.PARTS.append(p)
    p.bb = G.bbox_of(p)
    BY[p.key] = p
    return p

build_feature_card()

SUBSETS['COUPON_ONLY'] = ['10_FIT_COUPON']
emit('COUPON_ONLY', SUBSETS['COUPON_ONLY'],
     'PART 10 ONLY -- CUT THIS ON SCRAP BEFORE THE SHEET')
SUBSETS['TEST_CUT_FIRST'] = ['12_TEST_CARD', '10_FIT_COUPON',
                             '09A_TFT_FRAME', '09B_TFT_FRAME']
emit('TEST_CUT_FIRST', SUBSETS['TEST_CUT_FIRST'],
     'CUT THIS FIRST -- EVERY CHANGED FEATURE, TRUE SIZE')
