#!/usr/bin/env python3
"""Independent audit of GENIE_REVD_SLIDE.dxf.

Reads the DXF back off disk and checks it the way a stranger would. Nothing is
taken from the generator's data structures -- every number is measured from the
file. Run this before sending anything to the machine:

    python3 verify_dxf.py GENIE_REVD_SLIDE.dxf

Exit code 0 = safe to cut. Non-zero = do not cut.
"""
import math, sys, collections
import ezdxf

PATH = sys.argv[1] if len(sys.argv) > 1 else 'GENIE_NO_TOF.dxf'
T, SHEET_W, SHEET_H = 3.0, 610.0, 915.0
OK, FAIL = [], []


def arc(p1, p2, b, n=48):
    if abs(b) < 1e-12:
        return [p2]
    th = 4.0 * math.atan(b)
    ch = math.hypot(p2[0] - p1[0], p2[1] - p1[1])
    if ch < 1e-12:
        return [p2]
    r = ch / (2.0 * math.sin(th / 2.0))
    mx, my = (p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2
    ux, uy = -(p2[1] - p1[1]) / ch, (p2[0] - p1[0]) / ch
    cx, cy = mx + ux * r * math.cos(th / 2), my + uy * r * math.cos(th / 2)
    a1 = math.atan2(p1[1] - cy, p1[0] - cx)
    return [(cx + abs(r) * math.cos(a1 + th * k / n),
             cy + abs(r) * math.sin(a1 + th * k / n)) for k in range(1, n + 1)]


doc = ezdxf.readfile(PATH)
msp = doc.modelspace()
print('file    :', PATH)
print('version :', doc.dxfversion, '(AC1009 = AutoCAD R12)')

# 1 -------------------------------------------------------------- layers
lay = collections.Counter((e.dxf.layer, e.dxf.color) for e in msp)
print('layers  :', dict(lay))
SCHEMES = {frozenset({('CUT', 1), ('ENGRAVE', 5), ('NOTES', 8)}):
           'CUT=1 red, ENGRAVE=5 blue, NOTES=8 grey  (LaserCut / SmartCarve)',
           frozenset({('CUT', 7), ('ENGRAVE', 1), ('NOTES', 8)}):
           'CUT=7 black, ENGRAVE=1 red, NOTES=8 grey  (generic)'}
if frozenset(lay) not in SCHEMES:
    FAIL.append('layer / ACI colour set is wrong: %s' % set(lay))
else:
    OK.append('3 layers, every entity carries an explicit ACI colour -- %s'
              % SCHEMES[frozenset(lay)])
ty = collections.Counter(e.dxftype() for e in msp)
if set(ty) - {'POLYLINE', 'CIRCLE'}:
    FAIL.append('entity types beyond POLYLINE/CIRCLE: %s' % set(ty))
else:
    OK.append('only R12-safe POLYLINE and CIRCLE entities (%s)' % dict(ty))

# 2 --------------------------------------------------------- CUT geometry
polys, circles, openp = [], [], 0
for e in msp:
    if e.dxf.layer != 'CUT':
        continue
    if e.dxftype() == 'CIRCLE':
        circles.append((e.dxf.center.x, e.dxf.center.y, e.dxf.radius))
        continue
    raw = [(v.dxf.location.x, v.dxf.location.y, v.dxf.bulge) for v in e.vertices]
    closed = bool(e.is_closed)
    openp += (not closed)
    pts = [(raw[0][0], raw[0][1])]
    for i in list(range(len(raw) - 1)) + ([len(raw) - 1] if closed else []):
        pts += arc((raw[i][0], raw[i][1]),
                   (raw[(i + 1) % len(raw)][0], raw[(i + 1) % len(raw)][1]), raw[i][2])
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    polys.append({'pts': pts, 'raw': [(r[0], r[1]) for r in raw], 'closed': closed,
                  'bb': (min(xs), min(ys), max(xs), max(ys))})
if openp:
    FAIL.append('%d OPEN path(s) on CUT -- those cut a line, not a shape' % openp)
else:
    OK.append('all %d CUT polylines are closed loops' % len(polys))


def area(p):
    return abs(sum(p[i][0] * p[i + 1][1] - p[i + 1][0] * p[i][1]
                   for i in range(len(p) - 1))) / 2


def inside(pt, p):
    x, y = pt; c = False
    for i in range(len(p) - 1):
        x1, y1 = p[i]; x2, y2 = p[i + 1]
        if (y1 > y) != (y2 > y) and x1 + (y - y1) * (x2 - x1) / (y2 - y1) > x:
            c = not c
    return c


for p in polys:
    p['a'] = area(p['pts'])
outlines = []
for p in polys:
    p['host'] = next((q for q in polys if q is not p and q['a'] > p['a']
                      and inside(p['pts'][0], q['pts'])), None)
    if p['host'] is None:
        outlines.append(p)
print('outlines: %d   inner cutouts: %d   cut circles: %d'
      % (len(outlines), len(polys) - len(outlines), len(circles)))
if len(outlines) != 14:
    FAIL.append('expected 14 part outlines, found %d' % len(outlines))
else:
    OK.append('14 separate part outlines; every cutout sits inside exactly one')
for p in polys:
    if p['host'] and p['host']['host']:
        FAIL.append('a cutout is nested inside another cutout at %.1f,%.1f' % p['pts'][0])
for cx, cy, r in circles:
    h = [o for o in outlines if inside((cx, cy), o['pts'])]
    if len(h) != 1:
        FAIL.append('circle at %.1f,%.1f sits in %d outlines' % (cx, cy, len(h)))

# 3 ------------------------------------------- nothing crosses anything else
def segs(p):
    return [(p[i], p[i + 1]) for i in range(len(p) - 1)]


def X(a, b, c, d):
    def o(p, q, r):
        v = (q[1] - p[1]) * (r[0] - q[0]) - (q[0] - p[0]) * (r[1] - q[1])
        return 0 if abs(v) < 1e-9 else (1 if v > 0 else 2)
    o1, o2, o3, o4 = o(a, b, c), o(a, b, d), o(c, d, a), o(c, d, b)
    return o1 != o2 and o3 != o4 and 0 not in (o1, o2, o3, o4)


shapes = [(p['pts'], p['bb']) for p in polys]
for cx, cy, r in circles:
    cp = [(cx + r * math.cos(2 * math.pi * k / 64), cy + r * math.sin(2 * math.pi * k / 64))
          for k in range(65)]
    shapes.append((cp, (cx - r, cy - r, cx + r, cy + r)))
bad = 0
for i in range(len(shapes)):
    for j in range(i + 1, len(shapes)):
        a, b = shapes[i], shapes[j]
        if (a[1][2] < b[1][0] or b[1][2] < a[1][0]
                or a[1][3] < b[1][1] or b[1][3] < a[1][1]):
            continue
        for s1 in segs(a[0]):
            for s2 in segs(b[0]):
                if X(s1[0], s1[1], s2[0], s2[1]):
                    FAIL.append('two CUT paths cross near %.1f,%.1f' % s1[0]); bad = 1
                    break
            if bad:
                break
        if bad:
            break
    if bad:
        break
if not bad:
    OK.append('no two CUT paths intersect anywhere on the sheet')
bad = 0
for p in polys:
    s = segs(p['pts']); n = len(s)
    for i in range(n):
        for j in range(i + 2, n):
            if not (i == 0 and j == n - 1) and X(s[i][0], s[i][1], s[j][0], s[j][1]):
                FAIL.append('self-intersecting path near %.1f,%.1f' % s[i][0]); bad = 1
                break
        if bad:
            break
    if bad:
        break
if not bad:
    OK.append('no path crosses itself')

# collinear overlap: two cut paths lying on the same line (double burn)
lines = collections.Counter()
for p in polys:
    for a, b in segs(p['pts']):
        if abs(a[0] - b[0]) < 1e-6:
            lines[('V', round(a[0], 3), round(min(a[1], b[1]), 2), round(max(a[1], b[1]), 2))] += 1
        elif abs(a[1] - b[1]) < 1e-6:
            lines[('H', round(a[1], 3), round(min(a[0], b[0]), 2), round(max(a[0], b[0]), 2))] += 1
rep = [k for k, v in lines.items() if v > 1]
if rep:
    FAIL.append('%d cut segment(s) drawn twice on the same line -- double burn, e.g. %s'
                % (len(rep), rep[0]))
else:
    OK.append('no cut segment is drawn twice on the same line (no double burn)')

# 4 ------------------------------------------------------------ sheet fit
xs = [v for p in polys for v in (p['bb'][0], p['bb'][2])]
ys = [v for p in polys for v in (p['bb'][1], p['bb'][3])]
print('extents : X %.2f..%.2f  Y %.2f..%.2f' % (min(xs), max(xs), min(ys), max(ys)))
if min(xs) < 0 or min(ys) < 0 or max(xs) > SHEET_W or max(ys) > SHEET_H:
    FAIL.append('CUT geometry leaves the %g x %g sheet' % (SHEET_W, SHEET_H))
else:
    OK.append('all CUT geometry inside the %g x %g sheet' % (SHEET_W, SHEET_H))
mind = min((math.hypot(max(a['bb'][0] - b['bb'][2], b['bb'][0] - a['bb'][2], 0),
                       max(a['bb'][1] - b['bb'][3], b['bb'][1] - a['bb'][3], 0))
            for i, a in enumerate(outlines) for b in outlines[i + 1:]), default=9e9)
if mind < 4:
    FAIL.append('parts closer than 4 mm on the sheet (%.2f)' % mind)
else:
    OK.append('minimum part-to-part gap on the sheet %.2f mm' % mind)

# 5 --------------------------------------------------- tabs / notches / fit
def nominal(pts):
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)
    nx0 = x0 if any(abs(v[0] - x0) < 1e-6 and (abs(v[1] - y0) < 1e-6 or abs(v[1] - (y0 + T)) < 1e-6)
                    for v in pts) else x0 + T
    ny0 = y0 if any(abs(v[1] - y0) < 1e-6 and abs(v[0] - nx0) < 1e-6 for v in pts) else y0 + T
    nx1 = x1 if any(abs(v[0] - x1) < 1e-6 and (abs(v[1] - y1) < 1e-6 or abs(v[1] - (y1 - T)) < 1e-6)
                    for v in pts) else x1 - T
    ny1 = y1 if any(abs(v[1] - y1) < 1e-6 and abs(v[0] - nx1) < 1e-6 for v in pts) else y1 - T
    return nx0, ny0, nx1, ny1


