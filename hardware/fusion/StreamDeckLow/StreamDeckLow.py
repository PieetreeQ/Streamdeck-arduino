"""DIY Stream Deck - low-profile enclosures (RGB LED in the lid, 2 mm chamfer) + 15° stand.

Builds in a new document:
  1. Low_Mega      - body 23/29 mm + lid 5 mm  (total 28/34 mm), Arduino Mega 2560
  2. Low_ProMicro  - body 12/16 mm + lid 5 mm  (total 17/21 mm), Arduino Pro Micro
  3. Stand 15°     - fits both
and exports print-ready STL files to a "streamdeck_stl" folder on the Desktop.

Run: Shift+S (Scripts and Add-Ins) -> "+" next to My Scripts -> select the StreamDeckLow folder -> Run.
"""
import adsk.core, adsk.fusion, math, os, struct, ctypes, traceback

MM = 0.1
W, D, WALL, FLOOR = 120, 85, 3, 2
LID_T, PLATE_T, SW_HOLE, PITCH, COLS, ROWS = 5, 1.5, 14.1, 19.05, 4, 3
POST_D, POST_HOLE, LID_HOLE, CB_D, CB_H = 7, 2.6, 3.4, 6.2, 2
LED_HOLE, LED_POCKET, LED_SKIN = 5.2, 10.6, 1.2
EDGE = 2.0
DECK_FEET = [(12, 12), (W - 12, 12), (12, D - 12), (W - 12, D - 12)]

# Arduino Mega
MEGA_W = 53.34
MEGA_HOLES = [(13.97, 2.54), (15.24, 50.8), (66.04, 7.62), (66.04, 35.56), (90.17, 50.8), (96.52, 2.54)]
SO_H, SO_D, SO_HOLE, PCB_T = 3, 6, 2.6, 1.6
MEGA_X = WALL + 6.5 - 1.5
MEGA_Y = D - WALL - 3 - POST_D / 2 - 2 - MEGA_W
USB_Y, USB_W, USB_H = 38.1, 15, 14

# Pro Micro (18 x 33 mm board, USB-C through the back wall, right side)
PM_W, PM_L = 18.5, 33.5
PM_X = W - WALL - PM_W - 0.2
PM_Y = D - WALL - PM_L
PM_RAIL_H = 2.5
PM_USB_W, PM_USB_Z0, PM_USB_Z1 = 12, FLOOR + 0.2, FLOOR + 7.2

POSTS_STD = [(WALL + 3, WALL + 3), (W - WALL - 3, WALL + 3), (WALL + 3, D - WALL - 3), (W - WALL - 3, D - WALL - 3)]
# Pro Micro version: right back post moved left so it does not hit the board
POSTS_PM = [(WALL + 3, WALL + 3), (W - WALL - 3, WALL + 3), (WALL + 3, D - WALL - 3), (94, D - WALL - 3)]

# stand
ST_ANG = math.radians(15); ST_H0 = 8; LIP_T, LIP_H = 4, 6; ST_LEN = D + LIP_T + 2

NB = adsk.fusion.FeatureOperations.NewBodyFeatureOperation
JOIN = adsk.fusion.FeatureOperations.JoinFeatureOperation
CUT = adsk.fusion.FeatureOperations.CutFeatureOperation


def P(x, y, z=0): return adsk.core.Point3D.create(x * MM, y * MM, z * MM)
def V(v): return adsk.core.ValueInput.createByReal(v * MM)


def plane(comp, base, off):
    if off == 0: return base
    pi = comp.constructionPlanes.createInput(); pi.setByOffset(base, V(off))
    return comp.constructionPlanes.add(pi)


def plane_at_y(comp, y):
    if y == 0: return comp.xZConstructionPlane
    pl = plane(comp, comp.xZConstructionPlane, y)
    if abs(pl.geometry.origin.y - y * MM) > 1e-6:
        pl.deleteMe(); pl = plane(comp, comp.xZConstructionPlane, -y)
    return pl


def poly_sketch(comp, pl, pts):
    sk = comp.sketches.add(pl)
    sp = [sk.modelToSketchSpace(P(*p)) for p in pts]
    for i in range(len(sp)): sk.sketchCurves.sketchLines.addByTwoPoints(sp[i], sp[(i + 1) % len(sp)])
    return sk


