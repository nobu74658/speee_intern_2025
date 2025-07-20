import streamlit as st
import requests
import folium
from streamlit_folium import st_folium
from typing import Literal

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

# UIコンテナ
with st.container():
    st.subheader("📍 住所を入力")
    
    # カスタム住所入力
    with st.form(key='address_form'):
        col1, col2 = st.columns([4, 1])
        with col1:
            custom_address = st.text_input(
                "住所",
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