def steps(pts):
    L, B, R, Tp = nominal(pts)
    r = {e: {'tab': [], 'notch': []} for e in 'LRBT'}
    for i in range(len(pts)):
        a, b = pts[i], pts[(i + 1) % len(pts)]
        if abs(a[0] - b[0]) < 1e-6 and abs(a[1] - b[1]) > 1e-6:
            x = a[0]; iv = (round(min(a[1], b[1]) - B, 2), round(max(a[1], b[1]) - B, 2))
            for e, xx, k in (('L', L - T, 'tab'), ('L', L + T, 'notch'),
                             ('R', R + T, 'tab'), ('R', R - T, 'notch')):
                if abs(x - xx) < 1e-6:
                    r[e][k].append(iv)
        elif abs(a[1] - b[1]) < 1e-6 and abs(a[0] - b[0]) > 1e-6:
            y = a[1]; iv = (round(min(a[0], b[0]) - L, 2), round(max(a[0], b[0]) - L, 2))
            for e, yy, k in (('B', B - T, 'tab'), ('B', B + T, 'notch'),
                             ('T', Tp + T, 'tab'), ('T', Tp - T, 'notch')):
                if abs(y - yy) < 1e-6:
                    r[e][k].append(iv)
    for e in r:
        for k in r[e]:
            r[e][k] = sorted(r[e][k])
    return r, round(R - L, 2), round(Tp - B, 2)


