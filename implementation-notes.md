# Implementation notes

## 2026-08-15 — Upload session and dataset profiling

- Upload declarations now use the stable message ID `upload:{dataset_key}` and session `dataset:{dataset_key}`. Re-uploading the same logical dataset replaces the existing declaration instead of creating another chat row.
- Selecting an uploaded dataset runs the real profiling endpoint with a 50,000-row sample before the pipeline bootstrap starts.
- The chat stream reports profiling start, completion, and API failure; no profile/demo fallback was added.
- Verification: backend Python syntax check and frontend TypeScript/build pass.
