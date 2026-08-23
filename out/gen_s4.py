# -*- coding: utf-8 -*-
"""Ⅳ. 선진사례 검증 — P18 / P19 재설계 마크업 생성기

P18b·P18c는 세로 여백이 3~4%로 이미 충족하므로 손대지 않음.
"""
import json, os

OUT = os.path.dirname(os.path.abspath(__file__))
LOGOS = json.load(open('/tmp/logos.json'))


def head(code, title, no):
    return (f'<div class="shead"><span class="bm">Deloitte<i>.</i></span>'
            f'<span class="ch">Ⅳ. 선진사례 검증</span><span class="cd2">{code}</span>'
            f'<h1>{title}</h1><span class="hlogo"></span><span class="no">{no} / 52</span></div>')


def msg(lines, ez):
    return ('<div class="msgb"><ul>' + ''.join(f'<li>{l}</li>' for l in lines) + '</ul>'
            '<div class="ezb"><ul>' + ''.join(f'<li>{l}</li>' for l in ez) + '</ul></div></div>')


def slide(sid, code, title, no, lines, ez, body):
    return (f'<section class="sl v5" id="sl-{sid}">' + head(code, title, no) +
            '<div class="sbody"><div class="sinner">' + msg(lines, ez) +
            '<figure class="fg"><div class="x">' + body + '</div></figure></div></div></section>')


S = []

# ───────────────────────────────────────────── 챕터 표지 (버튼 순서를 페이지 순으로 정렬)
DIV = [('p18', 'P18', '선진 사례는 개발 도구가 아니라 Runtime·Registry·Governance에 투자하고 있음'),
       ('p18b', 'P18B', 'SK하이닉스는 신규 포털 구축 없이 기존 협업 채널 내에서 요구를 해결함'),
       ('p18c', 'P18C', '레거시 이관 없이 도메인 VectorDB와 MCP로 연계함 — 국내 제조 선행 사례'),
       ('p19', 'P19', '범용 대화와 설비 Agent를 동일 위험 등급으로 운영하면 통제가 붕괴됨')]
dvl = ''.join(f'<button class="dvr" data-go="{g}"><i>{c}</i><span>{t}</span></button>'
              for g, c, t in DIV)
S.append('<section class="sl div" id="sl-d4">'
         '<div class="shead"><span class="bm">Deloitte<i>.</i></span><span class="ch">CHAPTER</span>'
         '<span class="cd2">Ⅳ</span><h1>선진사례 검증</h1><span class="hlogo"></span>'
         '<span class="no">33 / 52</span></div>'
         '<div class="dvb"><div class="dvi"><em>Ⅳ</em><b>선진사례 검증</b>'
         '<span>글로벌 Agent 플랫폼이 실제로 투자하고 있는 지점</span></div>'
         f'<div class="dvl">{dvl}</div></div></section>')

# ───────────────────────────────────────────── P18 — 4사 비교 매트릭스
CASES = [
    ('google', 'Google', 'Gemini Enterprise Agent Platform',
     'Agent Registry와 Gateway를 플랫폼 기본 구성으로 제공함',
     'Agent Runtime과 장기 Memory를 별도 계층으로 분리함',
     'Build·Scale·Govern·Optimize 4단계로 통제를 구조화함',
     'Low-Code와 Code-First 경로를 분리 제공함'),
    ('microsoft', 'Microsoft', '365 Copilot Agent Governance',
     'Agent 소유자와 공개 범위를 등록 시점에 확정함',
     'Copilot 실행을 사내 데이터 경계 안에서 수행함',
     'Policy·Process·People을 거버넌스 공통 축으로 제시함',
     '과다 공유 데이터 식별과 민감도 레이블을 적용함'),
    ('servicenow', 'ServiceNow', 'AI Agent Orchestrator',
     'Agent Studio에서 생성한 자산을 중앙 등록함',
     'Orchestrator가 Agent 간 협업 실행을 담당함',
     'AI Control Tower가 전사 Agent를 일괄 통제함',
     '기존 Workflow를 대체하지 않고 Agent가 호출함'),
    ('siemens', 'Siemens', 'Industrial Copilot',
     '산업 Agent를 목적별로 등록·조합함',
     'Copilot UI와 Orchestrator를 구조적으로 분리함',
     '보안·데이터 보호·검증·모니터링을 전제 조건으로 둠',
     '설계·엔지니어링·운영·유지보수 시스템과 통합함'),
]

rows = ''
for key, corp, prod, reg, run, gov, leg in CASES:
    lg = LOGOS[key]
    ratio = lg['w'] / lg['h']
    logo = (f'<img class="lg" src="{lg["uri"]}" alt="{corp}" '
            f'style="height:19px;width:{19 * ratio:.0f}px">')
    rows += ('<tr>'
             f'<td class="k case"><div>{logo}<b>{corp}</b><span>{prod}</span></div></td>'
             f'<td>{reg}</td><td>{run}</td><td>{gov}</td><td class="gn">{leg}</td></tr>')