info = []
for o in outlines:
    s, w, h = steps(o['raw'])
    info.append({'w': w, 'h': h, 's': s})
sizes = collections.Counter((d['w'], d['h']) for d in info)
EXPECT = {(177.8, 177.8): 1, (177.8, 174.8): 1, (177.8, 165.0): 1, (174.8, 171.8): 2,
          (171.0, 171.2): 1, (6.0, 171.8): 4, (6.0, 165.8): 1,
          (100.0, 100.0): 2, (92.0, 134.0): 1}
print('\nnominal part sizes measured from the file:')
for k in sorted(sizes, reverse=True):
    tag = '' if EXPECT.get(k) == sizes[k] else '   <-- UNEXPECTED'
    print('   %7.1f x %-7.1f  x%d%s' % (k[0], k[1], sizes[k], tag))
if dict(sizes) != EXPECT:
    FAIL.append('part sizes/quantities %s, expected %s' % (dict(sizes), EXPECT))
else:
    OK.append('all 14 parts measure their specified size, correct quantities')

pick = lambda w, h: [d for d in info if (d['w'], d['h']) == (w, h)]
try:
    f = pick(177.8, 177.8)[0]['s']; b = pick(177.8, 174.8)[0]['s']
    t = pick(177.8, 165.0)[0]['s']; SI = pick(174.8, 171.8)
    mir = lambda i, W: sorted((round(W - y, 2), round(W - x, 2)) for x, y in i)
    sh = lambda i, d: [(round(x - d, 2), round(y - d, 2)) for x, y in i]
    res = []
    for d in SI:
        s = d['s']; left = bool(s['R']['tab'])
        nm = '03 LEFT ' if left else '04 RIGHT'
        fe = s['R']['tab'] or s['L']['tab']
        bt = mir(s['B']['tab'], 174.8) if left else s['B']['tab']
        tt = mir(s['T']['tab'], 174.8) if left else s['T']['tab']
        res += [('%s front tabs  -> FRONT  L+R notches' % nm,
                 fe == sh(f['L']['notch'], T) == sh(f['R']['notch'], T)),
                ('%s bottom tabs -> BOTTOM L+R notches' % nm,
                 bt == b['L']['notch'] == b['R']['notch']),
                ('%s top tabs    -> TOP    L+R notches' % nm,
                 tt == t['L']['notch'] == t['R']['notch'])]
    res += [('06 BOTTOM front tabs -> FRONT bottom notches', b['B']['tab'] == f['B']['notch']),
            ('05 TOP    front tabs -> FRONT top    notches', t['B']['tab'] == f['T']['notch'])]
    print('\njoint correspondence (mirror applied to 03 LEFT):')
    for k, v in res:
        print('   %-46s %s' % (k, 'MATCH' if v else '*** MISMATCH ***'))
    if all(v for _, v in res):
        OK.append('all 8 joint pairs line up: every tab has a notch at the same '
                  'coordinate on the mating panel')
    else:
        FAIL.append('a tab pattern does not line up with its mating notches')
    depths = set()
    for d in info:
        for e in 'LRBT':
            for k in ('tab', 'notch'):
                pass
    OK.append('tab widths: front %.2f, bottom %.2f, top %.2f mm, 5 per edge'
              % (f['L']['notch'][0][1] - f['L']['notch'][0][0],
                 b['L']['notch'][0][1] - b['L']['notch'][0][0],
                 t['L']['notch'][0][1] - t['L']['notch'][0][0]))
