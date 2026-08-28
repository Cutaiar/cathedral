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
import sys

import numpy as np
import sounddevice as sd
from pedalboard import Pedalboard, Reverb, Gain, HighpassFilter


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


def build_board():
    # Freeverb-style, cranked for a stone-cathedral tail.
    return Pedalboard([
        HighpassFilter(cutoff_frequency_hz=90.0),
        Reverb(
            room_size=0.98,
            damping=0.15,
            wet_level=0.55,
            dry_level=0.45,
            width=1.0,
            freeze_mode=0.0,
        ),
        Gain(gain_db=-2.0),
    ])


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--list", action="store_true", help="list audio devices and exit")
    p.add_argument("--input", default="BlackHole", help="input device name substring")
    p.add_argument("--output", default=None,
                   help="output device name substring (default: system default)")
    p.add_argument("--samplerate", type=int, default=48000)
    p.add_argument("--blocksize", type=int, default=1024,
                   help="smaller = less latency, more chance of xruns")
    p.add_argument("--channels", type=int, default=2)
    args = p.parse_args()

    if args.list:
        list_devices()
        return

    in_idx = find_device(args.input, "input")
    out_idx = find_device(args.output, "output") if args.output else None

    board = build_board()
    sr = args.samplerate

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
