#!/usr/bin/env python3
"""Boîtier SENTINEL-X — modèle 3D paramétrique (CadQuery) → STEP/STL pour Fusion 360 et la K2 Plus.

    fablab/.venv/bin/python fablab/boitier.py            # génère fablab/export/*.step, *.stl, *.svg
    fablab/.venv/bin/python fablab/boitier.py --pack 118 62   # pack myDiL mesuré : longueur largeur

Trois pièces : BASE (bac + plots du pack + cheminées de vissage), COUVERCLE (avec logement de la plaque
gravée 80×50 et aérations) et GABARIT (plaque fine avec les découpes de la face avant, pour tester les
cotes en 15 min d'impression). Toutes les cotes sont en millimètres et dans la section PARAMÈTRES.
Importer les .step dans Fusion 360 (Insérer → Insérer un fichier CAO) pour la finition et les rendus.
"""
import argparse
import math
from pathlib import Path

import cadquery as cq

# ------------------------------------------------------------------ PARAMÈTRES
P = dict(
    inner_L=140.0, inner_W=95.0, inner_H=55.0,  # intérieur du bac
    wall=1.2, floor=1.2, corner_r=4.0,          # parois (consigne myDiL : 1,2 mm max), fond, arrondi vertical
    clear=0.3,                                  # jeu couvercle / bac
    # pack myDiL (ESP + 2 breadboards) : encombrement et entraxe des 4 trous de fixation (À MESURER)
    pack_L=115.0, pack_W=60.0, pack_hole_dx=105.0, pack_hole_dy=50.0, pack_post_h=4.0,
    # face avant (paroi +Y) : positions x (0 = milieu), z (0 = fond intérieur)
    oled_x=-42.0, oled_z=36.0, oled_w=24.0, oled_h=13.0,
    led_x=-22.0, led_z=36.0, led_d=5.2,
    pir_x=5.0, pir_z=32.0, pir_d=23.5,
    buz_x=34.0, buz_z=36.0, buz_hole_d=2.2, buz_pitch=4.0,
    mq2_x=56.0, mq2_z=32.0, mq2_slot_w=10.0, mq2_slot_h=1.6, mq2_slots=5, mq2_pitch=3.4,
    # paroi gauche (−X) : fentes du DHT22 ; paroi arrière (−Y) : micro-USB et passe-câble 7,5 V
    dht_y=20.0, dht_z=32.0, dht_slot_w=14.0, dht_slot_h=1.6, dht_slots=6, dht_pitch=3.2,
    usb_x=-30.0, usb_z=10.0, usb_w=12.0, usb_h=8.0,
    gland_x=45.0, gland_z=18.0, gland_d=6.5,
    # couvercle
    lid_t=2.0, lid_lip_h=3.0, lid_vent_n=8, lid_vent_w=22.0, lid_vent_h=1.6,
    plate_L=80.6, plate_W=50.6, plate_depth=1.0,   # logement de la plaque gravée (plexi 3 mm, dépasse de 2 mm)
    screw_d=2.6, screw_clear_d=3.4, post_sq=6.0,   # vis M3 autotaraudeuses dans les cheminées d'angle
)


def through_box(w, h, x, z, y_center, depth):
    """Pavé traversant une paroi (axe Y), pour les fenêtres rectangulaires."""
    return cq.Workplane("XY").box(w, depth, h).translate((x, y_center, z))


def through_cyl(d, x, z, y_center, depth):
    """Cylindre d'axe Y traversant une paroi, pour les trous ronds."""
    return cq.Workplane("XY").circle(d / 2).extrude(depth / 2, both=True).rotate((0, 0, 0), (1, 0, 0), 90).translate((x, y_center, z))


def through_cyl_x(d, y, z, x_center, depth):
    """Cylindre d'axe X traversant une paroi latérale."""
    return cq.Workplane("XY").circle(d / 2).extrude(depth / 2, both=True).rotate((0, 0, 0), (0, 1, 0), 90).translate((x_center, y, z))


