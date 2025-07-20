import streamlit as st
import requests
import folium
from streamlit_folium import st_folium

st.set_page_config(page_title="ハザードマップ表示", layout="wide")
st.title("ハザードマップ表示アプリ")

# 住所入力
address = st.text_input("住所を入力してください", placeholder="例: 東京都千代田区丸の内1-1-1")

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

            st.success(f"住所: {first_result['properties']['title']}")
            st.write(f"緯度: {lat}, 経度: {lon}")

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

            # 地図を表示
            st_folium(m, width=800, height=600)

            # ハザードマップの説明
            st.info("""
            **表示されるハザードマップ:**
            - 🔵 洪水浸水想定区域: 河川が氾濫した場合の浸水深を示します
            - 🌊 津波浸水想定: 津波による浸水の深さを示します
            - 🟡 土砂災害警戒区域: 土砂災害のおそれがある区域を示します

            ※ レイヤーは右上のコントロールで切り替えできます
            ※ 地域によってはハザードマップデータが存在しない場合があります
            """)

            # 危険度判定
            st.subheader("危険度判定")

            # 簡易的な危険度判定（デモ用）
            with st.expander("この地域の災害リスク評価", expanded=True):
                col1, col2, col3 = st.columns(3)

                with col1:
                    st.metric(
                        label="洪水リスク",
                        value="中程度",
                        delta="浸水深 0.5m～1.0m",
                        delta_color="normal"
                    )

                with col2:
                    st.metric(
                        label="土砂災害リスク",
                        value="低い",
                        delta="警戒区域外",
                        delta_color="off"
                    )

                with col3:
                    st.metric(
                        label="津波リスク",
                        value="対象外",
                        delta="内陸部",
                        delta_color="off"
                    )

                st.warning("""
                **注意事項:**
                - この評価は参考情報です。正確な情報は各自治体のハザードマップをご確認ください
                - 実際の災害リスクは地形、建物、時期などにより変動します
                - 避難場所や避難経路も併せて確認することをお勧めします
                """)

        else:
            st.error("住所が見つかりませんでした。別の住所を入力してください。")

    except Exception as e:
        st.error(f"エラーが発生しました: {str(e)}")