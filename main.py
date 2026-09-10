import datetime
import requests
import pandas as pd
import pytz
import streamlit as st

# 페이지 기본 설정
st.set_page_config(
    page_title="어제 박스오피스 순위", page_icon="🎬", layout="wide"
)

st.title("🎬 어제 일별 박스오피스")


# 1. API 데이터 불러오기 함수 (1시간 동안 데이터 캐싱)
@st.cache_data(ttl=3600)
def fetch_daily_boxoffice(target_date: str, api_key: str):
    """KOBIS API를 호출하여 해당 날짜의 박스오피스 데이터를 가져오는 함수"""
    url = "https://www.kobis.or.kr/kobisopenapi/webservice/rest/boxoffice/searchDailyBoxOfficeList.json"
    params = {"key": api_key, "targetDt": target_date}

    try:
        response = requests.get(url, params=params, timeout=10)
        # HTTP 요청 자체가 실패한 경우 예외 발생
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"error": f"네트워크 요청 실패: {e}"}


# 2. Secrets에서 API 키 불러오기
if "KOBIS_KEY" not in st.secrets:
    st.error(
        "🔒 API 키를 찾을 수 없습니다! Streamlit Secrets 설정에 'KOBIS_KEY'를 등록했는지 확인해 주세요."
    )
    st.stop()

api_key = st.secrets["0f9cfa80ffe30b5da502cf0b015534a3"]

# 3. 한국 표준시(KST) 기준 '어제' 날짜 계산하기
# 배포 서버의 시계가 해외 기준이어도 항상 한국 시간 기준으로 어제를 구합니다.
kst_timezone = pytz.timezone("Asia/Seoul")
now_in_kst = datetime.datetime.now(kst_timezone)
yesterday = now_in_kst - datetime.timedelta(days=1)

# API 요구 형식에 맞춰 YYYYMMDD 형태로 변환
target_date = yesterday.strftime("%Y%m%d")
display_date = yesterday.strftime("%Y년 %m월 %d일")

st.caption(f"기준 날짜: {display_date} (한국 시간 기준)")

# 4. API 데이터 요청 수행
data = fetch_daily_boxoffice(target_date, api_key)

# 5. 예외 및 오류 처리
if "error" in data:
    # 네트워크 오류 등 예외 처리
    st.error(f"⚠️ 데이터를 불러오지 못했습니다: {data['error']}")
    st.info("💡 인터넷 연결 상태를 확인하시거나 잠시 후 다시 시도해 주세요.")

elif "faultInfo" in data:
    # API 키 오류 등 KOBIS 서비스 예외 처리 (상태 코드가 200이어도 오루가 올 수 있음)
    fault_msg = data["faultInfo"].get("message", "알 수 없는 오류")
    st.error(f"⚠️ KOBIS API 오류 발생: {fault_msg}")
    st.info(
        "💡 Streamlit Secrets에 입력한 'KOBIS_KEY' 인증키가 올바른지 확인해 주세요."
    )

else:
    # 성공 응답 내부에서 영화 목록 추출
    box_office_result = data.get("boxOfficeResult", {})
    movie_list = box_office_result.get("dailyBoxOfficeList", [])

    if not movie_list:
        # 데이터가 비어 있는 경우
        st.warning("⚠️ 해당 날짜의 박스오피스 데이터가 비어 있습니다.")
        st.info(
            "💡 아직 집계 전이거나 영화진흥위원회(KOBIS) 데이터 점검 중일 수 있습니다."
        )

    else:
        # 6. 데이터프레임 변환 및 숫자형 데이터 정제
        df = pd.DataFrame(movie_list)

        # 문자열로 들어오는 주요 숫자 데이터들을 정수형(int)으로 변환
        numeric_columns = [
            "rank",
            "audiCnt",
            "audiAcc",
            "scrnCnt",
            "showCnt",
            "rankInten",
        ]
        for col in numeric_columns:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

        # 순위 기준으로 오름차순 정렬
        df = df.sort_values(by="rank", ascending=True)

        # 7. 1위 영화 하이라이트 (지표 카드 3개 표시)
        top_movie = df.iloc[0]
        st.subheader(f"🥇 1위: {top_movie['movieNm']}")

        col1, col2, col3 = st.columns(3)
        col1.metric("일일 관객수", f"{top_movie['audiCnt']:,} 명")
        col2.metric("누적 관객수", f"{top_movie['audiAcc']:,} 명")
        col3.metric("스크린수", f"{top_movie['scrnCnt']:,} 개")

        st.divider()

        # 8. 관객수 상위 5편 막대그래프
        st.subheader("📊 관객수 상위 5개 영화")
        top_5_df = df.head(5).copy()

        # 막대그래프 생성을 위해 가독성 좋은 컬럼 이름 지정
        chart_df = top_5_df[["movieNm", "audiCnt"]].set_index("movieNm")
        chart_df.columns = ["일일 관객수"]

        st.bar_chart(chart_df)

        st.divider()

        # 9. 전체 순위표 가공 및 화면 출력
        st.subheader("📋 박스오피스 전체 순위")

        # 화면에 표시할 주요 열만 선택 및 컬럼명 변경
        display_df = df[
            ["rank", "movieNm", "openDt", "audiCnt", "audiAcc", "scrnCnt"]
        ].copy()
        display_df.columns = [
            "순위",
            "영화명",
            "개봉일",
            "관객수",
            "누적관객",
            "스크린수",
        ]

        # 데이터 프레임의 인덱스를 1부터 시작하도록 조정 (선택 사항)
        display_df.index = range(1, len(display_df) + 1)

        # 숫자 포맷을 천 단위 쉼표(,)가 찍힌 문자열로 보기 좋게 설정하여 출력
        st.dataframe(
            display_df.style.format(
                {"관객수": "{:,.0f}", "누적관객": "{:,.0f}", "스크린수": "{:,.0f}"}
            ),
            use_container_width=True,
        )
