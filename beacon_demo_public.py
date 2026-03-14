from __future__ import annotations

import argparse
import hashlib
import json
import math
from dataclasses import asdict, dataclass
from decimal import Decimal, ROUND_FLOOR, getcontext
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

getcontext().prec = 50


@dataclass
class KernelConfig:
    X: float = 8.0
    tau: float = 2.5
    lambda_: float = 1.0
    Delta: float = 2.0
    dt: float = 1.0
    denom_cap: int = 128
    ratio_threshold: float = 0.55
    resource_cap: float = 1.0
    safety_margin: float = 0.10
    rounding_mode: str = "round_down_rational"
    abstain_token: str = "ABSTAIN"
    eta: float = 0.10


@dataclass
class Certificate:
    time: int
    X: str
    tau: str
    lambda_: str
    Delta: str
    m_tau_Delta: str
    delta_hat_pos: str
    delta_pos: str
    ratio_r: str
    s_sel: str
    control_signal: str
    resource_cap: str
    safety_margin: str
    rounding_mode: str
    hash_prev: str
    hash_curr: str


def to_decimal(x: Any) -> Decimal:
    if isinstance(x, Decimal):
        return x
    if isinstance(x, str):
        return Decimal(x)
    return Decimal(str(x))


def decimal_str(x: Decimal, places: int = 12) -> str:
    q = Decimal("1").scaleb(-places)
    return str(x.quantize(q).normalize())


def finite_window_kernel_weights(cfg: KernelConfig) -> List[Decimal]:
    steps = max(1, int(round(cfg.X / cfg.dt)))
    weights: List[Decimal] = []
    tau = max(cfg.tau, 1e-9)
    for i in range(steps + 1):
        t = Decimal(str(i * cfg.dt))
        exponent = -(to_decimal(cfg.lambda_) * t) / to_decimal(tau)
        w = exponent.exp()
        weights.append(w)
    total = sum(weights)
    return [w / total for w in weights]


def m_tau_delta(cfg: KernelConfig) -> Decimal:
    tau = max(cfg.tau, 1e-9)
    exponent = -(to_decimal(cfg.lambda_) * to_decimal(cfg.Delta)) / to_decimal(tau)
    return exponent.exp()


def causal_convolution(signal: Sequence[float], weights: Sequence[Decimal]) -> List[Decimal]:
    out: List[Decimal] = []
    for i in range(len(signal)):
        acc = Decimal("0")
        for lag, w in enumerate(weights):
            j = i - lag
            if j < 0:
                break
            acc += to_decimal(signal[j]) * w
        out.append(acc)
    return out


def round_down_rational(x: Decimal, denom_cap: int) -> Tuple[int, int, Decimal]:
    x = max(x, Decimal("0"))
    best_num = 0
    best_den = 1
    best_val = Decimal("0")
    for den in range(1, denom_cap + 1):
        num = int((x * den).to_integral_value(rounding=ROUND_FLOOR))
        val = Decimal(num) / Decimal(den)
        if val <= x and val >= best_val:
            best_num, best_den, best_val = num, den, val
    return best_num, best_den, best_val


def positive_log_decomposition(z: Decimal, eta: Decimal) -> Tuple[Decimal, Decimal, Decimal]:
    z = max(z, Decimal("1"))
    log_z = z.ln()
    if log_z <= 0:
        return Decimal("0"), Decimal("0"), Decimal("0")
    quanta = (log_z / eta).to_integral_value(rounding=ROUND_FLOOR)
    r_skel = quanta * eta
    e_x = log_z - r_skel
    denom = r_skel + e_x
    ratio = Decimal("0") if denom <= 0 else r_skel / denom
    return r_skel, e_x, ratio


def select_non_mixing(
    scores: Sequence[Decimal], ratios: Sequence[Decimal], threshold: Decimal, abstain_token: str
) -> str:
    eligible = [i for i, r in enumerate(ratios) if r >= threshold]
    if not eligible:
        return abstain_token
    best_idx = max(eligible, key=lambda i: (scores[i], ratios[i], -i))
    return str(best_idx)


def make_control_signal(selected: str, n_candidates: int, resource_cap: Decimal) -> str:
    if selected == "ABSTAIN":
        vec = [Decimal("0")] * n_candidates
    else:
        vec = [Decimal("0")] * n_candidates
        vec[int(selected)] = resource_cap
    return json.dumps([decimal_str(v, 6) for v in vec], separators=(",", ":"))


def canonical_hash(payload: Dict[str, Any]) -> str:
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def build_certificate(
    *,
    t: int,
    cfg: KernelConfig,
    delta_hat_pos: Decimal,
    delta_pos: Decimal,
    ratios: Sequence[Decimal],
    selected: str,
    scores: Sequence[Decimal],
    hash_prev: str,
) -> Certificate:
    max_ratio = max(ratios) if ratios else Decimal("0")
    control_signal = make_control_signal(selected, len(scores), to_decimal(cfg.resource_cap))
    payload = {
        "time": t,
        "X": decimal_str(to_decimal(cfg.X)),
        "tau": decimal_str(to_decimal(cfg.tau)),
        "lambda_": decimal_str(to_decimal(cfg.lambda_)),
        "Delta": decimal_str(to_decimal(cfg.Delta)),
        "m_tau_Delta": decimal_str(m_tau_delta(cfg)),
        "delta_hat_pos": decimal_str(delta_hat_pos),
        "delta_pos": decimal_str(delta_pos),
        "ratio_r": decimal_str(max_ratio),
        "s_sel": selected,
        "control_signal": control_signal,
        "resource_cap": decimal_str(to_decimal(cfg.resource_cap)),
        "safety_margin": decimal_str(to_decimal(cfg.safety_margin)),
        "rounding_mode": cfg.rounding_mode,
        "hash_prev": hash_prev,
    }
    hash_curr = canonical_hash(payload)
    return Certificate(hash_curr=hash_curr, **payload)


