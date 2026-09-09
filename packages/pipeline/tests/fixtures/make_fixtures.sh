#!/bin/sh
# Regenerates the synthetic test fixtures. Ground truth is in the filenames
# and asserted in the tests; do not edit the outputs by hand.
set -e
cd "$(dirname "$0")"
FF=${FFMPEG:-ffmpeg}
SZ=320x568; R=30

# Three shots, hard cuts at exactly 1.0s and 3.0s, total 4.5s.
$FF -v error -y \
  -f lavfi -t 1.0 -i "testsrc2=s=$SZ:r=$R" \
  -f lavfi -t 2.0 -i "smptebars=s=$SZ:r=$R" \
  -f lavfi -t 1.5 -i "rgbtestsrc=s=$SZ:r=$R" \
  -filter_complex "[0:v][1:v][2:v]concat=n=3:v=1:a=0[v]" \
  -map "[v]" -pix_fmt yuv420p three_shots_at_1.0_3.0.mp4

# One continuous shot, no audio track at all.
$FF -v error -y -f lavfi -t 3.0 -i "testsrc2=s=$SZ:r=$R" \
  -pix_fmt yuv420p silent_no_audio_track.mp4

# One continuous shot, with an audio track.
$FF -v error -y -f lavfi -t 3.0 -i "testsrc2=s=$SZ:r=$R" \
  -f lavfi -t 3.0 -i "sine=frequency=440:sample_rate=48000" \
  -pix_fmt yuv420p -c:a aac -shortest with_audio_track.mp4

# Three shots with a title overlay held at a constant position across all cuts.
# Rendered with Pillow because this ffmpeg has no drawtext/libass - which is
# also how the real renderer composites captions.
"${PYTHON:-python3}" ./make_title_fixture.py

# Same three shots, letterboxed with 85px bars top and bottom of a 568px frame
# (0.1496 each). Ground truth for letterbox detection.
$FF -v error -y -i three_shots_at_1.0_3.0.mp4 \
  -vf "scale=320:398,pad=320:568:0:85:black" -pix_fmt yuv420p \
  letterboxed_bars_0.1496.mp4
