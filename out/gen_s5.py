# -*- coding: utf-8 -*-
"""V. 추진 방안 (P20~P33) 개선 마크업 생성기"""
import io, os

OUT = os.path.dirname(os.path.abspath(__file__))


def head(code, ch, title, no):
    return (f'<div class="shead"><span class="bm">Deloitte<i>.</i></span>'
            f'<span class="ch">{ch}</span><span class="cd2">{code}</span>'
            f'<h1>{title}</h1><span class="hlogo"></span><span class="no">{no} / 52</span></div>')


def msg(lines, ez=None):
    s = '<div class="msgb"><ul>' + ''.join(f'<li>{l}</li>' for l in lines) + '</ul>'
    if ez:
        s += '<div class="ezb"><ul>' + ''.join(f'<li>{l}</li>' for l in ez) + '</ul></div>'
    return s + '</div>'


def slide(sid, code, title, no, lines, body, ez=None):
    return (f'<section class="sl v5" id="sl-{sid}">' + head(code, 'Ⅴ. 추진 방안', title, no) +
            '<div class="sbody"><div class="sinner">' + msg(lines, ez) +
            '<figure class="fg"><div class="x">' + body + '</div></figure></div>'
            '<button class="bkes" data-back="e4">‹ Executive Summary</button></div></section>')


def tags(items, cls=''):
    return f'<div class="tags {cls}">' + ''.join(f'<span>{i}</span>' for i in items) + '</div>'


def li(items, cls='li sp'):
    return f'<ul class="{cls}">' + ''.join(f'<li><span>{i}</span></li>' for i in items) + '</ul>'


def kpi(items, k='k4'):
    s = f'<div class="kpi {k}">'
    for it in items:
        c = it[2] if len(it) > 2 else ''
        s += f'<div class="{c}"><b>{it[0]}</b><span>{it[1]}</span></div>'
    return s + '</div>'


def card(title, body, extra='', tag=''):
    t = f'<h4>{title}' + (f'<u>{tag}</u>' if tag else '') + '</h4>'
    return f'<div class="c {extra}">{t}<div class="b">{body}</div></div>'


def gate(items, label='완료 GATE'):
    return (f'<div class="gate"><i>{label}</i>' +
            ''.join(f'<p>{i}</p>' for i in items) + '</div>')


def band(label, text):
    return f'<div class="band"><i>{label}</i><p>{text}</p></div>'


BG = {'신규': 'n', '재사용': 'r', '조건부': 'o', '선택': 'o'}


def spectable(rows, h1='영역', h2='소요 규모', w1='42%'):
    body = ''.join(f'<tr><td class="k">{a}</td><td>{b}</td></tr>' for a, b in rows)
    return (f'<div class="tw"><table><colgroup><col style="width:{w1}"><col></colgroup>'
            f'<thead><tr><th>{h1}</th><th>{h2}</th></tr></thead><tbody>{body}</tbody></table></div>')


SPEC = {
 'p22': [('기존 자산 활용', 'K8s Namespace · 공용 GPU · Elasticsearch'),
         ('App · RAG', '24~48 vCPU · 96~192GB RAM 상당'),
         ('PostgreSQL', '0.5~1TB 증분'), ('Search Index', '1~3TB 증분'),
         ('Model Replica', '운영 2 + 비운영 Capacity 1')],
 'p23': [('Orchestrator · Agent Worker', '32~64 vCPU'),
         ('Temporal Server · Worker', '12~24 vCPU'),
         ('Cache', 'Valkey HA 3 Node 또는 기존 Cache'),
         ('Tool 실행 격리', '전용 Namespace · Network Policy')],
 'p24': [('Workspace API', '16~24 vCPU'),
         ('PostgreSQL + pgvector', '1~2TB 논리 할당'),
         ('Project Index', '1~3TB 증분'), ('산출물 저장', '2~5TB 논리 할당')],
 'p25': [('Batch Worker', '32~64 vCPU Burst'),
         ('Evaluation DB · Trace', '1~3TB'),
         ('Langfuse 적용 시', 'ClickHouse · Valkey · S3 추가'),
         ('실시간 변경 필요 시', 'Kafka · Debezium 추가')],
 'p26': [('Integration Namespace', '24~48 vCPU'),
         ('Temporal Worker Queue', '업무별 분리'),
         ('내부 연계 구간', 'System Integration Zone · Allowlist'),
         ('감사 Log', '1~3TB 증분')],
}


def roletable(rows, w1='34%', w2='40%'):
    """역할 → 적용 제품 → 구분 매핑표"""
    body = ''.join(
        f'<tr><td class="k">{a}</td><td>{b}</td>'
        f'<td style="text-align:center"><span class="bg {BG[c]}">{c}</span></td></tr>'
        for a, b, c in rows)
    return (f'<div class="tw"><table><colgroup><col style="width:{w1}"><col style="width:{w2}">'
            f'<col></colgroup><thead><tr><th>역할</th><th>적용 제품</th>'
            f'<th style="text-align:center">구분</th></tr></thead><tbody>{body}</tbody></table></div>')


S = []

# ─────────────────────────────────────────────────────────── 챕터 표지
DIV = ['P20 · 5단계 45.9억원 로드맵과 단계별 투자 구조',
       'P21 · 현재 승인 대상은 1단계 8.1억원 — Stage-Gate 의사결정',
       'P22 · 1단계 — 통합 대화·EDM RAG 및 공통 모델·관측 기반',
       'P23 · 2단계 — Agent·Tool 실행 공통 기반과 구매 Agent',
       'P24 · 3단계 — Personal·Project Workspace와 Agent Hub',
       'P25 · 4단계 — Knowledge·Evaluation·운영 거버넌스',
       'P26 · 5단계 — 대표 레거시 조회·Transaction 실행 연계',
       'P27 · 공통 Golden Path — 단계마다 새 플랫폼을 만들지 않음',
       'P28 · 인프라 전제 — 기존 K8s·GPU·EDM·Search·IAM 재사용',
       'P29 · 오픈소스 선정 — 역할별 1개 표준과 조건부 대안',
       'P30 · OSS 공급망·라이선스·보안 통제',
       'P31 · 4개월·7~8명 Core Team과 20개월 일정',
       'P32 · 포함·제외·증분 단가를 수량으로 고정',
       'P33 · 즉시 착수안 — 1단계 8.1억원 승인 후 선택적 확장']

