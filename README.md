# cathedral

Real-time reverb for your macOS system audio. Play anything — Spotify, YouTube,
a video call — and hear it as if it's coming out of a stone cathedral.

Reads from a [BlackHole](https://existential.audio/blackhole/) loopback input,
runs the signal through [pedalboard](https://github.com/spotify/pedalboard)'s
Freeverb tuned for a long tail, writes to your speakers.

## Install

```bash
brew install blackhole-2ch
git clone https://github.com/Cutaiar/cathedral.git
cd cathedral
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

Optional but recommended: [`loopback/audio-route`](https://github.com/Cutaiar/loopback)
to switch macOS input/output devices to BlackHole and back with one command.

## Use

```bash
audio-route on                                   # loopback: route system audio into BlackHole
python cathedral.py --output "MacBook Pro Speakers"
# play anything, Ctrl+C to stop
audio-route off                                  # restore your normal devices
```

Without `audio-route`, do it by hand in **System Settings → Sound**: set output
to BlackHole 2ch (or a Multi-Output Device that includes it), then run
`python cathedral.py --output <your speakers>`.

## Presets and knobs

```bash
python cathedral.py --preset hall
python cathedral.py --preset cathedral --wet 0.7 --damping 0.05
```

`python cathedral.py --help` prints the full preset table. Any individual
`--room`, `--damping`, `--wet`, `--dry`, `--width`, `--hpf` overrides the
preset value.

## Troubleshooting

- **`input overflow`** — callback isn't keeping up. Raise `--blocksize` to 2048.
- **No sound at all** — you've routed output to bare BlackHole but nothing is
  playing it back. Either use a Multi-Output Device (Audio MIDI Setup →
  + → Create Multi-Output Device, tick BlackHole + your speakers) as your
  system output, or make sure cathedral is running with `--output` pointed at
  real speakers.
- **Choppy / clicky** — sample-rate mismatch. Check BlackHole's format in
  Audio MIDI Setup; either set it to 48000 Hz or pass `--samplerate 44100`.

## Ideas

Convolution reverb using real impulse responses from [OpenAIR](https://www.openair.hosted.york.ac.uk/)
(York Minster, Hamilton Mausoleum) is the biggest sonic upgrade over Freeverb.
Live keyboard control of the knobs would make it feel like an instrument.