tbl18 = ('<div class="tw"><table>'
         '<colgroup><col style="width:19%"><col><col><col><col></colgroup>'
         '<thead><tr><th>사례</th><th>Registry · 자산 관리</th><th>Runtime · 실행</th>'
         '<th>Governance · 통제</th><th>기존 자산 연계</th></tr></thead>'
         f'<tbody>{rows}</tbody></table></div>')

p18 = (('<div class="kpi k4">'
        '<div class="on"><b>4개사</b><span>Agent 플랫폼 공개 사례</span></div>'
        '<div><b>4개 계층</b><span>Registry·Runtime·Governance·연계</span></div>'
        '<div><b>4/4</b><span>Registry·Runtime을 별도 계층으로 분리</span></div>'
        '<div class="gn"><b>0개사</b><span>기존 업무 Workflow 대체</span></div>'
        '</div>')
       + f'<div class="grow" style="display:flex">'
         f'<div class="c acc"><h4>선진 4사가 실제로 투자한 지점<u>4개 계층 비교</u></h4>'
         f'<div class="b">{tbl18}</div></div></div>'
       + '<div class="co">4사 모두 개발 도구가 아니라 Registry·Runtime·Governance에 투자하고 있으며, '
         '기존 업무 시스템을 대체하지 않고 호출하는 구조를 공통으로 채택함</div>')

S.append(slide('p18', 'P18',
               '선진 사례는 개발 도구가 아니라 Runtime·Registry·Governance에 투자하고 있음', 34,
               ['Google·Microsoft·ServiceNow·Siemens 모두 Agent Studio만이 아니라 Runtime, Memory, Registry, Gateway, 평가·관측을 통합 구조로 제시함',
                '네 사례 모두 기존 업무 Workflow를 대체하지 않고 Agent가 호출하는 구조를 공통으로 채택함'],
               ['Agent 도입의 병목은 만드는 도구가 아니라 운영하고 통제하는 계층에 있음',
                'OLEDi Agent Hub를 단순 목록 화면으로 구현할 경우 동일한 한계가 재현됨'],
               p18))

# ───────────────────────────────────────────── P19 — 위험 등급 피라미드
LV = [
    ('L4', '4', '설비 제어 · 생산조건 변경', '승인권자 승인',
     '업무 승인권자 승인 필수 · 이중 확인 · 안전성·재현성·장애 대응 검증 후에만 개방함', 'r4'),
    ('L3', '3', '등록 · 수정 · 발주 실행', '사용자 확인',
     'Preview 제시 후 사용자 확인 · 실행 이력 전량 감사 · 취소 절차 사전 정의함', 'r3'),
    ('L2', '2', '설비 진단 · 이상 분석 · 설명', '자동 + 근거 제시',
     '자동 수행하되 근거 데이터와 판단 이유를 함께 제시하고 담당자 검토 경로를 남김', 'r2'),
    ('L1', '1', '일반 대화 · 문서 검색 · 요약', '자동 수행',
     '사용자 권한 범위 내 자동 수행 · 별도 승인 없음 · 조회 이력만 기록함', 'r1'),
]

bands = ''.join(f'<div class="band {c} b{i}"><b>{lab}</b></div>'
                for i, (lab, _n, _t, _chip, _d, c) in enumerate(LV))
descs = ''.join(f'<div class="lvrow {c}"><div class="lvh"><b>Level {n}</b>'
                f'<em>{chip}</em></div><strong>{t}</strong><small>{d}</small></div>'
                for lab, n, t, chip, d, c in LV)

p19 = ('<div class="pyrwrap">'
       f'<div class="pyr">{bands}</div>'
       f'<div class="lvcol">{descs}</div>'
       '</div>'
       '<div class="co gn">OLEDi는 제조시스템을 대체하지 않고 위험 등급별로 승인 강도를 달리하는 '
       '인터페이스 역할에 한정함</div>')

S.append(slide('p19', 'P19',
               '범용 대화와 설비 Agent를 동일 위험 등급으로 운영하면 통제가 붕괴됨', 37,
               ['SDC 제조 환경에서는 범용 챗봇과 산업·설비 Agent를 같은 위험 수준으로 관리할 수 없으며 설비 진단·설명과 장비 제어를 분리해야 함',
                '제조 Agent는 결과 정확도뿐 아니라 안전성·재현성·장애 대응까지 검증 대상에 포함해야 함'],
               ['설비 상태의 설명과 설비의 제어는 위험 등급이 상이한 행위임',
                'OLEDi는 제조시스템을 대체하지 않고 안전하게 연결하는 인터페이스 역할에 한정함'],
               p19))

open(os.path.join(OUT, 's4_slides.html'), 'w', encoding='utf-8').write('\n'.join(S))
print('slides:', len(S), '| bytes:', sum(len(x) for x in S))
