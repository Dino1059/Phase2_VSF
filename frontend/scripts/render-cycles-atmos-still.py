#!/usr/bin/env python3
"""Cycles delivery still: atmos.calm.webp (grill Q1=A teal+warm / Q2=C / Q3=B / Q4=C)."""
from __future__ import annotations

import math
import os
import subprocess
import sys

import bpy

OUT = "/tmp/dt_blender_pass"
WT = os.environ.get(
    "DT_WT",
    "/home/shayneeo/Downloads/Documents/Coding/AI_in_Action/P-086-wt-blender",
)
MAIN = os.environ.get(
    "DT_MAIN",
    "/home/shayneeo/Downloads/Documents/Coding/AI_in_Action/P-086",
)
PUBLIC = os.path.join(WT, "frontend/public/landing")
LOOP = os.path.join(MAIN, ".loop-state")
os.makedirs(OUT, exist_ok=True)
os.makedirs(PUBLIC, exist_ok=True)
os.makedirs(LOOP, exist_ok=True)

ATMOS_PNG = os.path.join(OUT, "atmos_cycles_v1.png")
ATMOS_LOOP = os.path.join(LOOP, "blender-atmos-cycles-v1.png")
ATMOS_WEBP = os.path.join(PUBLIC, "atmos.calm.webp")


def clear_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for block in (bpy.data.meshes, bpy.data.materials, bpy.data.lights, bpy.data.cameras, bpy.data.worlds):
        for b in list(block):
            block.remove(b)


def build_atmos() -> bpy.types.Object:
    """Calm undulating field — AC_* names only (no DT_* collision)."""
    bpy.ops.mesh.primitive_grid_add(x_subdivisions=96, y_subdivisions=96, size=18, location=(0, 0, 0))
    terrain = bpy.context.active_object
    terrain.name = "AC_Terrain"
    mesh = terrain.data
    for v in mesh.vertices:
        x, y = v.co.x, v.co.y
        h = 0.55 * math.sin(x * 0.55) * math.cos(y * 0.42)
        h += 0.28 * math.sin(x * 0.9 + 1.2) * math.sin(y * 0.7)
        h += 0.12 * math.sin((x + y) * 1.1)
        r = math.sqrt(x * x + y * y) / 9.0
        h *= max(0.0, 1.0 - r * 0.35)
        v.co.z = h
    mesh.update()
    mod = terrain.modifiers.new("AC_Subsurf", "SUBSURF")
    mod.levels = 1
    mod.render_levels = 2
    bpy.ops.object.shade_smooth()

    mat = bpy.data.materials.new("AC_TerrainMat")
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    n_out = nt.nodes.new("ShaderNodeOutputMaterial")
    n_out.location = (900, 0)
    n_bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    n_bsdf.location = (520, 0)
    n_mix = nt.nodes.new("ShaderNodeMixShader")
    n_mix.location = (720, 60)
    n_emit = nt.nodes.new("ShaderNodeEmission")
    n_emit.location = (520, 200)
    n_tex = nt.nodes.new("ShaderNodeTexCoord")
    n_tex.location = (-480, 80)
    n_map = nt.nodes.new("ShaderNodeMapping")
    n_map.location = (-300, 80)
    n_map.inputs["Scale"].default_value = (1.4, 1.0, 1.0)
    n_noise = nt.nodes.new("ShaderNodeTexNoise")
    n_noise.location = (-120, 160)
    n_noise.inputs["Scale"].default_value = 3.2
    n_noise.inputs["Detail"].default_value = 8.0
    n_noise.inputs["Roughness"].default_value = 0.55
    n_noise2 = nt.nodes.new("ShaderNodeTexNoise")
    n_noise2.location = (-120, -20)
    n_noise2.inputs["Scale"].default_value = 2.4
    n_noise2.inputs["Detail"].default_value = 6.0
    n_mask = nt.nodes.new("ShaderNodeValToRGB")
    n_mask.location = (80, 200)
    cr = n_mask.color_ramp
    cr.elements[0].position = 0.42
    cr.elements[0].color = (0, 0, 0, 1)
    cr.elements[1].position = 0.58
    cr.elements[1].color = (1, 1, 1, 1)
    n_pal = nt.nodes.new("ShaderNodeValToRGB")
    n_pal.location = (80, 0)
    p = n_pal.color_ramp
    p.elements[0].position = 0.0
    p.elements[0].color = (0.035, 0.055, 0.075, 1)
    el = p.elements.new(0.45)
    el.color = (0.06, 0.12, 0.14, 1)
    el2 = p.elements.new(0.62)
    el2.color = (0.02, 0.55, 0.52, 1)  # rich teal
    el3 = p.elements.new(0.82)
    el3.color = (0.85, 0.48, 0.22, 1)  # warm amber
    p.elements[1].position = 1.0
    p.elements[1].color = (0.95, 0.72, 0.35, 1)
    n_bump = nt.nodes.new("ShaderNodeBump")
    n_bump.location = (320, -140)
    n_bump.inputs["Strength"].default_value = 0.25

    nt.links.new(n_tex.outputs["Generated"], n_map.inputs["Vector"])
    nt.links.new(n_map.outputs["Vector"], n_noise.inputs["Vector"])
    nt.links.new(n_map.outputs["Vector"], n_noise2.inputs["Vector"])
    nt.links.new(n_noise2.outputs["Fac"], n_pal.inputs["Fac"])
    nt.links.new(n_noise.outputs["Fac"], n_mask.inputs["Fac"])
    nt.links.new(n_pal.outputs["Color"], n_bsdf.inputs["Base Color"])
    n_bsdf.inputs["Roughness"].default_value = 0.42
    try:
        n_bsdf.inputs["Specular IOR Level"].default_value = 0.35
    except Exception:
        pass
    nt.links.new(n_noise2.outputs["Fac"], n_bump.inputs["Height"])
    nt.links.new(n_bump.outputs["Normal"], n_bsdf.inputs["Normal"])
    n_emit.inputs["Color"].default_value = (0.05, 0.75, 0.68, 1)
    n_emit.inputs["Strength"].default_value = 0.35
    nt.links.new(n_mask.outputs["Color"], n_mix.inputs["Fac"])
    nt.links.new(n_bsdf.outputs["BSDF"], n_mix.inputs[1])
    nt.links.new(n_emit.outputs["Emission"], n_mix.inputs[2])
    nt.links.new(n_mix.outputs["Shader"], n_out.inputs["Surface"])
    terrain.data.materials.append(mat)

    cam_data = bpy.data.cameras.new("AC_CamData")
    cam = bpy.data.objects.new("AC_Cam", cam_data)
    bpy.context.scene.collection.objects.link(cam)
    cam.location = (0.2, -7.8, 1.65)
    cam.rotation_euler = (math.radians(78), 0, math.radians(2))
    cam_data.lens = 45
    cam_data.dof.use_dof = True
    cam_data.dof.focus_distance = 6.5
    cam_data.dof.aperture_fstop = 2.8
    bpy.context.scene.camera = cam

    def add_light(name: str, typ: str, loc, energy: float, color, size: float = 2.0):
        d = bpy.data.lights.new(name + "Data", typ)
        d.energy = energy
        d.color = color
        if typ == "AREA":
            d.size = size
        o = bpy.data.objects.new(name, d)
        o.location = loc
        bpy.context.scene.collection.objects.link(o)
        return o

    add_light("AC_Key", "AREA", (4.2, -3.5, 6.5), 280, (0.45, 0.95, 0.9), 5.0)
    add_light("AC_WarmFill", "AREA", (-4.5, -5.0, 3.8), 120, (1.0, 0.62, 0.35), 4.0)
    add_light("AC_Rim", "AREA", (-1.5, 4.0, 4.5), 90, (0.2, 0.7, 0.65), 3.5)
    add_light("AC_WarmAccent", "POINT", (1.2, -1.0, 2.2), 40, (1.0, 0.55, 0.25))

    world = bpy.data.worlds.new("AC_World")
    world.use_nodes = True
    wnt = world.node_tree
    wnt.nodes.clear()
    w_out = wnt.nodes.new("ShaderNodeOutputWorld")
    w_out.location = (400, 0)
    w_bg = wnt.nodes.new("ShaderNodeBackground")
    w_bg.location = (200, 0)
    w_bg.inputs["Color"].default_value = (0.012, 0.022, 0.035, 1)
    w_bg.inputs["Strength"].default_value = 0.45
    wnt.links.new(w_bg.outputs["Background"], w_out.inputs["Surface"])
    bpy.context.scene.world = world
    return cam


