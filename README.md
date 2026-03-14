# Beacon-Compatible Non-Mixing Selection Demo

<p align="center">
  <img src="Beacon-Compatible Non-Mixing Selection Pipeline Minimal Verifiable Reference Implementation.png" width="720">
</p>

This repository provides a **minimal, replay-verifiable demo implementation** of a **Beacon-compatible non-mixing selection mechanism**.
It is designed as a **demonstrator / certificate-chain integrity verifier / reproducibility support artifact**, **not** as a full production implementation.

In the Beacon architecture, the key design principle is **preserve-then-select** rather than weighted averaging by default.  
This demo illustrates a small, auditable selection pipeline aligned with that principle:

- a finite-window kernel over candidate streams
- a toy `R_skel + E_X` decomposition on positive log values
- `ratio_r = R_skel / (R_skel + E_X)`
- **non-mixing selection** of a single index `s_sel`
- outward rational rounding for `delta_pos`
- hash-chained certificates for replay and audit

## Related links

- **Project page:** [gd-attention](https://ghostdrifttheory.github.io/gd-attention/)
- **Preprint:** [Zenodo record 17472184](https://zenodo.org/records/17472184)
- **Organization:** [GhostDrift Mathematical Institute](https://ghostdriftresearch.com/)

## Positioning

This repository should be understood as:

- a **reference demonstrator** for a Beacon-compatible non-mixing selection flow
- a **minimal verifier-friendly artifact** for public explanation and replay
- a **supporting implementation layer**, not the full research or patent core

It is intentionally limited in scope.  
All constants and thresholds in this demo are **illustrative and demo-specific**, not a disclosure of a full adaptive or production parameterization.

The goal is to make the structure **publicly inspectable** without releasing the entire production or adaptive-core stack.

## What this demo shows

This demo exposes the following minimal pipeline:

1. maintain a finite-window kernel over a candidate score stream
2. compute a toy positive-log decomposition into `R_skel` and `E_X`
3. compute `ratio_r = R_skel / (R_skel + E_X)`
4. apply **non-mixing selection** to obtain a single `s_sel`
5. derive `delta_hat_pos` and outward-round it to `delta_pos`
6. emit **hash-chained certificates** for replay and audit

## What this demo does **not** claim

This repository does **not** provide:

- the full adaptive UWP core
- the full `delta_pos` generator used in a production stack
- a complete patent implementation
- a production-grade control system
- the entire optimization / safety / deployment layer

The kernel, decomposition, and lower-bound handling here are deliberately **minimal and demonstrative**.

## Quick start

```bash
python beacon_demo.py demo --out artifacts
python beacon_demo.py verify artifacts/certificates.jsonl
```

## Expected output

The demo produces replayable artifacts such as:

- `artifacts/certificates.jsonl`
- `artifacts/summary.json`

Each certificate contains a deliberately limited public field set aligned with the public write-up, including:

- `time`
- `X`, `tau`, `lambda_`, `Delta`
- `m_tau_Delta`
- `delta_hat_pos`, `delta_pos`
- `ratio_r`, `s_sel`
- `control_signal`
- `resource_cap`, `safety_margin`, `rounding_mode`
- `hash_prev`, `hash_curr`

## Repository structure

```text
.
├── beacon_demo.py
├── README.md
└── artifacts/
    ├── certificates.jsonl
    └── summary.json
```

## Why this repository exists

The purpose of this repository is **not** to present a complete closed-form implementation of the broader theory.  
Its purpose is narrower and more practical:

- to make a core **non-mixing selection idea** inspectable
- to provide a small **verification-oriented artifact**
- to support public explanation of Beacon-compatible selection logic
- to give an auditable example of certificate chaining and replay verification

## Suggested public description

A concise way to describe this repository publicly is:

> This repository provides a minimal demo implementation that illustrates a non-mixing selection mechanism compatible with the Beacon architecture. It is intended for certificate-chain integrity verification, demonstration, and reproducibility support, not as a full production implementation.

## Notes

- This demo is intentionally small.
- It should be presented as a **demo implementation / certificate-chain integrity verifier / demonstrator**.
- It should **not** be presented as the complete production core.

## Citation / reference context

If you refer to this repository in external communication, it is recommended to position it together with:

- the **project page** for the broader architectural context
- the **Zenodo preprint** for the public research record
- the **organization page** for institutional attribution

## Contact / organization

For research, technical collaboration, implementation discussions, or institutional inquiries:

**GhostDrift Mathematical Institute**  
[https://ghostdriftresearch.com/](https://ghostdriftresearch.com/)