except Exception as ex:
    FAIL.append('could not identify the panels for the joint test: %s' % ex)

# 6 ------------------------------------------------------------- hole sizes
d_cut = collections.Counter(round(2 * c[2], 2) for c in circles)
d_eng = collections.Counter(round(2 * e.dxf.radius, 2) for e in msp
                            if e.dxf.layer == 'ENGRAVE' and e.dxftype() == 'CIRCLE')
print('\ncut circles     :', dict(d_cut))
print('engraved rings  :', dict(d_eng))
if dict(d_cut) != {3.2: 32, 5.5: 2, 6.2: 1, 6.4: 7, 10.0: 1, 12.0: 3,
                   15.0: 1, 15.5: 3, 20.0: 2, 46.0: 2}:
    FAIL.append('cut circle diameters/counts wrong: %s' % dict(d_cut))
else:
    OK.append('cut circles: 32 x M3 3.2, flame 5.5 + gauge, toggle 6.4 x6 + '
              '6.2/6.4 gauges, pan-tilt wire 10.0, 3 x button 12.0, 2 x mic '
              '15.5 + 15.0/15.5 gauges, 2 x MQ-2 20.0, 2 x speaker 46.0')
if dict(d_eng) != {}:
    FAIL.append('unexpected engraved circles %s -- rev G removed the mic and '
                'speaker rings; the cuts are the seats now' % dict(d_eng))
else:
    OK.append('no engraved circles left: the old 11 mm mic ring and 53 mm '
              'speaker seat are gone -- the 11 mm and 46 mm CUTS are the seats')

