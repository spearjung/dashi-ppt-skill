# -*- coding: utf-8 -*-
"""통합본을 claude.ai 아티팩트용 파일로 변환

아티팩트는 게시 시점에 <!doctype>…<head>…</head><body> 스켈레톤으로 감싸지므로
문서의 래퍼 태그를 벗기고 title + style + body 내용만 남김.
"""
import os, re

OUT = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(OUT, 'OLEDi_고도화_방안_통합본.html')
DST = os.path.join(OUT, 'artifact_deck.html')
# 갤러리·탭에 걸릴 이름 — 원본 통합본의 title 은 그대로 두고 아티팩트용으로만 축약함
TITLE = '<title>OLEDi 고도화 방안</title>'

h = open(SRC, encoding='utf-8').read()
head = re.search(r'<head>(.*?)</head>', h, re.S).group(1)
body = re.search(r'<body[^>]*>(.*)</body>', h, re.S).group(1)
styles = re.findall(r'<style[^>]*>.*?</style>', head, re.S)
assert styles, '<style> 블록 없음'

out = TITLE + '\n' + '\n'.join(styles) + '\n' + body
for bad in ['<!DOCTYPE', '<html', '</html>', '<head>', '</head>', '<body', '</body>']:
    assert bad not in out, f'래퍼 태그 잔여: {bad}'
assert 'https://' not in re.sub(r'data:image/[^"\')]+', '', out), '외부 리소스 참조 있음'

open(DST, 'w', encoding='utf-8').write(out)
print(f'{DST}  {len(out)/1024/1024:.2f}MB  style {len(styles)}블록')
