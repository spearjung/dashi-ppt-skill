import { Panel } from './Common'

/** 캡처 품질 가이드(§13). 업로드 화면 하단에 상시 표시한다. */
const RECOMMENDED = [
  '전체 브라우저 화면보다 표 영역 중심으로 캡처',
  '표 제목·조회 기준일·조회 기간·필터 조건 포함',
  'WBS Code 열이 잘리지 않도록 캡처',
  '열 제목·합계 행 포함',
  '금액 단위(원·천원·백만원) 표시 포함',
  '가로 스크롤 표는 여러 장으로 나누되 WBS Code 열 중복 포함',
  '확대율 일정 유지, 커서·팝업이 숫자를 가리지 않게 처리',
]

const AVOID = [
  '숫자가 잘린 화면',
  '표 제목이 없는 일부 행만 캡처',
  '합계와 세부행이 다른 화면에 있으나 연결 표시가 없는 경우',
  '동일 화면 다중 업로드',
  '단위 미표시 캡처',
  '여러 프로젝트 혼재이나 프로젝트명 없는 화면',
]

export function QualityGuide() {
  return (
    <Panel title="캡처 품질 가이드" hint="판독 정확도를 좌우합니다">
      <div className="grid cols-2">
        <table>
          <thead>
            <tr>
              <th>권장</th>
            </tr>
          </thead>
          <tbody>
            {RECOMMENDED.map((item) => (
              <tr key={item}>
                <td className="small">{item}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <table>
          <thead>
            <tr>
              <th>지양</th>
            </tr>
          </thead>
          <tbody>
            {AVOID.map((item) => (
              <tr key={item}>
                <td className="small">{item}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Panel>
  )
}