def make_base(p):
    L, W, H, w, f = p["inner_L"], p["inner_W"], p["inner_H"], p["wall"], p["floor"]
    oL, oW, oH = L + 2 * w, W + 2 * w, H + f
    base = cq.Workplane("XY").box(oL, oW, oH, centered=(True, True, False)).edges("|Z").fillet(p["corner_r"])
    base = base.faces(">Z").shell(-w)                       # bac ouvert, parois d'épaisseur wall, fond = wall
    if f != w:                                               # épaisseur du fond distincte
        base = base.union(cq.Workplane("XY").box(L, W, f, centered=(True, True, False)))
    yF, yB, xL = W / 2 + w / 2, -(W / 2 + w / 2), -(L / 2 + w / 2)   # centres des parois avant, arrière, gauche
    cut = w * 3
    # --- face avant ---
    base = base.cut(through_box(p["oled_w"], p["oled_h"], p["oled_x"], p["oled_z"] + f, yF, cut))
    base = base.cut(through_cyl(p["led_d"], p["led_x"], p["led_z"] + f, yF, cut))
    base = base.cut(through_cyl(p["pir_d"], p["pir_x"], p["pir_z"] + f, yF, cut))
    base = base.cut(through_cyl(p["buz_hole_d"], p["buz_x"], p["buz_z"] + f, yF, cut))
    for k in range(6):                                       # grille hexagonale du buzzer
        a = math.radians(60 * k)
        base = base.cut(through_cyl(p["buz_hole_d"], p["buz_x"] + p["buz_pitch"] * math.cos(a), p["buz_z"] + f + p["buz_pitch"] * math.sin(a), yF, cut))
    for k in range(p["mq2_slots"]):                          # aération du MQ-2
        z = p["mq2_z"] + f + (k - (p["mq2_slots"] - 1) / 2) * p["mq2_pitch"]
        base = base.cut(through_box(p["mq2_slot_w"], p["mq2_slot_h"], p["mq2_x"], z, yF, cut))
    # --- paroi gauche : fentes DHT22 ---
    for k in range(p["dht_slots"]):
        z = p["dht_z"] + f + (k - (p["dht_slots"] - 1) / 2) * p["dht_pitch"]
        base = base.cut(cq.Workplane("XY").box(cut, p["dht_slot_w"], p["dht_slot_h"]).translate((xL, p["dht_y"], z)))
    # --- paroi arrière : micro-USB et passe-câble ---
    base = base.cut(through_box(p["usb_w"], p["usb_h"], p["usb_x"], p["usb_z"] + f, yB, cut))
    base = base.cut(through_cyl(p["gland_d"], p["gland_x"], p["gland_z"] + f, yB, cut))
    # --- plots du pack myDiL ---
    for sx in (-1, 1):
        for sy in (-1, 1):
            post = cq.Workplane("XY").circle(3.0).extrude(p["pack_post_h"]).faces(">Z").workplane().hole(2.4)
            base = base.union(post.translate((sx * p["pack_hole_dx"] / 2, sy * p["pack_hole_dy"] / 2, f)))
    # --- cheminées de vissage du couvercle, dans les angles ---
    s = p["post_sq"]
    for sx in (-1, 1):
        for sy in (-1, 1):
            x, y = sx * (L / 2 - s / 2), sy * (W / 2 - s / 2)
            post = cq.Workplane("XY").box(s, s, H, centered=(True, True, False)).translate((x, y, f))
            base = base.union(post)
            base = base.cut(cq.Workplane("XY").circle(p["screw_d"] / 2).extrude(12).translate((x, y, f + H - 12)))
    return base


def make_lid(p):
    L, W, w, t = p["inner_L"], p["inner_W"], p["wall"], p["lid_t"]
    oL, oW = L + 2 * w, W + 2 * w
    lid = cq.Workplane("XY").box(oL, oW, t, centered=(True, True, False)).edges("|Z").fillet(p["corner_r"])
    # lèvre de centrage sous le couvercle (entre dans le bac avec le jeu)
    c = p["clear"]
    lip = (cq.Workplane("XY").rect(L - 2 * c, W - 2 * c).rect(L - 2 * c - 2 * w, W - 2 * c - 2 * w)
           .extrude(-p["lid_lip_h"]))
    # la lèvre évite les cheminées d'angle
    s = p["post_sq"] + 2 * c
    for sx in (-1, 1):
        for sy in (-1, 1):
            lip = lip.cut(cq.Workplane("XY").box(s, s, p["lid_lip_h"] * 2).translate((sx * (L / 2 - s / 2 + c), sy * (W / 2 - s / 2 + c), -p["lid_lip_h"] / 2)))
    lid = lid.union(lip)
    # trous de vis
    for sx in (-1, 1):
        for sy in (-1, 1):
            x, y = sx * (L / 2 - p["post_sq"] / 2), sy * (W / 2 - p["post_sq"] / 2)
            lid = lid.cut(cq.Workplane("XY").circle(p["screw_clear_d"] / 2).extrude(t * 3, both=True).translate((x, y, 0)))
    # logement de la plaque gravée (avant du couvercle)
    pocket = cq.Workplane("XY").box(p["plate_L"], p["plate_W"], p["plate_depth"], centered=(True, True, False)).translate((-20, 14, t - p["plate_depth"]))
    lid = lid.cut(pocket)
    # aérations (arrière du couvercle)
    for k in range(p["lid_vent_n"]):
        y = -W / 2 + 10 + k * 3.2
        lid = lid.cut(cq.Workplane("XY").box(p["lid_vent_w"], p["lid_vent_h"], t * 3).translate((40, y, 0)))
    return lid


