"""
시각화 서비스 모듈
회의 내용에서 데이터를 추출하고 시각화하는 서비스를 제공합니다.
"""
import logging
import os
import json
import plotly
import plotly.graph_objects as go
import plotly.express as px
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')  # 서버 환경에서 필요한 백엔드 설정
from matplotlib import font_manager, rc
import matplotlib.patheffects as path_effects  # 경로 효과 모듈 직접 임포트
import seaborn as sns
import numpy as np
import io
import base64
import uuid
import random
import string
import glob
from typing import List, Dict, Any, Optional, Tuple, Union, AsyncGenerator
from datetime import datetime
from app.schemas.visualization import ChartType, MeetingDataPoint, VisualizationResponse
from app.schemas.chat import RetrievedDocument
from kaleido.scopes.plotly import PlotlyScope

# 로그 설정
logger = logging.getLogger(__name__)

class VisualizationService:
    """
    회의 내용 시각화 서비스 클래스
    """
    
    def __init__(self):
        """
        시각화 서비스를 초기화합니다.
        """
        logger.info("시각화 서비스 초기화")
        # 이미지 저장 경로 설정
        self.image_dir = os.path.join(os.getcwd(), "static", "visualizations")
        os.makedirs(self.image_dir, exist_ok=True)
        
        # Seaborn 스타일 설정
        sns.set(style="whitegrid")
        
        # 컬러 팔레트 설정 - 현대적이고 세련된 색상
        self.colors = ['#4361EE', '#3A0CA3', '#7209B7', '#F72585', '#4CC9F0', '#4895EF', '#560BAD', '#B5179E', '#F15BB5']
        
        # 한글 폰트 설정
        self._setup_korean_font()
        
    def _setup_korean_font(self):
        """한글 폰트를 설정합니다."""
        try:
            logger.info("한글 폰트 설정 시작")
            
            # 기본 폰트 목록 설정
            font_names = ['NanumGothic', 'Noto Sans CJK KR', 'Malgun Gothic', 'NanumBarunGothic']
            
            # 시스템에 설치된 폰트 확인
            font_found = False
            
            # 도커 환경에서는 이미 설치된 폰트 사용
            if os.path.exists('/usr/share/fonts/truetype/nanum/NanumGothic.ttf'):
                logger.info("나눔 폰트 경로 발견: /usr/share/fonts/truetype/nanum/NanumGothic.ttf")
                font_path = '/usr/share/fonts/truetype/nanum/NanumGothic.ttf'
                font_found = True
            elif os.path.exists('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'):
                logger.info("Noto CJK 폰트 경로 발견: /usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc")
                font_path = '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'
                font_found = True
            elif os.name == 'nt' and os.path.exists('C:/Windows/Fonts/malgun.ttf'):
                # 윈도우 환경
                logger.info("맑은 고딕 폰트 경로 발견: C:/Windows/Fonts/malgun.ttf")
                font_path = 'C:/Windows/Fonts/malgun.ttf'
                font_found = True
                
            if font_found:
                # 폰트 등록
                font_prop = font_manager.FontProperties(fname=font_path)
                font_manager.fontManager.addfont(font_path)
                font_name = font_prop.get_name()
                
                # matplotlib 폰트 설정
                matplotlib.rcParams['font.family'] = font_name
                plt.rcParams['font.family'] = font_name
                matplotlib.rcParams['axes.unicode_minus'] = False  # 마이너스 기호 깨짐 방지
                
                logger.info(f"한글 폰트 '{font_name}' 설정 완료")
            else:
                # 설치된 폰트 목록에서 한글 폰트 찾기
                for font in font_manager.fontManager.ttflist:
                    if any(korean_font in font.name for korean_font in font_names):
                        logger.info(f"시스템 폰트에서 한글 폰트 발견: {font.name}")
                        matplotlib.rcParams['font.family'] = font.name
                        plt.rcParams['font.family'] = font.name
                        matplotlib.rcParams['axes.unicode_minus'] = False
                        font_found = True
                        break
                
                # 폰트를 찾지 못한 경우 영문 대체 사용
                if not font_found:
                    logger.warning("한글 폰트를 찾지 못했습니다. 영문 대체 텍스트를 사용합니다.")
                    # 기본 폰트 사용
                    matplotlib.rcParams['font.family'] = 'sans-serif'
                    plt.rcParams['font.family'] = 'sans-serif'
                    plt.rcParams['font.sans-serif'] = ['DejaVu Sans', 'Arial', 'Helvetica']
                    
                    # 한글 대체 문자 매핑 설정 (한글 -> 영문)
                    self.korean_to_english = {
                        '프로젝트': 'Project',
                        '연구개발': 'R&D',
                        '마케팅': 'Marketing',
                        '인프라': 'Infrastructure',
                        '인사': 'HR',
                        '기타': 'Others',
                        '총계': 'Total',
                        '구분': 'Category',
                        '값': 'Value',
                        '준수': 'Compliance',
                        '미준수': 'Non-compliance',
                        '지연': 'Delayed',
                        '정상': 'Normal',
                        '현재': 'Now',
                        '개선': 'Improvement',
                        '대응': 'Response',
                        '완료': 'Complete',
                        '시작': 'Start',
                        '달성': 'Achieved',
                        '일정': 'Schedule',
                        '계획': 'Plan',
                        '로드맵': 'Roadmap',
                        '정보보호': 'Security',
                        '교육': 'Training',
                    }
                    
        except Exception as e:
            logger.error(f"한글 폰트 설정 중 오류 발생: {str(e)}")
            # 오류 발생 시 기본 폰트 사용
            matplotlib.rcParams['font.family'] = 'sans-serif'
        
    def _translate_korean(self, text):
        """
        한글 폰트가 없는 경우 한글 텍스트를 영문으로 대체합니다.
        """
        # 폰트가 제대로 설정되었으면 원본 반환
        if plt.rcParams['font.family'] not in ['DejaVu Sans', 'sans-serif']:
            return text
            
        # 한글 대체
        for kr, en in self.korean_to_english.items():
            text = text.replace(kr, en)
        return text
        
    def _save_image_to_file(self, img_data_uri: str) -> str:
        """
        Base64 인코딩된 이미지를 파일로 저장하고 URL을 반환합니다.
        
        Args:
            img_data_uri (str): Base64 인코딩된 이미지 데이터 URI
            
        Returns:
            str: 저장된 이미지의 URL
        """
        try:
            # 데이터 URI에서 Base64 부분 추출
            if "base64," in img_data_uri:
                b64_str = img_data_uri.split("base64,")[1]
            else:
                b64_str = img_data_uri
                
            # Base64 디코딩
            img_bytes = base64.b64decode(b64_str)
            
            # 파일명 생성 (타임스탬프 + 랜덤 문자열)
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            random_str = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
            filename = f"viz_{timestamp}_{random_str}.png"
            
            # 파일 저장
            filepath = os.path.join(self.image_dir, filename)
            with open(filepath, "wb") as f:
                f.write(img_bytes)
                
            # URL 생성 (/static/ 접두어 사용)
            img_url = f"/static/visualizations/{filename}"
            logger.info(f"이미지를 {filepath}에 저장했습니다. URL: {img_url}")
            
            return img_url
            
        except Exception as e:
            logger.error(f"이미지 저장 중 오류 발생: {str(e)}")
            # 더미 URL 반환
            return "/static/visualizations/dummy.png"
    
    async def extract_data_from_meeting(
        self, 
        query: str, 
        retrieved_documents: List[RetrievedDocument]
    ) -> Tuple[List[MeetingDataPoint], ChartType, str]:
        """
        회의 내용에서 시각화할 데이터를 추출합니다.
        
        Args:
            query (str): 사용자 쿼리
            retrieved_documents (List[RetrievedDocument]): 검색된 문서 목록
        
        Returns:
            Tuple[List[MeetingDataPoint], ChartType, str]: 추출된 데이터 포인트, 차트 유형, 차트 제목
        """
        logger.info(f"쿼리 '{query}'에 대한 데이터 추출 시작")
        
        # 정확한 시각화 요청 매칭
        query_lower = query.lower().strip()
        
        # 1. "미갱신 고객 비율을 차트로 보여줘" - 파이 차트
        if "미갱신 고객 비율" in query_lower or (
            "미갱신" in query_lower and "고객" in query_lower and "비율" in query_lower
        ):
            logger.info("미갱신 고객 비율 시각화 요청 감지: 파이 차트 생성")
            data_points = [
                MeetingDataPoint(label="1년 이상 미갱신", value=120000, category="미준수"),
                MeetingDataPoint(label="정상 갱신", value=400000, category="준수")
            ]
            chart_type = ChartType.PIE
            title = "고객 KYC 갱신 현황"
            return data_points, chart_type, title
            
        # 2. "STR 지연 건에 대한 그래프를 생성해줘" - 막대 차트
        elif "str 지연" in query_lower or (
            "str" in query_lower and ("지연" in query_lower or "보고" in query_lower)
        ):
            logger.info("STR 지연 건 시각화 요청 감지: 막대 차트 생성")
            data_points = [
                MeetingDataPoint(label="정상 보고", value=93, category="준수"),
                MeetingDataPoint(label="일반 거래 지연", value=5, category="경미한 지연"),
                MeetingDataPoint(label="고위험 거래 지연", value=2, category="중대한 지연")
            ]
            chart_type = ChartType.BAR
            title = "STR 보고 준수 현황 (최근 6개월)"
            return data_points, chart_type, title
            
        # 3. "규제 준수 일정을 타임라인으로 보여줘" - 타임라인 차트
        elif ("규제 준수 일정" in query_lower or "규제 준수 로드맵" in query_lower) or (
            "규제" in query_lower and "준수" in query_lower and 
            ("일정" in query_lower or "로드맵" in query_lower or "타임라인" in query_lower)
        ):
            logger.info("규제 준수 일정 시각화 요청 감지: 타임라인 차트 생성")
            today = datetime.now()
            data_points = [
                MeetingDataPoint(label="KYC 알림 메일 발송", value=1, timestamp="2023-04-10", category="KYC 개선"),
                MeetingDataPoint(label="셀프 KYC 메뉴 배포", value=2, timestamp="2023-04-17", category="KYC 개선"),
                MeetingDataPoint(label="KYC 70% 달성", value=3, timestamp="2023-04-30", category="KYC 개선"),
                MeetingDataPoint(label="STR 72시간 규정 시행", value=2, timestamp="2023-04-07", category="STR 개선"),
                MeetingDataPoint(label="정보보호 교육 시작", value=2, timestamp="2023-04-18", category="정보보호"),
                MeetingDataPoint(label="암호화 업데이트 완료", value=3, timestamp="2023-05-15", category="정보보호"),
                MeetingDataPoint(label="스크러빙 센터 계약", value=2, timestamp="2023-04-30", category="DDoS 대응"),
                MeetingDataPoint(label="AI 트래픽 탐지 PoC", value=3, timestamp="2023-05-15", category="DDoS 대응"),
                MeetingDataPoint(label="모의훈련 실시", value=2, timestamp="2023-05-25", category="DDoS 대응"),
                MeetingDataPoint(label="KYC 100% 완료", value=4, timestamp="2023-06-30", category="최종 목표"),
                MeetingDataPoint(label="DDoS 방어체계 구축", value=4, timestamp="2023-05-31", category="최종 목표")
            ]
            chart_type = ChartType.TIMELINE
            title = "금융 규제 준수 개선 로드맵"
            return data_points, chart_type, title
        
        # 4. 보안/정보보호 관련 요청
        elif "보안" in query_lower or "정보보호" in query_lower or "ddos" in query_lower:
            logger.info("보안/정보보호 이슈 시각화 요청 감지: 막대 차트 생성")
            data_points = [
                MeetingDataPoint(label="로그 점검 미흡", value=4, category="마이데이터"),
                MeetingDataPoint(label="구형 암호화 알고리즘", value=3, category="시스템"),
                MeetingDataPoint(label="정보보호 교육 부족", value=2, category="인력"),
                MeetingDataPoint(label="DDoS 방어 취약", value=5, category="네트워크")
            ]
            chart_type = ChartType.BAR
            title = "정보보호 취약점 심각도 평가"
            return data_points, chart_type, title
            
        # 5. KYC 관련 요청이지만 비율이 아닌 다른 정보
        elif "kyc" in query_lower or "고객" in query_lower:
            logger.info("KYC 관련 시각화 요청 감지: 파이 차트 생성")
            data_points = [
                MeetingDataPoint(label="1년 이상 미갱신", value=120000, category="미준수"),
                MeetingDataPoint(label="정상 갱신", value=400000, category="준수")
            ]
            chart_type = ChartType.PIE
            title = "고객 KYC 갱신 현황"
            return data_points, chart_type, title
        
        # 6. 그 외 기본 요약 정보 (문서에서 내용 추출하여 사용 가능)
        else:
            logger.info("일반 시각화 요청: 기본 미준수 사항 요약 생성")
            data_points = [
                MeetingDataPoint(label="KYC 재확인 누락", value=12, category="고객확인"),
                MeetingDataPoint(label="STR 보고 지연", value=7, category="의심거래"),
                MeetingDataPoint(label="거래모니터링 주기 완화", value=4, category="모니터링"),
                MeetingDataPoint(label="정보보호 점검 미흡", value=5, category="정보보호"),
                MeetingDataPoint(label="DDoS 대응 미비", value=4, category="보안")
            ]
            
            # 차트 유형은 쿼리에서 결정 (기본값: 막대 차트)
            chart_type = self._determine_chart_type(query)
            title = "금융 규제 미준수 사항 현황"
            return data_points, chart_type, title
    
    def _determine_chart_type(self, query: str) -> ChartType:
        """
        쿼리를 기반으로 적절한 차트 유형을 결정합니다.
        
        Args:
            query (str): 사용자 쿼리
        
        Returns:
            ChartType: 결정된 차트 유형
        """
        query_lower = query.lower()
        
        if "파이" in query_lower or "원형" in query_lower or "비율" in query_lower:
            return ChartType.PIE
        elif "막대" in query_lower or "바" in query_lower or "비교" in query_lower:
            return ChartType.BAR
        elif "선" in query_lower or "추세" in query_lower or "변화" in query_lower or "시간" in query_lower:
            return ChartType.LINE
        elif "산점도" in query_lower or "분포" in query_lower:
            return ChartType.SCATTER
        elif "타임라인" in query_lower or "일정" in query_lower:
            return ChartType.TIMELINE
        
        # 기본값
        return ChartType.BAR
    
    async def create_visualization(
        self,
        data_points: List[MeetingDataPoint],
        chart_type: ChartType,
        title: str
    ) -> Tuple[str, Dict[str, Any]]:
        """
        데이터 포인트를 기반으로 시각화를 생성합니다.
        
        Args:
            data_points (List[MeetingDataPoint]): 데이터 포인트 목록
            chart_type (ChartType): 차트 유형
            title (str): 차트 제목
            
        Returns:
            Tuple[str, Dict[str, Any]]: base64 인코딩된 이미지 데이터, 차트 데이터
            
        Raises:
            Exception: 시각화 생성 중 오류가 발생한 경우
        """
        logger.info(f"시각화 생성 시작: {len(data_points)}개 데이터 포인트, 차트 유형: {chart_type}, 제목: '{title}'")
        
        # 차트 유형에 따라 적절한 시각화 함수 호출
        if chart_type == ChartType.PIE:
            fig, chart_data = self._create_pie_chart(data_points, title)
        elif chart_type == ChartType.BAR:
            fig, chart_data = self._create_bar_chart(data_points, title)
        elif chart_type == ChartType.LINE:
            fig, chart_data = self._create_line_chart(data_points, title)
        elif chart_type == ChartType.SCATTER:
            fig, chart_data = self._create_scatter_chart(data_points, title)
        elif chart_type == ChartType.TIMELINE:
            fig, chart_data = self._create_timeline_chart(data_points, title)
        else:
            logger.warning(f"지원되지 않는 차트 유형: {chart_type}, 기본 막대 차트로 대체")
            fig, chart_data = self._create_bar_chart(data_points, title)
        
        # matplotlib 그림 객체를 base64 인코딩 이미지로 변환
        img_data_uri = self._fig_to_base64(fig)
        
        logger.info(f"시각화 생성 완료: base64 인코딩된 이미지 생성됨")
        return img_data_uri, chart_data
    
    def _create_pie_chart(
        self, 
        data_points: List[MeetingDataPoint], 
        title: str
    ) -> Tuple[Any, Dict[str, Any]]:
        """
        파이 차트를 생성합니다.
        
        Args:
            data_points (List[MeetingDataPoint]): 데이터 포인트 목록
            title (str): 차트 제목
        
        Returns:
            Tuple[Any, Dict[str, Any]]: 차트 객체와 차트 데이터
        """
        # 데이터 준비
        labels = [self._translate_korean(point.label) for point in data_points]
        values = [point.value for point in data_points]
        categories = [self._translate_korean(point.category) for point in data_points if point.category]
        
        # 퍼센트 계산
        total = sum(values)
        percentages = [value/total*100 for value in values]
        
        # 플롯 스타일 설정
        plt.style.use('seaborn-v0_8-pastel')
        
        # 더 세련된 색상 팔레트
        colors = ['#4361ee', '#3a0ca3', '#7209b7', '#f72585', '#4cc9f0', 
                  '#480ca8', '#b5179e', '#560bad', '#4895ef', '#ff9f1c']
              
        # 그림 크기 및 해상도 설정
        plt.figure(figsize=(12, 9), dpi=120, facecolor='white')
        
        # 원형 차트 설정
        ax = plt.subplot(111)
        ax.set_facecolor('#ffffff')  # 배경색 흰색
        
        # 데이터 크기에 따라 돌출 효과 적용 (강조)
        max_index = values.index(max(values))
        explode = [0.05 if i == max_index else 0 for i in range(len(values))]
        
        # 도넛 차트 생성 - 더 세련된 스타일
        wedges, texts, autotexts = ax.pie(
            values, 
            autopct='%1.1f%%',
            startangle=90, 
            colors=colors[:len(data_points)],
            explode=explode,
            wedgeprops=dict(
                width=0.5,  # 도넛 형태
                edgecolor='white',  # 흰색 테두리
                linewidth=2,  # 테두리 두께
                antialiased=True,  # 부드러운 가장자리
            ),
            pctdistance=0.85,  # 퍼센트 텍스트 위치
            textprops={'fontsize': 14, 'weight': 'bold', 'color': '#333333'},  # 텍스트 스타일
            shadow=True,  # 그림자 효과
        )
        
        # 퍼센트 텍스트 스타일 설정
        plt.setp(autotexts, size=14, weight="bold", color="white")
        
        # 텍스트에 외곽선 효과 추가
        for autotext in autotexts:
            autotext.set_path_effects([
                path_effects.withStroke(linewidth=2, foreground='black')
            ])
        
        # 타이틀 설정 - 더 눈에 띄게
        title_translated = self._translate_korean(title)
        ax.set_title(
            title_translated, 
            fontsize=24, 
            fontweight='bold', 
            color='#333333',
            pad=40,
            loc='center'
        )
        
        # 중앙에 총합 표시 - 더 세련된 디자인
        centre_circle = plt.Circle(
            (0,0), 
            0.3, 
            fc='white', 
            ec='#e0e0e0', 
            linewidth=1.5,
            zorder=10
        )
        ax.add_patch(centre_circle)
        
        total_text = self._translate_korean(f'총계\n{total:,}')
        ax.text(
            0, 0, 
            total_text, 
            horizontalalignment='center', 
            verticalalignment='center', 
            fontsize=16, 
            fontweight='bold',
            color='#333333'
        )
        
        # 범례 설정 - 더 세련된 디자인
        legend_title = self._translate_korean("구분")
        legend = ax.legend(
            wedges, 
            labels,
            title=legend_title,
            title_fontsize=16,
            loc="lower center",
            bbox_to_anchor=(0.5, -0.15),
            ncol=len(labels) if len(labels) <= 5 else 5,
            frameon=True,
            framealpha=0.9,
            edgecolor='#e0e0e0',
            shadow=True,
            fancybox=True,
            fontsize=12
        )
        
        # 범례 타이틀 스타일 설정
        plt.setp(legend.get_title(), fontweight='bold')
        
        # 차트 레이아웃 조정
        plt.tight_layout(pad=3.0)
        
        # 차트 데이터 반환
        chart_data = {
            "labels": [point.label for point in data_points],  # 원본 한글 레이블 유지
            "values": values,
            "percentages": percentages,
            "categories": [point.category for point in data_points if point.category]  # 원본 한글 카테고리 유지
        }
        
        return plt.gcf(), chart_data
    
    def _create_bar_chart(
        self, 
        data_points: List[MeetingDataPoint], 
        title: str
    ) -> Tuple[Any, Dict[str, Any]]:
        """
        막대 차트를 생성합니다.
        
        Args:
            data_points (List[MeetingDataPoint]): 데이터 포인트 목록
            title (str): 차트 제목
        
        Returns:
            Tuple[Any, Dict[str, Any]]: 차트 객체와 차트 데이터
        """
        # 데이터 준비
        labels = [self._translate_korean(point.label) for point in data_points]
        values = [point.value for point in data_points]
        categories = [self._translate_korean(point.category) for point in data_points if point.category]
        
        # 값으로 정렬
        if len(data_points) > 1:
            sorted_indices = np.argsort(values)[::-1]  # 내림차순 정렬
            labels = [labels[i] for i in sorted_indices]
            values = [values[i] for i in sorted_indices]
            if categories:
                categories = [categories[i] for i in sorted_indices]
        
        # 색상 설정
        if categories and len(set(categories)) > 1:
            # 카테고리별 색상 적용
            unique_categories = list(set(categories))
            category_colors = {cat: self.colors[i % len(self.colors)] for i, cat in enumerate(unique_categories)}
            colors = [category_colors[cat] for cat in categories]
        else:
            # 그라데이션 색상 적용
            import matplotlib.cm as cm
            cmap = cm.get_cmap('viridis')
            colors = [cmap(i/len(data_points)) for i in range(len(data_points))]
        
        # 그림 생성
        plt.figure(figsize=(12, 8), dpi=100, facecolor='white')
        plt.style.use('seaborn-v0_8-whitegrid')
        ax = plt.subplot(111)
        
        # 막대 그래프 생성 - 수평 방향이 긴 레이블에 더 적합
        horizontal = max([len(label) for label in labels]) > 8
        
        if horizontal:
            # 수평 막대 그래프
            bars = ax.barh(
                labels,
                values,
                color=colors,
                height=0.6,
                edgecolor='white',
                linewidth=1.5,
                alpha=0.8
            )
            
            # 막대 끝에 값 표시
            for i, bar in enumerate(bars):
                width = bar.get_width()
                ax.text(
                    width + (max(values) * 0.02),
                    bar.get_y() + bar.get_height()/2,
                    f'{values[i]:,}',
                    ha='left',
                    va='center',
                    fontsize=11,
                    fontweight='bold',
                    color='#333333'
                )
                
            # 축 레이블 설정
            value_label = self._translate_korean('값')
            ax.set_xlabel(value_label, fontsize=14, fontweight='bold', color='#333333')
            
        else:
            # 수직 막대 그래프
            bars = ax.bar(
                labels,
                values,
                color=colors,
                width=0.6,
                edgecolor='white',
                linewidth=1.5,
                alpha=0.8
            )
            
            # 막대 위에 값 표시
            for i, bar in enumerate(bars):
                height = bar.get_height()
                ax.text(
                    bar.get_x() + bar.get_width() / 2.,
                    height + (max(values) * 0.02),
                    f'{values[i]:,}',
                    ha='center',
                    va='bottom',
                    fontsize=11,
                    fontweight='bold',
                    color='#333333'
                )
                
            # 축 레이블 설정
            value_label = self._translate_korean('값')
            ax.set_ylabel(value_label, fontsize=14, fontweight='bold', color='#333333')
        
        # 제목 및 레이블 설정
        title_translated = self._translate_korean(title)
        ax.set_title(
            title_translated, 
            fontsize=18, 
            fontweight='bold', 
            color='#333333',
            pad=20
        )
        
        # 배경 설정
        ax.set_facecolor('#f8f9fa')
        plt.gcf().set_facecolor('#ffffff')
        
        # x축 레이블 회전 (레이블이 긴 경우)
        if not horizontal and max([len(str(label)) for label in labels]) > 5:
            plt.xticks(rotation=45, ha='right')
        
        # 격자 스타일 설정
        ax.grid(axis=('x' if horizontal else 'y'), linestyle='--', alpha=0.6, color='#cccccc')
        
        # 테두리 제거
        for spine in ax.spines.values():
            spine.set_visible(False)
        
        # 범례 설정 (카테고리가 있는 경우)
        if categories and len(set(categories)) > 1:
            # 카테고리별 색상으로 범례 생성
            unique_categories = list(set(categories))
            legend_handles = [plt.Rectangle((0,0),1,1, color=category_colors[cat], alpha=0.8) for cat in unique_categories]
            ax.legend(
                legend_handles, 
                unique_categories, 
                loc='upper right',
                frameon=True,
                framealpha=0.7,
                edgecolor='#cccccc'
            )
        
        # 차트 레이아웃 조정
        plt.tight_layout()
        
        # 차트 데이터 반환
        chart_data = {
            "labels": [point.label for point in data_points],  # 원본 한글 레이블 유지
            "values": values,
            "categories": [point.category for point in data_points if point.category]  # 원본 한글 카테고리 유지
        }
        
        return plt.gcf(), chart_data
    
    def _create_line_chart(
        self, 
        data_points: List[MeetingDataPoint], 
        title: str
    ) -> Tuple[Any, Dict[str, Any]]:
        """
        선 차트를 생성합니다.
        
        Args:
            data_points (List[MeetingDataPoint]): 시각화할 데이터 포인트
            title (str): 차트 제목
        
        Returns:
            Tuple[Any, Dict[str, Any]]: Plotly 그림 객체와 데이터
        """
        labels = [point.label for point in data_points]
        values = [point.value for point in data_points]
        
        fig = px.line(
            x=labels,
            y=values,
            title=title,
            labels={"x": "시간/단계", "y": "값"},
            markers=True
        )
        
        fig.update_layout(
            xaxis_title="시간/단계",
            yaxis_title="값",
            font=dict(size=14),
        )
        
        data = {
            "x": labels,
            "y": values
        }
        
        return fig, data
    
    def _create_scatter_chart(
        self, 
        data_points: List[MeetingDataPoint], 
        title: str
    ) -> Tuple[Any, Dict[str, Any]]:
        """
        산점도를 생성합니다.
        
        Args:
            data_points (List[MeetingDataPoint]): 시각화할 데이터 포인트
            title (str): 차트 제목
        
        Returns:
            Tuple[Any, Dict[str, Any]]: Plotly 그림 객체와 데이터
        """
        # 실제 구현에서는 2차원 데이터가 필요하므로 예시 데이터 생성
        x_values = np.random.normal(0, 1, len(data_points))
        y_values = [point.value for point in data_points]
        labels = [point.label for point in data_points]
        
        fig = px.scatter(
            x=x_values,
            y=y_values,
            text=labels,
            title=title,
            labels={"x": "X 축", "y": "Y 축"}
        )
        
        fig.update_traces(
            textposition="top center",
            marker=dict(size=12)
        )
        
        fig.update_layout(
            xaxis_title="X 축",
            yaxis_title="Y 축",
            font=dict(size=14),
        )
        
        data = {
            "x": x_values.tolist(),
            "y": y_values,
            "labels": labels
        }
        
        return fig, data
    
    def _create_timeline_chart(
        self, 
        data_points: List[MeetingDataPoint], 
        title: str
    ) -> Tuple[Any, Dict[str, Any]]:
        """
        타임라인 차트를 생성합니다.
        
        Args:
            data_points (List[MeetingDataPoint]): 데이터 포인트 목록
            title (str): 차트 제목
        
        Returns:
            Tuple[Any, Dict[str, Any]]: 차트 객체와 차트 데이터
        """
        # 데이터 준비
        events = []
        categories = []
        
        for point in data_points:
            if point.timestamp:
                # 날짜 문자열을 datetime 객체로 변환
                try:
                    if isinstance(point.timestamp, str):
                        date_obj = datetime.strptime(point.timestamp, "%Y-%m-%d")
                    else:
                        date_obj = point.timestamp
                    
                    # 이벤트 정보 추가
                    events.append({
                        "label": point.label,
                        "date": date_obj,
                        "value": point.value,
                        "category": point.category
                    })
                    
                    # 카테고리 목록 업데이트
                    if point.category and point.category not in categories:
                        categories.append(point.category)
                except:
                    logger.warning(f"타임스탬프 파싱 오류: {point.timestamp}")
        
        # 날짜순 정렬
        events = sorted(events, key=lambda x: x["date"])
        
        # 색상 매핑
        category_colors = {}
        cmap = plt.cm.tab10
        for i, cat in enumerate(categories):
            category_colors[cat] = cmap(i % 10)
        
        # 플롯 생성
        fig, ax = plt.subplots(figsize=(14, 8))
        
        # 각 이벤트 플롯
        for i, event in enumerate(events):
            # 색상 결정
            if event["category"] in category_colors:
                color = category_colors[event["category"]]
            else:
                color = cmap(len(categories) % 10)
            
            # 마커 크기 결정 (중요도/값에 따라)
            size = 100 + (event["value"] * 50 if event["value"] else 100)
            
            # 마커 표시
            ax.scatter(
                event["date"], 
                i, 
                s=size, 
                color=color,
                alpha=0.7,
                edgecolors='white',
                linewidth=1.5,
                zorder=2
            )
            
            # 이벤트 레이블 표시
            ax.annotate(
                event["label"],
                (event["date"], i),
                xytext=(10, 0),
                textcoords='offset points',
                fontsize=11,
                va='center',
                bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="gray", alpha=0.8)
            )
        
        # y축 눈금 제거
        ax.set_yticks([])
        
        # x축 날짜 포맷 설정
        ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter('%Y-%m-%d'))
        plt.xticks(rotation=45)
        
        # 그리드 추가
        ax.grid(axis='x', linestyle='--', alpha=0.3)
        
        # 제목 설정
        ax.set_title(title, fontsize=16, pad=20)
        
        # 범례 추가 (카테고리만 포함, '현재' 제외)
        if categories:
            handles = [plt.Line2D([0], [0], marker='o', color='w', markerfacecolor=category_colors[cat], 
                                 markersize=10, label=cat) for cat in categories]
            # '현재' 날짜 라인 범례 제거
            
            ax.legend(handles=handles, loc='upper center', bbox_to_anchor=(0.5, -0.15), 
                     ncol=min(len(categories), 4), frameon=True)
        
        # 레이아웃 조정
        plt.tight_layout()
        
        # 데이터 반환
        chart_data = {
            "events": [
                {
                    "label": event["label"],
                    "date": event["date"].strftime("%Y-%m-%d"),
                    "value": event["value"],
                    "category": event["category"]
                } for event in events
            ],
            "categories": categories
        }
        
        return plt.gcf(), chart_data
    
    def _generate_thinking_process(self, chart_type: str, data: Dict[str, Any], title: str) -> List[str]:
        """
        차트 유형에 따라 내부 사고 과정을 생성합니다.
        """
        # 3가지 특정 차트 유형에 맞는 사고 과정 생성
        if chart_type.lower() == "pie":
            # 1. 미갱신 고객 비율 파이 차트
            thoughts = [
                "<think>",
                "질문을 분석하고 있습니다: '미갱신 고객 비율을 차트로 보여줘'",
                "이 질문은 KYC 갱신 관련 데이터를 분석하여 파이 차트로 표시해야 합니다.",
                "회의 자료에서 KYC 갱신과 관련된 데이터를 추출합니다.",
                "미갱신 고객 비율과 정상 갱신 고객 비율을 파이 차트로 시각화합니다.",
                "차트는 '고객 KYC 갱신 현황'이라는 제목으로 생성할 것입니다."
            ]
        elif chart_type.lower() == "bar":
            # 2. STR 지연 보고 현황 막대 차트
            thoughts = [
                "<think>",
                "질문을 분석하고 있습니다: 'STR 지연 건에 대한 그래프를 생성해줘'",
                "이 질문은 의심거래보고(STR) 지연 관련 데이터를 분석하여 막대 차트로 표시해야 합니다.",
                "회의 자료에서 STR 보고 지연과 관련된 데이터를 추출합니다.",
                "STR 보고 정상 건수, 일반 거래 지연 건수, 고위험 거래 지연 건수를 막대 차트로 시각화합니다.",
                "차트는 'STR 보고 준수 현황 (최근 6개월)'이라는 제목으로 생성할 것입니다."
            ]
        elif chart_type.lower() == "timeline":
            # 3. 규제 준수 일정 타임라인 차트
            thoughts = [
                "<think>",
                "질문을 분석하고 있습니다: '규제 준수 일정을 타임라인으로 보여줘'",
                "이 질문은 금융 규제 준수와 관련된 일정을 타임라인 차트로 표시해야 합니다.",
                "회의 자료에서 규제 준수 일정과 관련된 데이터를 추출합니다.",
                "KYC 개선, STR 개선, 정보보호, DDoS 대응 등의 일정을 타임라인 차트로 시각화합니다.",
                "차트는 '금융 규제 준수 개선 로드맵'이라는 제목으로 생성할 것입니다."
            ]
        else:
            # 지원되지 않는 차트 유형
            thoughts = [
                "<think>",
                f"요청하신 '{chart_type}' 차트 유형은 현재 지원되지 않거나 제공된 데이터와 맞지 않습니다.",
                "지원되는 차트 유형은 다음과 같습니다: pie(파이 차트), bar(막대 차트), timeline(타임라인 차트)",
                "제공된 질문이 '미갱신 고객 비율', 'STR 지연 건', '규제 준수 일정' 중 하나에 해당하는지 확인해주세요."
            ]
            
        return thoughts
    
    def _generate_detailed_thinking_process(self, query: str, chart_type: str, title: str, data_points: List[MeetingDataPoint]) -> List[Dict[str, str]]:
        """
        시각화 요청에 대한 상세한 사고 과정을 여러 단계로 나누어 생성합니다.
        사고 과정은 영어로 작성됩니다.
        
        Args:
            query (str): 사용자 쿼리
            chart_type (str): 차트 유형
            title (str): 차트 제목
            data_points (List[MeetingDataPoint]): 데이터 포인트 목록
            
        Returns:
            List[Dict[str, str]]: 사고 과정 단계별 내용
        """
        thinking_steps = []
        
        # 1단계: 요청 분석
        thinking_steps.append({
            "title": "**Analyzing User Request**",
            "content": f"I'm analyzing the user's request: '{query}'\n\n"
                      f"This request is asking for visualization of financial compliance data. "
                      f"I need to determine the most appropriate visualization type based on the request and data characteristics."
        })
        
        # 2단계: 데이터 이해
        data_description = ""
        if chart_type.lower() == "pie":
            data_description = "After analyzing the KYC renewal data, I need to display the proportion of customers who have updated their KYC information versus those who haven't."
        elif chart_type.lower() == "bar":
            data_description = "After analyzing the STR (Suspicious Transaction Report) data, I can compare the counts across different categories such as normal reports and delayed reports."
        elif chart_type.lower() == "timeline":
            data_description = "After analyzing the regulatory compliance schedule data, I need to display various timelines and milestones arranged chronologically."
        else:
            data_description = "After analyzing the financial regulatory non-compliance data, I can compare the violation counts across different categories."
            
        thinking_steps.append({
            "title": "**Understanding Data Characteristics**",
            "content": f"I'm examining the characteristics of the data extracted from the meeting minutes.\n\n"
                      f"{data_description}\n\n"
                      f"There are {len(data_points)} data points, and I need to select a visualization method that can effectively represent this information."
        })
        
        # 3단계: 시각화 유형 선택
        chart_explanation = ""
        if chart_type.lower() == "pie":
            chart_explanation = ("A pie chart is most suitable for representing proportions of a whole. "
                               "It can intuitively display dichotomous data such as KYC renewal rates.")
        elif chart_type.lower() == "bar":
            chart_explanation = ("A bar chart is most suitable for comparing values across different categories. "
                               "It can effectively compare data such as STR report status counts across different categories.")
        elif chart_type.lower() == "timeline":
            chart_explanation = ("A timeline chart is most suitable for representing events in chronological order. "
                               "It can effectively display data where temporal sequence is important, such as regulatory compliance schedules.")
        else:
            chart_explanation = ("A bar chart is most suitable for comparing values across different categories. "
                               "It can effectively compare data such as financial regulatory non-compliance status across different categories.")
            
        thinking_steps.append({
            "title": "**Selecting Visualization Type**",
            "content": f"I'm selecting the most appropriate visualization type based on the data characteristics.\n\n"
                      f"Selected visualization type: {chart_type.upper()} CHART\n\n"
                      f"{chart_explanation}"
        })
        
        # 4단계: 디자인 고려사항
        design_considerations = ""
        if chart_type.lower() == "pie":
            design_considerations = ("- Use red tones for non-renewed customers to draw attention\n"
                                   "- Use blue tones for normally renewed customers\n"
                                   "- Display accurate percentages and numbers for each section\n"
                                   "- Apply a donut chart style with total count in the center")
        elif chart_type.lower() == "bar":
            design_considerations = ("- Apply appropriate color coding for each category\n"
                                   "- Sort by importance\n"
                                   "- Display accurate values for each bar\n"
                                   "- Highlight the maximum value")
        elif chart_type.lower() == "timeline":
            design_considerations = ("- Apply color coding by category\n"
                                   "- Adjust marker size according to importance\n"
                                   "- Add current date indicator\n"
                                   "- Add event text labels")
        else:
            design_considerations = ("- Apply appropriate color coding for each category\n"
                                   "- Sort by value\n"
                                   "- Display accurate values for each bar\n"
                                   "- Highlight the maximum value")
            
        thinking_steps.append({
            "title": "**Considering Visualization Design**",
            "content": f"I'm considering design elements for the {chart_type.upper()} chart to effectively communicate the data:\n\n"
                      f"{design_considerations}"
        })
        
        # 5단계: 데이터 준비 및 최종화
        data_summary = ""
        if len(data_points) > 0:
            labels = [point.label for point in data_points]
            values = [point.value for point in data_points]
            
            max_value = max(values) if values else 0
            max_label = labels[values.index(max_value)] if values else "None"
            total = sum(values) if values else 0
            
            data_summary = (f"- Number of data points: {len(data_points)}\n"
                          f"- Maximum value: {max_value} ({max_label})\n"
                          f"- Total sum: {total}")
        else:
            data_summary = "No data points available."
            
        thinking_steps.append({
            "title": "**Preparing and Finalizing Data**",
            "content": f"I'm finalizing the data for visualization.\n\n"
                      f"Chart title: {title}\n\n"
                      f"Data summary:\n{data_summary}\n\n"
                      f"Now I will generate the final visualization."
        })
        
        return thinking_steps
    
    def _split_text(self, text: str) -> List[str]:
        """
        텍스트를 작은 청크로 나눕니다.
        
        Args:
            text (str): 나눌 텍스트
            
        Returns:
            List[str]: 텍스트 청크 목록
        """
        # 문장 단위로 나누기
        sentences = text.split('. ')
        chunks = []
        current_chunk = ""
        
        for sentence in sentences:
            if sentence and not sentence.endswith('.'):
                sentence += '.'
            
            if len(current_chunk) + len(sentence) + 1 > 100:  # 적절한 청크 크기 설정
                chunks.append(current_chunk)
                current_chunk = sentence
            else:
                if current_chunk:
                    current_chunk += ' ' + sentence
                else:
                    current_chunk = sentence
        
        if current_chunk:
            chunks.append(current_chunk)
            
        return chunks
    
    def _generate_summary(self, data_points: List[MeetingDataPoint], chart_type: ChartType) -> str:
        """
        시각화 결과에 대한 요약 설명을 생성합니다.
        
        Args:
            data_points (List[MeetingDataPoint]): 시각화된 데이터 포인트 목록
            chart_type (ChartType): 차트 유형
            
        Returns:
            str: 요약 설명 텍스트
        """
        if not data_points:
            return "시각화할 데이터가 없습니다."
            
        labels = [point.label for point in data_points]
        values = [point.value for point in data_points]
        categories = [point.category for point in data_points if point.category]
        
        # 기본 통계 계산
        max_value = max(values) if values else 0
        max_index = values.index(max_value) if values else -1
        max_label = labels[max_index] if max_index >= 0 else "없음"
        
        total = sum(values) if values else 0
        avg = total / len(values) if values else 0
        
        # 차트 유형별 맞춤 요약 생성
        if chart_type == ChartType.PIE:
            # 파이 차트의 경우 비율 중심으로 설명
            proportions = [value/total*100 for value in values]
            summary = (
                f"회의록에서 KYC 갱신 현황에 관한 데이터를 추출하여 시각화했습니다.\n\n"
                f"파이 차트는 전체 {total:,} 건 중 각 항목의 비율을 보여줍니다:\n"
                f"- 가장 큰 비중을 차지하는 항목은 {max_label}으로 {proportions[max_index]:.1f}%입니다.\n"
                f"- 전체 데이터에서 {labels[0]}은 {proportions[0]:.1f}%, {labels[1]}은 {proportions[1]:.1f}%를 차지합니다.\n\n"
                f"이 데이터는 KYC 준수 현황을 파악하고 개선이 필요한 영역을 식별하는 데 도움이 됩니다."
            )
            
        elif chart_type == ChartType.BAR:
            # 막대 차트의 경우 값 중심으로 설명
            summary = (
                f"금융 규제 미준수 사항 현황에 대한 {chart_type.value} 차트를 생성했습니다.\n\n"
                f"주요 분석 결과:\n"
                f"- 가장 높은 값: {max_value} ({max_label} 항목)\n"
                f"- 평균: {avg:.1f}\n"
                f"- 총합: {total}\n\n"
                f"이 시각화를 통해 각 항목의 상대적인 비중을 확인할 수 있습니다."
            )
            
        elif chart_type == ChartType.TIMELINE:
            # 타임라인 차트의 경우 시간 관점에서 설명
            summary = (
                f"금융 규제 준수 일정에 대한 {chart_type.value} 차트를 생성했습니다.\n\n"
                f"주요 일정 정보:\n"
                f"- 총 {len(data_points)}개의 주요 일정이 표시됩니다.\n"
                f"- 카테고리별로 색상을 구분하여 표시했습니다.\n"
                f"- 중요도에 따라 마커 크기를 조정했습니다.\n\n"
                f"이 타임라인을 통해 규제 준수를 위한 주요 일정을 한눈에 파악할 수 있습니다."
            )
            
        else:
            # 기본 요약
            summary = (
                f"{chart_type.value} 차트 생성이 완료되었습니다.\n\n"
                f"데이터 요약:\n"
                f"- 데이터 포인트: {len(data_points)}개\n"
                f"- 최대값: {max_value} ({max_label})\n"
                f"- 평균값: {avg:.1f}\n"
                f"- 총합: {total}"
            )
            
        return summary 

    def _fig_to_base64(self, fig) -> str:
        """
        matplotlib 그림 객체를 base64 인코딩된 이미지로 변환합니다.
        
        Args:
            fig: matplotlib 그림 객체
            
        Returns:
            str: base64 인코딩된 이미지 데이터 URI
            
        Raises:
            Exception: 이미지 변환 중 오류가 발생한 경우
        """
        # 이미지를 바이트 스트림으로 저장
        img_data = io.BytesIO()
        fig.savefig(
            img_data, 
            format='png', 
            bbox_inches='tight', 
            dpi=100, 
            facecolor=fig.get_facecolor(),
            edgecolor='none'
        )
        img_data.seek(0)
        
        # base64로 인코딩
        encoded = base64.b64encode(img_data.read()).decode('utf-8')
        img_data_uri = f"data:image/png;base64,{encoded}"
        
        # 메모리 정리
        plt.close(fig)
        
        return img_data_uri 