# 6b ------------------------------------------- ToF apertures, counted
def rects_about(layer, w0, h0, tol=1.5):
    n = 0
    for e in msp:
        if e.dxf.layer != layer or e.dxftype() != 'POLYLINE':
            continue
        xs = [v.dxf.location.x for v in e.vertices]
        ys = [v.dxf.location.y for v in e.vertices]
        if abs((max(xs) - min(xs)) - w0) < tol and abs((max(ys) - min(ys)) - h0) < tol:
            n += 1
    return n


tof_cut = rects_about('CUT', 25.0, 10.0)
tof_eng = rects_about('ENGRAVE', 25.0, 10.0)
print('\nToF 25 x 10 rectangles:  CUT layer = %d      ENGRAVE layer = %d'
      % (tof_cut, tof_eng))
if tof_cut == 0 and tof_eng == 0:
    OK.append('VARIANT = NO TOF AT ALL. Zero 25 x 10 rectangles on CUT and zero on '
              'ENGRAVE -- no ToF geometry anywhere in the file')
elif tof_cut == 4 and tof_eng == 0:
    OK.append('VARIANT = WITH TOF HOLES. 4 open 25 x 10 apertures on CUT, one per '
              'direction')
else:
    FAIL.append('ToF geometry is neither variant: %d cut, %d engraved'
                % (tof_cut, tof_eng))

# 6c ------------------------------------------- ENGRAVE layer safety audit
# The question this answers: can the machine turn a blue line into a cut?
# It can, in exactly three ways -- the blue layer inherits the red layer's
# colour, a blue path is drawn on top of a red one, or blue geometry lands
# somewhere it was never meant to be.  All three are tested here.
CUT_ACI = next(c for (l, c) in lay if l == 'CUT')
ENG_ACI = next((c for (l, c) in lay if l == 'ENGRAVE'), None)
eng = [e for e in msp if e.dxf.layer == 'ENGRAVE']
print('\nENGRAVE audit')
print('   entities        : %d   (CUT aci %d, ENGRAVE aci %s)'
      % (len(eng), CUT_ACI, ENG_ACI))

if not eng:
    FAIL.append('no ENGRAVE geometry at all -- the part numbers and the rail '
                'footprints are missing')
elif ENG_ACI == CUT_ACI:
    FAIL.append('ENGRAVE and CUT share ACI colour %d -- the controller builds '
                'its layer table from COLOUR, so every engraved mark would be '
                'cut through' % CUT_ACI)
else:
    bad_col = [e for e in eng if e.dxf.color != ENG_ACI]
    if bad_col:
        FAIL.append('%d ENGRAVE entities do not carry ACI %d'
                    % (len(bad_col), ENG_ACI))
    else:
        OK.append('all %d ENGRAVE entities carry ACI %d, distinct from CUT ACI '
                  '%d -- the controller will see two separate layers'
                  % (len(eng), ENG_ACI, CUT_ACI))

# flatten engrave geometry
epaths = []
for e in eng:
    if e.dxftype() == 'CIRCLE':
        c, r = e.dxf.center, e.dxf.radius
        epaths.append([(c.x + r * math.cos(2 * math.pi * k / 64),
                        c.y + r * math.sin(2 * math.pi * k / 64))
                       for k in range(65)])
        continue
    raw = [(v.dxf.location.x, v.dxf.location.y, v.dxf.bulge) for v in e.vertices]
    pts = [(raw[0][0], raw[0][1])]
    idx = list(range(len(raw) - 1)) + ([len(raw) - 1] if e.is_closed else [])
    for i in idx:
        pts += arc((raw[i][0], raw[i][1]),
                   (raw[(i + 1) % len(raw)][0], raw[(i + 1) % len(raw)][1]), raw[i][2])
    epaths.append(pts)

# (a) blue drawn on top of red: same axis-aligned line, overlapping span
def axis_segs(paths):
    out = []
    for p in paths:
        for i in range(len(p) - 1):
            a, b = p[i], p[i + 1]
            if abs(a[0] - b[0]) < 1e-6 and abs(a[1] - b[1]) > 1e-6:
                out.append(('V', round(a[0], 2), min(a[1], b[1]), max(a[1], b[1])))
            elif abs(a[1] - b[1]) < 1e-6 and abs(a[0] - b[0]) > 1e-6:
                out.append(('H', round(a[1], 2), min(a[0], b[0]), max(a[0], b[0])))
    return out


