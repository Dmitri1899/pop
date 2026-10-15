import re

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go


# --------------------------------------------------
# 1. 페이지 설정 및 따뜻한 색상 테마
# --------------------------------------------------
st.set_page_config(
    page_title="동네별 인구 피라미드",
    page_icon="🏘️",
    layout="wide",
)

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
        padding: 16px;
        border-radius: 12px;
    }

    div[data-baseweb="select"] {
        background-color: #FFFFFF;
    }

    .insight-box {
        background-color: #FFF0E2;
        border-left: 5px solid #D9826B;
        border-radius: 8px;
        padding: 16px 18px;
        margin-top: 12px;
        margin-bottom: 18px;
        color: #754C35;
        font-size: 16px;
        line-height: 1.7;
    }

    .warning-note {
        color: #A33A2B;
        font-weight: 600;
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


@st.cache_data(show_spinner="전국 인구 데이터를 불러오는 중...")
def load_data():
    """ZIP으로 압축된 CSV를 읽고 가장 최신 연도만 선택합니다."""

    df = pd.read_csv(DATA_URL, compression="zip")
    df.columns = df.columns.astype(str).str.strip()

    # 연도를 숫자로 바꿔 가장 최신 연도를 찾습니다.
    df["연도"] = pd.to_numeric(df["연도"], errors="coerce")
    df = df.dropna(subset=["연도"])
    df["연도"] = df["연도"].astype(int)

    # 남_0세, 여_0세, 남_100세 이상 등의 열을 찾습니다.
    age_columns = [
        col
        for col in df.columns
        if re.fullmatch(
            r"[남여]_(?:\d+세|100세 이상)",
            col,
        )
    ]

    if not age_columns:
        raise ValueError(
            "연령별 인구 열을 찾을 수 없습니다. "
            "CSV의 열 이름을 확인해 주세요."
        )

    # 인구 열을 숫자로 변환하고 결측치는 0으로 처리합니다.
    for col in age_columns:
        df[col] = pd.to_numeric(
            df[col], errors="coerce"
        ).fillna(0)

    latest_year = int(df["연도"].max())
    latest_df = df[df["연도"] == latest_year].copy()

    # 지역 이름을 정리합니다.
    for col in ["시도", "시군구", "동"]:
        if col not in latest_df.columns:
            raise ValueError(
                f"필수 열 '{col}'이 데이터에 없습니다."
            )

        latest_df[col] = (
            latest_df[col]
            .fillna("")
            .astype(str)
            .str.strip()
        )

    # 지역명이 비어 있는 행은 제외합니다.
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
        "데이터를 불러오지 못했습니다. 인터넷 연결과 CSV 구조를 "
        f"확인해 주세요.\n\n오류 내용: {e}"
    )
    st.stop()


# --------------------------------------------------
# 3. 연령별 열 이름 정리
# --------------------------------------------------
# 0~99세와 100세 이상을 각각 하나의 연령 구간으로 사용합니다.
# 따라서 그래프에는 총 101개의 연령 구간이 표시됩니다.
ages = [f"{age}세" for age in range(100)] + ["100세 이상"]


def find_age_column(columns, age_label):
    """주어진 나이에 해당하는 데이터 열을 찾습니다."""
    expected = f"_{age_label}"

    for col in columns:
        if col.endswith(expected):
            return col

    return None


male_columns = [
    col for col in age_columns if col.startswith("남_")
]
female_columns = [
    col for col in age_columns if col.startswith("여_")
]

male_age_columns = [
    find_age_column(male_columns, age)
    for age in ages
]
female_age_columns = [
    find_age_column(female_columns, age)
    for age in ages
]


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

# 시도를 선택하면 해당 시도의 시군구만 가져옵니다.
sigungu_df = df[df["시도"] == selected_sido]
sigungu_options = sorted(
    sigungu_df["시군구"].unique().tolist()
)

with col2:
    selected_sigungu = st.selectbox(
        "② 시군구",
        sigungu_options,
        key="selected_sigungu",
    )

# 시군구를 선택하면 해당 시군구의 읍·면·동만 가져옵니다.
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
# 5. 선택한 지역의 연령별 인구 계산
# --------------------------------------------------
selected_rows = dong_df[
    dong_df["동"] == selected_dong
]

