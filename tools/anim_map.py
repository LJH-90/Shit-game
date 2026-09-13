"""Hand-mapped animation sets: animation name -> list of frame indices from
tools/frames (as produced by extract_sprites.py; see tools/contact.png).

All chosen frames are full-body, facing right, at the sheet's "large" scale
(standing ~56-60 px, crouched run ~42 px).  The only exception is the 6-frame
pistol run cycle (188-193), which the sheet draws at ~33 px; FRAME_SCALE
resamples it up so its head size matches the other frames.
"""

ANIM_MAP = {
    # standing with pistol, two breathing frames
    "idle": [42, 43],
    # 6-frame run cycle (small-scale row, resampled x1.35)
    "run": [188, 189, 190, 191, 192, 193],
    # arms out, legs down (ascending)
    "jump": [100, 101, 102],
    # leaning forward (descending)
    "fall": [103, 104, 105],
    # standing rifle shot with recoil
    "shoot": [58, 233, 57],
    # hunched dash with pistol extended
    "shoot_run": [152, 209],
    # kneeling with rifle
    "crouch": [231],
    # crouched rifle shot
    "crouch_shoot": [254, 60, 235],
    # stumble, stumble, sit, crumple, lie flat
    "death": [236, 237, 240, 241, 242],
    # standing, wave, salute, salute
    "victory": [248, 249, 250, 251],
}

# frame index -> resample factor applied before quantisation (default 1.0)
FRAME_SCALE = {i: 1.35 for i in (188, 189, 190, 191, 192, 193)}

ANIM_FPS = {
    "idle": 3.0,
    "run": 12.0,
    "jump": 8.0,
    "fall": 8.0,
    "shoot": 12.0,
    "shoot_run": 10.0,
    "crouch": 4.0,
    "crouch_shoot": 12.0,
    "death": 7.0,
    "victory": 4.0,
}
