import streamlit as st
import requests
import folium
from streamlit_folium import st_folium
from typing import Literal
import openai
import base64
import os
from dotenv import load_dotenv

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

def call_llm_api_with_image(image_file, api_key):
    """画像ファイルを直接LLM APIに送信して結果を取得"""
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    try:
        openai.api_key = api_key
        
        # 画像ファイルをBase64エンコード
        image_file.seek(0)  # ファイルポインタを先頭に戻す
        image_base64 = base64.b64encode(image_file.read()).decode('utf-8')
        
        # ファイルタイプを取得
        file_type = image_file.type if hasattr(image_file, 'type') else 'image/png'
        
        full_prompt = """
{
 'request': 'Extract the following information from the provided PDF document into a JSON format:',
 'fields': {
  'document_type': 'The type of the document',
  'sample_document': "Boolean indicating if it's a sample document ()",
  'date_of_issue': 'The issue date of the document',
  'issuing_office': 'The office that issued the document',
  'registrar': 'The name of the registrar',
  'management_number': 'The management number',
  'disclaimer_underline': 'The disclaimer regarding underlined items',
  'land_information': {
   'real_estate_number': '不動産番号',
   'location': '所在',
   'lot_number': '地番',
   'land_category': '地目',
   'land_area_sqm': '地積 (m²)',
   'cause_and_date': {
    'cause': '原因',
    'registration_date': '登記の日付'
   },
   'owner': {
    'address': '所有者住所',
    'name': '所有者名'
   }
  },
  'rights_section_A_ownership': [
   {
    'sequence_number': '順位番号',
    'purpose_of_registration': '登記の目的',
    'reception_date_and_number': '受付年月日・受付番号',
    'rights_holder_and_other_matters': {
     'owner_address': '所有者住所',
     'owner_name': '所有者名',
     'cause': '原因',
     'is_erased': '抹消事項であるか (boolean, 下線があればtrue)'
    }
   }
  ],
  'rights_section_B_other_rights': [
   {
    'sequence_number': '順位番号',
    'purpose_of_registration': '登記の目的',
    'reception_date_and_number': '受付年月日・受付番号',
    'rights_holder_and_other_matters': {
     'cause': '原因',
     'debt_amount_yen': '債権額 (円)',
     'interest_rate_annual_percent': '利息 (年率%)',
     'damages_rate_annual_percent': '損害金 (年率%)',
     'debtor': {
      'address': '債務者住所',
      'name': '債務者名'
     },
     'mortgage_holder': {
      'address': '抵当権者住所',
      'name': '抵当権者名',
      'branch_name': '取扱店'
     },
     'joint_collateral_catalog_number': '共同担保目録番号',
     'is_erased': '抹消事項であるか (boolean, 下線があればtrue)'
    }
   }
  ],
  'joint_collateral_catalog': {
   'catalog_number': '共同担保目録の番号',
   'prepared_date': '調製日',
   'items': [
    {
     'number': '番号',
     'description_of_right': '担保の目的である権利の表示',
     'sequence_number': '順位番号',
     'is_erased': '抹消事項であるか (boolean, 下線があればtrue)'
    }
   ]
  }
 }
}
"""
        
        response = openai.chat.completions.create(
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

def extract_data_from_response(response_text):
    """LLMレスポンスから住所と土地情報を抽出"""
    addresses = []
    land_info = None
    
    try:
        # JSONとして解析を試みる
        import json
        data = json.loads(response_text)
        
        # land_information全体を保存
        if 'land_information' in data:
            land_info = data['land_information']
            
            # 土地の所在地を抽出
            if 'location' in land_info:
                location = land_info['location']
                if location and location not in addresses:
                    addresses.append(location)
            
            # 所有者住所を抽出
            if 'owner' in land_info and 'address' in land_info['owner']:
                owner_address = land_info['owner']['address']
                if owner_address and owner_address not in addresses:
                    addresses.append(owner_address)
        
        # 権利部A（所有権）から住所を抽出
        if 'rights_section_A_ownership' in data:
            for item in data['rights_section_A_ownership']:
                if 'rights_holder_and_other_matters' in item and 'owner_address' in item['rights_holder_and_other_matters']:
                    addr = item['rights_holder_and_other_matters']['owner_address']
                    if addr and addr not in addresses:
                        addresses.append(addr)
        
        # 権利部B（その他の権利）から住所を抽出
        if 'rights_section_B_other_rights' in data:
            for item in data['rights_section_B_other_rights']:
                if 'rights_holder_and_other_matters' in item:
                    matters = item['rights_holder_and_other_matters']
                    # 債務者住所
                    if 'debtor' in matters and 'address' in matters['debtor']:
                        addr = matters['debtor']['address']
                        if addr and addr not in addresses:
                            addresses.append(addr)
                    # 抵当権者住所
                    if 'mortgage_holder' in matters and 'address' in matters['mortgage_holder']:
                        addr = matters['mortgage_holder']['address']
                        if addr and addr not in addresses:
                            addresses.append(addr)
    
    except json.JSONDecodeError:
        # JSON解析に失敗した場合は、従来の方法で抽出を試みる
        lines = response_text.split('\n')
        for line in lines:
            line = line.strip()
            # 日本の住所パターンを探す（都道府県から始まる）
            if any(pref in line for pref in ['東京都', '大阪府', '京都府', '北海道'] + [f'{p}県' for p in ['青森', '岩手', '宮城', '秋田', '山形', '福島', '茨城', '栃木', '群馬', '埼玉', '千葉', '神奈川', '新潟', '富山', '石川', '福井', '山梨', '長野', '岐阜', '静岡', '愛知', '三重', '滋賀', '兵庫', '奈良', '和歌山', '鳥取', '島根', '岡山', '広島', '山口', '徳島', '香川', '愛媛', '高知', '福岡', '佐賀', '長崎', '熊本', '大分', '宮崎', '鹿児島', '沖縄']]):
                # 住所として抽出
                if line not in addresses and len(line) > 5:  # 最低限の長さチェック
                    addresses.append(line)
    
    return addresses, land_info

# セッション状態の初期化
if 'llm_response' not in st.session_state:
    st.session_state.llm_response = None
if 'extracted_addresses' not in st.session_state:
    st.session_state.extracted_addresses = []
if 'land_information' not in st.session_state:
    st.session_state.land_information = None

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


# 画像アップロード
with st.container():
    uploaded_file = st.file_uploader(
        "画像ファイルをアップロード",
        type=["png", "jpg", "jpeg"],
        help="分析したい画像ファイルを選択してください"
    )

# 分析実行ボタン
if uploaded_file:
    # 環境変数からAPIキーを取得
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    
    if api_key:
        if st.button("🤖 AI分析を実行", type="primary", use_container_width=True):
            with st.spinner("画像を分析中..."):
                # 画像ファイルを直接LLM APIに送信
                llm_response = call_llm_api_with_image(uploaded_file, api_key)
                
                if llm_response:
                    st.session_state.llm_response = llm_response
                    addresses, land_info = extract_data_from_response(llm_response)
                    st.session_state.extracted_addresses = addresses
                    st.session_state.land_information = land_info
    else:
        st.error("⚠️ OPENAI_API_KEY環境変数が設定されていません")

# LLM分析結果の表示
if st.session_state.llm_response:
    st.markdown("---")
    st.subheader("🤖 AI分析結果")
    
    # 分析結果を表示
    with st.expander("📋 完全な分析結果", expanded=False):
        st.markdown(st.session_state.llm_response)
    
    # 土地情報を表示
    if st.session_state.land_information:
        st.markdown("### 📄 土地情報")
        
        land_info = st.session_state.land_information
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**基本情報**")
            if 'real_estate_number' in land_info and land_info['real_estate_number']:
                st.write(f"• 不動産番号: {land_info['real_estate_number']}")
            
            # 所在地をクリック可能にする
            if 'location' in land_info and land_info['location']:
                location_col1, location_col2 = st.columns([1, 3])
                with location_col1:
                    st.write("• 所在:")
                with location_col2:
                    if st.button(
                        f"📍 {land_info['location']}", 
                        key="land_location_btn",
                        use_container_width=True,
                        help="クリックして住所として使用"
                    ):
                        st.session_state.search_address = land_info['location']
                        st.session_state.selected_extracted = land_info['location']
                        st.success(f"住所を設定しました: {land_info['location']}")
                        st.rerun()
            
            if 'lot_number' in land_info and land_info['lot_number']:
                st.write(f"• 地番: {land_info['lot_number']}")
            
            # 所在地と地番を組み合わせた完全な住所を提供
            if 'location' in land_info and land_info['location'] and 'lot_number' in land_info and land_info['lot_number']:
                full_address = f"{land_info['location']}{land_info['lot_number']}"
                if st.button(
                    f"📍 {full_address} (所在+地番)", 
                    key="full_address_btn",
                    use_container_width=True,
                    help="所在地と地番を組み合わせた住所を使用"
                ):
                    st.session_state.search_address = full_address
                    st.session_state.selected_extracted = full_address
                    st.success(f"住所を設定しました: {full_address}")
                    st.rerun()
            if 'land_category' in land_info and land_info['land_category']:
                st.write(f"• 地目: {land_info['land_category']}")
            if 'land_area_sqm' in land_info and land_info['land_area_sqm']:
                st.write(f"• 地積: {land_info['land_area_sqm']}")
        
        with col2:
            st.markdown("**所有者情報**")
            if 'owner' in land_info:
                if 'name' in land_info['owner'] and land_info['owner']['name']:
                    st.write(f"• 所有者名: {land_info['owner']['name']}")
                
                # 所有者住所をクリック可能にする
                if 'address' in land_info['owner'] and land_info['owner']['address']:
                    owner_col1, owner_col2 = st.columns([1, 3])
                    with owner_col1:
                        st.write("• 所有者住所:")
                    with owner_col2:
                        if st.button(
                            f"📍 {land_info['owner']['address']}", 
                            key="owner_address_btn",
                            use_container_width=True,
                            help="クリックして住所として使用"
                        ):
                            st.session_state.search_address = land_info['owner']['address']
                            st.session_state.selected_extracted = land_info['owner']['address']
                            st.success(f"住所を設定しました: {land_info['owner']['address']}")
                            st.rerun()
            
            if 'cause_and_date' in land_info:
                st.markdown("**原因・日付**")
                if 'cause' in land_info['cause_and_date'] and land_info['cause_and_date']['cause']:
                    st.write(f"• 原因: {land_info['cause_and_date']['cause']}")
                if 'registration_date' in land_info['cause_and_date'] and land_info['cause_and_date']['registration_date']:
                    st.write(f"• 登記日付: {land_info['cause_and_date']['registration_date']}")
    
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
        st.session_state.land_information = None
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