dvl = ''.join(
    f'<button class="dvr" data-go="p{20+i}"><i>P{20+i}</i><span>{d.split(" · ")[1]}</span></button>'
    for i, d in enumerate(DIV))
S.append('<section class="sl div v5" id="sl-d5">' +
         '<div class="shead"><span class="bm">Deloitte<i>.</i></span><span class="ch">CHAPTER</span>'
         '<span class="cd2">Ⅴ</span><h1>추진 방안</h1><span class="hlogo"></span>'
         '<span class="no">38 / 52</span></div>'
         '<div class="dvb exec-chapter"><div class="dvi"><em>Ⅴ</em><b>추진 방안</b>'
         '<span>8~10억원 단위 단계별 실행·인프라·오픈소스 SW Stack·투자 Gate</span></div>'
         f'<div class="dvl exec-dvl2">{dvl}</div></div></section>')

# ─────────────────────────────────────────────────────────── P20
STAGE = [
    dict(n='1단계', won='8.1억', title='통합 UX·EDM RAG', cap='검색·권한·Citation·Model Gateway·평가 기반',
         mm='27MM', mon='M1~M4', gate='G1 · RAG',
         gk='동일 대화·권한·Citation 품질로 2단계 판정',
         task=['현행 구조·권한·Session·검색 상세진단',
               '일반 대화와 EDM RAG의 동일 화면 통합',
               'Hybrid Search·Chunk·Re-ranking 고도화',
               '검색·원문·답변 반환 시점 권한 검증',
               'Citation·기준일 표시와 Model Gateway MVP'],
         stack='K8s · Elasticsearch · vLLM · LiteLLM · OTel'),
    dict(n='2단계', won='9.6억', title='Agent·Tool 기반', cap='Orchestrator·Registry·Runtime·Gateway',
         mm='32MM', mon='M5~M8', gate='G2 · Agent',
         gk='Registry 통제와 Tool 재사용률로 3단계 판정',
         task=['Intent 분류·Agent/Tool Routing Orchestrator',
               'Agent·Tool Registry·Version·Owner 관리',
               'Tool Gateway 인증·Schema·Timeout·오류처리',
               '기존 기능 3~4개 Tool화',
               '구매·원가 분석 Agent PoC'],
         stack='LangGraph · Temporal · MCP · OPA · Valkey'),
    dict(n='3단계', won='9.0억', title='Workspace·Agent Hub', cap='Personal·Project Context와 Agent·Asset 재사용',
         mm='30MM', mon='M9~M12', gate='G3 · 협업',
         gk='Workspace 이용률·산출물 재사용으로 4단계 판정',
         task=['Personal·Project Workspace 구축',
               'Context Service·Memory·Session 분리',
               'Agent Hub 검색·선택·호출 UI',
               'Agent 등록·검증·승인·공개 Workflow',
               '설비 문제 분석 Workspace PoC'],
         stack='PostgreSQL · pgvector · IAM · OPA'),
    dict(n='4단계', won='9.6억', title='Knowledge·운영', cap='증분 색인·승격·평가·관측·Admin',
         mm='32MM', mon='M13~M16', gate='G4 · 운영',
         gk='지식 승인·평가 Gate 작동으로 5단계 판정',
         task=['개인·프로젝트·공식 지식 상태·Owner 관리',
               '후보·평가·검토·승인 승격 Pipeline',
               'EDM 변경 감지·증분 색인·Lineage',
               'RAG·Agent Evaluation Dataset·Score',
               '품질·비용·오류 관측·Admin Console'],
         stack='Argo · Ragas · Promptfoo · Langfuse(선택)'),
    dict(n='5단계', won='9.6억', title='레거시 실행', cap='대표 조회 3개·Transaction 1개·HITL',
         mm='32MM', mon='M17~M20', gate='G5 · 실행',
         gk='Transaction 오류·승인·감사·ROI로 확산 판정',
         task=['ERP·MES·PLM 또는 QMS 조회 Tool 각 1개',
               '등록·수정·요청 Transaction Workflow 1개',
               '실행 전 대상·입력·영향 Preview',
               '사용자 확인·승인권자 승인·유효시간',
               'Idempotency·Lock·Timeout·보상 Workflow'],
         stack='MCP/OpenAPI · Temporal · API GW · OPA'),
]

rail = '<div class="rail">' + ''.join(
    f'<div class="s{i+1}">{s["mon"]}<u>{s["mm"]} · 4개월</u></div>' for i, s in enumerate(STAGE)) + '</div>'

# 각 단계가 남기는 공통 기반 — 다음 단계가 재사용하는 자산
BASE = [['Model Gateway', '검색·권한 Pipeline', '평가 Dataset', 'Telemetry'],
        ['Agent Registry', 'Tool Registry', 'Tool Gateway', 'Durable Workflow'],
        ['Context Service', 'Workspace 권한', 'Agent Hub', '산출물 저장'],
        ['지식 승격 Pipeline', '증분 색인·Lineage', '평가·Regression Gate', 'Admin Console'],
        ['Transaction Workflow', 'HITL 승인', '보상 Workflow', '전량 감사']]

cards = '<div class="g5" style="flex:1.0;min-height:0">'
for i, s in enumerate(STAGE):
    cards += (f'<div class="stg s{i+1}"><div class="h"><b>{s["n"]}</b><em>{s["won"]}</em></div>'
              f'<div class="b"><h3>{s["title"]}</h3><p class="cap">{s["cap"]}</p>'
              '<div class="sub">구축 범위</div>' + li(s['task'], 'li') +
              '</div></div>')
cards += '</div>'

