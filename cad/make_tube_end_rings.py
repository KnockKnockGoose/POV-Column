"""Cut the bottom and top 20 mm of rotor_tube.stl into two watertight rings for a PLA fit check (2026-11-03).
Run from cad/: py make_tube_end_rings.py  ->  tube_end_rings_fitcheck.stl (both rings, one plate, print orientation)."""
import trimesh, numpy as np, sys
m = trimesh.load('rotor_tube.stl')
def band(z0, z1):  # boolean intersection with a slab (manifold3d): cut faces come out capped, mesh stays watertight
    box = trimesh.creation.box(extents=[400,400,z1-z0]); box.apply_translation([0,0,(z0+z1)/2])
    return trimesh.boolean.intersection([m, box], engine='manifold')
bot = band(-1.0, 20.0)
top = band(230.0, 251.0)
top.apply_translation([0,0,-230.0])                         # same orientation, cut face on the bed
for n,r in (('bottom',bot),('top',top)):
    print(n, 'wt',r.is_watertight,'vol',round(r.volume,1),'bounds',r.bounds.round(2).tolist(),'winding',r.is_winding_consistent)
# diagonal layout inside the both-nozzle area (25..325 x 0..320), centre of bbox goes to (175,160)
dx, dy = 115.0, 135.0
bot.apply_translation([-dx/2, -dy/2, 0]); top.apply_translation([dx/2, dy/2, 0])
c = trimesh.util.concatenate([bot, top])
print('combined wt', c.is_watertight, 'bodies', len(c.split()), 'bounds', c.bounds.round(2).tolist(),
      'gap between ODs', round(np.hypot(dx,dy)-2*81.35,2))
c.export('tube_end_rings_fitcheck.stl')
if len(sys.argv) > 1: c.export(sys.argv[1])
