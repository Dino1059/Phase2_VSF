#!/usr/bin/env python3
"""Cycles delivery stills for DataTrust LP (grill locks 1A/2C/3B/4C).

Q1=A teal/cyan + warm key · Q2=C Khronos PBR Neutral finals · Q3=B rich sat · Q4=C Cycles only

  blender -b -P frontend/scripts/render-cycles-delivery-stills.py
"""
from __future__ import annotations

import math
import os
import subprocess
import sys

import bpy
from mathutils import Vector, noise

WT = os.environ.get(
    "DT_WT",
    os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..")),
)
PUBLIC = os.path.join(WT, "frontend", "public", "landing")
LOOP = os.path.join(WT, ".loop-state")
OUT = os.environ.get("DT_OUT", "/tmp/dt_blender_pass")
SAMPLES = int(os.environ.get("DT_SAMPLES", "64"))
GRID_N = 36

os.makedirs(PUBLIC, exist_ok=True)
os.makedirs(LOOP, exist_ok=True)
os.makedirs(OUT, exist_ok=True)

# Color recipe (locked)
FABRIC = (0.08, 0.22, 0.24, 1.0)
FILAMENT = (0.10, 0.98, 0.92, 1.0)
PLANE_GLOW = (0.20, 0.90, 0.85, 1.0)
WARM_KEY = (1.0, 0.82, 0.68)
COOL_FILL = (0.55, 0.78, 0.88)
TEAL_RIM = (0.35, 0.78, 0.72)
ACCENT = (0.25, 0.95, 0.88)


def clear_scene() -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)


def set_view_transform(scene: bpy.types.Scene) -> str:
    # Enum probe can return stub ['NONE'] in some headless contexts — force-assign.
    for cand in ("Khronos PBR Neutral", "AgX", "Filmic"):
        try:
            scene.view_settings.view_transform = cand
            print("SET_VT", cand, "actual", scene.view_settings.view_transform)
            return scene.view_settings.view_transform
        except Exception as exc:
            print("vt_fail", cand, exc)
    return scene.view_settings.view_transform


def configure_cycles(scene: bpy.types.Scene) -> None:
    scene.render.engine = "CYCLES"
    set_view_transform(scene)
    scene.view_settings.exposure = -0.15
    scene.view_settings.gamma = 1.0
    try:
        scene.view_settings.look = "None"
    except Exception:
        pass
    c = scene.cycles
    c.samples = SAMPLES
    c.use_denoising = True
    try:
        c.denoiser = "OPENIMAGEDENOISE"
    except Exception:
        pass
    try:
        prefs = bpy.context.preferences.addons["cycles"].preferences
        for dtype in ("CUDA", "OPTIX", "HIP", "ONEAPI", "METAL"):
            try:
                prefs.compute_device_type = dtype
                break
            except Exception:
                continue
        for d in prefs.devices:
            d.use = True
        scene.cycles.device = "GPU"
        print("DEVICE GPU", [(d.name, d.type, d.use) for d in prefs.devices])
    except Exception as exc:
        scene.cycles.device = "CPU"
        print("DEVICE CPU", exc)
    scene.render.resolution_x = 1920
    scene.render.resolution_y = 1080
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.film_transparent = False


def setup_world(scene: bpy.types.Scene) -> None:
    w = bpy.data.worlds.new("DT_World")
    scene.world = w
    w.use_nodes = True
    n, l = w.node_tree.nodes, w.node_tree.links
    n.clear()
    out = n.new("ShaderNodeOutputWorld")
    bg = n.new("ShaderNodeBackground")
    bg.inputs["Color"].default_value = (0.015, 0.025, 0.03, 1.0)
    bg.inputs["Strength"].default_value = 0.45
    bg2 = n.new("ShaderNodeBackground")
    bg2.inputs["Color"].default_value = (0.05, 0.12, 0.13, 1.0)
    bg2.inputs["Strength"].default_value = 0.6
    mix = n.new("ShaderNodeMixShader")
    mix.inputs["Fac"].default_value = 0.28
    l.new(bg.outputs["Background"], mix.inputs[1])
    l.new(bg2.outputs["Background"], mix.inputs[2])
    l.new(mix.outputs["Shader"], out.inputs["Surface"])
    vol = n.new("ShaderNodeVolumePrincipled")
    vol.inputs["Density"].default_value = 0.006
    vol.inputs["Color"].default_value = (0.08, 0.14, 0.16, 1.0)
    l.new(vol.outputs["Volume"], out.inputs["Volume"])


