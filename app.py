import streamlit as st
import requests
import folium
from streamlit_folium import st_folium
from typing import Literal
from openai import OpenAI
import base64
import os

st.set_page_config(page_title="ハザードマップ表示", layout="wide", page_icon="🗾")
st.title("🗾 ハザードマップ表示アプリ")
st.markdown("住所を入力すると、その地域の災害リスク情報を確認できます")

@st.cache_data(ttl=3600)
def get_hazard_info(lat, lon):
    """指定座標のハザード情報を取得"""
    hazard_info = {
        "flood": {"level": "不明", "detail": "データなし"},
        "landslide": {"level": "不明", "detail": "データなし"},
        "tsunami": {"level": "不明", "detail": "データなし"}
    }
    
    # 標高データを取得（津波リスク判定用）
    try:
        elevation_url = f"https://cyberjapandata2.gsi.go.jp/general/dem/scripts/getelevation.php?lon={lon}&lat={lat}&outtype=JSON"
        elev_response = requests.get(elevation_url)
        elev_data = elev_response.json()
        
        if "elevation" in elev_data:
            elevation = float(elev_data["elevation"])
            
            # 簡易的な津波リスク判定
            if elevation < 5:
                hazard_info["tsunami"]["level"] = "高い"
                hazard_info["tsunami"]["detail"] = f"標高 {elevation:.1f}m（沿岸低地）"
            elif elevation < 10:
                hazard_info["tsunami"]["level"] = "中程度"
                hazard_info["tsunami"]["detail"] = f"標高 {elevation:.1f}m"
            else:
                hazard_info["tsunami"]["level"] = "低い"
                hazard_info["tsunami"]["detail"] = f"標高 {elevation:.1f}m"
    except:
        pass
    
    # 洪水リスクの簡易判定（河川からの距離等で判定する実装が必要）
    # プロトタイプでは地域によって仮の値を設定
    if lat > 35.6 and lat < 35.7 and lon > 139.7 and lon < 139.8:  # 東京都心部
        hazard_info["flood"]["level"] = "中程度"
        hazard_info["flood"]["detail"] = "河川氾濫想定区域"
    
    return hazard_info

def check_proxy_settings():
    proxy_keys = [
        "http_proxy", "https_proxy",
        "HTTP_PROXY", "HTTPS_PROXY"
    ]
    
    found = False
    for key in proxy_keys:
        value = os.environ.get(key)
        if value:
            st.write(f"⚠️ `{key}` が設定されています: `{value}`")
            found = True
    
    if not found:
        st.success("プロキシ環境変数は設定されていません。")

check_proxy_settings()

def call_llm_api_with_image(image_file, prompt, api_key):
    """画像ファイルを直接LLM APIに送信して結果を取得"""
    check_proxy_settings()
    try:
        client = OpenAI(api_key=api_key)
        
        # 画像ファイルをBase64エンコード
        image_file.seek(0)  # ファイルポインタを先頭に戻す
        image_base64 = base64.b64encode(image_file.read()).decode('utf-8')
        
        # ファイルタイプを取得
        file_type = image_file.type if hasattr(image_file, 'type') else 'image/png'
        
        full_prompt = f"""
アップロードされた画像ファイルを分析してください。
特に住所情報に注目して分析してください。

ユーザーのプロンプト: {prompt}

住所情報が含まれている場合は、以下の形式で出力してください：
【住所一覧】
- 住所1
- 住所2
- ...

その他の分析結果も含めて回答してください。
"""
        
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "あなたは日本の住所情報の抽出と分析を得意とするAIアシスタントです。画像ファイルの内容を読み取り、分析することができます。"},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": full_prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{file_type};base64,{image_base64}"
                            }
                        }
                    ]
                }
            ],
            max_tokens=1500,
            temperature=0.3
        )
        
        return response.choices[0].message.content
    except Exception as e:
        st.error(f"API呼び出しエラー: {str(e)}")
        return None

def extract_addresses_from_response(response_text):
    """LLMレスポンスから住所を抽出"""
    addresses = []
    lines = response_text.split('\n')
    in_address_section = False
    
    for line in lines:
        line = line.strip()
        if '【住所一覧】' in line or '住所一覧' in line:
            in_address_section = True
            continue
        elif line.startswith('【') and line.endswith('】'):
            in_address_section = False
            continue
        elif in_address_section and line.startswith('- '):
            address = line[2:].strip()
            if address:
                addresses.append(address)
    
    return addresses

# セッション状態の初期化
if 'llm_response' not in st.session_state:
    st.session_state.llm_response = None
if 'extracted_addresses' not in st.session_state:
    st.session_state.extracted_addresses = []

# サンプル住所
sample_addresses = {
    "東京都江東区豊洲3-3-3": "河川に近い地域",
    "東京都港区海岸1-1-1": "沿岸部の地域",
    "東京都世田谷区成城6-1-1": "内陸の住宅地",
    "神奈川県鎌倉市由比ガ浜2-1-1": "海岸沿いの地域",
    "東京都八王子市高尾町1-1": "山間部の地域"
}

