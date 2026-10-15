import re
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

# --------------------------------------------------
# 1. 페이지 기본 설정
# --------------------------------------------------
st.set_page_config(
    page_title="동네별 인구 피라미드",
    page_icon="🏘️",
    layout="wide",
)

# 따뜻한 색상의 화면 스타일
st.markdown(
    """
    <style>
    .stApp {
        background-color: #FFF9F2;
    }
    h1, h2, h3 {
        color: #754C35;
    }
    div[data-testid="stMetric"] {
        background-color: #FFF0E2;
        border: 1px solid #F0D8C4;
        padding: 14px;
        border-radius: 12px;
    }
    div[data-baseweb="select"] {
        background-color: #FFFFFF;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("🏘️ 동네별 인구 피라미드")
st.markdown(
    "우리 동네의 연령별 인구 구성을 살펴보세요. "
    "남성은 왼쪽, 여성은 오른쪽에 표시됩니다."
)

# --------------------------------------------------
# 2. 데이터 불러오기
# --------------------------------------------------
DATA_URL = (
    "https://raw.githubusercontent.com/Dmitri1899/pop/"
    "main/population_ts_yearly_gender.zip"
)


@st.cache_data(show_spinner="전국 읍·면·동 인구 데이터를 불러오는 중...")
def load_data():
    """압축 CSV를 읽고 최신 연도의 데이터만 반환합니다."""

    # pandas는 ZIP 압축 파일 URL도 직접 읽을 수 있습니다.
    df = pd.read_csv(DATA_URL, compression="zip")

    # 열 이름 양쪽에 불필요한 공백이 있다면 제거합니다.
    df.columns = df.columns.astype(str).str.strip()

    # 연도는 숫자로 변환해 최신 연도를 정확하게 찾습니다.
    df["연도"] = pd.to_numeric(df["연도"], errors="coerce")
    df = df.dropna(subset=["연도"])
    df["연도"] = df["연도"].astype(int)

    # 나이별 남녀 인구 열을 찾습니다.
    age_columns = [
        col for col in df.columns
        if re.fullmatch(r"[남여]_(?:[0-9]+세|100세 이상)", col)
    ]

    if not age_columns:
        raise ValueError(
            "남_0세, 여_0세 등의 인구 열을 찾을 수 없습니다."
        )

    # 인구 열은 숫자로 변환합니다. 비어 있는 값은 0으로 처리합니다.
    for col in age_columns:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    # 전국 데이터 중 가장 최신 연도만 선택합니다.
    latest_year = int(df["연도"].max())
    latest_df = df.loc[df["연도"] == latest_year].copy()

    # 행정구역 이름의 공백 때문에 선택이 꼬이지 않도록 정리합니다.
    for col in ["시도", "시군구", "동"]:
        if col not in latest_df.columns:
            raise ValueError(f"필수 열 '{col}'이 데이터에 없습니다.")

        latest_df[col] = (
            latest_df[col].fillna("").astype(str).str.strip()
        )

    # 읍·면·동 이름이 없는 행정구역은 선택 목록에서 제외합니다.
    latest_df = latest_df[
        (latest_df["시도"] != "")
        & (latest_df["시군구"] != "")
        & (latest_df["동"] != "")
    ]

    return latest_year, latest_df, age_columns


try:
    latest_year, df, age_columns = load_data()
except Exception as e:
    st.error(
        "데이터를 불러오지 못했습니다. 인터넷 연결과 CSV 열 이름을 "
        f"확인해 주세요.\n\n오류 내용: {e}"
    )
    st.stop()

# --------------------------------------------------
# 3. 나이별 열 이름을 0세부터 100세 이상까지 정렬
# --------------------------------------------------
# 문자열 정렬을 하면 10세가 2세보다 먼저 나올 수 있으므로
# 나이 숫자를 직접 추출하여 올바른 순서로 정렬합니다.
def age_sort_key(column):
    age_text = column.split("_", 1)[1]

    if age_text == "100세 이상":
        return 100

    return int(age_text.replace("세", ""))


ages = [f"{age}세" for age in range(101)] + ["100세 이상"]

# 실제 데이터의 열 이름을 나이 숫자 기준으로 정렬합니다.
male_columns = sorted(
    [c for c in age_columns if c.startswith("남_")],
    key=age_sort_key,
)
female_columns = sorted(
    [c for c in age_columns if c.startswith("여_")],
    key=age_sort_key,
)

# 0~100세 및 100세 이상 열을 나이 라벨에 맞춰 연결합니다.
def find_age_column(columns, age_label):
    expected = f"_{age_label}"
    for col in columns:
        if col.endswith(expected):
            return col
    return None


male_age_columns = [
    find_age_column(male_columns, age) for age in ages
]
female_age_columns = [
    find_age_column(female_columns, age) for age in ages
]

# 일부 나이 열이 누락된 데이터에도 대응합니다.
# 없는 나이는 그래프에서 인구 0명으로 표시합니다.

# --------------------------------------------------
# 4. 시도 → 시군구 → 동 선택
# --------------------------------------------------
st.subheader("📍 지역 선택")

col1, col2, col3 = st.columns(3)

with col1:
    sido_options = sorted(df["시도"].unique().tolist())
    selected_sido = st.selectbox(
        "① 시도",
        sido_options,
        key="selected_sido",
    )

# 선택한 시도에 속하는 시군구만 보여 줍니다.
sigungu_df = df[df["시도"] == selected_sido]
sigungu_options = sorted(sigungu_df["시군구"].unique().tolist())

with col2:
    selected_sigungu = st.selectbox(
        "② 시군구",
        sigungu_options,
        key="selected_sigungu",
    )

# 선택한 시군구에 속하는 동만 보여 줍니다.
dong_df = sigungu_df[
    sigungu_df["시군구"] == selected_sigungu
]
dong_options = sorted(dong_df["동"].unique().tolist())

with col3:
    selected_dong = st.selectbox(
        "③ 읍·면·동",
        dong_options,
        key="selected_dong",
    )

# --------------------------------------------------
# 5. 선택한 동네의 인구 데이터 계산
# --------------------------------------------------
selected_rows = dong_df[dong_df["동"] == selected_dong]

if selected_rows.empty:
    st.warning("선택한 지역의 데이터가 없습니다.")
    st.stop()

# 같은 동네가 여러 행으로 나뉘어 있다면 나이별로 합산합니다.
# 이렇게 하면 중복 행이 있어도 그래프는 한 개의 인구 분포를 표시합니다.
row = selected_rows[age_columns].sum(numeric_only=True)

male_population = np.array(
    [
        float(row[col]) if col is not None else 0.0
        for col in male_age_columns
    ],
    dtype=float,
)

female_population = np.array(
    [
        float(row[col]) if col is not None else 0.0
        for col in female_age_columns
    ],
    dtype=float,
)

# 혹시 음수나 결측치가 있으면 표시 전에 안전하게 정리합니다.
male_population = np.nan_to_num(
    male_population, nan=0.0, posinf=0.0, neginf=0.0
)
female_population = np.nan_to_num(
    female_population, nan=0.0, posinf=0.0, neginf=0.0
)

male_population = np.maximum(male_population, 0)
female_population = np.maximum(female_population, 0)

male_total = int(male_population.sum())
female_total = int(female_population.sum())
total_population = male_total + female_total

# --------------------------------------------------
# 6. 주요 인구 지표
# --------------------------------------------------
st.markdown("---")
st.subheader(
    f"📊 {selected_sido} {selected_sigungu} {selected_dong}"
)

st.caption(f"데이터 기준 연도: {latest_year}년")

metric1, metric2, metric3 = st.columns(3)

metric1.metric("전체 인구", f"{total_population:,}명")
metric2.metric("남성 인구", f"{male_total:,}명")
metric3.metric("여성 인구", f"{female_total:,}명")

# --------------------------------------------------
# 7. 인구 피라미드 그리기
# --------------------------------------------------
# 남성 인구는 음수로 바꿔 왼쪽에, 여성은 양수로 표시합니다.
fig = go.Figure()

fig.add_trace(
    go.Bar(
        name="남성",
        y=ages,
        x=-male_population,
        orientation="h",
        marker_color="#D9826B",
        hovertemplate=(
            "나이: %{y}<br>"
            "남성 인구: %{customdata:,}명"
            "<extra></extra>"
        ),
        customdata=male_population,
    )
)

fig.add_trace(
    go.Bar(
        name="여성",
        y=ages,
        x=female_population,
        orientation="h",
        marker_color="#E9AD65",
        hovertemplate=(
            "나이: %{y}<br>"
            "여성 인구: %{x:,}명"
            "<extra></extra>"
        ),
    )
)

# 좌우가 같은 기준으로 비교되도록 X축 범위를 대칭으로 설정합니다.
max_population = max(
    float(male_population.max()) if len(male_population) else 0,
    float(female_population.max()) if len(female_population) else 0,
    1,
)
x_limit = max_population * 1.12

fig.update_layout(
    title={
        "text": f"{selected_dong} 연령별 인구 피라미드",
        "x": 0.5,
        "xanchor": "center",
    },
    barmode="overlay",
    bargap=0.12,
    height=1000,
    paper_bgcolor="#FFF9F2",
    plot_bgcolor="#FFF9F2",
    font=dict(
        family="Arial, sans-serif",
        size=12,
        color="#5E4636",
    ),
    legend=dict(
        orientation="h",
        yanchor="bottom",
        y=1.01,
        xanchor="center",
        x=0.5,
    ),
    margin=dict(l=95, r=35, t=100, b=70),
)

fig.update_xaxes(
    title_text="인구 (명)",
    range=[-x_limit, x_limit],
    zeroline=True,
    zerolinewidth=2,
    zerolinecolor="#A88E7A",
    gridcolor="#EADFD4",
    tickformat=",d",
    # 음수인 남성 인구도 눈금에는 양수로 표시합니다.
    tickvals=[
        -x_limit,
        -x_limit / 2,
        0,
        x_limit / 2,
        x_limit,
    ],
    ticktext=[
        f"{int(x_limit):,}",
        f"{int(x_limit / 2):,}",
        "0",
        f"{int(x_limit / 2):,}",
        f"{int(x_limit):,}",
    ],
)

# 중요: 나이축은 0세 → 100세 이상 순서로 명시적으로 고정합니다.
# Plotly 가로 막대그래프는 카테고리 순서에 따라 위아래가 결정되므로
# 역순으로 된 배열을 전달하여 0세가 아래쪽에 오도록 합니다.
# 축을 뒤집는 autorange 옵션은 사용하지 않습니다.
fig.update_yaxes(
    title_text="나이",
    categoryorder="array",
    categoryarray=ages[::-1],
    tickmode="array",
    tickvals=ages,
    ticktext=ages,
    showgrid=True,
    gridcolor="#F0E5DA",
)

st.plotly_chart(fig, use_container_width=True)

# --------------------------------------------------
# 8. 그래프 읽는 방법
# --------------------------------------------------
with st.expander("💡 그래프 읽는 방법"):
    st.markdown(
        """
        - **왼쪽의 주황빛 붉은색:** 남성 인구
        - **오른쪽의 따뜻한 노란색:** 여성 인구
        - **가운데 세로선:** 인구 0명 기준선
        - **가로 막대의 길이:** 해당 나이의 인구수
        - **세로축:** 아래에서 위로 0세부터 100세 이상까지
        - 막대 위에 마우스를 올리면 정확한 인구수를 확인할 수 있습니다.
        """
    )

st.caption(
    "자료: GitHub 인구 통계 CSV | "
    f"선택된 최신 연도: {latest_year}년"
)
