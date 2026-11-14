"""Hub top revision stream (own SolidWorks instance): rebuild the hub at DISH_Y (env), copy to _sim, run the spigot-clamped
cases. python hub_stream.py TAG"""
import os, shutil, subprocess, sys
os.environ.setdefault('SW_STATE_NAME', '.sw_instance_pid_hub')
os.environ.setdefault('SW_LOG_NAME', 'build_log_hub.txt')
import build_parts as B
from swk import OUT, CAD, finish
B.build_hub()
shutil.copy2(OUT / 'shoulder_hub_left.SLDPRT', CAD / '_sim' / 'shoulder' / 'hub_fea.SLDPRT')
import fea_shoulder as FS
tag = sys.argv[1] if len(sys.argv) > 1 else 'B'
for c in (sys.argv[2].split(',') if len(sys.argv) > 2 else ('HUBS_A', 'HUBS_B')):
    FS.run(f'{c}_{tag}', FS.CASES[c])
finish()
