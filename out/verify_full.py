# -*- coding: utf-8 -*-
"""통합본 전수 렌더 검증 — 52장 전체 겹침·이탈·오버플로 린트 + Ⅴ장 캡처"""
import os, sys
from playwright.sync_api import sync_playwright

OUT = os.path.dirname(os.path.abspath(__file__))
PAGE = os.path.join(OUT, 'OLEDi_고도화_방안_통합본.html')
SHOTS = os.path.join(OUT, 'shots_full')
os.makedirs(SHOTS, exist_ok=True)
W, H = int(os.environ.get('VW', 1600)), int(os.environ.get('VH', 1000))
CAP = set((os.environ.get('CAP') or 'd5,p20,p21,p22,p26,p27,p28,p29,p31,p33').split(','))

LINT = """
(id) => {
  const sec = document.getElementById('sl-'+id);
  if(!sec) return {err:'no section'};
  const out = {over:[], clip:[]};
  const sr = sec.getBoundingClientRect();
  sec.querySelectorAll('*').forEach(e => {
    const r = e.getBoundingClientRect();
    if(r.width===0 || r.height===0) return;
    if(r.right > sr.right+1 || r.bottom > sr.bottom+1 || r.left < sr.left-1)
      out.over.push(e.className+'|'+e.tagName);
    const cs = getComputedStyle(e);
    if(e.scrollHeight > e.clientHeight+2 && cs.overflowY !== 'visible' && cs.overflowY !== 'auto')
      out.clip.push('Y:'+e.className+'|'+e.tagName+'|'+(e.scrollHeight-e.clientHeight));
    if(e.scrollWidth > e.clientWidth+2 && cs.overflowX !== 'visible' && cs.overflowX !== 'auto')
      out.clip.push('X:'+e.className+'|'+e.tagName+'|'+(e.scrollWidth-e.clientWidth));
  });
  return out;
}
"""

with sync_playwright() as p:
    b = p.chromium.launch(
        executable_path='/opt/pw-browsers/chromium-1194/chrome-linux/chrome',
        args=['--font-render-hinting=none', '--no-sandbox'])
    pg = b.new_page(viewport={'width': W, 'height': H}, device_scale_factor=2)
    errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.on('console', lambda m: errs.append('console.' + m.type + ': ' + m.text)
          if m.type == 'error' else None)
    pg.goto('file://' + PAGE)
    pg.wait_for_timeout(600)

    order = pg.evaluate('() => ORDER')
    bad = 0
    for n, sid in enumerate(order):
        pg.evaluate('(i) => show(i)', n)
        pg.wait_for_timeout(70)
        vis = pg.evaluate("(s) => {const e=document.getElementById('sl-'+s);"
                          "return e ? getComputedStyle(e).display : 'MISSING';}", sid)
        r = pg.evaluate(LINT, sid)
        flag = ''
        if vis != 'flex':
            flag += f' 표시안됨({vis})'
        if r.get('over'):
            flag += f" OVER={len(r['over'])} {r['over'][:2]}"
        if r.get('clip'):
            flag += f" CLIP={len(r['clip'])} {r['clip'][:2]}"
        if flag:
            bad += 1
            print(f'[!] {n:>2} {sid}{flag}')
        if sid in CAP:
            pg.screenshot(path=os.path.join(SHOTS, f'{n:02d}_{sid}.png'))

    # 목차 / 상세 패널 / 도트 동작 확인
    pg.evaluate('() => tix()')
    pg.wait_for_timeout(200)
    ix = pg.evaluate("() => getComputedStyle(document.getElementById('ix')).display")
    pg.evaluate('() => tix()')
    pg.wait_for_timeout(150)
    pg.evaluate("() => show(ORDER.indexOf('p22'))")
    pg.wait_for_timeout(150)
    pg.evaluate('() => tg()')
    pg.wait_for_timeout(250)
    dp = pg.evaluate("() => getComputedStyle(document.getElementById('dp')).display")
    dpt = pg.evaluate("() => document.getElementById('dpt').textContent")
    pg.evaluate('() => tg()')
    b.close()

print(f'--- 슬라이드 {len(order)}장 중 지적 {bad}건')
print(f'--- 목차 패널 display={ix} / 상세 패널 display={dp} (제목: "{dpt}")')
print(f'--- JS 오류: {errs if errs else "없음"}')
