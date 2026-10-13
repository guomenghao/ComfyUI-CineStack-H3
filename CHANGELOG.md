# Changelog

## 0.1.0 — 2026-10-13

Initial independent CineStack H3 release, derived from AIMixer Director commit
`8151b291fcacee5ddb70c6493eaed4f831bc6867`.

- Optional fixed `first_pass_seed` per segment, including zero and the full uint64 range.
- Seed persistence through all timeline modes, external groups and Director packs.
- `refine_only`: preflight selected first-pass caches; reject missing, mismatched or corrupt caches before sampling.
- Detailed cache mismatch diagnostics; inherited seed behavior and legacy cache layout preserved.
- `CineStackH3Director*` node IDs, `/cinestack/h3/*` routes and CineStack progress events.
- Legacy workflow/API migration with preserved widgets, seeds, graph IDs and links.
- Independent Registry metadata, manual publication workflow, CI and publishing guide.

Validation covers CPU control flow and browser UI fixtures. GPU model generation and
live ComfyUI integration still require release acceptance on a compatible NVIDIA host.
