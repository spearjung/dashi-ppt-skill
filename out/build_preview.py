# -*- coding: utf-8 -*-
"""개선된 V. 추진 방안 섹션 단독 미리보기 파일 생성"""
import os, re

OUT = os.path.dirname(os.path.abspath(__file__))
SRC = '/tmp/claude-0/-home-user-dashi-ppt-skill/1c2979f0-57a2-5e3d-a483-4d69937c0948/scratchpad/orig.html'

orig = open(SRC, encoding='utf-8').read()
base_css = ''.join(re.findall(r'<style[^>]*>(.*?)</style>', orig, re.S))
new_css = open(os.path.join(OUT, 's5_css.css'), encoding='utf-8').read()
slides = open(os.path.join(OUT, 's5_slides.html'), encoding='utf-8').read()

# 원본 푸터 마크업 재사용
fm = re.search(r'<div class="sfoot">.*?</div>\s*(?=<button class="navb)', orig, re.S)
sfoot = fm.group(0) if fm else '<div class="sfoot"></div>'
sfoot = re.sub(r'<span class="dots".*?</span>', '<span class="dots" id="dots"></span>', sfoot, flags=re.S)

ORDER = ['d5'] + [f'p{n}' for n in range(20, 34)]

VIEW = """
<script>
var ORDER=%s, cur=0;
function el(c){return document.getElementById('sl-'+c);}
function show(n){n=Math.max(0,Math.min(ORDER.length-1,n));
  for(var i=0;i<ORDER.length;i++){var e=el(ORDER[i]); if(e) e.style.display=(i===n?'flex':'none');}
  cur=n; document.getElementById('bar').style.width=((n+1)/ORDER.length*100)+'%%';
  var d=document.getElementById('pgi'); if(d) d.textContent=(n+1)+' / '+ORDER.length;}
function step(d){show(cur+d);}
document.addEventListener('keydown',function(e){
  if(e.key==='ArrowRight'||e.key==='PageDown'||e.key===' ')  {step(1);e.preventDefault();}
  if(e.key==='ArrowLeft' ||e.key==='PageUp') {step(-1);e.preventDefault();}
  if(e.key==='Home'){show(0);} if(e.key==='End'){show(ORDER.length-1);}});
document.querySelectorAll('[data-go]').forEach(function(b){
  b.addEventListener('click',function(){var i=ORDER.indexOf(b.getAttribute('data-go')); if(i>=0)show(i);});});
show(0);
</script>
""" % (str(ORDER).replace("'", '"'),)

PATCH = """
<style>
/* 미리보기 전용 — 통합 시 불필요 */
#stage{padding-bottom:42px}
.sfoot .dots{display:none}
#pgi{font-size:11px;color:#8D9AB8;font-weight:700;margin-right:12px}
.sl.v5 .bkes{display:none}
</style>
"""

html = ('<!DOCTYPE html><html lang="ko"><head><meta charset="utf-8"/>'
        '<meta content="width=device-width,initial-scale=1" name="viewport"/>'
        '<title>OLEDi 고도화 방안 | Ⅴ. 추진 방안 (P20~P33) 개선안</title>'
        f'<style>{base_css}</style>'
        f'<style id="s5-upgrade">{new_css}</style>'
        f'{PATCH}</head><body>'
        '<div id="bar"></div><div id="stage">'
        + slides +
        sfoot.replace('<span class="sp"></span>', '<span class="sp"></span><span id="pgi"></span>') +
        '<button class="navb navl" onclick="step(-1)" aria-label="이전"><i></i></button>'
        '<button class="navb navr" onclick="step(1)" aria-label="다음"><i></i></button>'
        '</div>' + VIEW + '</body></html>')

p = os.path.join(OUT, 'OLEDi_V_추진방안_개선안.html')
open(p, 'w', encoding='utf-8').write(html)
print(p, len(html))
