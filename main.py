import datetime
import requests
import pandas as pd
import pytz
import streamlit as st

# 페이지 기본 레이아웃 및 제목 설정
st.set_page_config(
    page_title="어제 박스오피스 순위",
    page_icon="🎬",
    layout="wide"
)

st.title("🎬 어제 일별 박스오피스")


# 1. API 요청 및 데이터 캐싱 (1시간 = 3600초 동안 결과 보관)
@st.cache_data(ttl=3600)
def fetch_daily_boxoffice(target_date: str, api_key: str):
    """KOBIS API를 통해 해당 날짜의 박스오피스 데이터를 가져옵니다."""
    url = "https://www.kobis.or.kr/kobisopenapi/webservice/rest/boxoffice/searchDailyBoxOfficeList.json"
    params = {
        "key": api_key,
        "targetDt": target_date
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        # 네트워크 에러(4xx, 5xx) 체크
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"error": f"네트워크 요청 실패: {e}"}


# 2. Secrets 비밀 금고에서 인증키(KOBIS_KEY) 불러오기
if "KOBIS_KEY" not in st.secrets:
    st.error("🔒 Secrets 금고에서 'KOBIS_KEY'를 찾을 수 없습니다.")
    st.info("💡 Streamlit Cloud의 Secrets 설정에 KOBIS_KEY = '발급받은_키' 형식으로 등록해 주세요.")
    st.stop()

api_key = st.secrets["KOBIS_KEY"]

# 3. 한국 시간(KST) 기준 '어제' 날짜 계산
# 해외에 위치한 배포 서버 시계 대신 한국 표준시(Asia/Seoul)를 기준으로 계산합니다.
kst_timezone = pytz.timezone("Asia/Seoul")
now_in_kst = datetime.datetime.now(kst_timezone)
yesterday = now_in_kst - datetime.timedelta(days=1)

target_date = yesterday.strftime("%Y%m%d")      # API 요청용 (예: 20260910)
display_date = yesterday.strftime("%Y년 %m월 %d일") # 화면 표시용

st.caption(f"기준 날짜: {display_date} (한국 시간 기준)")

# 4. API 데이터 호출
data = fetch_daily_boxoffice(target_date, api_key)

# 5. 응답 결과 및 오류 검증
if "error" in data:
    # 네트워크 및 요청 자체 실패 시
    st.error(f"⚠️ 데이터를 불러오지 못했습니다: {data['error']}")
    st.info("💡 인터넷 연결을 확인하거나 KOBIS 서비스 상태를 점검해 보세요.")

elif "faultInfo" in data:
    # API 키 오타 등 KOBIS에서 오류 상자를 보낸 경우 (상태 코드는 200)
    fault_msg = data["faultInfo"].get("message", "인증 오류 발생")
    st.error(f"⚠️ KOBIS API 오류: {fault_msg}")
    st.info("💡 Secrets에 설정한 'KOBIS_KEY' 값이 올바른지 확인해 주세요.")

else:
    # 정상 응답 구조 확인
    box_office_result = data.get("boxOfficeResult", {})
    movie_list = box_office_result.get("dailyBoxOfficeList", [])

    if not movie_list:
        # 응답은 정상이나 목록이 비어 있는 경우
        st.warning("⚠️ 해당 날짜의 영화 목록이 비어 있습니다.")
        st.info("💡 아직 어제 집계가 완료되지 않았거나 KOBIS 점검 중일 수 있습니다.")
        
    else:
        # 6. 데이터프레임 변환 및 숫자형 타입 변경
        df = pd.DataFrame(movie_list)

        # 문자열로 온 숫자 데이터들을 정수형(int)으로 변경
        numeric_columns = ["rank", "audiCnt", "audiAcc", "scrnCnt", "showCnt", "rankInten"]
        for col in numeric_columns:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

        # 순위(rank) 오름차순 정렬
        df = df.sort_values(by="rank", ascending=True)

        # 7. 1위 영화 지표 카드 3개로 크게 강조
        top_movie = df.iloc[0]
        st.subheader(f"🥇 1위: {top_movie['movieNm']}")

        col1, col2, col3 = st.columns(3)
        col1.metric("일일 관객수", f"{int(top_movie['audiCnt']):,} 명")
        col2.metric("누적 관객수", f"{int(top_movie['audiAcc']):,} 명")
        col3.metric("스크린수", f"{int(top_movie['scrnCnt']):,} 개")

        st.divider()

        # 8. 관객수 상위 5편 막대그래프
        st.subheader("📊 관객수 상위 5개 영화")
        top_5_df = df.head(5).copy()

        # 막대그래프용 데이터 추출 및 가독성 높은 컬럼 설정
        chart_df = top_5_df[["movieNm", "audiCnt"]].set_index("movieNm")
        chart_df.columns = ["일일 관객수"]

        st.bar_chart(chart_df)

        st.divider()

        # 9. 전체 순위표 표시
        st.subheader("📋 전체 박스오피스 순위")

        # 주요 항목 컬럼 추출 및 한글명 변경
        display_df = df[["rank", "movieNm", "openDt", "audiCnt", "audiAcc", "scrnCnt"]].copy()
        display_df.columns = ["순위", "영화명", "개봉일", "관객수", "누적관객", "스크린수"]

        # 표 인덱스를 1부터 시작하도록 설정
        display_df.index = range(1, len(display_df) + 1)

        # 천 단위 쉼표 포맷팅 후 표시
        st.dataframe(
            display_df.style.format({
                "관객수": "{:,.0f}",
                "누적관객": "{:,.0f}",
                "스크린수": "{:,.0f}"
            }),
            use_container_width=True
        )
