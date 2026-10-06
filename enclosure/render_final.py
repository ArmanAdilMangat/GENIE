#!/usr/bin/env python3
"""Previews for both GENIE Rev J variants.

ONE colour convention everywhere, matching the DXF layers:
    RED   = CUT      -- the laser goes through
    BLUE  = ENGRAVE  -- surface mark only, never through
    GREY  = NOTES    -- title block, output OFF
"""
import math, os, sys
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as MPoly
import genie_case_final as G

CUTC, ENGC, NOTEC = '#c0392b', '#1f5fa8', '#8b8b8b'
COL = {G.CUT: CUTC, G.ENG: ENGC, G.NOTE: NOTEC}
LW = {G.CUT: 1.15, G.ENG: 0.55, G.NOTE: 0.45}


def paths(pr):
    if isinstance(pr, G.Circle):
        return [[(pr.c[0] + pr.r * math.cos(t), pr.c[1] + pr.r * math.sin(t))
                 for t in [i * 2 * math.pi / 72 for i in range(73)]]]
    return [G.flatten(pr)]


def build(tof_cut):
    G.CFG['TOF_CUT'] = tof_cut
    G.reset()
    G.build_front()
    G.build_side('03_LEFT', 'LEFT', True)
    G.build_side('04_RIGHT', 'RIGHT', False)
    G.build_top(); G.build_bottom(); G.build_back()
    G.build_strips(); G.build_tft_frame('09A_TFT_FRAME', G.CFG['TFT_BOARD_A'], 'TFT CLAMP FRAME A'); G.build_tft_frame('09B_TFT_FRAME', G.CFG['TFT_BOARD_B'], 'TFT CLAMP FRAME B'); G.build_coupon()
    G.nest(); G.build_notes()


def sheet_png(path, title, sub):
    fig, ax = plt.subplots(figsize=(11, 16.2), dpi=140)
    for _p, prims in G.placed() + [(None, G.NOTES_PRIMS)]:
        for pr in prims:
            for q in paths(pr):
                ax.plot([a[0] for a in q], [a[1] for a in q],
                        color=COL[pr.layer], lw=LW[pr.layer], solid_capstyle='round')
    ax.set_xlim(-10, 620); ax.set_ylim(-10, 925)
    ax.set_aspect('equal'); ax.axis('off')
    ax.set_title(title + '\n' + sub, fontsize=12.5, pad=12)
    fig.tight_layout(); fig.savefig(path, facecolor='#fff', bbox_inches='tight')
    plt.close(fig)


def nest_png(path, title, sub):
    fig, ax = plt.subplots(figsize=(13, 12.6), dpi=150)
    ax.add_patch(MPoly([(0, 0), (610, 0), (610, 600), (0, 600)], closed=True,
                       fc='#faf8f4', ec='#c9c2b4', lw=1.2, zorder=0))
    for _p, prims in G.placed():
        for pr in prims:
            for q in paths(pr):
                ax.plot([a[0] for a in q], [a[1] for a in q],
                        color=COL[pr.layer], lw=LW[pr.layer],
                        solid_capstyle='round', zorder=2)
    ax.set_xlim(-8, 618); ax.set_ylim(-8, 600)
    ax.set_aspect('equal'); ax.axis('off')
    ax.set_title(title + '\n' + sub, fontsize=13, pad=14)
    fig.tight_layout(); fig.savefig(path, facecolor='#fff', bbox_inches='tight')
    plt.close(fig)


# ---------------------------------------------------------------- isometric
C30, S30 = math.cos(math.radians(30)), math.sin(math.radians(30))
S, T = G.S, G.T
iso = lambda p: ((p[0] - p[1]) * C30, (p[0] + p[1]) * S30 + p[2])
tf_front = lambda u, v: (u, 0.0, v)
tf_left = lambda u, v: (0.0, S - u, v + T)
tf_right = lambda u, v: (S, u + T, v + T)
tf_top = lambda u, v: (u, v + T, S)
tf_bottom = lambda u, v: (u, v + T, 0.0)


def tf_back(dz):
    return lambda u, v: (u + 3.4, G.CHANNEL_A[0] + T, v + T + dz)


def draw_panel(ax, part, tf, face, alpha, z, engrave=False):
    out = next(pr for pr in part.prims if pr.layer == G.CUT)
    ax.add_patch(MPoly([iso(tf(*q)) for q in G.flatten(out)], closed=True,
                       fc=face, ec='none', alpha=alpha, zorder=z))
    for pr in part.prims:
        if pr.layer == G.NOTE or (pr.layer == G.ENG and not engrave):
            continue
        for p in paths(pr):
            pp = [iso(tf(*q)) for q in p]
            ax.plot([q[0] for q in pp], [q[1] for q in pp],
                    color=COL[pr.layer], lw=1.0 if pr.layer == G.CUT else 0.6,
                    alpha=1.0 if pr.layer == G.CUT else 0.8, zorder=z + 1,
                    solid_capstyle='round')