def add_light(name: str, energy: float, color, size: float, loc, rot) -> None:
    ld = bpy.data.lights.new(name, "AREA")
    ld.energy = energy
    ld.color = color
    ld.size = size
    o = bpy.data.objects.new(name, ld)
    bpy.context.collection.objects.link(o)
    o.location = loc
    o.rotation_euler = rot


def setup_camera(scene: bpy.types.Scene) -> None:
    cam_data = bpy.data.cameras.new("DT_Cam")
    cam = bpy.data.objects.new("DT_Cam", cam_data)
    bpy.context.collection.objects.link(cam)
    scene.camera = cam
    # brand-safe negative space left/top
    cam.location = (0.2, -6.6, 2.7)
    cam.rotation_euler = (math.radians(66), 0.0, math.radians(2))
    cam_data.lens = 38


def make_fabric_mat() -> bpy.types.Material:
    mat = bpy.data.materials.new("DT_FabricMat")
    mat.use_nodes = True
    n, l = mat.node_tree.nodes, mat.node_tree.links
    n.clear()
    out = n.new("ShaderNodeOutputMaterial")
    p = n.new("ShaderNodeBsdfPrincipled")
    p.inputs["Base Color"].default_value = FABRIC
    p.inputs["Roughness"].default_value = 0.45
    if "Specular IOR Level" in p.inputs:
        p.inputs["Specular IOR Level"].default_value = 0.45
    for key, val in [
        ("Sheen Weight", 0.42),
        ("Sheen Roughness", 0.5),
        ("Sheen Tint", (0.35, 0.85, 0.82, 1.0)),
        ("Subsurface Weight", 0.12),
    ]:
        if key in p.inputs:
            try:
                p.inputs[key].default_value = val
            except Exception:
                pass
    noise_n = n.new("ShaderNodeTexNoise")
    noise_n.inputs["Scale"].default_value = 18.0
    mapr = n.new("ShaderNodeMapRange")
    mapr.inputs["From Min"].default_value = 0.2
    mapr.inputs["From Max"].default_value = 0.8
    mapr.inputs["To Min"].default_value = 0.28
    mapr.inputs["To Max"].default_value = 0.58
    l.new(noise_n.outputs["Fac"], mapr.inputs["Value"])
    l.new(mapr.outputs["Result"], p.inputs["Roughness"])
    wire = n.new("ShaderNodeWireframe")
    wire.inputs[0].default_value = 0.009
    emis = n.new("ShaderNodeEmission")
    emis.inputs["Color"].default_value = FILAMENT
    emis.inputs["Strength"].default_value = 3.2
    mix = n.new("ShaderNodeMixShader")
    l.new(wire.outputs["Fac"], mix.inputs["Fac"])
    l.new(p.outputs["BSDF"], mix.inputs[1])
    l.new(emis.outputs["Emission"], mix.inputs[2])
    l.new(mix.outputs["Shader"], out.inputs["Surface"])
    return mat


