# Meteor Scatter V2

Detect meteors using 6-meter radio waves in
the [live stream from Astronomiemuseum der Sternwarte Sonneberg ](https://www.twitch.tv/astronomiemuseum) or in WAV
files.

Old [version, repository and deprecated/long description](https://github.com/maxbundscherer/meteor-scatter).

## Examples

![](resources/beispielTwitch.png)
![](resources/beispielWav.png)

## Approach

![](resources/SystemMS.jpg)

## Instructions

### Install (macOS or newer linux)

- `python3.14 -m venv .venv`
- `source .venv/bin/activate`
- `pip install -r requirements.txt`

### Install (old Ubuntu)

- `python -m venv .venv`
- `source .venv/bin/activate`
- `pip install -r requirements_ubuntu.txt`

### Run (Detection)

- `source .venv/bin/activate`
- `./run_wav.sh` (offline demo) or `./run_twitch.sh` (live stream)

### Run (Analyze)

- `source .venv/bin/activate`
- `python meteor_analyse.py`

### Run (old Analyze)

- `old/MS.ipynb`
