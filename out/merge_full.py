# -*- coding: utf-8 -*-
"""원본 52장 덱에 개선된 Ⅳ장(P18·P19)과 Ⅴ장(P20~P33)을 병합한 완성본 생성"""
import os, re, sys

OUT = os.path.dirname(os.path.abspath(__file__))
SRC = '/root/.claude/uploads/1c2979f0-57a2-5e3d-a483-4d69937c0948/ea54353b-OLEDi____________________________OSS_SW______________.html'
DST = os.path.join(OUT, 'OLEDi_고도화_방안_통합본.html')

orig = open(SRC, encoding='utf-8').read()
merged = orig
log = []


def section_span(html, sid):
    """<section ... id="sl-{sid}"> ~ 대응 </section> 구간 반환 (section 은 중첩되지 않음)"""
    m = re.search(r'<section class="sl[^"]*" id="sl-%s">' % re.escape(sid), html)
    assert m, f'섹션 sl-{sid} 탐색 실패'
    end = html.index('</section>', m.end()) + len('</section>')
    return m.start(), end


def split_sections(frag):
    """생성 파일을 id → 마크업 사전으로 분해"""
    out = {}
    for m in re.finditer(r'<section class="sl[^"]*" id="sl-([^"]+)">', frag):
        sid = m.group(1)
        end = frag.index('</section>', m.end()) + len('</section>')
        out[sid] = frag[m.start():end]
    return out


# ── 1. Ⅴ장 — sl-d5 ~ sl-p33 구간 일괄 교체 ────────────────────────────
s5 = open(os.path.join(OUT, 's5_slides.html'), encoding='utf-8').read()
i, _ = section_span(merged, 'd5')
_, j = section_span(merged, 'p33')
old_ids = re.findall(r'<section class="sl[^"]*" id="sl-([^"]+)">', merged[i:j])
new_ids = re.findall(r'<section class="sl[^"]*" id="sl-([^"]+)">', s5)
assert old_ids == new_ids, f'Ⅴ장 ID 불일치\n원본: {old_ids}\n신규: {new_ids}'
merged = merged[:i] + s5 + merged[j:]
log.append(f'Ⅴ장 {len(new_ids)}장 교체')

# ── 2. Ⅳ장 — d4 / p18 / p19 개별 교체 (p18b·p18c 는 원본 유지) ─────────
s4 = split_sections(open(os.path.join(OUT, 's4_slides.html'), encoding='utf-8').read())
for sid in ['d4', 'p18', 'p19']:
    assert sid in s4, f's4_slides.html 에 sl-{sid} 없음'
    a, b = section_span(merged, sid)
    merged = merged[:a] + s4[sid] + merged[b:]
log.append(f'Ⅳ장 {len(s4)}장 교체 (p18b·p18c 는 원본 유지)')

# ── 3. 개선 CSS 삽입 (원본 CSS 는 무수정, </head> 직전) ────────────────
css = (open(os.path.join(OUT, 's5_css.css'), encoding='utf-8').read() + '\n' +
       open(os.path.join(OUT, 's4_css.css'), encoding='utf-8').read())
k = merged.find('</head>')
assert k > 0, '</head> 탐색 실패'
merged = merged[:k] + '<style id="s5-upgrade">\n' + css + '\n</style>' + merged[k:]

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
for line in log:
    print(f'  · {line}')
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

# 챕터 표지 버튼이 실제 섹션을 가리키는지
for sid in ['d4', 'd5']:
    s, e = section_span(merged, sid)
    gos = re.findall(r'data-go="([^"]+)"', merged[s:e])
    bad = [g for g in gos if g not in ids]
    print(f'  sl-{sid} 표지 버튼 {len(gos)}개 → 끊긴 링크: {bad if bad else "없음"}')
