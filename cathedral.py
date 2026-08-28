"""Route system audio through a cathedral-sized reverb.

Setup:
  1. Install BlackHole (2ch) and create a Multi-Output Device in
     Audio MIDI Setup that combines BlackHole + your real speakers,
     OR just set macOS output to BlackHole and let this script
     play the wet signal to your speakers.
  2. Set macOS system output -> BlackHole 2ch.
  3. Run this script; pass --list to see device indices.
"""

import argparse
import random
import sys
from pathlib import Path

import numpy as np
import sounddevice as sd
from pedalboard import Pedalboard, Reverb, Gain, HighpassFilter, Convolution

IR_DIR = Path(__file__).resolve().parent / "irs"


def list_devices():
    print(sd.query_devices())


def find_device(name_substr, kind):
    name_substr = name_substr.lower()
    for i, d in enumerate(sd.query_devices()):
        if name_substr in d["name"].lower():
            if kind == "input" and d["max_input_channels"] > 0:
                return i
            if kind == "output" and d["max_output_channels"] > 0:
                return i
    raise RuntimeError(f"No {kind} device matching {name_substr!r}")


# Space presets. Each is a starting point; individual CLI flags override.
# room/damping/wet/dry/width map to pedalboard.Reverb; hpf is the low-cut
# before the reverb (keeps bass out of the tail so things don't turn to mud).
PRESETS = {
    "cathedral": dict(room=0.98, damping=0.15, wet=0.55, dry=0.45, width=1.0, hpf=90),
    "hall":      dict(room=0.85, damping=0.30, wet=0.40, dry=0.60, width=1.0, hpf=80),
    "chamber":   dict(room=0.60, damping=0.40, wet=0.35, dry=0.65, width=0.9, hpf=100),
    "plate":     dict(room=0.70, damping=0.50, wet=0.40, dry=0.60, width=1.0, hpf=120),
    "room":      dict(room=0.40, damping=0.50, wet=0.25, dry=0.75, width=0.8, hpf=100),
}


def build_board(p, ir_path=None, sample_rate=None):
    if ir_path is not None:
        # Convolution reverb: the IR (an audio recording of a real space's
        # response) *is* the space. Freeverb knobs don't apply; --wet is the
        # dry/wet mix passed straight to pedalboard.Convolution.
        return Pedalboard([
            HighpassFilter(cutoff_frequency_hz=p["hpf"]),
            Convolution(ir_path, mix=p["wet"], sample_rate=sample_rate),
            Gain(gain_db=-2.0),
        ])
    return Pedalboard([
        HighpassFilter(cutoff_frequency_hz=p["hpf"]),
        Reverb(
            room_size=p["room"],
            damping=p["damping"],
            wet_level=p["wet"],
            dry_level=p["dry"],
            width=p["width"],
            freeze_mode=0.0,
        ),
        Gain(gain_db=-2.0),
    ])


def format_presets():
    keys = ("room", "damping", "wet", "dry", "width", "hpf")
    name_w = max(len(n) for n in PRESETS)
    col_w = {k: max(len(k), max(len(f"{v[k]:g}") for v in PRESETS.values())) for k in keys}
    header = "  " + " " * name_w + "  " + "  ".join(f"{k:>{col_w[k]}}" for k in keys)
    rows = [
        "  " + f"{name:<{name_w}}" + "  " + "  ".join(f"{vals[k]:>{col_w[k]}g}" for k in keys)
        for name, vals in PRESETS.items()
    ]
    return "presets:\n" + header + "\n" + "\n".join(rows)


def main():
    p = argparse.ArgumentParser(
        description="Route system audio through a cathedral-sized reverb.",
        epilog=format_presets(),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--list", action="store_true", help="list audio devices and exit")
    p.add_argument("--input", default="BlackHole", help="input device name substring")
    p.add_argument("--output", default=None,
                   help="output device name substring (default: system default)")
    p.add_argument("--samplerate", type=int, default=48000)
    p.add_argument("--blocksize", type=int, default=1024,
                   help="smaller = less latency, more chance of xruns")
    p.add_argument("--channels", type=int, default=2)

    p.add_argument("--preset", choices=sorted(PRESETS), default="cathedral",
                   help="starting point for the reverb (default: cathedral)")
    p.add_argument("--room",    type=float, help="room size 0..1")
    p.add_argument("--damping", type=float, help="damping 0..1 (higher = darker/shorter)")
    p.add_argument("--wet",     type=float, help="wet mix 0..1")
    p.add_argument("--dry",     type=float, help="dry mix 0..1")
    p.add_argument("--width",   type=float, help="stereo width 0..1")
    p.add_argument("--hpf",     type=float, help="pre-reverb high-pass cutoff Hz")

    p.add_argument("--ir", metavar="PATH",
                   help="convolution reverb using an impulse response WAV "
                        "(overrides Freeverb; only --wet and --hpf apply). "
                        "Try IRs from https://www.openair.hosted.york.ac.uk/")
    p.add_argument("--random-ir", action="store_true",
                   help=f"pick a random *.wav from {IR_DIR}/ (searched recursively)")

    args = p.parse_args()

    if args.list:
        list_devices()
        return

    in_idx = find_device(args.input, "input")
    out_idx = find_device(args.output, "output") if args.output else None

    params = dict(PRESETS[args.preset])
    for k in ("room", "damping", "wet", "dry", "width", "hpf"):
        v = getattr(args, k)
        if v is not None:
            params[k] = v

    sr = args.samplerate

    ir_path = args.ir
    if args.random_ir:
        if not IR_DIR.exists():
            sys.exit(f"cathedral: no IR directory at {IR_DIR} — put some .wav files there first")
        wavs = sorted(IR_DIR.rglob("*.wav")) + sorted(IR_DIR.rglob("*.WAV"))
        if not wavs:
            sys.exit(f"cathedral: no .wav files under {IR_DIR}")
        ir_path = str(random.choice(wavs))

    board = build_board(params, ir_path=ir_path, sample_rate=sr)

    def callback(indata, outdata, frames, time_info, status):
        if status:
            print(status, file=sys.stderr)
        # pedalboard wants float32 (frames, channels)
        wet = board(indata, sample_rate=sr, reset=False)
        # ensure shape matches outdata
        if wet.shape != outdata.shape:
            wet = np.resize(wet, outdata.shape)
        outdata[:] = wet.astype(np.float32)

    print(f"input  = [{in_idx}] {sd.query_devices(in_idx)['name']}")
    print(f"output = " + (f"[{out_idx}] {sd.query_devices(out_idx)['name']}"
                          if out_idx is not None else "system default"))
    if ir_path:
        print(f"ir     = {ir_path}  wet={params['wet']}  hpf={params['hpf']}")
    else:
        print(f"preset = {args.preset}  " +
              "  ".join(f"{k}={params[k]}" for k in ("room", "damping", "wet", "dry", "width", "hpf")))
    print("Reverb is running. Ctrl+C to quit.")

    with sd.Stream(
        device=(in_idx, out_idx) if out_idx is not None else (in_idx, sd.default.device[1]),
        samplerate=sr,
        blocksize=args.blocksize,
        dtype="float32",
        channels=args.channels,
        callback=callback,
        latency="low",
    ):
        try:
            while True:
                sd.sleep(1000)
        except KeyboardInterrupt:
            print("\nbye.")


if __name__ == "__main__":
    main()
