# -*- coding: utf-8 -*-
"""슬라이드 실렌더 캡처 + 오버플로 린터"""
import sys, os, json
from playwright.sync_api import sync_playwright

OUT = os.path.dirname(os.path.abspath(__file__))
SHOTS = os.path.join(OUT, 'shots')
os.makedirs(SHOTS, exist_ok=True)
PAGE = os.path.join(OUT, 'OLEDi_V_추진방안_개선안.html')
import os as _o
W, H = int(_o.environ.get("VW",1600)), int(_o.environ.get("VH",1000))
targets = sys.argv[1:] or ['d5'] + [f'p{n}' for n in range(20, 34)]

LINT = """
(id) => {
  const sec = document.getElementById('sl-'+id);
  if(!sec) return {err:'no section'};
  const out = {over:[], clip:[], empty:null};
  const sr = sec.getBoundingClientRect();
  sec.querySelectorAll('*').forEach(e=>{
    const r = e.getBoundingClientRect();
    if(r.width===0||r.height===0) return;
    if(r.right > sr.right+1 || r.bottom > sr.bottom+1 || r.left < sr.left-1)
      out.over.push(e.className+'|'+e.tagName+'|'+Math.round(r.right-sr.right)+','+Math.round(r.bottom-sr.bottom));
    if(e.scrollHeight > e.clientHeight+2 && getComputedStyle(e).overflow!=='visible')
      out.clip.push(e.className+'|'+e.tagName+'|'+(e.scrollHeight-e.clientHeight));
    if(e.scrollWidth > e.clientWidth+2 && getComputedStyle(e).overflowX!=='visible')
      out.clip.push('X:'+e.className+'|'+e.tagName+'|'+(e.scrollWidth-e.clientWidth));
  });
  const fg = sec.querySelector('.fg');
  if(fg){ const x = fg.querySelector('.x');
    if(x){ const fr=fg.getBoundingClientRect(), xr=x.getBoundingClientRect();
      out.empty = Math.round(fr.bottom - xr.bottom - 13); } }
  return out;
}
"""

with sync_playwright() as p:
    b = p.chromium.launch(executable_path='/opt/pw-browsers/chromium-1194/chrome-linux/chrome', args=['--font-render-hinting=none','--no-sandbox'])
    pg = b.new_page(viewport={'width': W, 'height': H}, device_scale_factor=2)
    pg.goto('file://' + PAGE)
    pg.wait_for_timeout(400)
    report = {}
    for t in targets:
        pg.evaluate("(i)=>show(ORDER.indexOf(i))", t)
        pg.wait_for_timeout(120)
        pg.screenshot(path=os.path.join(SHOTS, f'{t}.png'))
        report[t] = pg.evaluate(LINT, t)
    b.close()

bad = 0
for k, v in report.items():
    o, c, e = v.get('over', []), v.get('clip', []), v.get('empty')
    flag = ''
    if o: flag += f" OVER={len(o)} {o[:3]}"
    if c: flag += f" CLIP={len(c)} {c[:3]}"
    if e is not None and e > 12: flag += f" GAP={e}px"
    if flag:
        bad += 1
        print(f'[!] {k}{flag}')
    else:
        print(f'[ok] {k}  gap={e}px')
print('---', bad, 'slides with findings')