# セッション状態の初期化
if 'search_address' not in st.session_state:
    st.session_state.search_address = None

# 画像アップロードセクション
st.markdown("---")
st.subheader("🖼️ 画像分析機能")
st.markdown("画像ファイルをアップロードして、AI分析により住所情報を抽出します")

with st.container():
    col1, col2 = st.columns([3, 1])
    
    with col1:
        # APIキー入力
        api_key = st.text_input(
            "OpenAI APIキー",
            type="password",
            placeholder="sk-...",
            help="OpenAI APIキーを入力してください"
        )
    
    with col2:
        st.markdown("")  # スペース調整

# 画像アップロードとプロンプト入力
with st.container():
    col1, col2 = st.columns([2, 2])
    
    with col1:
        uploaded_file = st.file_uploader(
            "画像ファイルをアップロード",
            type=["png", "jpg", "jpeg"],
            help="分析したい画像ファイルを選択してください"
        )
    
    with col2:
        prompt = st.text_area(
            "分析プロンプト",
            placeholder="例: この文書から住所情報を抽出してください",
            height=100,
            help="画像に対してどのような分析を行いたいか入力してください"
        )

# 分析実行ボタン
if uploaded_file and prompt and api_key:
    if st.button("🤖 AI分析を実行", type="primary", use_container_width=True):
        with st.spinner("画像を分析中..."):
            # 画像ファイルを直接LLM APIに送信
            llm_response = call_llm_api_with_image(uploaded_file, prompt, api_key)
            
            if llm_response:
                st.session_state.llm_response = llm_response
                st.session_state.extracted_addresses = extract_addresses_from_response(llm_response)

# LLM分析結果の表示
if st.session_state.llm_response:
    st.markdown("---")
    st.subheader("🤖 AI分析結果")
    
    # 分析結果を表示
    with st.expander("📋 完全な分析結果", expanded=False):
        st.markdown(st.session_state.llm_response)
    
    # 抽出された住所を表示
    if st.session_state.extracted_addresses:
        st.markdown("### 📍 抽出された住所")
        
        # 住所をボタンで表示（クリックでカスタム住所欄に入力）
        address_cols = st.columns(min(3, len(st.session_state.extracted_addresses)))
        for idx, address in enumerate(st.session_state.extracted_addresses):
            col_idx = idx % len(address_cols)
            with address_cols[col_idx]:
                if st.button(
                    f"📍 {address}",
                    key=f"extracted_address_{idx}",
                    use_container_width=True,
                    help="クリックしてカスタム住所欄に入力"
                ):
                    st.session_state.search_address = address
                    st.session_state.selected_extracted = address
                    st.success(f"住所を設定しました: {address}")
                    st.rerun()
    
    # 結果をクリアするボタン
    if st.button("🗑️ 分析結果をクリア", type="secondary"):
        st.session_state.llm_response = None
        st.session_state.extracted_addresses = []
        st.rerun()

# UIコンテナ
with st.container():
    st.subheader("📍 住所を入力")
    
    # カスタム住所入力
    with st.form(key='address_form'):
        col1, col2 = st.columns([4, 1])
        with col1:
            # 抽出された住所が選択されている場合はデフォルト値として設定
            default_address = ""
            if hasattr(st.session_state, 'selected_extracted') and st.session_state.selected_extracted:
                default_address = st.session_state.selected_extracted
                # 一度使ったらクリア
                st.session_state.selected_extracted = None
            
            custom_address = st.text_input(
                "住所",
                value=default_address,
                placeholder="例: 東京都千代田区丸の内1-1-1",
                label_visibility="collapsed"
            )
        with col2:
            search_button = st.form_submit_button("🔍 検索", type="primary", use_container_width=True)
    
    # サンプル住所選択
    with st.expander("💡 サンプル住所から選択", expanded=False):
        sample_cols = st.columns(2)
        for idx, (address, description) in enumerate(sample_addresses.items()):
            col = sample_cols[idx % 2]
            with col:
                if st.button(f"{address}\n({description})", key=f"sample_{idx}", use_container_width=True):
                    st.session_state.search_address = address
                    st.session_state.selected_sample = address

# 検索実行の判定
address = None

# カスタム住所の検索ボタンが押された場合
if search_button and custom_address:
    st.session_state.search_address = custom_address
    address = custom_address

# 前回の検索結果を維持またはサンプル選択
elif st.session_state.search_address:
    address = st.session_state.search_address

# 住所情報の表示
if address and address in sample_addresses:
    st.info(f"📍 {address} - {sample_addresses[address]}")