class BeaconCompatibleDemo:
    def __init__(self, cfg: KernelConfig):
        self.cfg = cfg
        self.weights = finite_window_kernel_weights(cfg)
        self.history: List[List[Decimal]] = []
        self.certificates: List[Certificate] = []

    def step(self, candidate_scores: Sequence[float]) -> Certificate:
        dec_scores = [to_decimal(x) for x in candidate_scores]
        self.history.append(dec_scores)
        n_candidates = len(dec_scores)
        phis: List[Decimal] = []
        z_values: List[Decimal] = []
        r_skel_values: List[Decimal] = []
        e_x_values: List[Decimal] = []
        ratios: List[Decimal] = []

        for idx in range(n_candidates):
            signal = [step[idx] for step in self.history]
            phi = causal_convolution([float(x) for x in signal], self.weights)[-1]
            phis.append(phi)
            z = Decimal("1") + max(phi, Decimal("0"))
            z_values.append(z)
            r_skel, e_x, ratio = positive_log_decomposition(z, to_decimal(self.cfg.eta))
            r_skel_values.append(r_skel)
            e_x_values.append(e_x)
            ratios.append(ratio)

        s_min = min(max(phi, Decimal("0")) for phi in phis)
        delta_hat = m_tau_delta(self.cfg) * s_min
        _, _, delta_pos = round_down_rational(delta_hat, self.cfg.denom_cap)
        selected = select_non_mixing(dec_scores, ratios, to_decimal(self.cfg.ratio_threshold), self.cfg.abstain_token)
        hash_prev = self.certificates[-1].hash_curr if self.certificates else "GENESIS"
        cert = build_certificate(
            t=len(self.history) - 1,
            cfg=self.cfg,
            delta_hat_pos=delta_hat,
            delta_pos=delta_pos,
            ratios=ratios,
            selected=selected,
            scores=dec_scores,
            hash_prev=hash_prev,
        )
        self.certificates.append(cert)
        return cert

    def run(self, stream: Iterable[Sequence[float]]) -> List[Certificate]:
        for candidate_scores in stream:
            self.step(candidate_scores)
        return self.certificates


def verify_certificate_chain(path: Path) -> bool:
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    prev = "GENESIS"
    for idx, record in enumerate(records):
        if record["hash_prev"] != prev:
            raise ValueError(f"Broken hash_prev at line {idx + 1}")
        payload = dict(record)
        hash_curr = payload.pop("hash_curr")
        expect = canonical_hash(payload)
        if hash_curr != expect:
            raise ValueError(f"Broken hash_curr at line {idx + 1}")
        prev = hash_curr
    return True


def toy_stream() -> List[List[float]]:
    return [
        [0.2, 0.1, 0.4, 0.15],
        [0.6, 0.3, 0.5, 0.2],
        [0.7, 0.2, 0.4, 0.1],
        [0.9, 0.1, 0.45, 0.2],
        [1.0, 0.2, 0.35, 0.15],
        [0.95, 0.25, 0.30, 0.10],
    ]


def write_chain(path: Path, certificates: Sequence[Certificate]) -> None:
    lines = [json.dumps(asdict(c), ensure_ascii=True, separators=(",", ":")) for c in certificates]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Beacon-compatible non-mixing selection demo")
    sub = p.add_subparsers(dest="cmd", required=True)

    demo = sub.add_parser("demo", help="run the toy demo")
    demo.add_argument("--out", type=Path, default=Path("artifacts"))

    verify = sub.add_parser("verify", help="verify a certificate chain")
    verify.add_argument("path", type=Path)
    return p


def main() -> None:
    args = build_argparser().parse_args()
    if args.cmd == "demo":
        out_dir: Path = args.out
        out_dir.mkdir(parents=True, exist_ok=True)
        cfg = KernelConfig()
        engine = BeaconCompatibleDemo(cfg)
        certificates = engine.run(toy_stream())
        chain_path = out_dir / "certificates.jsonl"
        write_chain(chain_path, certificates)
        summary = {
            "selected_sequence": [c.s_sel for c in certificates],
            "max_ratio_sequence": [c.ratio_r for c in certificates],
            "delta_pos_sequence": [c.delta_pos for c in certificates],
            "chain_path": str(chain_path),
        }
        (out_dir / "summary.json").write_text(
            json.dumps(summary, indent=2, ensure_ascii=True), encoding="utf-8"
        )
        print(json.dumps(summary, indent=2, ensure_ascii=True))
        return

    if args.cmd == "verify":
        ok = verify_certificate_chain(args.path)
        print("OK" if ok else "NG")
        return


if __name__ == "__main__":
    main()
