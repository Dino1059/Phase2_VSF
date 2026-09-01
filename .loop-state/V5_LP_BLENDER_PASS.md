# V5 LP Blender Pass — Handoff SoT

**Branch:** `feat/lp-blender-best`  
**Worktree:** `../P-086-wt-blender`  
**Updated:** 2026-09-01 ~22:25 ICT  
**Ownership:** Blender-only (no LandingPage.tsx / CSS)  
**Status:** **DONE** — Cycles stills → webp committed/pushed

## Grill LOCKED

| Q | Lock |
|---|---|
| Q1=A | Teal/cyan data-trust accents + warm key (no purple neon) |
| Q2=C | AgX lookdev → **final Cycles + Khronos PBR Neutral** (v1 = AgX due to enum stub; script patched to force Khronos) |
| Q3=B | Rich saturation — fabric + lights clearly colored |
| Q4=C | **Cycles only** delivery stills |

## Color recipe

| Role | RGB | Notes |
|---|---|---|
| Fabric base | `(0.08, 0.22, 0.24)` | Teal-tinted graphite, rich |
| Filament / wire emission | `(0.10, 0.98, 0.92)` @ 3.2 | Cyan data filaments |
| Trusted plane glow | `(0.20, 0.90, 0.85)` @ 0.75 | Soft teal plane |
| Tele OK | teal metal + cyan emission | Instrument bars |
| Tele Bad | warm amber `(1.0, 0.58, 0.2)` | Warning, not purple |
| Key | warm `(1.0, 0.82, 0.68)` energy 780 | Studio key |
| Fill | cool `(0.55, 0.78, 0.88)` 160 | |
| Rim | teal `(0.35, 0.78, 0.72)` 420 | |
| Accent | cyan area 180 over tele grid | |
| World | dark teal BG + volume density ~0.006–0.012 | Soft HDRI-like |

**Avoid:** purple neon, cream/terracotta, flat clay, chrome overkill.

## Engine settings (delivery)

| Setting | Value |
|---|---|
| Script | `frontend/scripts/render-cycles-delivery-stills.py` |
| Engine | `CYCLES` (CPU this host — CUDA lib missing) |
| Samples | 48 · OIDN denoising |
| View transform | Prefer `Khronos PBR Neutral` (v1 = AgX; script force-sets Khronos next run) |
| Exposure | `-0.15` |
| Resolution | 1920×1080 PNG → webp q86 |

## Asset paths (final)

| Role | Path |
|---|---|
| Hero webp | `frontend/public/landing/hero.poster.webp` (~146 KiB) |
| Atmos webp | `frontend/public/landing/atmos.calm.webp` (~30 KiB) |
| Hero master | `.loop-state/blender-hero-cycles-v1.png` (~3.2 MB) |
| Atmos master | `.loop-state/blender-atmos-cycles-v1.png` (~2.7 MB) |

## Vision iterate (v1)

| Still | Verdict | Notes |
|---|---|---|
| Hero | **Y improved** | Teal fabric + cyan wire + amber tele; left/top negative space for VI |
| Atmos | **Y / mixed** | Teal present; muddy tan mix — optional v2 |

## Quality improved?

**Y** — vs prior grey clay posters: colored teal fabric, cyan filaments, warm amber data bars, Cycles masters.

## Deploy

No d086 / no t086 from this seat. Orchestrator merges.
