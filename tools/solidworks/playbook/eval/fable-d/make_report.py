"""Assemble REPORT.md from the drafted sections (parts/*.md) and the tables the scripts generated."""
from common import HERE

P = HERE / 'parts'


def R(n):
    p = P / n if (P / n).exists() else HERE / n
    return p.read_text(encoding='utf-8')


rep = (R('head.md') + R('report_d1.md') + '\n' + R('report_d2a.md') + '\n' + R('report_d2b.md') + '\n### Results\n\n' + R('d2_tables.md')
       + R('report_d2c.md') + '\n' + R('report_d3a.md') + R('d3_mid1.md') + R('d3_table_one.md') + R('d3_mid2.md') + R('d3_table_two.md')
       + R('d3_end.md') + '\n' + R('report_end.md') + R('tail.md') + R('sha.md'))
(HERE / 'REPORT.md').write_text(rep, encoding='utf-8')
print(len(rep), 'characters')