def make_gabarit(p):
    """Plaque 2 mm reprenant toutes les découpes de la face avant : test d'ajustement rapide."""
    L, H, f = p["inner_L"], p["inner_H"], 0.0
    g = cq.Workplane("XY").box(L + 2 * p["wall"], 2.0, H).translate((0, 0, H / 2))
    cut = 6.0
    g = g.cut(through_box(p["oled_w"], p["oled_h"], p["oled_x"], p["oled_z"], 0, cut))
    g = g.cut(through_cyl(p["led_d"], p["led_x"], p["led_z"], 0, cut))
    g = g.cut(through_cyl(p["pir_d"], p["pir_x"], p["pir_z"], 0, cut))
    g = g.cut(through_cyl(p["buz_hole_d"], p["buz_x"], p["buz_z"], 0, cut))
    for k in range(6):
        a = math.radians(60 * k)
        g = g.cut(through_cyl(p["buz_hole_d"], p["buz_x"] + p["buz_pitch"] * math.cos(a), p["buz_z"] + p["buz_pitch"] * math.sin(a), 0, cut))
    for k in range(p["mq2_slots"]):
        z = p["mq2_z"] + (k - (p["mq2_slots"] - 1) / 2) * p["mq2_pitch"]
        g = g.cut(through_box(p["mq2_slot_w"], p["mq2_slot_h"], p["mq2_x"], z, 0, cut))
    return g


def export(name, shape, out: Path, views=True):
    cq.exporters.export(shape, str(out / f"{name}.step"))
    cq.exporters.export(shape, str(out / f"{name}.stl"), tolerance=0.05, angularTolerance=0.1)
    if views:
        cq.exporters.export(shape, str(out / f"{name}.svg"),
                            opt={"width": 900, "height": 600, "marginLeft": 20, "marginTop": 20,
                                 "projectionDir": (1.2, -1.6, 1.0), "showAxes": False, "strokeWidth": 0.4,
                                 "showHidden": False})
    bb = shape.val().BoundingBox()
    print(f"{name:10s} {bb.xlen:6.1f} × {bb.ylen:6.1f} × {bb.zlen:5.1f} mm  volume {shape.val().Volume()/1000:6.1f} cm³")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pack", nargs=2, type=float, metavar=("L", "W"), help="encombrement mesuré du pack myDiL")
    ap.add_argument("--holes", nargs=2, type=float, metavar=("DX", "DY"), help="entraxe mesuré des trous du pack")
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent / "export"))
    a = ap.parse_args()
    if a.pack: P["pack_L"], P["pack_W"] = a.pack
    if a.holes: P["pack_hole_dx"], P["pack_hole_dy"] = a.holes
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    base, lid, gab = make_base(P), make_lid(P), make_gabarit(P)
    export("base", base, out)
    export("couvercle", lid, out)
    export("gabarit-face", gab, out)
    # vue d'ensemble : couvercle posé 25 mm au-dessus du bac
    asm = cq.Workplane("XY").add(base.val()).add(lid.val().translate((0, 0, P["inner_H"] + P["floor"] + 25)))
    cq.exporters.export(asm, str(out / "ensemble.svg"),
                        opt={"width": 1000, "height": 700, "marginLeft": 20, "marginTop": 20,
                             "projectionDir": (1.2, -1.6, 1.0), "showAxes": False, "strokeWidth": 0.4, "showHidden": False})
    print("exports dans", out)


if __name__ == "__main__":
    main()