def rail(ax, a0, a1, side, z):
    x0 = T if side == 'L' else S - 2 * T
    x1, y0, y1 = x0 + T, a0 + T, a1 + T
    for f in ([(x0, y0, T), (x1, y0, T), (x1, y1, T), (x0, y1, T)],
              [(x0, y0, S - T), (x1, y0, S - T), (x1, y1, S - T), (x0, y1, S - T)],
              [(x0, y0, T), (x0, y0, S - T), (x0, y1, S - T), (x0, y1, T)],
              [(x1, y0, T), (x1, y0, S - T), (x1, y1, S - T), (x1, y1, T)]):
        ax.add_patch(MPoly([iso(p) for p in f], closed=True, fc='#3f7fb5',
                           ec='#245a86', lw=0.7, alpha=0.55, zorder=z))


def assembly_png(path, title):
    by = {p.key: p for p in G.PARTS}
    fig, ax = plt.subplots(figsize=(12, 11), dpi=150)
    draw_panel(ax, by['06_BOTTOM'], tf_bottom, '#dfe6ea', .55, 2)
    draw_panel(ax, by['03_LEFT'], tf_left, '#e6eef2', .40, 6, engrave=True)
    for a in (G.RAIL_FRONT_A, G.RAIL_REAR_A):
        rail(ax, a[0], a[1], 'L', 8); rail(ax, a[0], a[1], 'R', 8)
    draw_panel(ax, by['04_RIGHT'], tf_right, '#e6eef2', .40, 10)
    draw_panel(ax, by['02_BACK_SLIDER'], tf_back(232.0), '#cfe3f5', .75, 14, engrave=True)
    draw_panel(ax, by['05_TOP'], tf_top, '#e9edf0', .45, 16)
    draw_panel(ax, by['01_FRONT'], tf_front, '#eef2f5', .42, 20, engrave=True)
    ax.annotate('', xy=iso((S / 2, G.CHANNEL_A[0] + T, S + 198)),
                xytext=iso((S / 2, G.CHANNEL_A[0] + T, S - 26)),
                arrowprops=dict(arrowstyle='-|>', lw=2.4, color='#1f6fb2',
                                mutation_scale=22), zorder=30)
    px, py = iso((S / 2 - 30, G.CHANNEL_A[0] + T, S + 96))
    ax.text(px - 26, py, 'BACK PANEL\nSLIDES UP\nTO OPEN', color='#1f6fb2',
            fontsize=11.5, fontweight='bold', ha='right', va='center', zorder=30)
    qx, qy = iso((0, S, 40))
    ax.text(qx - 16, qy, 'guide rails\n2 per side, 6 mm strips\n3.4 mm channel',
            color='#245a86', fontsize=10, ha='right', va='center', zorder=30)
    ax.set_aspect('equal'); ax.axis('off')
    ax.set_title(title, fontsize=14, pad=10)
    ax.autoscale_view(); fig.tight_layout()
    fig.savefig(path, facecolor='#fff', bbox_inches='tight')
    plt.close(fig)


KEY = ('RED = CUT (laser goes through)     BLUE = ENGRAVE (surface mark only, '
       'NEVER a hole)     GREY = NOTES, output OFF')

for tof_cut, folder, stem, name in (
        (True, 'DESIGN_A_WITH_TOF_HOLES', 'GENIE_WITH_TOF', 'WITH ToF holes'),
        (False, 'DESIGN_B_NO_TOF', 'GENIE_NO_TOF', 'NO ToF at all')):
    build(tof_cut)
    os.makedirs(folder, exist_ok=True)
    tofline = ('4 open 25 x 10 ToF apertures, one per direction'
               if tof_cut else
               'NO ToF geometry anywhere - not cut, not engraved, not marked')
    sheet_png(os.path.join(folder, 'SHEET.png'),
              '%s.dxf  -  %s' % (stem, name), KEY + '\n' + tofline)
    nest_png(os.path.join(folder, 'NEST.png'),
             'GENIE Rev J  -  %s  -  flat nest, 3 mm clear acrylic, mm' % name,
             KEY + '\n' + tofline)
    assembly_png(os.path.join(folder, 'ASSEMBLY.png'),
                 'GENIE Rev J  -  %s  -  back panel withdrawn' % name)
    print('rendered', folder)
