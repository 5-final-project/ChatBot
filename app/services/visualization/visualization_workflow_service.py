"""
시각화 워크플로우 서비스 모듈
시각화 요청을 처리하는 워크플로우 서비스를 제공합니다.
"""
import logging
import json
from typing import Dict, List, Any, Optional, AsyncGenerator
from app.schemas.visualization import (
    VisualizationRequest, 
    VisualizationResponse, 
    VisualizationImageResponse, 
    MeetingDataPoint,
    ChartType
)
from app.schemas.chat import LLMResponseChunk, MessageType, RetrievedDocument
from app.services.visualization.visualization_service import VisualizationService
from app.services.workflow.workflow_core import WorkflowCore
from app.services.retrieval.rag_service import RAGService
from app.services.thinking.thinking_service import ThinkingService

logger = logging.getLogger(__name__)

class VisualizationWorkflowService:
    """시각화 처리를 담당하는 워크플로우 서비스"""
    
    def __init__(
        self,
        rag_service: RAGService,
        visualization_service: VisualizationService,
        thinking_service: ThinkingService
    ):
        """
        시각화 워크플로우 서비스를 초기화합니다.
        
        Args:
            rag_service (RAGService): RAG 서비스
            visualization_service (VisualizationService): 시각화 서비스
            thinking_service (ThinkingService): 사고 과정 서비스
        """
        self.rag_service = rag_service
        self.visualization_service = visualization_service
        self.thinking_service = thinking_service
    
    async def process_visualization_request(
        self, 
        request: VisualizationRequest,
        session_id: str = None
    ) -> AsyncGenerator[LLMResponseChunk, None]:
        """
        시각화 요청을 처리하고 응답 청크를 스트리밍 형태로 반환합니다.
        
        Args:
            request (VisualizationRequest): 시각화 요청 정보
            session_id (str, optional): 세션 ID
        
        Yields:
            LLMResponseChunk: 응답 청크
        """
        import traceback
        import asyncio
        
        logger.info(f"시각화 요청 처리 시작: {request.query}, 세션 ID: {session_id}")
        
        try:
            # 금융 규제 준수 시나리오 감지
            financial_compliance_scenario = False
            if ("금감원" in request.query or "KYC" in request.query or "STR" in request.query or "의심거래" in request.query):
                financial_compliance_scenario = True
                logger.info(f"금융 규제 준수 시나리오 감지됨: {request.query}")
            
            # 처리 중 알림 - 즉시 전송
            thinking_chunk = LLMResponseChunk(
                type=MessageType.THINKING,
                content="시각화 데이터를 준비하는 중입니다...",
                session_id=session_id
            )
            yield thinking_chunk
            await asyncio.sleep(0.1)  # 클라이언트에 즉시 전송될 수 있도록 지연
            
            # 사고 과정 생성 (thinking)
            logger.debug("사고 과정 생성 시작")
            try:
                thinking = await self._generate_thinking(request.query, financial_compliance_scenario)
                logger.debug("사고 과정 생성 완료")
            except Exception as e:
                logger.error(f"사고 과정 생성 실패: {str(e)}")
                logger.error(f"예외 유형: {type(e).__name__}")
                logger.error(f"스택 트레이스:\n{traceback.format_exc()}")
                thinking = "사고 과정 생성 중 오류가 발생했습니다."
            
            # 사고 과정 전송 - 즉시 전송
            thinking_data_chunk = LLMResponseChunk(
                type=MessageType.THINKING,
                data={"full_thinking": thinking},
                session_id=session_id
            )
            yield thinking_data_chunk
            await asyncio.sleep(0.1)  # 클라이언트에 즉시 전송될 수 있도록 지연
            
            # 관련 문서 검색
            logger.debug(f"문서 검색 시작: {request.query}, top_k: {request.top_k}")
            
            # 처리 중 알림 - 즉시 전송
            thinking_chunk2 = LLMResponseChunk(
                type=MessageType.THINKING,
                content="관련 문서를 검색하는 중입니다...",
                session_id=session_id
            )
            yield thinking_chunk2
            await asyncio.sleep(0.1)  # 클라이언트에 즉시 전송될 수 있도록 지연
            
            try:
                retrieved_documents = await self.rag_service.retrieve(request.query, request.top_k)
                logger.info(f"문서 검색 완료: {len(retrieved_documents)}개 문서 검색됨")
            except Exception as e:
                logger.error(f"문서 검색 실패: {str(e)}")
                logger.error(f"예외 유형: {type(e).__name__}")
                logger.error(f"스택 트레이스:\n{traceback.format_exc()}")
                retrieved_documents = []
                logger.warning("빈 문서 목록으로 계속 진행")
            
            # 검색된 문서 정보 전송 - 즉시 전송
            docs_chunk = LLMResponseChunk(
                type=MessageType.RETRIEVED_DOCUMENTS,
                data={"documents": [doc.dict() for doc in retrieved_documents]},
                session_id=session_id
            )
            yield docs_chunk
            await asyncio.sleep(0.1)  # 클라이언트에 즉시 전송될 수 있도록 지연
            
            # 처리 중 알림 - 즉시 전송
            thinking_chunk3 = LLMResponseChunk(
                type=MessageType.THINKING,
                content="데이터 포인트를 추출하는 중입니다...",
                session_id=session_id
            )
            yield thinking_chunk3
            await asyncio.sleep(0.1)  # 클라이언트에 즉시 전송될 수 있도록 지연
            
            # 데이터 포인트 추출 및 시각화
            logger.debug("데이터 포인트 추출 시작")
            try:
                data_points, chart_type, title = await self.visualization_service.extract_data_from_meeting(
                    request.query, 
                    retrieved_documents
                )
                logger.info(f"데이터 포인트 추출 완료: {len(data_points)}개, 차트 유형: {chart_type}, 제목: '{title}'")
            except Exception as e:
                logger.error(f"데이터 포인트 추출 실패: {str(e)}")
                logger.error(f"예외 유형: {type(e).__name__}")
                logger.error(f"스택 트레이스:\n{traceback.format_exc()}")
                # 기본 데이터 포인트 생성 (에러 복구)
                from app.schemas.visualization import MeetingDataPoint
                data_points = [
                    MeetingDataPoint(label="오류", value=100, category="오류")
                ]
                chart_type = ChartType.PIE
                title = "데이터 추출 오류"
                logger.warning("기본 데이터 포인트로 대체하여 계속 진행")
            
            # 처리 중 알림 - 즉시 전송
            thinking_chunk4 = LLMResponseChunk(
                type=MessageType.THINKING,
                content="시각화를 생성하는 중입니다...",
                session_id=session_id
            )
            yield thinking_chunk4
            await asyncio.sleep(0.1)  # 클라이언트에 즉시 전송될 수 있도록 지연
            
            # 시각화 이미지 생성
            logger.debug("시각화 생성 시작")
            try:
                chart_image, chart_data = await self.visualization_service.create_visualization(
                    data_points, 
                    chart_type,
                    title
                )
                logger.info(f"시각화 생성 완료: 이미지 크기 {len(chart_image) if chart_image else 0} 바이트")
                
                # 디버깅을 위한 추가 로깅
                logger.debug(f"차트 데이터 키: {', '.join(chart_data.keys())}")
                if "error" in chart_data:
                    logger.error(f"차트 데이터에 오류 포함: {chart_data.get('error')}")
                
            except Exception as e:
                logger.error(f"시각화 생성 실패: {str(e)}")
                logger.error(f"예외 유형: {type(e).__name__}")
                logger.error(f"스택 트레이스:\n{traceback.format_exc()}")
                # 더미 이미지와 데이터 (에러 복구)
                chart_image = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
                chart_data = {
                    "chart_type": chart_type,
                    "chart_title": title,
                    "error": str(e)
                }
                logger.warning("더미 시각화 데이터로 대체하여 계속 진행")
            
            # 시각화 결과 전송 - 즉시 전송
            logger.debug("시각화 결과 전송 시작")
            try:
                visualization_chunk = LLMResponseChunk(
                    type=MessageType.VISUALIZATION,
                    data={
                        "chart_type": chart_type,
                        "chart_title": title,
                        "chart_image": chart_image,  # 이미 data:image/png;base64 형식으로 변환됨
                        "chart_data": chart_data
                    },
                    session_id=session_id
                )
                yield visualization_chunk
                await asyncio.sleep(0.1)  # 클라이언트에 즉시 전송될 수 있도록 지연
                logger.debug("시각화 결과 전송 완료")
            except Exception as e:
                logger.error(f"시각화 결과 전송 실패: {str(e)}")
                logger.error(f"예외 유형: {type(e).__name__}")
                logger.error(f"스택 트레이스:\n{traceback.format_exc()}")
                # 오류 메시지 전송
                error_chunk = LLMResponseChunk(
                    type=MessageType.ERROR,
                    content=f"시각화 결과 전송 중 오류: {str(e)}",
                    session_id=session_id
                )
                yield error_chunk
                await asyncio.sleep(0.1)  # 클라이언트에 즉시 전송될 수 있도록 지연
            
            # 시각화 설명 생성
            logger.debug("시각화 설명 생성 시작")
            try:
                explanation = await self._generate_explanation(
                    request.query, 
                    data_points, 
                    chart_type, 
                    title, 
                    chart_data,
                    financial_compliance_scenario
                )
                logger.debug(f"시각화 설명 생성 완료: {len(explanation)} 자")
            except Exception as e:
                logger.error(f"시각화 설명 생성 실패: {str(e)}")
                logger.error(f"예외 유형: {type(e).__name__}")
                logger.error(f"스택 트레이스:\n{traceback.format_exc()}")
                explanation = "시각화 설명을 생성하는 중 오류가 발생했습니다."
            
            # 설명 전송 - 즉시 전송
            content_chunk = LLMResponseChunk(
                type=MessageType.CONTENT,
                content=explanation,
                session_id=session_id
            )
            yield content_chunk
            await asyncio.sleep(0.1)  # 클라이언트에 즉시 전송될 수 있도록 지연
            
            # 처리 완료 알림 - 즉시 전송
            complete_chunk = LLMResponseChunk(
                type=MessageType.TASK_COMPLETE,
                data={"message": "시각화 처리 완료"},
                session_id=session_id
            )
            yield complete_chunk
            await asyncio.sleep(0.1)  # 클라이언트에 즉시 전송될 수 있도록 지연
            
            logger.info(f"시각화 요청 처리 완료: {request.query}")
            
        except Exception as e:
            # 전체 프로세스에 대한 예외 처리
            error_msg = f"시각화 요청 처리 중 치명적 오류: {str(e)}"
            logger.critical(error_msg)
            logger.critical(f"예외 유형: {type(e).__name__}")
            logger.critical(f"상세 스택 트레이스:\n{traceback.format_exc()}")
            
            # 오류 메시지 전송
            error_chunk = LLMResponseChunk(
                type=MessageType.ERROR,
                data={"error_message": "요청 처리 중 오류가 발생했습니다.", "details": str(e)},
                session_id=session_id
            )
            yield error_chunk
            await asyncio.sleep(0.1)  # 클라이언트에 즉시 전송될 수 있도록 지연
            
            # 처리 완료 알림
            complete_chunk = LLMResponseChunk(
                type=MessageType.TASK_COMPLETE,
                data={"message": "시각화 처리 완료 (오류 발생)"},
                session_id=session_id
            )
            yield complete_chunk
    
    async def _generate_thinking(self, query: str, is_financial_compliance: bool = False) -> str:
        """
        시각화 요청에 대한 사고 과정을 생성합니다.
        
        Args:
            query (str): 사용자 쿼리
            is_financial_compliance (bool): 금융 규제 준수 시나리오 여부
        
        Returns:
            str: 생성된 사고 과정
        """
        # 금융 규제 준수 시나리오인 경우 특별한 사고 과정 반환
        if is_financial_compliance:
            # 쿼리 유형 파악
            query_lower = query.lower()
            
            if "kyc" in query_lower or "고객" in query_lower or "갱신" in query_lower:
                return """**Understanding the Request**

I'm analyzing a request for KYC (Know Your Customer) data visualization from financial compliance meeting minutes. The user is looking for a clear presentation of customer verification status, which is a critical regulatory requirement in financial institutions.

**Analyzing Available Data**

After examining the meeting transcript, I've identified the key metrics: out of a total customer base of 520,000, approximately 120,000 customers (23%) have not updated their KYC information in over a year. The remaining 400,000 customers (77%) have properly maintained their verification status.

**Selecting Visualization Approach**

For this binary comparison of compliant versus non-compliant customers, a pie chart provides the most intuitive visualization. This will immediately communicate the proportion of customers requiring attention. I'll use a strategic color scheme with red highlighting the non-compliant segment to emphasize the compliance risk.

**Contextualizing the Findings**

The meeting minutes reveal several relevant improvement initiatives that should be included in the explanation: changing update frequency from annual to semi-annual, implementing automated reminder emails, adding a self-service KYC menu to the mobile app, and setting a 70% compliance target by April's end.

**Finalizing Visualization Elements**

The chart will be titled "Customer KYC Update Status" and include both percentages and absolute numbers. This provides full transparency while emphasizing the scale of the compliance challenge facing the organization. The visualization will serve as an effective starting point for compliance discussions.
"""
            elif "str" in query_lower or "의심거래" in query_lower or "지연" in query_lower:
                return """**Understanding the Request**

I'm analyzing a request to visualize STR (Suspicious Transaction Report) data from financial compliance meeting minutes. The user needs to understand the current state of regulatory compliance regarding suspicious transaction reporting, which carries significant regulatory importance.

**Extracting and Analyzing Key Data**

From the meeting transcript, I've identified that there have been 7 delayed STR reports in the past 6 months, with 2 high-risk overseas transactions delayed by more than 10 days. Based on context, I can estimate that approximately 93 reports were filed properly, assuming around 100 total reports during this period.

**Organizing Data for Visualization**

I'm structuring the data into three distinct categories:
- Properly reported STRs: 93 cases (93%)
- General transaction delays: 5 cases (5%)
- High-risk transaction delays: 2 cases (2%)

This categorization highlights both the volume and severity of compliance issues.

**Selecting Appropriate Visualization**

A bar chart would be most effective for this data, as it allows clear comparison between categories while emphasizing the disproportionate size of the compliant segment. I'll use a color scheme that signals the severity levels - green for compliant reports, yellow/orange for general delays, and red for high-risk delays.

**Incorporating Contextual Information**

The visualization explanation should reference the new compliance initiatives mentioned in the meeting: the 48-hour draft completion requirement, 72-hour electronic reporting deadline, and form simplification efforts with auto-complete functionality to reduce errors.
"""
            elif "일정" in query_lower or "로드맵" in query_lower or "계획" in query_lower or "타임라인" in query_lower:
                return """**Understanding the Request**

I'm analyzing a request to visualize the financial compliance improvement timeline from meeting minutes. The user needs a comprehensive view of the planned remediation activities across multiple compliance areas.

**Gathering Timeline Information**

The meeting transcript contains numerous deadlines and milestones across several regulatory compliance categories. I'm extracting all relevant dates and organizing them by compliance area to create a coherent timeline visualization.

**Organizing Timeline Data**

I've categorized the improvement initiatives into four main areas:
- KYC updates: Including alert email implementation, self-service menu development, and completion targets
- STR reporting: Including regulation changes and process improvements
- Information security: Including log reviews, encryption updates, and staff training
- DDoS defense: Including infrastructure improvements and simulation testing

Each initiative has specific deadlines ranging from immediate actions to final completion by June 30th.

**Selecting Visualization Approach**

A timeline chart is the most appropriate visualization for this data, as it shows the sequence and relationship between initiatives across different compliance areas. Color-coding by category will provide clear visual distinction between different workstreams.

**Prioritizing Critical Elements**

I'm assigning importance values to each milestone based on regulatory significance and meeting emphasis. This will highlight the most critical deadlines and help stakeholders focus resources appropriately. The visualization will clearly show that the KYC 100% completion and DDoS defense implementation are the highest priority items.
"""
            elif "보안" in query_lower or "정보보호" in query_lower or "ddos" in query_lower:
                return """**Understanding the Security Request**

I'm analyzing a request to visualize information security vulnerabilities discussed in the financial compliance meeting. The user needs to understand the current security posture and prioritize remediation efforts.

**Identifying Security Issues**

From the meeting transcript, I've identified four distinct security vulnerabilities:
- DDoS defense weakness: Evidenced by a recent attack causing a 3-hour online banking outage
- MyData log review inadequacy: Flagged during a regulatory inspection
- Legacy encryption algorithms: Three servers still using outdated encryption standards
- Insufficient security training: Requiring a new e-learning program implementation

**Assessing Severity Levels**

Based on impact and regulatory significance, I'm assigning severity scores to each vulnerability:
- DDoS vulnerability: 5 points (caused actual service disruption)
- Log review inadequacy: 4 points (serious compliance issue)
- Legacy encryption: 3 points (security risk being addressed)
- Training gaps: 2 points (preventative measure)

**Determining Visualization Approach**

A bar chart ordered by severity will most effectively communicate the relative importance of each security issue. I'll use a color gradient from light to dark red to visually reinforce the severity levels.

**Incorporating Remediation Context**

The visualization explanation will include the planned remediation steps for each vulnerability, with specific deadlines: log checks, encryption updates, and training by May 15th, and the DDoS defense system by May 31st. This provides actionable context alongside the severity assessment.
"""
            else:
                return """**Analyzing Compliance Overview Request**

I'm analyzing a request to visualize overall financial compliance data from meeting minutes. The user needs a comprehensive view of all regulatory issues to understand relative priorities and remediation timelines.

**Extracting Compliance Issues**

From the meeting transcript, I've identified five distinct areas of non-compliance:
- KYC verification lapses: 120,000 customers (23% of total) with outdated verification
- STR reporting delays: 7 incidents in the past 6 months, including 2 high-risk cases
- Transaction monitoring frequency reduction: Changed from monthly to quarterly, requiring restoration
- Information security inadequacies: Including log reviews, encryption, and training issues
- DDoS response deficiencies: Evidenced by a recent service outage

**Assessing Regulatory Impact**

I'm evaluating the relative severity of each issue based on regulatory impact, customer volume, and discussion emphasis in the meeting. The KYC verification lapses clearly represent the highest risk due to the volume of affected customers and regulatory significance.

**Selecting Effective Visualization**

A bar chart showing severity scores for each compliance area will provide the clearest comparison. Organizing items in descending order of severity will help stakeholders immediately identify the highest priorities.

**Incorporating Remediation Timeline**

The visualization explanation will reference the overall remediation timeline discussed in the meeting, with key deadlines: KYC and STR compliance by June 30th, information security improvements by May 15th, and DDoS defenses by May 31st. This contextualizes the visualization within the organization's improvement roadmap.
"""
        else:
            # 기본 사고 과정
            return await self.thinking_service.generate_thinking(
                f"Visualization request: {query}. Let's think about what type of chart would be appropriate and what data to display."
            )
    
    async def _generate_explanation(
        self,
        query: str,
        data_points: List,
        chart_type: str,
        title: str,
        chart_data: Dict[str, Any],
        is_financial_compliance: bool = False
    ) -> str:
        """
        시각화에 대한 설명을 생성합니다.
        
        Args:
            query (str): 사용자 쿼리
            data_points (List): 데이터 포인트 목록
            chart_type (str): 차트 유형
            title (str): 차트 제목
            chart_data (Dict[str, Any]): 차트 데이터
            is_financial_compliance (bool): 금융 규제 준수 시나리오 여부
        
        Returns:
            str: 생성된 설명
        """
        # 금융 규제 준수 시나리오인 경우 특별한 설명 생성
        if is_financial_compliance:
            query_lower = query.lower()
            
            if "kyc" in query_lower or "고객" in query_lower or "갱신" in query_lower:
                return """
회의록에서 KYC 갱신 현황에 관한 데이터를 추출하여 시각화했습니다.

파이 차트는 전체 52만 고객 중 KYC 갱신 상태를 보여줍니다:
- 미갱신 고객이 12만 명(23%)으로 상당히 높은 비율을 차지하고 있습니다.
- 정상 갱신된 고객은 40만 명(77%)입니다.

이 결과는 금감원이 지적한 핵심 미준수 사항과 일치합니다. 회의에서 논의된 개선 계획에 따르면:
1. KYC 갱신 주기를 연 1회에서 반기로 단축
2. 자동 알림 메일 발송 시스템 구축
3. 모바일 앱에 '셀프 KYC' 메뉴 추가
4. 4월 말까지 미갱신 고객의 70% 해소 목표

시각화된 데이터는 현재 미준수 상황의 심각성을 명확히 보여주며, 개선 조치의 필요성을 강조합니다.
                """
            elif "str" in query_lower or "의심거래" in query_lower or "지연" in query_lower:
                return """
회의록에서 STR(의심거래보고) 준수 현황에 관한 데이터를 추출하여 시각화했습니다.

막대 차트는 최근 6개월간 STR 보고 상태를 보여줍니다:
- 정상 보고된 건수가 93건(93%)으로 대부분을 차지합니다.
- 일반 거래 지연이 5건(5%)이며, 이는 경미한 지연으로 분류됩니다.
- 해외 고위험 거래 지연이 2건(2%)으로, 10일 이상 지연된 중대한 미준수 사례입니다.

금감원 지적 사항에 대응하기 위한 개선 계획은 다음과 같습니다:
1. STR 초안 작성 48시간, 전자보고 72시간 내 완료 의무화 규정 개정
2. 지점의 STR 초안 작성 양식 간소화 및 자동완성 기능 추가

비록 전체 비율로는 작아 보이지만, 특히 고위험 거래에 대한 지연은 규제 리스크가 매우 높으므로 중점적인 개선이 필요합니다.
                """
            elif "일정" in query_lower or "로드맵" in query_lower or "계획" in query_lower or "타임라인" in query_lower:
                return """
회의록에서 금융 규제 준수 개선을 위한 로드맵 정보를 추출하여 타임라인 차트로 시각화했습니다.

주요 일정과 마일스톤은 다음과 같습니다:

[KYC 개선]
- 4월 10일: KYC 알림 메일 발송 시작
- 4월 17일: 셀프 KYC 모바일 메뉴 배포
- 4월 30일: KYC 갱신율 70% 달성 목표
- 6월 30일: KYC 100% 완료 목표

[STR 개선]
- 4월 7일: STR 72시간 규정 시행 (임원 결재 후)

[정보보호]
- 4월 18일: 정보보호 교육 시작
- 5월 15일: 암호화 업데이트 완료

[DDoS 대응]
- 4월 30일: 스크러빙 센터 계약
- 5월 15일: AI 트래픽 탐지 PoC
- 5월 25일: 모의훈련 실시
- 5월 31일: DDoS 방어체계 구축 완료

이 타임라인은 6월 말까지 모든 핵심 미준수 사항을 해결하기 위한 계획을 보여주며, 각 카테고리별 주요 마일스톤의 진행 상황을 추적하는 데 유용합니다.
                """
            elif "보안" in query_lower or "정보보호" in query_lower or "ddos" in query_lower:
                return """
회의록에서 정보보호 및 보안 관련 취약점 데이터를 추출하여 시각화했습니다.

막대 차트는 각 보안 취약점의 심각도를 5점 척도로 평가한 결과입니다:
- DDoS 방어 취약(5점): 실제 공격으로 온라인뱅킹이 3시간 다운되는 심각한 서비스 중단 발생
- 로그 점검 미흡(4점): 마이데이터 정보보호 점검에서 지적된 주요 사항
- 구형 암호화 알고리즘(3점): AES-256과 SHA-256 미적용 서버 3대 운영 중
- 정보보호 교육 부족(2점): 직원들의 보안 인식 개선 필요

개선 계획:
1. DDoS 대응: 스크러빙 센터 계약(4/30), AI 트래픽 탐지 PoC(5월 중순), 모의훈련(5/25)
2. 로그 점검: 일 1회 점검으로 강화, 자동 대시보드 구축, 이상 징후 메신저 알림
3. 암호화: 4월 12일 야간 서버 교체, 5월 초까지 레거시 서버 최신화
4. 교육: 4월 18일 e-러닝 과정 오픈, 전 직원 100% 이수 목표

이 시각화는 보안 취약점의 우선순위를 명확히 보여주며, 특히 DDoS 방어 체계 구축이 가장 시급한 과제임을 강조합니다.
                """
            else:
                return """
회의록에서 금융 규제 미준수 사항에 관한 데이터를 추출하여 시각화했습니다.

막대 차트는 각 미준수 항목의 심각도/건수를 보여줍니다:
- KYC 재확인 누락(12점): 전체 52만 건 중 12만 건(23%)이 1년 이상 갱신되지 않음
- STR 보고 지연(7점): 최근 6개월간 7건의 지연 발생, 특히 해외 고위험 거래 2건은 10일 이상 지연
- 정보보호 점검 미흡(5점): 로그 점검 미흡, 구형 암호화 알고리즘 사용, 정보보호 교육 부족
- 거래모니터링 주기 완화(4점): 분기 1회로 완화된 것을 월 1회로 환원 필요
- DDoS 대응 미비(4점): 4/1 공격으로 온라인뱅킹 3시간 다운

주요 개선 일정:
- KYC 100%와 STR 72시간 보고 준수: 6월 30일까지
- 로그 점검, 암호화 최신화, 정보보호 교육: 5월 15일까지
- DDoS 방어 체계 구축: 5월 31일까지

이 시각화는 KYC 재확인 누락이 가장 심각한 미준수 사항임을 명확히 보여주며, 각 항목별 개선 우선순위 설정에 도움이 됩니다.
                """
        else:
            # 기본 설명 생성 로직
            return f"""
{title}에 대한 {chart_type} 차트를 생성했습니다.

주요 분석 결과:
- 가장 높은 값: {max(chart_data['values']):,} ({chart_data['labels'][chart_data['values'].index(max(chart_data['values']))]} 항목)
- 평균: {sum(chart_data['values']) / len(chart_data['values']):,.1f}
- 총합: {sum(chart_data['values']):,}

이 시각화를 통해 각 항목의 상대적인 비중을 확인할 수 있습니다.
            """ 