def rect_sketch(comp, pl, rects):
    sk = comp.sketches.add(pl)
    for (x0, y0, x1, y1) in rects: sk.sketchCurves.sketchLines.addTwoPointRectangle(P(x0, y0), P(x1, y1))
    return sk


def circ_sketch(comp, pl, pts, d):
    sk = comp.sketches.add(pl)
    for (x, y) in pts: sk.sketchCurves.sketchCircles.addByCenterRadius(P(x, y), d / 2 * MM)
    return sk


def profiles(sk):
    oc = adsk.core.ObjectCollection.create()
    for p in sk.profiles: oc.add(p)
    return oc


def extrude(comp, prof, dist, op, body=None, symmetric=False):
    ei = comp.features.extrudeFeatures.createInput(prof, op)
    if symmetric: ei.setSymmetricExtent(V(dist), True)
    else: ei.setDistanceExtent(False, V(dist))
    if body is not None and op != NB: ei.participantBodies = [body]
    return comp.features.extrudeFeatures.add(ei)


def rot_x(a):
    m = adsk.core.Matrix3D.create(); m.setToRotation(a, adsk.core.Vector3D.create(1, 0, 0), adsk.core.Point3D.create(0, 0, 0)); return m


def trans(x, y, z):
    m = adsk.core.Matrix3D.create(); m.translation = adsk.core.Vector3D.create(x * MM, y * MM, z * MM); return m


def move_m(comp, bodies, m):
    oc = adsk.core.ObjectCollection.create()
    for b in bodies: oc.add(b)
    mi = comp.features.moveFeatures.createInput2(oc); mi.defineAsFreeMove(m)
    comp.features.moveFeatures.add(mi)


def chamfer(comp, edges, dist=EDGE):
    try:
        ci = comp.features.chamferFeatures.createInput2()
        ci.chamferEdgeSets.addEqualDistanceChamferEdgeSet(edges, V(dist), True)
    except Exception:
        ci = comp.features.chamferFeatures.createInput(edges, True); ci.setToEqualDistance(V(dist))
    return comp.features.chamferFeatures.add(ci)


def near(a, vals, tol=0.001): return any(abs(a - v * MM) < tol for v in vals)


def outer_edges(body, xs, ys, zplane):
    oc = adsk.core.ObjectCollection.create()
    for e in body.edges:
        if not isinstance(e.geometry, adsk.core.Line3D): continue
        a, b = e.startVertex.geometry, e.endVertex.geometry
        vertical = abs(a.x - b.x) < 1e-6 and abs(a.y - b.y) < 1e-6 and abs(a.z - b.z) > 1e-4
        if vertical and near(a.x, xs) and near(a.y, ys): oc.add(e); continue
        if near(a.z, [zplane]) and near(b.z, [zplane]):
            if (near(a.x, xs) and abs(a.x - b.x) < 1e-6) or (near(a.y, ys) and abs(a.y - b.y) < 1e-6): oc.add(e)
    return oc