def make_plane_mat() -> bpy.types.Material:
    mat = bpy.data.materials.new("DT_PlaneMat")
    mat.use_nodes = True
    n, l = mat.node_tree.nodes, mat.node_tree.links
    n.clear()
    out = n.new("ShaderNodeOutputMaterial")
    p = n.new("ShaderNodeBsdfPrincipled")
    p.inputs["Base Color"].default_value = (0.10, 0.28, 0.30, 1.0)
    p.inputs["Roughness"].default_value = 0.16
    if "Metallic" in p.inputs:
        p.inputs["Metallic"].default_value = 0.2
    if "Transmission Weight" in p.inputs:
        p.inputs["Transmission Weight"].default_value = 0.35
    emis = n.new("ShaderNodeEmission")
    emis.inputs["Color"].default_value = PLANE_GLOW
    emis.inputs["Strength"].default_value = 0.75
    add = n.new("ShaderNodeAddShader")
    l.new(p.outputs["BSDF"], add.inputs[0])
    l.new(emis.outputs["Emission"], add.inputs[1])
    l.new(add.outputs["Shader"], out.inputs["Surface"])
    return mat


def create_fabric(mat: bpy.types.Material) -> bpy.types.Object:
    import bmesh

    mesh = bpy.data.meshes.new("DT_FabricMesh")
    obj = bpy.data.objects.new("DT_Fabric", mesh)
    bpy.context.collection.objects.link(obj)
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=GRID_N, y_segments=GRID_N, size=8.0)
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
    # settled plane with residual micro-warp (hero poster = trusted end-state)
    for v in mesh.vertices:
        co = v.co.copy()
        n1 = noise.noise(Vector((co.x * 0.55, co.y * 0.55, 0.2)))
        n2 = noise.noise(Vector((co.x * 1.1 + 3.1, co.y * 0.9 - 1.7, 1.4)))
        v.co = Vector((co.x + n1 * 0.08, co.y + n2 * 0.08, co.z + n1 * 0.18 + n2 * 0.12))
    mesh.update()
    obj.data.materials.append(mat)
    obj.rotation_euler = (math.radians(-8), math.radians(6), math.radians(12))
    return obj


def create_plane(mat: bpy.types.Material) -> bpy.types.Object:
    bpy.ops.mesh.primitive_plane_add(size=8.2, location=(0, 0, -0.02))
    plane = bpy.context.active_object
    plane.name = "DT_TrustedPlane"
    plane.data.materials.append(mat)
    plane.rotation_euler = (math.radians(-8), math.radians(6), math.radians(12))
    return plane


def create_tele_bars() -> None:
    ok = bpy.data.materials.new("DT_TeleOK")
    ok.use_nodes = True
    n, l = ok.node_tree.nodes, ok.node_tree.links
    n.clear()
    out = n.new("ShaderNodeOutputMaterial")
    p = n.new("ShaderNodeBsdfPrincipled")
    p.inputs["Base Color"].default_value = (0.12, 0.62, 0.58, 1.0)
    p.inputs["Metallic"].default_value = 0.88
    p.inputs["Roughness"].default_value = 0.26
    emis = n.new("ShaderNodeEmission")
    emis.inputs["Color"].default_value = FILAMENT
    emis.inputs["Strength"].default_value = 1.4
    add = n.new("ShaderNodeAddShader")
    l.new(p.outputs["BSDF"], add.inputs[0])
    l.new(emis.outputs["Emission"], add.inputs[1])
    l.new(add.outputs["Shader"], out.inputs["Surface"])

    bad = bpy.data.materials.new("DT_TeleBad")
    bad.use_nodes = True
    n, l = bad.node_tree.nodes, bad.node_tree.links
    n.clear()
    out = n.new("ShaderNodeOutputMaterial")
    p = n.new("ShaderNodeBsdfPrincipled")
    p.inputs["Base Color"].default_value = (0.62, 0.32, 0.10, 1.0)
    p.inputs["Metallic"].default_value = 0.72
    p.inputs["Roughness"].default_value = 0.34
    emis = n.new("ShaderNodeEmission")
    emis.inputs["Color"].default_value = (1.0, 0.58, 0.2, 1.0)
    emis.inputs["Strength"].default_value = 1.0
    add = n.new("ShaderNodeAddShader")
    l.new(p.outputs["BSDF"], add.inputs[0])
    l.new(emis.outputs["Emission"], add.inputs[1])
    l.new(add.outputs["Shader"], out.inputs["Surface"])

    import random

    rng = random.Random(42)
    for ix in range(8):
        for iy in range(6):
            h = 0.15 + rng.random() * 0.45
            bpy.ops.mesh.primitive_cube_add(
                size=1,
                location=(-1.6 + ix * 0.45, -1.0 + iy * 0.4, h / 2 + 0.05),
            )
            bar = bpy.context.active_object
            bar.name = f"DT_Tele_{ix}_{iy}"
            bar.scale = (0.12, 0.12, h)
            bar.data.materials.append(ok if rng.random() > 0.18 else bad)


