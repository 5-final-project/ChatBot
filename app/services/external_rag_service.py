import httpx
from typing import List, Optional, Dict, Any
import logging
import json
import os

from app.core.config import settings
from app.schemas.chat import RetrievedDocument

logger = logging.getLogger(__name__)

class ExternalRAGService:
    def __init__(self):
        # 오픈서치 API URL 설정
        self.base_url = os.environ.get("OPENSEARCH_API_URL", "https://team5opensearch.ap.loclx.io")
        self.timeout = 500.0  # 요청 타임아웃 설정 (초)
        self.search_endpoint = "/search/hybrid-reranked"  # 하이브리드 검색 엔드포인트
        # TODO: 실제 사용할 OpenSearch 인덱스 이름을 설정에서 가져오거나 상수로 정의하는 것을 고려
        self.default_search_indices = ["documents"] # 기본 검색 인덱스
        logger.info(f"오픈서치 API URL 설정: {self.base_url}, 기본 검색 인덱스: {self.default_search_indices}")

    async def search_documents(
        self,
        query: str,
        search_in_meeting_only: Optional[bool] = False,
        document_ids: Optional[List[str]] = None,
        top_k: int = 5
    ) -> List[RetrievedDocument]:
        """
        오픈서치 API를 통해 하이브리드 검색을 수행합니다.
        크로스 인코더 재정렬을 적용한 검색 결과를 반환합니다.
        
        Args:
            query (str): 검색할 질의
            search_in_meeting_only (bool, optional): 회의록만 검색할지 여부. 기본값은 False
            document_ids (List[str], optional): 특정 문서만 검색할 경우 문서 ID 목록
            top_k (int, optional): 반환할 결과 수. 기본값은 5
        
        Returns:
            List[RetrievedDocument]: 검색된 문서 목록
        """
        if not self.base_url:
            logger.warning("오픈서치 API URL이 설정되지 않았습니다. 검색을 건너뚵니다.")
            return []

        # 하이브리드 검색 요청 페이로드 구성
        payload = {
            "query": query,
            "top_k": top_k,
            "indices": ["master_documents"]
        }
        
        # document_ids가 있는 경우 필터링 정보 추가 (오픈서치 API가 지원하는 경우)
        if document_ids:
            payload["filter"] = {"document_ids": document_ids}
            logger.info(f"특정 문서 ID 필터 추가: {document_ids}")
        
        # 회의록 관련 검색 필터 추가 (오픈서치 API가 지원하는 경우)
        # if search_in_meeting_only:
        #     if "filter" not in payload:
        #         payload["filter"] = {}
        #     payload["filter"]["document_type"] = "meeting"  # 회의록 문서 타입
        #     logger.info("회의록 문서만 검색하도록 필터 추가")

        # 요청 URL 구성
        request_url = f"{self.base_url}{self.search_endpoint}"
        
        logger.info(f"오픈서치 API 검색 요청: URL='{request_url}', 질의='{query}', 결과수={top_k}, 인덱스={payload['indices']}")
        logger.debug(f"요청 페이로드: {json.dumps(payload, ensure_ascii=False)}")

        try:
            # 비동기 HTTP 클라이언트로 요청 전송
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(request_url, json=payload)
                response.raise_for_status()  # HTTP 오류 발생 시 예외 발생
                
                response_data = response.json()
                logger.debug(f"오픈서치 API 응답 수신: {json.dumps(response_data, ensure_ascii=False)[:500]}...")
                
                # 검색 결과 처리
                retrieved_docs: List[RetrievedDocument] = []
                if "results" in response_data and isinstance(response_data["results"], list):
                    for item in response_data["results"]:
                        # 오픈서치 API 응답 형식에 맞게 처리
                        metadata = item.get("metadata", {})
                        doc_id = metadata.get("doc_id", "unknown_doc_id")
                        doc_name = metadata.get("doc_name", "")
                        source = metadata.get("source", "")
                        page_content = item.get("page_content", "")
                        score = item.get("score", 0.0)
                        
                        # 추가 정보가 있는 경우 메타데이터에 포함
                        additional_metadata = {}
                        if doc_name:
                            additional_metadata["title"] = doc_name
                        if source:
                            additional_metadata["source"] = source
                        
                        # RetrievedDocument 객체 생성
                        retrieved_docs.append(
                            RetrievedDocument(
                                source_document_id=doc_id,
                                content_chunk=page_content,
                                score=score,
                                metadata=additional_metadata
                            )
                        )
                        
                logger.info(f"{len(retrieved_docs)}개의 문서를 오픈서치 API에서 검색했습니다.")
                return retrieved_docs

        except httpx.HTTPStatusError as e:
            logger.error(f"오픈서치 API HTTP 오류: {e.response.status_code} - {e.response.text[:500]}...")
        except httpx.RequestError as e:
            logger.error(f"오픈서치 API 요청 오류: {type(e).__name__} - {e}") 
        except json.JSONDecodeError as e:
            logger.error(f"오픈서치 API 응답 JSON 디코딩 오류: {e}. 위치: {e.lineno}:{e.colno}")
        except Exception as e:
            logger.error(f"오픈서치 API 처리 중 오류: {e}", exc_info=True)
        
        # 오류 발생 시 빈 결과 반환
        return []
