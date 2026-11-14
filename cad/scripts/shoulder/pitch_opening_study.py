"""Pitch cable crossing against the shell opening's size (checks/PITCH_OPENING_150.md). Numbers only; nothing is changed.

    python pitch_opening_study.py

Stack-up outward from the pitch axis (dims.py COVER, RING): inner wall to r 57.4, the loop channel, the outer wall 2.4,
the ring 1.6 proud of the wall, 2.5 to the opening. So opening radius = 57.4 + channel + 6.5.

Spiral (clock spring) in the channel: a band of thickness t, n turns. Wound tight on the inner wall it has n1 turns,
lying out against the outer wall n2; the length is the same, and the travel is (n1 - n2) x 360 deg. This is the ideal
limit (turns touching at both ends of travel), the same model that gave "2 to 2.3 turns, about 115 deg" in CABLE_TRAVEL.md.
A real spiral needs slack between the turns: take three quarters of it until the rig says otherwise.

Wrap and bight: one layer on the inner wall (needs t + 1.5 of channel), the rest hangs as a loop of radius R in the void
under the frame's step (117 mm deep, PITCH_BIGHT.md). Depth = half the stored length + R + half the spare.
"""
import math

from dims import COVER, RING

RI = COVER['in_'][1]
WALL = COVER['out'][1] - COVER['out'][0]
PROUD = RING['ro'] - COVER['out'][1]
GAP = 80.0 - RING['ro']
ROOM = 117.0


def spiral_deg(w, t):
    best = (0.0, 0.0)
    for i in range(1, 2000):
        n1 = i * 0.005                               # turns when wound tight on the inner wall
        if n1 * t > w:
            break
        L = math.pi * n1 * (2 * RI + n1 * t)
        # the same length lying against the outer wall: pi n2 (2 ro - n2 t) = L
        ro = RI + w
        disc = (2 * ro) ** 2 - 4 * t * L / math.pi
        if disc < 0:
            continue
        n2 = (2 * ro - math.sqrt(disc)) / (2 * t)
        if (n1 - n2) > best[0]:
            best = (n1 - n2, n1)
    return best[0] * 360.0, best[1]


def opening_for(deg, t):
    w = t
    while spiral_deg(w, t)[0] < deg:
        w += 0.05
    return w, RI + w + WALL + PROUD + GAP


def bight_deg(R, spare=30.0, t=3.0):
    stored = 2.0 * (ROOM - R - spare / 2.0)
    return stored / math.radians(1.0) / (RI + t / 2.0), stored


if __name__ == '__main__':
    print(f'stack: inner wall r {RI}, outer wall {WALL:.1f}, ring proud {PROUD:.1f}, gap {GAP:.1f}: opening r = {RI + WALL + PROUD + GAP:.1f} + channel')
    for name, t in (('2 x 16 AWG + two pairs (band 3.0)', 3.0), ('2 x 18 AWG + two pairs (band 2.4)', 2.4)):
        print(name)
        for ropen in (80.0, 75.0, 70.0):
            w = ropen - (RI + WALL + PROUD + GAP)
            d, n = spiral_deg(w, t)
            print(f'  opening r {ropen:.0f} (dia {2 * ropen:.0f}): channel {w:.1f}, layers that fit {int(w // t)}; spiral ideal {d:.0f} deg at {n:.2f} turns, with slack about {0.75 * d:.0f} deg')
        for deg in (115.0, 230.0):
            w, r = opening_for(deg, t)
            w2, r2 = opening_for(deg / 0.75, t)
            print(f'  spiral {deg:.0f} deg: ideal needs channel {w:.1f}, opening r {r:.1f} (dia {2 * r:.0f}); with slack channel {w2:.1f}, opening r {r2:.1f} (dia {2 * r2:.0f})')
        for R in (30.0, 24.0, 18.0):
            d, s = bight_deg(R, 30.0, t)
            print(f'  wrap and bight, loop R {R:.0f}, spare 30: stores {s:.0f} mm = {d:.0f} deg in the {ROOM:.0f} mm of room (any opening with a channel of {t + 1.5:.1f} or more)')