BASELINE = ['모델·검색·평가 기반', 'Agent·Tool 실행 기반', 'Workspace·Context 기반',
            '지식·평가·운영 기반', '실행·승인·감사 기반']

stair = '<div class="stair">'
for col in range(5):
    stair += '<div class="col">'
    for k in range(col, -1, -1):
        stair += (f'<div class="blk s{k+1}"><i>{k+1}</i>'
                  f'<span>{BASELINE[k]}</span></div>')
    stair += '</div>'
stair += '</div>'
base = card('단계가 남기는 공통 기반은 다음 단계가 그대로 재사용함', stair, '',
            '누적 Golden Path')
base = f'<div style="flex:1.05;min-height:0;display:flex">{base}</div>'

gates20 = '<div class="g5" style="flex:none">' + ''.join(
    f'<div class="gstrip s{i+1}"><i>{s["gate"].split(" · ")[0]}</i>'
    f'<span>{s["gk"]}</span></div>' for i, s in enumerate(STAGE)) + '</div>'

p20 = (rail + cards + base + gates20 +
       kpi([('153MM', '전체 외부 구축공수'), ('45.9억원', '평균 3,000만원/MM'),
            ('18~20개월', '순차 수행 기준'), ('8.1억원', '현재 승인 대상', 'gn')], 'k4'))
S.append(slide('p20', 'P20', 'OLEDi 고도화는 8~10억원 단위 5개 독립 사업으로 분할하고 단계별 Go·Stop을 적용함', 39,
               ['전체 45.9억원은 장기 프로그램 한도이며 일괄 계약금액이 아님 — 1단계 8.1억원만 우선 착수함',
                '각 단계가 하나의 사용자 가치와 하나의 공통 기반을 완결하도록 구성하여 성과 공백과 재개발을 동시에 차단함'],
               p20,
               ez=['평균 단가 3,000만원/MM을 적용하며, 신규 GPU·대규모 HW 구매는 별도 인프라 투자로 분리함']))

# ─────────────────────────────────────────────────────────── P21
GATES = [('G1', 'RAG 품질·권한', '동일 대화·권한 검증·Citation·검색 품질 개선', '2단계 판단'),
         ('G2', 'Agent 공통화', 'Registry 통제·Tool 재사용률·구매 Agent 성과', '3단계 판단'),
         ('G3', '협업 전환', 'Workspace 이용률·산출물 재사용·Context 권한', '4단계 판단'),
         ('G4', '운영 통제', '지식 승인·평가 Gate·운영조직 수용성', '5단계 판단'),
         ('G5', '실행 통제', 'Transaction 오류·승인·전량 감사·ROI', '확산 판단')]
grail = '<div class="grail">' + ''.join(
    f'<div class="grr {"fin" if g[0]=="G5" else ""}"><b>{g[0]}</b>'
    f'<div><strong>{g[1]}</strong><small>{g[2]}</small></div><em>{g[3]}</em></div>' for g in GATES) + '</div>'

DEC = [('1단계', '8.1억원', '즉시 승인 대상', 'now'),
       ('2단계', '9.6억원', 'G1 통과 시 별도 발주', ''),
       ('3단계', '9.0억원', 'G2 통과 시 별도 발주', ''),
       ('4단계', '9.6억원', 'G3 통과 시 별도 발주', ''),
       ('5단계', '9.6억원', 'G4 통과 시 별도 발주', '')]
dectbl = ('<div class="tw"><table><colgroup><col style="width:22%"><col style="width:28%"><col></colgroup>'
          '<thead><tr><th>단계</th><th>사업비</th><th>발주 조건</th></tr></thead><tbody>' +
          ''.join(f'<tr class="{c}"><td class="k">{a}</td><td class="gn">{b}</td><td>{d}</td></tr>'
                  for a, b, d, c in DEC) + '</tbody></table></div>')
left21 = card('투자 의사결정 — 단계별 독립 발주',
              '<div class="big"><b>8.1억원</b><span>1단계 우선 승인 · 27MM · 4개월</span></div>' +
              dectbl +
              '<div class="co gn">Stop 시에도 1단계 산출물은 독립 운영이 가능하며 전체 45.9억원을 한 번에 Commit하지 않음</div>',
              'acc')
right21 = card('Exit Gate — 문서가 아니라 운영 지표로 판정함', grail, '', '5개 판정 시점')

p21 = (kpi([('8.1억원', '즉시 승인 대상', 'on'), ('37.8억원', 'Gate 통과 시 조건부'),
            ('4개월', '의사결정 주기'), ('5회', 'Go·Stop 판단 횟수')], 'k4') +
       f'<div class="gL grow">{left21}{right21}</div>' +
       '<div class="kpi k4">' +
       ''.join(f'<div><b style="font-size:12.4px">{a}</b><span>{b}</span></div>' for a, b in
               [('Steering Committee', '단계 착수·중단 결정'), ('Product Owner', '업무가치·백로그'),
                ('EA·Security', '아키텍처·통제 승인'), ('System Owner', '연계·운영 승인')]) + '</div>')
S.append(slide('p21', 'P21', '현재 의사결정 대상은 전체 45.9억원이 아니라 1단계 8.1억원임', 40,
               ['각 단계는 별도 계약 또는 선택권이 포함된 다단계 계약으로 발주하여 범위·성과·중단 선택권을 보유함',
                'Exit Gate는 문서 제출 여부가 아니라 실제 서비스의 품질·이용률·권한·운영성·ROI로 판정함'],
               p21))