# ---------------------------------------------------------------- BODY
def build_korpus(comp, name, hf, hb, board):
    comp.name = name
    posts = POSTS_PM if board == 'pm' else POSTS_STD
    yz, xy = comp.yZConstructionPlane, comp.xYConstructionPlane
    body = extrude(comp, poly_sketch(comp, yz, [(0, 0, 0), (0, D, 0), (0, D, hb), (0, 0, hf)]).profiles.item(0), W, NB).bodies.item(0)
    body.name = name
    sk = poly_sketch(comp, plane(comp, yz, WALL), [(WALL, WALL, FLOOR), (WALL, D - WALL, FLOOR), (WALL, D - WALL, hb + 20), (WALL, WALL, hf + 20)])
    extrude(comp, sk.profiles.item(0), W - 2 * WALL, CUT, body)
    extrude(comp, profiles(circ_sketch(comp, xy, posts, POST_D)), hb + 1, JOIN, body)
    s = (hb - hf) / D
    if board == 'mega':
        holes = [(MEGA_X + hx, MEGA_Y + hy) for hx, hy in MEGA_HOLES]
        extrude(comp, profiles(circ_sketch(comp, xy, holes, SO_D)), FLOOR + SO_H, JOIN, body)
    else:
        # Pro Micro cradle: front wall + left rail (the right side is the case wall)
        fl = plane(comp, xy, FLOOR)
        rails = [(PM_X - 1.2, PM_Y - 1.2, PM_X + PM_W, PM_Y), (PM_X - 1.2, PM_Y, PM_X, D - WALL)]
        extrude(comp, profiles(rect_sketch(comp, fl, rails)), PM_RAIL_H, JOIN, body)
    # cut the top with the sloped plane
    sk = poly_sketch(comp, plane(comp, yz, -1), [(-1, -1, hf - s), (-1, D + 1, hf + s * (D + 1)), (-1, D + 1, hb + 60), (-1, -1, hb + 60)])
    extrude(comp, sk.profiles.item(0), W + 2, CUT, body)
    extrude(comp, profiles(circ_sketch(comp, plane(comp, xy, FLOOR), posts, POST_HOLE)), hb, CUT, body)
    if board == 'mega':
        extrude(comp, profiles(circ_sketch(comp, plane(comp, xy, 1), holes, SO_HOLE)), FLOOR + SO_H, CUT, body)
        uz = FLOOR + SO_H + PCB_T - 1.5; uy = MEGA_Y + USB_Y - USB_W / 2
        sk = poly_sketch(comp, plane(comp, yz, -1), [(-1, uy, uz), (-1, uy + USB_W, uz), (-1, uy + USB_W, uz + USB_H), (-1, uy, uz + USB_H)])
        extrude(comp, sk.profiles.item(0), WALL + 2, CUT, body)
    else:
        cx = PM_X + PM_W / 2
        sk = comp.sketches.add(plane_at_y(comp, D))
        a = sk.modelToSketchSpace(P(cx - PM_USB_W / 2, D, PM_USB_Z0))
        b = sk.modelToSketchSpace(P(cx + PM_USB_W / 2, D, PM_USB_Z1))
        sk.sketchCurves.sketchLines.addTwoPointRectangle(a, b)
        extrude(comp, sk.profiles.item(0), 2 * WALL + 2, CUT, body, symmetric=True)
    extrude(comp, profiles(circ_sketch(comp, xy, DECK_FEET, 10.5)), 1, CUT, body)
    chamfer(comp, outer_edges(body, [0, W], [0, D], 0))
    return body


# ---------------------------------------------------------------- LID (with LED)
def build_pokrywa(comp, name, hf, hb, board):
    comp.name = name
    posts = POSTS_PM if board == 'pm' else POSTS_STD
    ang = math.atan((hb - hf) / D); lid_l = D / math.cos(ang)
    xy = comp.xYConstructionPlane
    body = extrude(comp, rect_sketch(comp, xy, [(0, 0, W, lid_l)]).profiles.item(0), LID_T, NB).bodies.item(0)
    body.name = name
    gx, gy = COLS * PITCH, ROWS * PITCH
    ox, oy = (W - gx) / 2, (lid_l - gy) / 2
    extrude(comp, rect_sketch(comp, xy, [(ox - 1, oy - 1, ox + gx + 1, oy + gy + 1)]).profiles.item(0), LID_T - PLATE_T, CUT, body)
    rects = []
    for c in range(COLS):
        for r in range(ROWS):
            cx, cy = ox + c * PITCH + PITCH / 2, oy + r * PITCH + PITCH / 2
            rects.append((cx - SW_HOLE / 2, cy - SW_HOLE / 2, cx + SW_HOLE / 2, cy + SW_HOLE / 2))
    extrude(comp, profiles(rect_sketch(comp, xy, rects)), LID_T, CUT, body)
    lx = ox + gx + (W - ox - gx) / 2
    extrude(comp, circ_sketch(comp, xy, [(lx, lid_l / 2)], LED_HOLE).profiles.item(0), LID_T, CUT, body)
    extrude(comp, circ_sketch(comp, xy, [(lx, lid_l / 2)], LED_POCKET).profiles.item(0), LID_T - LED_SKIN, CUT, body)
    lp = [(px, py / math.cos(ang)) for px, py in posts]
    extrude(comp, profiles(circ_sketch(comp, xy, lp, LID_HOLE)), LID_T, CUT, body)
    extrude(comp, profiles(circ_sketch(comp, plane(comp, xy, LID_T - CB_H), lp, CB_D)), CB_H + 0.1, CUT, body)
    chamfer(comp, outer_edges(body, [0, W], [0, lid_l], LID_T))
    return body, ang


