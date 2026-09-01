#!/usr/bin/env python3
"""Cycles delivery still: hero.poster.webp (grill 1A/2C/3B/4C)."""
from __future__ import annotations

import os
import subprocess
import sys

import bpy

OUT = "/tmp/dt_blender_pass"
WT = os.environ.get(
    "DT_WT",
    "/home/shayneeo/Downloads/Documents/Coding/AI_in_Action/P-086-wt-blender",
)
PUBLIC = os.path.join(WT, "frontend/public/landing")
LOOP = os.path.join(WT, ".loop-state")
os.makedirs(OUT, exist_ok=True)
os.makedirs(PUBLIC, exist_ok=True)
os.makedirs(LOOP, exist_ok=True)

HERO_PNG = os.path.join(OUT, "hero_cycles_v1.png")
HERO_LOOP = os.path.join(LOOP, "blender-hero-cycles-v1.png")
HERO_WEBP = os.path.join(PUBLIC, "hero.poster.webp")


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
    for cand in ("Khronos PBR Neutral", "Khronos Neutral", "AgX"):
        if cand in vts or not vts:
            try:
                scene.view_settings.view_transform = cand
                print("SET_VT", cand)
                break
            except Exception as exc:
                print("vt_fail", cand, exc)
    scene.view_settings.exposure = -0.15
    scene.view_settings.gamma = 1.0
    try:
        scene.view_settings.look = "None"
    except Exception:
        pass

    c = scene.cycles
    c.samples = int(os.environ.get("DT_SAMPLES", "64"))
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
    scene.render.filepath = HERO_PNG


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
    configure_cycles()
    scene = bpy.context.scene
    print(
        "RENDER_START",
        HERO_PNG,
        scene.view_settings.view_transform,
        scene.cycles.samples,
        scene.cycles.device,
    )
    bpy.ops.render.render(write_still=True)
    if not os.path.exists(HERO_PNG):
        raise FileNotFoundError(HERO_PNG)
    print("RENDER_DONE", os.path.getsize(HERO_PNG))
    subprocess.run(["cp", "-f", HERO_PNG, HERO_LOOP], check=True)
    encode_webp(HERO_PNG, HERO_WEBP)
    print("DONE_HERO")


if __name__ == "__main__":
    main()