ROLES = {
 'p22': [('통합 UI', '기존 OLEDi UI', '재사용'), ('Container', 'Kubernetes', '재사용'),
         ('Search', 'Elasticsearch', '재사용'), ('State·Metadata', 'PostgreSQL', '재사용'),
         ('Model Serving', 'vLLM', '신규'), ('Model Gateway', 'LiteLLM Community', '신규'),
         ('관측·평가', 'OTel · Prometheus · Ragas', '신규')],
 'p23': [('Agent State', 'LangGraph Core', '신규'), ('Durable Workflow', 'Temporal OSS', '신규'),
         ('Tool 표준', 'MCP SDK · OpenAPI', '신규'), ('실행 정책', 'OPA', '신규'),
         ('Session·Cache', 'Valkey', '신규'), ('Registry DB', 'PostgreSQL', '재사용'),
         ('외부 노출', '기존 API Gateway', '재사용'), ('Serving 확장', 'KServe', '조건부')],
 'p24': [('Workspace DB', 'PostgreSQL', '재사용'), ('Context Vector', 'pgvector', '신규'),
         ('Session·Cache', 'Valkey', '신규'), ('전사 문서 검색', '기존 Elasticsearch', '재사용'),
         ('인증·권한', '기존 IAM/OIDC', '재사용'), ('접근 정책', 'OPA', '신규'),
         ('산출물 저장', '기존 Object Storage', '재사용'), ('Agent 등록', 'Registry API', '신규')],
 'p25': [('색인 원천', '기존 EDM · Elasticsearch', '재사용'), ('Batch Pipeline', 'Argo Workflows', '신규'),
         ('RAG 평가', 'Ragas', '신규'), ('Prompt Regression', 'Promptfoo', '신규'),
         ('Trace·Metric', 'OTel · Prometheus', '신규'), ('LLM 관측', 'Langfuse OSS', '선택'),
         ('Trace 저장', 'ClickHouse', '선택'), ('실시간 변경', 'Debezium + Kafka', '조건부')],
 'p26': [('Tool 표준', 'MCP + OpenAPI', '신규'), ('Transaction Workflow', 'Temporal OSS', '신규'),
         ('Agent State', 'LangGraph Core', '신규'), ('실행 정책', 'OPA', '신규'),
         ('Lock·Idempotency', 'Valkey', '신규'), ('외부 연계', '기존 API Gateway', '재사용'),
         ('인증·암호화', '기존 IAM/KMS', '재사용'), ('감사·추적', 'OpenTelemetry', '신규')],
}

# ─────────────────────────────────────────────── P22~P26 공통 템플릿
PH = [
    dict(sid='p22', code='P22', no=41, stage='1단계', won='8.1억원', mm='27MM', mon='M1~M4', g='G1 · RAG',
         title='1단계 8.1억원은 통합 대화와 EDM RAG 품질을 개선하고 공통 모델·관측 기반을 확보함',
         task=['현행 구조·권한·Session·검색 상세진단', '일반 대화와 EDM RAG의 동일 화면 통합',
               'Hybrid Search·Chunk·Re-ranking 고도화', '검색·원문·답변 반환 시점 권한 검증',
               'Citation·기준일·버전 표시', 'Model Gateway MVP·Golden Dataset·모니터링'],
         new=['vLLM', 'LiteLLM Community', 'OpenTelemetry', 'Prometheus', 'Ragas'],
         reuse=['기존 OLEDi UI', 'Kubernetes', 'Elasticsearch', 'PostgreSQL'],
         infra=['기존 K8s Namespace·공용 GPU·Elasticsearch 활용', 'App/RAG 24~48 vCPU·96~192GB RAM 상당',
                'PostgreSQL 0.5~1TB·Search 1~3TB 증분', '운영 Model Replica 2 + 비운영 Capacity 1'],
         gates=['권한 외 문서 노출 0건', '동일 대화·Citation 작동', '평가·응답·오류 추적 가능'],
         bl='범위 제외', bt='KServe·Agent Runtime·Workspace는 1단계에 도입하지 않음'),
    dict(sid='p23', code='P23', no=42, stage='2단계', won='9.6억원', mm='32MM', mon='M5~M8', g='G2 · Agent',
         title='2단계 9.6억원은 Agent·Tool 등록·호출 경로를 공통화하고 구매 Agent로 검증함',
         task=['Intent 분류·Agent/Tool Routing Orchestrator MVP', 'Agent Registry·Tool Registry·Version·Owner 관리',
               'Tool Gateway 인증·Schema·Timeout·오류처리', 'Agent Runtime·Session State·Retry',
               'EDM·PPT·외부검색 등 기존 기능 3~4개 Tool화', '구매·원가 분석 Agent PoC'],
         new=['LangGraph Core', 'Temporal OSS', 'MCP SDK', 'OpenAPI', 'OPA', 'Valkey', 'KServe(조건부)'],
         reuse=['PostgreSQL', '기존 API Gateway'],
         infra=['Orchestrator·Agent Worker 32~64 vCPU', 'Temporal Server·Worker 12~24 vCPU',
                'Valkey HA 3 Node 또는 기존 Cache', 'Tool 실행 격리 Namespace·Network Policy'],
         gates=['Registry 미등록 Agent 호출 차단', '기존 기능 3~4개 Tool 재사용', '구매 Agent E2E 완료'],
         bl='역할 분리', bt='LangGraph는 LLM 상태, Temporal은 장기 실행·Retry·승인을 담당함'),
    dict(sid='p24', code='P24', no=43, stage='3단계', won='9.0억원', mm='30MM', mon='M9~M12', g='G3 · 협업',
         title='3단계 9.0억원은 Personal·Project Workspace와 Agent Hub로 개인 결과를 팀 자산으로 전환함',
         task=['Personal Workspace·Prompt·Template·개인 Context', 'Project Workspace·멤버·문서·대화·Agent·산출물',
               'Context Service·Memory·Session 분리', 'Agent Hub 검색·선택·호출 UI',
               'Agent 등록·검증·승인·공개 Workflow', '설비 문제 분석 Workspace PoC'],
         new=['pgvector', 'Valkey', 'OPA', 'Registry API'],
         reuse=['PostgreSQL', '기존 Elasticsearch', '기존 IAM/OIDC', '기존 Object Storage'],
         infra=['Workspace API 16~24 vCPU', 'PostgreSQL+pgvector 1~2TB 논리 할당',
                'Project Index 1~3TB 증분', '산출물 저장 2~5TB 논리 할당'],
         gates=['비참여자 Context 접근 차단', '팀원이 분석을 이어받음', '설비 분석부터 산출물까지 완결'],
         bl='역할 분리', bt='전사 문서는 Elasticsearch, 개인·프로젝트 Context만 pgvector로 역할을 분리함'),
    dict(sid='p25', code='P25', no=44, stage='4단계', won='9.6억원', mm='32MM', mon='M13~M16', g='G4 · 운영',
         title='4단계 9.6억원은 지식 승격·평가·관측을 배포와 운영의 통제선으로 전환함',
         task=['개인·프로젝트·공식 지식 상태·Owner 관리', '후보·자동평가·검토·승인·승격 Pipeline',
               'EDM 변경 감지·증분 색인·Lineage', 'RAG·Agent Evaluation Dataset·Score',
               'Prompt·Model·Agent Regression Gate', '품질·비용·오류·Latency 관측·Admin Console'],
         new=['Argo Workflows', 'Ragas', 'Promptfoo', 'OpenTelemetry', 'Prometheus',
              'Langfuse OSS(선택)', 'ClickHouse(선택)', 'Debezium+Kafka(조건부)'],
         reuse=['기존 EDM·Elasticsearch', 'PostgreSQL'],
         infra=['Batch Worker 32~64 vCPU Burst', 'Evaluation DB·Trace Storage 1~3TB',
                'Langfuse 적용 시 ClickHouse·Valkey·S3 필요', '실시간 변경 필요 시에만 Kafka·Debezium'],
         gates=['미승인 지식 자동 반영 차단', '품질 미달 버전 배포 차단', 'Owner·Version·기준일 확인'],
         bl='조건부 도입', bt='Batch-first를 기본으로 하고 실시간 CDC와 Langfuse HA는 사용량·요건 충족 시에만 도입함'),
    dict(sid='p26', code='P26', no=45, stage='5단계', won='9.6억원', mm='32MM', mon='M17~M20', g='G5 · 실행',
         title='5단계 9.6억원은 대표 조회 3개와 Transaction 1개만 연계해 실행 통제의 완결성을 검증함',
         task=['ERP·MES·PLM 또는 QMS 조회 Tool 각 1개', '등록·수정·요청 Transaction Workflow 1개',
               '실행 전 대상·입력·영향 Preview', '사용자 확인·승인권자 승인·유효시간',
               'Idempotency·Lock·Timeout·보상 Workflow', '조회·분석·추천·승인·실행 E2E 시험'],
         new=['MCP + OpenAPI', 'Temporal OSS', 'LangGraph Core', 'OPA', 'Valkey', 'OpenTelemetry', 'Promptfoo'],
         reuse=['기존 API Gateway', '기존 IAM/KMS'],
         infra=['Integration Namespace 24~48 vCPU', 'Temporal Worker Queue 업무별 분리',
                '내부 System Integration Zone·Allowlist', '감사 Log 1~3TB 증분'],
         gates=['Agent 직접 DB/API 호출 금지', '승인 전 Transaction 미실행', '요청·승인·변경 전후 전량 감사'],
         bl='범위 제외', bt='ERP·MES·PLM·QMS 전체 연계와 설비 자동제어는 범위에서 제외함'),
]

