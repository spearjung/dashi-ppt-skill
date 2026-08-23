# -*- coding: utf-8 -*-
"""원본 52장 덱에 개선된 Ⅴ. 추진 방안(P20~P33) 섹션을 병합한 완성본 생성"""
import os, re, sys

OUT = os.path.dirname(os.path.abspath(__file__))
SRC = '/root/.claude/uploads/1c2979f0-57a2-5e3d-a483-4d69937c0948/ea54353b-OLEDi____________________________OSS_SW______________.html'
DST = os.path.join(OUT, 'OLEDi_고도화_방안_통합본.html')

orig = open(SRC, encoding='utf-8').read()
new_css = open(os.path.join(OUT, 's5_css.css'), encoding='utf-8').read()
new_sec = open(os.path.join(OUT, 's5_slides.html'), encoding='utf-8').read()

# ── 1. 교체 대상 구간 확인 ────────────────────────────────────────────
i = orig.find('<section class="sl div" id="sl-d5"')
j = orig.find('<div class="sfoot">')
assert i > 0 and j > i, f'섹션 경계 탐색 실패 i={i} j={j}'
old_sec = orig[i:j]
assert old_sec.rstrip().endswith('</section></div>'), '구간 종료 형태가 예상과 다름'

old_ids = re.findall(r'<section class="sl[^"]*" id="(sl-[^"]+)"', old_sec)
new_ids = re.findall(r'<section class="sl[^"]*" id="(sl-[^"]+)"', new_sec)
assert old_ids == new_ids, f'슬라이드 ID 불일치\n원본: {old_ids}\n신규: {new_ids}'

# ── 2. 섹션 마크업 교체 (#stage 닫는 </div> 보존) ──────────────────────
merged = orig[:i] + new_sec + '\n</div>' + orig[j:]

# ── 3. 개선 CSS 삽입 (원본 CSS는 무수정, </head> 직전) ─────────────────
k = merged.find('</head>')
assert k > 0, '</head> 탐색 실패'
merged = (merged[:k]
          + '<style id="s5-upgrade">\n' + new_css + '\n</style>'
          + merged[k:])

open(DST, 'w', encoding='utf-8').write(merged)

# ── 4. 무결성 요약 ────────────────────────────────────────────────────
def stat(html):
    return {
        'sections': len(re.findall(r'<section class="sl', html)),
        'ids': re.findall(r'<section class="sl[^"]*" id="sl-([^"]+)"', html),
        'dots': len(re.findall(r'<i data-d="', html)),
        'ix_rows': len(re.findall(r'<button class="ir" data-go="', html)),
        'dpg': len(re.findall(r'<div class="dpg" id="dp-', html)),
    }

a, b = stat(orig), stat(merged)
print(f'출력: {DST}')
print(f'크기: {len(orig)/1024/1024:.2f}MB → {len(merged)/1024/1024:.2f}MB')
for key in a:
    if key == 'ids':
        same = a[key] == b[key]
        print(f'  슬라이드 ID 순서 동일: {same} ({len(b[key])}장)')
        if not same:
            print('   원본:', a[key])
            print('   신규:', b[key])
    else:
        print(f'  {key}: {a[key]} → {b[key]}  {"OK" if a[key]==b[key] else "!! 불일치"}')

order = re.search(r'var ORDER=\[(.*?)\]', merged, re.S)
ids = set(b['ids'])
missing = [x.strip().strip('"\'') for x in order.group(1).split(',')
           if x.strip().strip('"\'') and x.strip().strip('"\'') not in ids]
print(f'  ORDER 항목 중 실제 섹션 없는 것: {missing if missing else "없음"}')