def configure_cycles() -> None:
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    vts = []
    try:
        vts = [
            i.identifier
            for i in scene.view_settings.bl_rna.properties["view_transform"].enum_items
        ]
    except Exception as exc:
        print("vt_enum", exc)
    print("AVAILABLE_VT", vts)
    # Q2: AgX lookdev → Cycles PBR Neutral final (enum_items often stub in headless)
    for cand in ("Khronos PBR Neutral", "Khronos Neutral", "AgX"):
        try:
            scene.view_settings.view_transform = cand
            print("SET_VT", cand, "->", scene.view_settings.view_transform)
            break
        except Exception as exc:
            print("vt_fail", cand, exc)
    scene.view_settings.exposure = -0.05
    scene.view_settings.gamma = 1.0
    try:
        scene.view_settings.look = "None"
    except Exception:
        pass

    c = scene.cycles
    c.samples = int(os.environ.get("DT_SAMPLES", "96"))
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
    scene.render.filepath = ATMOS_PNG


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
        print("ffmpeg_webp_fail", r.stderr[-500:], file=sys.stderr)
        raise SystemExit(r.returncode)
    print("WEBP", dst, os.path.getsize(dst))


def main() -> None:
    clear_scene()
    build_atmos()
    configure_cycles()
    scene = bpy.context.scene
    print(
        "RENDER_START",
        ATMOS_PNG,
        scene.view_settings.view_transform,
        scene.cycles.samples,
        scene.cycles.device,
    )
    bpy.ops.render.render(write_still=True)
    if not os.path.exists(ATMOS_PNG):
        raise FileNotFoundError(ATMOS_PNG)
    print("RENDER_DONE", os.path.getsize(ATMOS_PNG))
    subprocess.run(["cp", "-f", ATMOS_PNG, ATMOS_LOOP], check=True)
    # also keep a dated sample under loop-state
    subprocess.run(
        ["cp", "-f", ATMOS_PNG, os.path.join(LOOP, "blender-atmos-v4.png")],
        check=True,
    )
    encode_webp(ATMOS_PNG, ATMOS_WEBP)
    print("DONE_ATMOS", ATMOS_WEBP)


if __name__ == "__main__":
    main()