for p in PH:
    top = kpi([(p['won'], f'{p["stage"]} 사업비', 'on'), (p['mm'], '외부 구축공수'),
               ('4개월', p['mon']), (p['g'], '완료 판정 Gate', 'gn')], 'k4')
    c1 = card(f'핵심 과업 · {p["mm"]}', li(p['task'], 'li num sp'), 'acc', '6개 과업')
    rows = ROLES[p['sid']]
    nn = sum(1 for r in rows if r[2] == '신규')
    c2 = card('오픈소스·플랫폼 — 역할별 1개 표준', roletable(rows), '',
              f'{nn}종 신규 · {len(rows)-nn}종 재사용·조건부')
    c3 = card('인프라 소요와 완료 Gate', spectable(SPEC[p['sid']]) + gate(p['gates']),
              '', '단계 종료 판정')
    body = top + f'<div class="g3 grow">{c1}{c2}{c3}</div>' + band(p['bl'], p['bt'])
    S.append(slide(p['sid'], p['code'], p['title'], p['no'],
                   [f'{p["won"]} · {p["mm"]} · 4개월을 기준으로 독립 구축·시험·전환이 가능하도록 범위를 고정함',
                    '기존 OLEDi·IAM·EDM·검색·GPU 자산을 재사용하고 다음 단계 기능은 선행 구현하지 않음'],
                   body))

# ─────────────────────────────────────────────────────────── P27
LAYERS = [('L1', '기존 OLEDi UI', '통합 대화 · Workspace · Agent Hub', '1·3단계'),
          ('L2', 'API Gateway · IAM', '인증 · Rate Limit · Network 격리', '기존 자산'),
          ('L3', 'Orchestrator', 'LangGraph Agent State + Temporal Durable Workflow', '2단계'),
          ('L4', 'RAG · Agent · Tool', 'Elasticsearch · Registry · MCP/OpenAPI Gateway', '1·2단계'),
          ('L5', 'Model · Enterprise', 'LiteLLM Gateway · vLLM 추론 / ERP · MES · PLM · QMS', '1·5단계')]
stack = '<div class="stk">' + ''.join(
    f'<div class="lyr"><i>{a}</i><div><strong>{b}</strong><small>{c}</small></div>'
    f'<em>{d}</em></div>' for a, b, c, d in LAYERS) + '</div>'

PLANE = [('State·Metadata', ['PostgreSQL', 'pgvector', 'Valkey'], '1·3단계 도입'),
         ('Policy', ['기존 IAM', 'OPA', 'Execution Policy'], '2·5단계 강화'),
         ('Observability', ['OpenTelemetry', 'Prometheus', 'Ragas', 'Langfuse 선택'], '1·4단계 도입'),
         ('Container·Batch', ['Kubernetes', 'Helm', 'Argo Workflows', 'KServe 조건부'], '기존 + 4단계')]