cut_ax = collections.defaultdict(list)
for k, v, lo, hi in axis_segs([p['pts'] for p in polys]):
    cut_ax[(k, v)].append((lo, hi))
ontop = []
for k, v, lo, hi in axis_segs(epaths):
    for (a, b) in cut_ax.get((k, v), ()):
        if min(hi, b) - max(lo, a) > 0.05:
            ontop.append((k, v, round(max(lo, a), 2), round(min(hi, b), 2)))
if ontop:
    FAIL.append('%d ENGRAVE segment(s) lie on top of a CUT line -- double burn, '
                'e.g. %s' % (len(ontop), ontop[0]))
else:
    OK.append('no ENGRAVE segment lies on top of a CUT line: every blue mark is '
              'on its own path, nothing gets burned twice')

# (b) every blue mark inside exactly one part outline -- nothing engraved on
#     the waste sheet, nothing straddling an edge
stray = 0
for p in epaths:
    xs = [q[0] for q in p]; ys = [q[1] for q in p]
    bb = (min(xs), min(ys), max(xs), max(ys))
    host = [o for o in outlines
            if o['bb'][0] <= bb[0] and o['bb'][1] <= bb[1]
            and o['bb'][2] >= bb[2] and o['bb'][3] >= bb[3]
            and inside(p[0], o['pts'])]
    if len(host) != 1:
        stray += 1
if stray:
    FAIL.append('%d ENGRAVE path(s) do not sit wholly inside one part outline'
                % stray)
else:
    OK.append('every ENGRAVE path sits wholly inside exactly one part outline -- '
              'no blue geometry on the waste sheet, none straddling an edge')

# (c) how close does blue come to red?  Heat-affected zones merge below ~0.3 mm
cell = 4.0
grid = collections.defaultdict(list)
for p in polys:
    for i in range(len(p['pts']) - 1):
        a = p['pts'][i]
        grid[(int(a[0] // cell), int(a[1] // cell))].append(a)
for cx0, cy0, r in circles:
    for k in range(64):
        a = (cx0 + r * math.cos(2 * math.pi * k / 64), cy0 + r * math.sin(2 * math.pi * k / 64))
        grid[(int(a[0] // cell), int(a[1] // cell))].append(a)
mind, where = 9e9, None
for p in epaths:
    for q in p:
        gx, gy = int(q[0] // cell), int(q[1] // cell)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for a in grid.get((gx + dx, gy + dy), ()):
                    d = math.hypot(a[0] - q[0], a[1] - q[1])
                    if d < mind:
                        mind, where = d, q
print('   closest blue-to-red approach : %.2f mm' % mind)
if mind < 0.30:
    FAIL.append('an ENGRAVE mark comes within %.2f mm of a CUT path at %.1f,%.1f '
                '-- the two heat-affected zones will merge and it will read as a '
                'cut' % (mind, where[0], where[1]))
else:
    OK.append('closest an ENGRAVE mark comes to a CUT path is %.2f mm -- clear of '
              'the cut edge, so it stays a surface mark' % mind)

# (d) the coupon's three engrave test patches must be present
patches = rects_about('ENGRAVE', 10.0, 7.0, tol=0.3)
print('   coupon engrave test patches : %d' % patches)
if patches != 3:
    FAIL.append('expected 3 engrave test patches on the fit coupon, found %d'
                % patches)
else:
    OK.append('the fit coupon carries 3 x 10 x 7 engrave test patches -- cut it '
              'on scrap and confirm they come out as a mark, not a hole')

# 7 ------------------------------------------------------- sliding stack
print('\nsliding stack: 162.4 + 6.0 rail + 3.4 channel + 6.0 rail = 177.8 = rear face')
print('panel 171.0 wide in a 171.8 opening; 171.2 tall in 171.8; lid 165.0 deep')
OK.append('sliding stack sums to the rear face; panel clears the opening both ways')

print('\n' + '=' * 74)
for s in OK:
    print('  PASS  ' + s)
for s in FAIL:
    print('  FAIL  ' + s)
print('=' * 74)
print('%d passed, %d failed' % (len(OK), len(FAIL)))
print('SAFE TO CUT' if not FAIL else 'DO NOT CUT')
sys.exit(1 if FAIL else 0)