if selected_rows.empty:
    st.warning("선택한 지역의 데이터가 없습니다.")
    st.stop()

# 동일 지역의 데이터가 여러 행이면 연령별 인구를 합산합니다.
row = selected_rows[age_columns].sum(numeric_only=True)


def get_population(column):
    """열이 존재하면 인구를 반환하고, 없으면 0을 반환합니다."""
    if column is None:
        return 0.0

    return float(row.get(column, 0.0))


male_population = np.array(
    [get_population(c) for c in male_age_columns],
    dtype=float,
)
female_population = np.array(
    [get_population(c) for c in female_age_columns],
    dtype=float,
)

# 비정상적인 수치를 정리하고 음수 인구를 방지합니다.
male_population = np.nan_to_num(
    male_population, nan=0.0, posinf=0.0, neginf=0.0
)
female_population = np.nan_to_num(
    female_population, nan=0.0, posinf=0.0, neginf=0.0
)

male_population = np.maximum(male_population, 0)
female_population = np.maximum(female_population, 0)

# 남녀 인구를 합쳐 연령별 전체 인구를 계산합니다.
total_by_age = male_population + female_population

male_total = int(male_population.sum())
female_total = int(female_population.sum())
total_population = int(total_by_age.sum())


# --------------------------------------------------
# 6. 총인구 · 평균연령 · 고령화율 계산
# --------------------------------------------------
# 연령 구간별 인구에 해당 나이를 곱한 뒤 합산합니다.
# 100세 이상 구간은 계산 가능한 대표값인 100세로 간주합니다.
age_values = np.array(
    list(range(100)) + [100],
    dtype=float,
)

if total_population > 0:
    average_age = float(
        np.sum(age_values * total_by_age)
        / total_by_age.sum()
    )
else:
    average_age = 0.0

# 65세 이상 인구는 65~99세와 100세 이상을 합산합니다.
elderly_population = int(total_by_age[65:].sum())

if total_population > 0:
    aging_rate = elderly_population / total_population * 100
else:
    aging_rate = 0.0

# 어린이는 0~14세로 정의합니다.
children_population = int(total_by_age[:15].sum())

if total_population > 0:
    children_rate = children_population / total_population * 100
else:
    children_rate = 0.0

elderly_rate = aging_rate

# 20%를 초과할 때만 주의 표시를 켭니다.
is_aging_warning = aging_rate > 20


# --------------------------------------------------
# 7. 지표 카드 3개
# --------------------------------------------------
st.markdown("---")

st.subheader(
    f"📊 {selected_sido} {selected_sigungu} {selected_dong}"
)
st.caption(f"데이터 기준 연도: {latest_year}년")

card1, card2, card3 = st.columns(3)

with card1:
    st.metric(
        label="👥 총인구",
        value=f"{total_population:,}명",
        help="선택한 동네의 남녀 전체 인구입니다.",
    )

with card2:
    st.metric(
        label="🎂 평균연령",
        value=(
            f"{average_age:.1f}세"
            if total_population > 0
            else "계산 불가"
        ),
        help=(
            "연령별 인구 가중평균입니다. "
            "100세 이상은 100세로 계산한 추정치입니다."
        ),
    )

with card3:
    aging_label = (
        "⚠️ 고령화율 · 주의"
        if is_aging_warning
        else "🌿 고령화율"
    )

    st.metric(
        label=aging_label,
        value=(
            f"{aging_rate:.1f}%"
            if total_population > 0
            else "계산 불가"
        ),
        help=(
            "전체 인구 중 65세 이상 인구의 비율입니다. "
            "20% 초과 시 주의 표시를 합니다."
        ),
    )

if is_aging_warning:
    st.warning(
        "⚠️ 고령화율이 20%를 초과합니다. "
        "65세 이상 인구가 전체 인구의 5분의 1보다 많습니다."
    )


# --------------------------------------------------
# 8. 인구 피라미드
# --------------------------------------------------
st.subheader("📈 연령별 인구 피라미드")

fig = go.Figure()