planes = ''.join(
    f'<div class="pl"><h5>{t}</h5><div class="pb">' +
    ''.join(f'<span>{x}</span>' for x in g2) +
    f'</div><u>{w}</u></div>' for t, g2, w in PLANE)

arch = (f'<div class="arch"><div class="archL">'
        '<div class="archh">요청 처리 경로 — 5개 계층</div>' + stack + '</div>'
        '<div class="archR"><div class="archh">횡단 Control Plane — 전 계층 공통</div>'
        f'<div class="pls">{planes}</div></div></div>')

p27 = (arch +
       '<div class="co">신규 Agent와 기능은 이 Golden Path 위에서만 개발하고, 기존 Point-to-Point 연동은 Tool 전환 완료 순서대로 폐기함</div>')
S.append(slide('p27', 'P27', '기술스택은 단계마다 새로 도입하지 않고 하나의 Golden Path를 누적 확장함', 46,
               ['1단계에서 Container·검색·모델 Gateway·Telemetry 기반을 만들고 2~5단계가 같은 Control Plane을 재사용함',
                'LLM 추론, 장기 Workflow, 검색, Context, 정책, 관측의 역할을 분리하여 제품 중복과 특정 Vendor 종속을 최소화함'],
               p27))

# ─────────────────────────────────────────────────────────── P28
INF = [('Kubernetes', '기존 Cluster·Namespace', 'Agent·Workspace·Batch·Integration Worker 순차 증설'),
       ('GPU Model Serving', '공용 GPU·vLLM', '운영 2 Replica + 비운영 1 Capacity, 모델·동시성 측정 후 확정'),
       ('Search', '기존 Elasticsearch', '전사 문서·EDM 인덱스 1~3TB 단위 증분'),
       ('PostgreSQL', '기존 HA DB 또는 신규 논리 DB', 'Registry·Workspace·Knowledge·Evaluation Schema 확장'),
       ('Object Storage', '기존 EDM·S3 호환 저장소', '원문 복제 금지, 산출물·Trace Blob만 증분'),
       ('Network·IAM', '기존 API Gateway·SSO·KMS', 'Model·Tool 직접 노출 금지, Integration Zone 분리')]
tbl28 = ('<div class="tw"><table><colgroup><col style="width:21%"><col style="width:31%"><col></colgroup>'
         '<thead><tr><th>영역</th><th>공통 제공 — 고객 자산</th><th>단계별 확장</th></tr></thead><tbody>' +
         ''.join(f'<tr><td class="k">{a}</td><td>{b}</td><td>{c}</td></tr>' for a, b, c in INF) +
         '</tbody></table></div>')
SEG28 = [('고객 공용자산 제공', '기존 K8s · GPU · EDM · Search · IAM을 단계 사업비 없이 제공함', 'r'),
         ('단계 사업비 포함', '오픈소스 설치·구성·개발·시험·전환을 단계 사업비로 수행함', 'n'),
         ('별도 조달', 'GPU·Search Storage 증설은 1단계 부하시험 결과로 별도 조달함', 'o')]
seg28 = '<div class="segs">' + ''.join(
    f'<div class="seg {c}"><i>{a}</i><p>{b}</p></div>' for a, b, c in SEG28) + '</div>'
left28 = card('10억원 상한의 전제',
              '<div class="big"><b>물리 HW<br>신규 구매 제외</b><span>단계 사업비의 성립 조건</span></div>'
              + seg28, 'acc')
p28 = (f'<div class="gR grow">{left28}{card("공통 인프라와 단계별 확장", tbl28, "", "6개 영역")}</div>' +
       '<div class="co gn">용량 확정 입력값 — 동시 사용자 · 피크 QPS · Retrieval 수 · 문서·변경량 · Token · 응답시간 · 모델 Throughput</div>')
S.append(slide('p28', 'P28', '단계당 10억원 상한은 기존 K8s·GPU·EDM·Elasticsearch·IAM을 공용 자산으로 제공할 때 성립함', 47,
               ['단계 사업비에는 오픈소스 플랫폼 구축과 Application 개발을 포함하되 신규 GPU·대규모 Search Storage·전용 Cluster 구매는 포함하지 않음',
                '현재 EDM 분당 호출량만으로 물리 사양을 확정하지 않고 1단계의 부하·모델 Benchmark 결과로 인프라를 재산정함'],
               p28))

# ─────────────────────────────────────────────────────────── P29
OSS = [('Model Serving', 'vLLM', 'KServe — 모델·Replica 증가 시', '사용자에게 vLLM 직접 노출'),
       ('Agent', 'LangGraph Core', '다른 Framework는 업무별 예외', '상용 Agent Platform 종속'),
       ('Durable Workflow', 'Temporal OSS', '기존 BPM/Workflow 재사용 검토', 'LangGraph로 장기 승인까지 처리'),
       ('Search', '기존 Elasticsearch', 'OpenSearch — 전환 필요 시', 'Elasticsearch·OpenSearch 병행'),
       ('Context Vector', 'pgvector', '대규모 전용 Vector DB는 확산 후', '초기부터 Milvus·Qdrant 추가'),
       ('Policy', 'OPA', '기존 IAM Authorization 보완', 'Agent별 자체 권한'),
       ('Observability', 'OTel·Prometheus·Ragas', 'Langfuse OSS — 필요 시', '1단계부터 별도 HA 관측 Stack')]
tbl29 = ('<div class="tw"><table><colgroup><col style="width:17%"><col style="width:22%"><col style="width:31%"><col></colgroup>'
         '<thead><tr><th>역할</th><th>기본 표준 1개</th><th>조건부 대안</th><th>비권고</th></tr></thead><tbody>' +
         ''.join(f'<tr><td class="k">{a}</td><td class="gn">{b}</td><td>{c}</td><td class="no">{d}</td></tr>'
                 for a, b, c, d in OSS) + '</tbody></table></div>')