def encode_webp(src: str, dst: str) -> None:
    r = subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            src,
            "-frames:v",
            "1",
            "-c:v",
            "libwebp",
            "-quality",
            "86",
            "-vf",
            "scale=1920:-1",
            dst,
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        print(r.stderr[-800:], file=sys.stderr)
        raise SystemExit(r.returncode)
    print("WEBP", dst, os.path.getsize(dst))


def render_still(path: str) -> None:
    scene = bpy.context.scene
    scene.render.filepath = path
    print("RENDER_START", path, scene.view_settings.view_transform, scene.cycles.samples)
    bpy.ops.render.render(write_still=True)
    print("RENDER_DONE", path, os.path.getsize(path) if os.path.exists(path) else 0)


def main() -> None:
    clear_scene()
    scene = bpy.context.scene
    configure_cycles(scene)
    setup_world(scene)
    setup_camera(scene)
    add_light("DT_Key", 780, WARM_KEY, 9.5, (3.6, -4.2, 7.8), (math.radians(50), 0, math.radians(22)))
    add_light("DT_Fill", 160, COOL_FILL, 12.0, (-2.8, -6.2, 4.2), (math.radians(62), 0, math.radians(-18)))
    add_light("DT_Rim", 420, TEAL_RIM, 6.0, (-3.8, 3.2, 5.2), (math.radians(48), 0, math.radians(-35)))
    add_light("DT_Accent", 180, ACCENT, 2.2, (0.0, -0.2, 3.8), (math.radians(90), 0, 0))

    fab_mat = make_fabric_mat()
    plane_mat = make_plane_mat()
    create_fabric(fab_mat)
    create_plane(plane_mat)
    create_tele_bars()

    hero_png = os.path.join(OUT, "hero_cycles_v1.png")
    render_still(hero_png)
    subprocess.run(["cp", "-f", hero_png, os.path.join(LOOP, "blender-hero-cycles-v1.png")], check=True)
    encode_webp(hero_png, os.path.join(PUBLIC, "hero.poster.webp"))

    # atmos: pull camera back, denser calm field, hide tele bars
    for o in list(bpy.data.objects):
        if o.name.startswith("DT_Tele_"):
            o.hide_render = True
    cam = bpy.data.objects["DT_Cam"]
    cam.location = (-0.4, -8.2, 3.4)
    cam.rotation_euler = (math.radians(62), 0.0, math.radians(-6))
    cam.data.lens = 32
    if scene.world and scene.world.use_nodes:
        for node in scene.world.node_tree.nodes:
            if "Density" in getattr(node, "inputs", {}):
                node.inputs["Density"].default_value = 0.012
    atmos_png = os.path.join(OUT, "atmos_cycles_v1.png")
    render_still(atmos_png)
    subprocess.run(["cp", "-f", atmos_png, os.path.join(LOOP, "blender-atmos-cycles-v1.png")], check=True)
    encode_webp(atmos_png, os.path.join(PUBLIC, "atmos.calm.webp"))
    print("DONE_CYCLES_DELIVERY")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("FAILED", exc, file=sys.stderr)
        raise