# ---------------------------------------------------------------- STAND
def top_pt(s): return (s * math.cos(ST_ANG), ST_H0 + s * math.sin(ST_ANG))


def build_podstawka(comp):
    comp.name = 'Stand_15deg'
    yz, xy = comp.yZConstructionPlane, comp.xYConstructionPlane
    yb, zb = top_pt(ST_LEN)
    body = extrude(comp, poly_sketch(comp, yz, [(0, 0, 0), (0, yb, 0), (0, yb, zb), (0, 0, ST_H0)]).profiles.item(0), W, NB).bodies.item(0)
    body.name = 'Stand_15deg'
    y1, z1 = top_pt(LIP_T)
    nx, nz = -math.sin(ST_ANG), math.cos(ST_ANG)
    F = (y1 + nx * LIP_H, z1 + nz * LIP_H); G = (nx * LIP_H, ST_H0 + nz * LIP_H)
    extrude(comp, poly_sketch(comp, yz, [(0, 0, ST_H0 - 0.5), (0, y1, z1 - 0.5), (0, F[0], F[1]), (0, G[0], G[1])]).profiles.item(0), W, JOIN, body)
    # chamfers: bottom + back corners + back top edge (2 mm), lip (1 mm); each step separately
    def edges_where(pred):
        oc = adsk.core.ObjectCollection.create()
        for e in body.edges:
            if not isinstance(e.geometry, adsk.core.Line3D): continue
            a, b = e.startVertex.geometry, e.endVertex.geometry
            if pred(a, b): oc.add(e)
        return oc
    steps = [
        (lambda a, b: (abs(a.x - b.x) < 1e-6 and abs(a.y - b.y) < 1e-6 and abs(a.z - b.z) > 1e-4 and near(a.x, [0, W]) and near(a.y, [yb]))
                      or (abs(a.z) < 1e-6 and abs(b.z) < 1e-6), EDGE),
        (lambda a, b: abs(a.y - b.y) < 1e-6 and abs(a.z - b.z) < 1e-6 and abs(a.y - yb * MM) < 0.03 and abs(a.z - zb * MM) < 0.03, EDGE),
        (lambda a, b: abs(a.y - b.y) < 1e-6 and abs(a.z - b.z) < 1e-6 and any(abs(a.y - p[0] * MM) < 0.03 and abs(a.z - p[1] * MM) < 0.03 for p in (F, G)), 1.0),
    ]
    for pred, dist in steps:
        try:
            oc = edges_where(pred)
            if oc.count: chamfer(comp, oc, dist)
        except Exception:
            pass
    top_face = None
    for f in body.faces:
        n = f.geometry.normal if isinstance(f.geometry, adsk.core.Plane) else None
        if n and abs(n.z - math.cos(ST_ANG)) < 1e-3 and abs(n.y + math.sin(ST_ANG)) < 1e-3:
            if top_face is None or f.area > top_face.area: top_face = f
    sk = comp.sketches.add(top_face)
    for (fx, fy) in DECK_FEET:
        yy, zz = top_pt(LIP_T + fy)
        sk.sketchCurves.sketchCircles.addByCenterRadius(sk.modelToSketchSpace(P(fx, yy, zz)), 6.0 * MM)
    ei = comp.features.extrudeFeatures.createInput(profiles(sk), CUT)
    ei.setOneSideExtent(adsk.fusion.DistanceExtentDefinition.create(V(1.5)), adsk.fusion.ExtentDirections.NegativeExtentDirection)
    ei.participantBodies = [body]
    comp.features.extrudeFeatures.add(ei)
    extrude(comp, profiles(circ_sketch(comp, xy, [(14, 14), (W - 14, 14), (14, yb - 14), (W - 14, yb - 14)], 10.5)), 1, CUT, body)
    return body