p29 = (kpi([('7개', '역할별 기본 표준 수', 'on'), ('1개', '역할당 허용 제품 수'),
            ('4종', '기존 자산 그대로 유지'), ('0종', '동일 목적 Engine 중복', 'gn')], 'k4') +
       f'<div class="grow" style="display:flex">{card("역할별 1개 기본 표준과 교체 가능한 인터페이스", tbl29, "acc", "7개 역할")}</div>' +
       '<div class="co">오픈소스 우선의 목적은 제품 수 확대가 아니라 라이선스 비용과 Vendor Lock-in을 낮추면서 운영 표준을 단순화하는 것임</div>')
S.append(slide('p29', 'P29', '오픈소스 우선은 제품 수 확대가 아니라 역할별 1개 표준과 교체 가능한 인터페이스를 의미함', 48,
               ['기존 Elasticsearch를 유지하면서 별도 Search·Vector 제품을 중복 도입하지 않고 PostgreSQL·pgvector는 개인·프로젝트 Context에 한정함',
                'LangGraph는 Agent State, Temporal은 Durable Workflow, Argo는 Batch에 사용하여 동일 목적의 Engine 중복을 방지함'],
               p29))

# ─────────────────────────────────────────────────────────── P30
STEPS = [('선정', ['공식 Repository·License 확인', 'Open-core 기능 경계 식별', '대체 가능한 Interface 설계']),
         ('반입', ['내부 Registry·Version Pin', 'SBOM·License·CVE Scan', 'Image Signature·Digest 고정']),
         ('배포', ['Non-root·Secret 분리', 'Network Policy·Allowlist', '개발·시험·운영 동일 Artifact']),
         ('운영', ['정기 Patch·EOL 관리', 'Critical CVE 긴급 배포', 'Audit·Trace 기존 SIEM 전송'])]
steps = '<div class="steps">' + ''.join(
    f'<div class="step"><div class="h"><i>{i+1}</i><b>{t}</b></div><div class="b">'
    '<div class="rail2">' + ''.join(f'<span>{x}</span>' for x in gg) + '</div></div></div>'
    for i, (t, gg) in enumerate(STEPS)) + '</div>'
bot30 = ('<div class="g2" style="flex:none;height:132px">' +
         card('Open-core 관리', tags(['LiteLLM Community', 'Langfuse OSS'], 'hi') +
              li(['Enterprise SSO·RBAC를 기본 예산에 가정하지 않음',
                  '기존 IAM·API Gateway·Audit으로 보완함'], 'li'), 'lite') +
         card('Agent·Tool 보안', tags(['MCP Registry', 'OPA', 'HITL', 'Promptfoo'], 'hi') +
              li(['승인된 Tool Allowlist만 노출함',
                  '고위험 Tool은 Preview·승인·전량 감사를 적용함'], 'li'), 'lite') + '</div>')
S.append(slide('p30', 'P30', '오픈소스 비용 절감은 공급망·라이선스·운영 책임을 내부화하므로 반입·버전·SBOM 통제가 필수임', 49,
               ['무료 사용 가능 여부와 운영에 필요한 Enterprise 기능을 분리하고, 특정 제품의 상용 기능이 핵심 통제점이 되지 않도록 설계함',
                '모델·Agent·MCP Tool은 사용자망에 직접 노출하지 않고 API Gateway·Policy·Registry·Audit 경로를 의무화함'],
               steps + bot30))

# ─────────────────────────────────────────────────────────── P31
LANE = [('단계', [f'{i}단계<br>{w}' for i, w in zip(range(1, 6), ['8.1억', '9.6억', '9.0억', '9.6억', '9.6억'])], 'on'),
        ('수행 기간', ['M1~M4', 'M5~M8', 'M9~M12', 'M13~M16', 'M17~M20'], ''),
        ('일정', None, 'bar'),
        ('대표 성과', ['RAG·Gateway', 'Agent·Tool', 'Workspace·Hub', '평가·운영', '업무 실행'], ''),
        ('외부 공수', ['27MM', '32MM', '30MM', '32MM', '32MM'], ''),
        ('Exit Gate', ['G1', 'G2', 'G3', 'G4', 'G5'], 'gt')]
lanes = '<div class="lanes">'
for lb, vals, cls in LANE:
    lanes += f'<div class="lane"><div class="lb">{lb}</div>'
    if vals is None:
        lanes += ''.join(f'<div class="bar s{i+1}"><i></i></div>' for i in range(5))
    else:
        lanes += ''.join(f'<div class="{cls}">{v}</div>' for v in vals)
    lanes += '</div>'
lanes += '</div>'
COL3 = [('외부 Core Team · 평균 7~8명', '단계당 상주',
         ['PM/Product', 'Solution·AI Architect', 'Backend·Platform 2',
          'AI·RAG 1~2', 'Front-end 1', 'DevOps·QA·Security 1~2']),
        ('고객 내부 · 단계별 4~7MM', '병행 투입',
         ['OLEDi PO', 'EDM·Search', 'IAM·Security', '업무 SME',
          'ERP·MES·PLM/QMS Owner', '운영·UAT']),
        ('레거시 연계 단계 선결조건', '5단계 일정 전제',
         ['원 시스템 API 제공', '테스트 환경 제공', '권한·계정 정의',
          '오류·취소 절차 정의', 'System Owner 승인'])]
team = '<div class="g3" style="flex:1;min-height:0">' + ''.join(
    f'<div class="c lite"><h4>{t}<u>{w}</u></h4><div class="b" style="padding:8px 9px">'
    '<div class="rail2">' + ''.join(f'<span>{x}</span>' for x in xs) +
    '</div></div></div>' for t, w, xs in COL3) + '</div>'

p31 = (kpi([('20개월', '순차 수행 기준', 'on'), ('18개월', '상세설계 조건부 선행 시', 'gn'),
            ('7~8명', '단계별 외부 Core Team'), ('4~7MM', '단계별 고객 내부 투입')], 'k4') +
       f'<div style="flex:none">{lanes}</div>' + team)
