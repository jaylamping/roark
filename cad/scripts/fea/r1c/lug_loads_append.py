"""Append one case's lug_loads.py output to a lug-loads file, before its SUMMARY section if it has one (2026-11-13).
    python lug_loads_append.py LOADS_TXT CASE_TITLE LUG_LOADS_OUTPUT [SUMMARY_LINE ...]"""
import sys
F, title, src = sys.argv[1:4]
t = open(F, encoding='utf-8').read()
body = open(src, encoding='utf-8').read().split('\n', 1)[1].rstrip('\n')
blk = f'\n==================== {title}\n{body}\n'
k = t.find('\nSUMMARY')
t = t[:k] + blk + t[k:] if k >= 0 else t.rstrip('\n') + '\n' + blk
for line in sys.argv[4:]:
    t = t.rstrip('\n') + '\n' + line + '\n'
open(F, 'w', encoding='utf-8', newline='\n').write(t)
print('appended', title)