# ---------------------------------------------------------------- STL export
def desktop():
    try:
        buf = ctypes.create_unicode_buffer(260)
        ctypes.windll.shell32.SHGetFolderPathW(None, 0x10, None, 0, buf)
        if buf.value: return buf.value
    except Exception: pass
    return os.path.join(os.path.expanduser('~'), 'Desktop')


def mesh_tris(body):
    mc = body.meshManager.createMeshCalculator()
    mc.setQuality(adsk.fusion.TriangleMeshQualityOptions.VeryHighQualityTriangleMesh)
    m = mc.calculate(); c = m.nodeCoordinatesAsDouble; idx = m.nodeIndices
    pts = [(c[i] * 10, c[i + 1] * 10, c[i + 2] * 10) for i in range(0, len(c), 3)]
    return [(pts[idx[i]], pts[idx[i + 1]], pts[idx[i + 2]]) for i in range(0, len(idx), 3)]


def flip(tris): return [tuple((p[0], -p[1], -p[2]) for p in t) for t in tris]


def to_bed(tris):
    mn = [min(p[k] for t in tris for p in t) for k in range(3)]
    return [tuple(tuple(p[k] - mn[k] for k in range(3)) for p in t) for t in tris]


def write_stl(path, tris):
    with open(path, 'wb') as f:
        f.write(b'streamdeck'.ljust(80, b' ')); f.write(struct.pack('<I', len(tris)))
        for a, b, c in tris:
            u = [b[i] - a[i] for i in range(3)]; v = [c[i] - a[i] for i in range(3)]
            n = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0]); l = math.sqrt(sum(x * x for x in n)) or 1
            f.write(struct.pack('<12fH', n[0] / l, n[1] / l, n[2] / l, *a, *b, *c, 0))


def run(_context: str):
    app = adsk.core.Application.get()
    ui = app.userInterface
    try:
        app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
        design = adsk.fusion.Design.cast(app.activeProduct)
        design.designType = adsk.fusion.DesignTypes.ParametricDesignType
        root = design.rootComponent
        I = adsk.core.Matrix3D.create()
        out = os.path.join(desktop(), 'streamdeck_stl'); os.makedirs(out, exist_ok=True)
        built = []
        versions = [('Mega', 23, 29, 'mega', 0), ('ProMicro', 12, 16, 'pm', -(D + 40))]
        for label, hf, hb, board, dy in versions:
            ck = root.occurrences.addNewComponent(I).component
            bk = build_korpus(ck, 'Body_low_' + label, hf, hb, board)
            cp = root.occurrences.addNewComponent(I).component
            bp, ang = build_pokrywa(cp, 'Lid_low_' + label, hf, hb, board)
            write_stl(os.path.join(out, 'case_body_' + label.lower() + '.stl'), to_bed(mesh_tris(bk)))
            write_stl(os.path.join(out, 'case_lid_' + label.lower() + '.stl'), to_bed(flip(mesh_tris(bp))))
            # preview: lid placed on the body
            mp = rot_x(ang); mp.transformBy(trans(0, 0, hf))
            if dy: mp.transformBy(trans(0, dy, 0))
            move_m(cp, [bp], mp)
            if dy: move_m(ck, [bk], trans(0, dy, 0))
            built += [ck, cp]
        cs = root.occurrences.addNewComponent(I).component
        bs = build_podstawka(cs)
        write_stl(os.path.join(out, 'stand_15deg.stl'), to_bed(mesh_tris(bs)))
        move_m(cs, [bs], trans(W + 30, 0, 0))
        built.append(cs)
        if app.preferences.generalPreferences.defaultModelingOrientation == adsk.core.DefaultModelingOrientations.YUpModelingOrientation:
            for comp in built: move_m(comp, list(comp.bRepBodies), rot_x(-math.pi / 2))
        app.activeViewport.fit()
        ui.messageBox('Done.\n\nLow Mega case (28/34 mm), low Pro Micro case (17/21 mm) and 15° stand.\n'
                      'STL files: Desktop / streamdeck_stl\n\nSave the document: Ctrl+S.')
    except Exception:
        ui.messageBox('Error:\n' + traceback.format_exc())