S.append(slide('p31', 'P31', '각 단계는 4개월·7~8명 Core Team으로 수행하고 고객 내부 4~7MM를 병행 투입함', 50,
               ['기본 순차 수행은 20개월이며 다음 단계 상세설계를 직전 단계 후반에 조건부 착수하면 약 18개월로 단축 가능함',
                '레거시 연계 단계는 고객 System Owner의 API·테스트환경·권한·오류·취소 절차 제공이 일정의 핵심 선결조건임'],
               p31))

# ─────────────────────────────────────────────────────────── P32
RATE = [('기존 기능 Tool화', '1~2MM', '0.3~0.6억'), ('조회 Connector', '2~4MM', '0.6~1.2억'),
        ('등록·수정 Transaction', '5~7MM', '1.5~2.1억'), ('승인·발주 고위험 실행', '7~10MM', '2.1~3.0억'),
        ('단순 업무 Agent', '2~4MM', '0.6~1.2억'), ('복합 Agent Workflow', '4~7MM', '1.2~2.1억')]
tbl32 = ('<div class="tw"><table><colgroup><col><col style="width:22%"><col style="width:24%"></colgroup>'
         '<thead><tr><th>추가 범위</th><th>공수</th><th>비용</th></tr></thead><tbody>' +
         ''.join(f'<tr><td class="k">{a}</td><td>{b}</td><td class="gn">{c}</td></tr>' for a, b, c in RATE) +
         '</tbody></table></div>')
def rail(items, cls=''):
    return f'<div class="rail2 {cls}">' + ''.join(f'<span>{x}</span>' for x in items) + '</div>'


left32 = ('<div class="g2" style="height:100%">' +
          card('단계비에 포함', rail(['Architecture·상세설계·개발', 'OSS 설치·구성·CI/CD',
                                '통합·보안·성능·UAT', '운영 전환·초기 안정화']), 'acc', '4개 항목') +
          card('별도·제외', rail(['신규 GPU·전용 K8s·대규모 Storage', '레거시 자체 API 신규 개발',
                              '전사 데이터 정비·온톨로지', '전사 Agent 일괄 개발·24×7 운영'], 'off'),
               'lite', '4개 항목') + '</div>')
p32 = (f'<div class="gL grow">{left32}'
       f'{card("계약서에 고정할 증분 단가 · 평균 3,000만원/MM", tbl32, "", "6개 유형")}</div>' +
       '<div class="co">각 단계의 Agent·Tool·Connector·Transaction 개수와 고객 선결조건을 수량으로 명시하지 않으면 10억원 상한은 유지되지 않음</div>')
S.append(slide('p32', 'P32', '단계별 10억원을 지키려면 포함·제외·증분 단가를 계약서에 수량으로 고정해야 함', 51,
               ['범위를 기능명으로만 정의하지 않고 Agent·Tool·Connector·Transaction·환경·평가 Dataset의 개수와 수용기준을 명시함',
                '추가 요청은 사전 합의된 MM 단가표로 변경관리하고, 물리 인프라와 원 시스템 개편을 구축비에 암묵적으로 포함하지 않음'],
               p32))

# ─────────────────────────────────────────────────────────── P33
NEXT = [('2단계', 'Agent·Tool 기반', '9.6억'), ('3단계', 'Workspace·Agent Hub', '9.0억'),
        ('4단계', 'Knowledge·Evaluation', '9.6억'), ('5단계', '대표 업무 실행', '9.6억')]
nxt = '<div class="grail">' + ''.join(
    f'<div class="grr"><b>{a}</b><div><strong>{b}</strong></div><em>{c}</em></div>' for a, b, c in NEXT) + '</div>'
SEG33 = [('사용자 가치', '통합 대화·EDM RAG·권한·Citation 품질을 개선함', 'n'),
         ('공통 기반', 'vLLM·LiteLLM·OTel·평가 기반을 공통 자산으로 확보함', 'n'),
         ('판정 시점', '4개월 후 G1에서 2단계 Go·Stop을 판정함', 'o')]
seg33 = '<div class="segs">' + ''.join(
    f'<div class="seg {c}"><i>{a}</i><p>{b}</p></div>' for a, b, c in SEG33) + '</div>'
left33 = card('즉시 승인',
              '<div class="big gn"><b>1단계 · 8.1억원</b><span>27MM · 4개월 · G1 판정 후 2단계 결정</span></div>'
              + seg33, 'acc')
FOUR = [('유지', ['OLEDi UI', 'IAM', 'EDM', 'Elasticsearch', 'GPU'], 're'),
        ('공통화', ['Gateway', 'Registry', 'Policy', 'Audit'], 'hi'),
        ('단계화', ['기능+기반', 'Exit Gate', '독립 발주'], 'hi'),
        ('통제', ['원천 권한', '지식 승인', 'HITL', '전량 감사'], 'hi')]
four = ('<div class="g4" style="flex:none;height:104px">' +
        ''.join(card(t, tags(g, c), 'lite') for t, g, c in FOUR) + '</div>')
p33 = (f'<div class="gL grow">{left33}{card("선택적 확장 · Gate 통과 시에만 발주", nxt, "", "37.8억원")}</div>' +
       four + '<div class="co gn">최종 의사결정 — 1단계 8.1억원을 우선 착수하고, 성과가 입증된 영역만 9~10억원 단위로 확장함</div>')
S.append(slide('p33', 'P33', '즉시 착수안은 1단계 8.1억원이며 이후 9~10억원 단위로 선택적으로 확장함', 52,
               ['대규모 플랫폼을 선투자하지 않고 현재 OLEDi의 가장 큰 문제인 대화·검색·권한·근거 품질부터 개선함',
                '공통 오픈소스 Golden Path를 재사용하면서 Agent·협업·지식·레거시 실행을 독립 사업으로 확장함'],
               p33))

open(os.path.join(OUT, 's5_slides.html'), 'w', encoding='utf-8').write('\n'.join(S))
print('slides:', len(S))