# 남성 인구를 음수로 바꿔 왼쪽에 표시합니다.
fig.add_trace(
    go.Bar(
        name="남성",
        y=ages,
        x=-male_population,
        orientation="h",
        marker_color="#D9826B",
        customdata=male_population,
        hovertemplate=(
            "나이: %{y}<br>"
            "남성 인구: %{customdata:,.0f}명"
            "<extra></extra>"
        ),
    )
)

# 여성 인구는 양수로 오른쪽에 표시합니다.
fig.add_trace(
    go.Bar(
        name="여성",
        y=ages,
        x=female_population,
        orientation="h",
        marker_color="#E9AD65",
        hovertemplate=(
            "나이: %{y}<br>"
            "여성 인구: %{x:,.0f}명"
            "<extra></extra>"
        ),
    )
)

# 좌우의 축 범위를 동일하게 만들어 비교하기 쉽게 합니다.
max_population = max(
    float(male_population.max()),
    float(female_population.max()),
    1.0,
)
x_limit = max_population * 1.12

# 눈금 간격을 일정하게 정하고 좌우에 같은 숫자를 표시합니다.
tick_step = max(x_limit / 4, 1)
tick_values = [
    -x_limit,
    -x_limit / 2,
    0,
    x_limit / 2,
    x_limit,
]
tick_text = [
    f"{abs(value):,.0f}"
    for value in tick_values
]

fig.update_layout(
    title={
        "text": f"{selected_dong} 인구 피라미드",
        "x": 0.5,
        "xanchor": "center",
    },
    barmode="overlay",
    bargap=0.12,
    height=950,
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
    margin=dict(l=100, r=35, t=95, b=65),
)

fig.update_xaxes(
    title_text="인구 (명)",
    range=[-x_limit, x_limit],
    tickmode="array",
    tickvals=tick_values,
    ticktext=tick_text,
    zeroline=True,
    zerolinewidth=2,
    zerolinecolor="#A88E7A",
    gridcolor="#EADFD4",
)

# 중요: 나이 라벨을 명시적으로 지정합니다.
# 카테고리 순서를 역순으로 전달해야 0세가 아래에 놓입니다.
# autorange="reversed" 등 축을 뒤집는 옵션은 사용하지 않습니다.
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
# 9. 연령 구조를 한 줄로 설명
# --------------------------------------------------
st.subheader("💬 우리 동네 인구 한눈에 보기")

if total_population == 0:
    insight = (
        "인구 데이터가 없어 어린이와 어르신의 비중을 "
        "비교할 수 없습니다."
    )
elif elderly_rate > children_rate:
    insight = (
        f"이 동네는 어린이 비중({children_rate:.1f}%)보다 "
        f"어르신 비중({elderly_rate:.1f}%)이 높은 "
        "어르신 중심의 연령 구조를 보입니다."
    )
elif children_rate > elderly_rate:
    insight = (
        f"이 동네는 어르신 비중({elderly_rate:.1f}%)보다 "
        f"어린이 비중({children_rate:.1f}%)이 높은 "
        "어린이 비중이 상대적으로 큰 연령 구조를 보입니다."
    )
else:
    insight = (
        f"어린이 비중과 어르신 비중이 모두 "
        f"{children_rate:.1f}%로 같습니다."
    )

st.markdown(
    f'<div class="insight-box">{insight}</div>',
    unsafe_allow_html=True,
)

st.caption(
    "어린이: 0~14세 | 어르신: 65세 이상 | "
    "고령화율 20% 초과 시 주의 표시"
)

with st.expander("💡 그래프와 지표 읽는 방법"):
    st.markdown(
        """
        - **총인구:** 선택한 동네의 전체 남녀 인구
        - **평균연령:** 연령대별 인구를 반영한 가중평균 추정치
        - **고령화율:** 전체 인구 중 65세 이상 인구의 비율
        - **왼쪽 붉은색 막대:** 남성 인구
        - **오른쪽 노란색 막대:** 여성 인구
        - **세로축:** 아래쪽 0세부터 위쪽 100세 이상까지
        - **주의 표시:** 고령화율이 20%를 초과하는 경우
        """
    )

st.caption(
    f"자료: GitHub 인구 통계 CSV · 기준 연도 {latest_year}년"
)