if address:
    # 住所から緯度経度を取得（国土地理院ジオコーディングAPI）
    geocoding_url = f"https://msearch.gsi.go.jp/address-search/AddressSearch?q={address}"

    try:
        response = requests.get(geocoding_url)
        data = response.json()

        if data:
            # 最初の検索結果を使用
            first_result = data[0]
            lat = first_result["geometry"]["coordinates"][1]
            lon = first_result["geometry"]["coordinates"][0]

            with st.container():
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.success(f"📍 {first_result['properties']['title']}")
                with col2:
                    st.metric("座標", f"{lat:.4f}, {lon:.4f}", label_visibility="collapsed")

            # 地図を作成
            m = folium.Map(location=[lat, lon], zoom_start=15)

            # 入力した住所の位置にマーカーを配置
            folium.Marker(
                [lat, lon],
                popup=address,
                tooltip=address,
                icon=folium.Icon(color='red', icon='home')
            ).add_to(m)

            # ハザードマップタイルレイヤーを追加
            # 洪水浸水想定区域（想定最大規模）
            folium.TileLayer(
                tiles='https://disaportaldata.gsi.go.jp/raster/01_flood_l2_shinsuishin_data/{z}/{x}/{y}.png',
                attr='国土地理院',
                name='洪水浸水想定区域',
                overlay=True,
                control=True,
                opacity=0.6
            ).add_to(m)

            # 津波浸水想定
            folium.TileLayer(
                tiles='https://disaportaldata.gsi.go.jp/raster/04_tsunami_newlegend_data/{z}/{x}/{y}.png',
                attr='国土地理院',
                name='津波浸水想定',
                overlay=True,
                control=True,
                opacity=0.6
            ).add_to(m)

            # 土砂災害警戒区域
            folium.TileLayer(
                tiles='https://disaportaldata.gsi.go.jp/raster/05_dosekiryukeikaikuiki/{z}/{x}/{y}.png',
                attr='国土地理院',
                name='土砂災害警戒区域',
                overlay=True,
                control=True,
                opacity=0.6
            ).add_to(m)

            # レイヤーコントロールを追加
            folium.LayerControl().add_to(m)

            # 地図とハザードマップ説明を横並びに
            st.markdown("---")
            st.subheader("🗺️ ハザードマップ")
            
            map_col, info_col = st.columns([3, 1])
            
            with map_col:
                # 地図を表示
                st_folium(m, width=700, height=500, returned_objects=[])
            
            with info_col:
                st.markdown("### 凡例")
                st.markdown("""
                🔵 **洪水浸水想定区域**  
                河川氾濫時の浸水深
                
                🌊 **津波浸水想定**  
                津波による浸水深
                
                🟡 **土砂災害警戒区域**  
                土砂災害の危険性
                
                ---
                
                💡 **操作方法**
                - 右上のボタンでレイヤー切替
                - マウスで地図の移動・拡大縮小
                """)
                
                st.warning("地域によってはデータが存在しない場合があります", icon="⚠️")

            # 危険度判定
            st.markdown("---")
            st.subheader("📊 危険度判定")

            # 実際のハザード情報を取得
            hazard_info = get_hazard_info(lat, lon)
            
            # リスク評価を3列で表示
            risk_cols = st.columns(3)
            
            # リスクレベルに応じた色とアイコンを設定
            def get_risk_color(level) -> Literal["normal", "inverse", "off"]:
                if level == "高い":
                    return "inverse"
                elif level == "中程度":
                    return "normal"
                else:
                    return "off"
            
            def get_risk_icon(level) -> str:
                if level == "高い":
                    return "🔴"
                elif level == "中程度":
                    return "🟡"
                else:
                    return "🟢"
            
            with risk_cols[0]:
                icon = get_risk_icon(hazard_info["flood"]["level"])
                color = get_risk_color(hazard_info["flood"]["level"])
                st.metric(
                    label=f"{icon} 洪水リスク",
                    value=hazard_info["flood"]["level"],
                    delta=hazard_info["flood"]["detail"],
                    delta_color=color
                )
            
            with risk_cols[1]:
                icon = get_risk_icon(hazard_info["landslide"]["level"])
                color = get_risk_color(hazard_info["landslide"]["level"])
                st.metric(
                    label=f"{icon} 土砂災害リスク",
                    value=hazard_info["landslide"]["level"],
                    delta=hazard_info["landslide"]["detail"],
                    delta_color=color
                )
            
            with risk_cols[2]:
                icon = get_risk_icon(hazard_info["tsunami"]["level"])
                color = get_risk_color(hazard_info["tsunami"]["level"])
                st.metric(
                    label=f"{icon} 津波リスク",
                    value=hazard_info["tsunami"]["level"],
                    delta=hazard_info["tsunami"]["detail"],
                    delta_color=color
                )
            
            # 注意事項
            with st.expander("⚠️ 重要な注意事項", expanded=False):
                st.warning("""
                - この評価は標高データ等を基にした簡易的な判定です
                - 正確な情報は各自治体の公式ハザードマップをご確認ください
                - 実際の災害リスクは地形、建物、季節、気象条件により変動します
                - 避難場所や避難経路も併せて確認することをお勧めします
                - 最新の防災情報は自治体の防災ページでご確認ください
                """)

        else:
            st.error("住所が見つかりませんでした。別の住所を入力してください。")

    except Exception as e:
        st.error(f"エラーが発生しました: {str(e)}")