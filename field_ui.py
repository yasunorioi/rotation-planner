"""
ほ場登録アプリ UIモジュール

portal.py に統合するためのUIコンポーネント。
認証はportal.pyで一元管理するため、このモジュールには含まない。

使用方法:
    from field_ui import create_field_register_ui

    # portal.py 内で
    with gr.Tab("ほ場登録"):
        field_components = create_field_register_ui(user_state)
"""

import gradio as gr
import pandas as pd
import json
import os
import requests
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from shapely.geometry import Polygon
from pyproj import Geod

# DBモジュール（認証はportal.pyで管理）
from db_access import FieldRepository, CropHistoryRepository, UserRepository

os.environ["GRADIO_ANALYTICS_ENABLED"] = "False"

# =============================================================================
# 定数
# =============================================================================

# 北海道の初期位置（札幌付近）
DEFAULT_LAT = 43.06
DEFAULT_LNG = 141.35
DEFAULT_ZOOM = 12

# Nominatim API エンドポイント
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"


# =============================================================================
# 面積計算
# =============================================================================

def calculate_area_from_coords(coordinates: List[List[float]]) -> float:
    """
    座標リストから面積を計算（平方メートル）
    WGS84楕円体上の面積を正確に計算
    """
    if len(coordinates) < 3:
        return 0.0

    # 座標を (lng, lat) 形式に変換（Shapelyは経度,緯度の順）
    coords_lnglat = [(coord[1], coord[0]) for coord in coordinates]

    # ポリゴンを閉じる
    if coords_lnglat[0] != coords_lnglat[-1]:
        coords_lnglat.append(coords_lnglat[0])

    # Geod（測地線計算）を使用して面積を計算
    geod = Geod(ellps="WGS84")

    # polygon_area_perimeter は (面積, 周長) を返す
    # 面積は符号付きで返されるので abs() を使用
    lons = [c[0] for c in coords_lnglat]
    lats = [c[1] for c in coords_lnglat]
    area_m2, _ = geod.polygon_area_perimeter(lons, lats)

    return abs(area_m2)


def m2_to_a(m2: float) -> float:
    """平方メートルをアールに変換"""
    return m2 / 100.0


def m2_to_ha(m2: float) -> float:
    """平方メートルをヘクタールに変換"""
    return m2 / 10000.0


# =============================================================================
# 住所検索
# =============================================================================

def search_address(query: str) -> Tuple[Optional[float], Optional[float], str]:
    """
    住所・地名からNominatim APIで座標を検索
    Returns: (lat, lng, message)
    """
    if not query.strip():
        return None, None, "検索語を入力してください"

    try:
        params = {
            "q": query,
            "format": "json",
            "limit": 1,
            "countrycodes": "jp",  # 日本に限定
        }
        headers = {
            "User-Agent": "FieldRegisterApp/1.0"  # Nominatim利用規約に準拠
        }

        response = requests.get(NOMINATIM_URL, params=params, headers=headers, timeout=10)
        response.raise_for_status()

        results = response.json()

        if results:
            lat = float(results[0]["lat"])
            lng = float(results[0]["lon"])
            display_name = results[0].get("display_name", query)
            return lat, lng, f"検索結果: {display_name}"
        else:
            return None, None, f"「{query}」の検索結果が見つかりません"

    except requests.exceptions.Timeout:
        return None, None, "検索がタイムアウトしました"
    except requests.exceptions.RequestException as e:
        return None, None, f"検索エラー: {str(e)}"
    except Exception as e:
        return None, None, f"予期しないエラー: {str(e)}"


# =============================================================================
# ヘルパー関数
# =============================================================================

def get_user_id_from_state(user_state: Dict[str, Any]) -> Optional[int]:
    """user_stateからユーザーIDを取得"""
    if user_state:
        return user_state.get('user_id')
    return None


def get_username_from_state(user_state: Dict[str, Any]) -> Optional[str]:
    """user_stateからユーザー名を取得"""
    if user_state:
        return user_state.get('username')
    return None


# =============================================================================
# Leaflet HTML/JS 生成
# =============================================================================

def generate_map_html(
    center_lat: float = DEFAULT_LAT,
    center_lng: float = DEFAULT_LNG,
    zoom: int = DEFAULT_ZOOM,
    existing_fields: List[Dict[str, Any]] = None
) -> str:
    """Leaflet地図のHTMLを生成"""

    existing_fields = existing_fields or []

    # 既存ほ場のポリゴンデータをJSON形式で埋め込む
    fields_json = json.dumps([
        {
            "field_id": f.get("field_code", f.get("id", "")),
            "name": f.get("name", ""),
            "coordinates": json.loads(f.get("coordinates_json", "[]")) if isinstance(f.get("coordinates_json"), str) else f.get("coordinates_json", []),
            "area_a": f.get("area_a", f.get("area_ha", 0) * 100)
        }
        for f in existing_fields
        if f.get("coordinates_json")
    ])

    html = f'''
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet.draw/1.0.4/leaflet.draw.css" />
        <style>
            #map {{
                width: 100%;
                height: 500px;
                border: 2px solid #ccc;
                border-radius: 8px;
            }}
            .area-display {{
                background: white;
                padding: 10px;
                border-radius: 5px;
                box-shadow: 0 2px 5px rgba(0,0,0,0.2);
            }}
            .field-popup {{
                min-width: 150px;
            }}
        </style>
    </head>
    <body>
        <div id="map"></div>

        <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet.draw/1.0.4/leaflet.draw.js"></script>
        <script>
            // 地図初期化
            var map = L.map('map').setView([{center_lat}, {center_lng}], {zoom});

            // OpenStreetMap タイルレイヤー
            L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
                attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
                maxZoom: 19
            }}).addTo(map);

            // 描画レイヤー
            var drawnItems = new L.FeatureGroup();
            map.addLayer(drawnItems);

            // 既存ほ場レイヤー
            var existingFields = new L.FeatureGroup();
            map.addLayer(existingFields);

            // 描画コントロール
            var drawControl = new L.Control.Draw({{
                position: 'topright',
                draw: {{
                    polygon: {{
                        allowIntersection: false,
                        showArea: true,
                        shapeOptions: {{
                            color: '#3388ff',
                            fillColor: '#3388ff',
                            fillOpacity: 0.3
                        }}
                    }},
                    polyline: false,
                    circle: false,
                    rectangle: false,
                    marker: false,
                    circlemarker: false
                }},
                edit: {{
                    featureGroup: drawnItems,
                    remove: true,
                    edit: true
                }}
            }});
            map.addControl(drawControl);

            // 面積表示コントロール
            var areaInfo = L.control({{position: 'bottomright'}});
            areaInfo.onAdd = function(map) {{
                this._div = L.DomUtil.create('div', 'area-display');
                this.update();
                return this._div;
            }};
            areaInfo.update = function(area_m2) {{
                if (area_m2) {{
                    var area_a = (area_m2 / 100).toFixed(2);
                    var area_ha = (area_m2 / 10000).toFixed(4);
                    this._div.innerHTML = '<b>描画中の面積</b><br>' +
                        area_a + ' a<br>' +
                        area_ha + ' ha';
                }} else {{
                    this._div.innerHTML = '<b>面積</b><br>ポリゴンを描画してください';
                }}
            }};
            areaInfo.addTo(map);

            // 現在描画中のポリゴン座標
            var currentPolygonCoords = null;

            // ポリゴン作成完了イベント
            map.on(L.Draw.Event.CREATED, function(event) {{
                var layer = event.layer;
                drawnItems.clearLayers();  // 1つだけ描画可能
                drawnItems.addLayer(layer);

                // 座標を取得
                var latlngs = layer.getLatLngs()[0];
                currentPolygonCoords = latlngs.map(function(ll) {{
                    return [ll.lat, ll.lng];
                }});

                // 面積計算（クライアント側の概算）
                var area_m2 = L.GeometryUtil.geodesicArea(latlngs);
                areaInfo.update(area_m2);

                // Gradioに座標を送信
                sendCoordinatesToGradio(currentPolygonCoords);
            }});

            // ポリゴン編集完了イベント
            map.on(L.Draw.Event.EDITED, function(event) {{
                var layers = event.layers;
                layers.eachLayer(function(layer) {{
                    var latlngs = layer.getLatLngs()[0];
                    currentPolygonCoords = latlngs.map(function(ll) {{
                        return [ll.lat, ll.lng];
                    }});

                    var area_m2 = L.GeometryUtil.geodesicArea(latlngs);
                    areaInfo.update(area_m2);

                    sendCoordinatesToGradio(currentPolygonCoords);
                }});
            }});

            // ポリゴン削除イベント
            map.on(L.Draw.Event.DELETED, function(event) {{
                currentPolygonCoords = null;
                areaInfo.update(null);
                sendCoordinatesToGradio(null);
            }});

            // Gradioへ座標送信
            function sendCoordinatesToGradio(coords) {{
                var coordsJson = coords ? JSON.stringify(coords) : '';

                // Gradioのhidden textboxに値を設定
                var event = new CustomEvent('polygon_update', {{
                    detail: {{ coordinates: coordsJson }}
                }});
                document.dispatchEvent(event);

                // 親ウィンドウにも送信（iframe対応）
                if (window.parent) {{
                    window.parent.postMessage({{
                        type: 'polygon_coordinates',
                        coordinates: coordsJson
                    }}, '*');
                }}
            }}

            // 既存ほ場を表示
            var existingData = {fields_json};
            existingData.forEach(function(field) {{
                if (field.coordinates && field.coordinates.length > 0) {{
                    var polygon = L.polygon(field.coordinates, {{
                        color: '#28a745',
                        fillColor: '#28a745',
                        fillOpacity: 0.3
                    }}).addTo(existingFields);

                    polygon.bindPopup(
                        '<div class="field-popup">' +
                        '<b>' + field.field_id + '</b><br>' +
                        field.name + '<br>' +
                        field.area_a.toFixed(2) + ' a' +
                        '</div>'
                    );
                }}
            }});

            // 地図の中心移動関数（外部から呼び出し用）
            window.moveMapTo = function(lat, lng, zoom) {{
                map.setView([lat, lng], zoom || 15);
            }};

            // 現在の座標を取得する関数
            window.getCurrentCoords = function() {{
                return currentPolygonCoords ? JSON.stringify(currentPolygonCoords) : '';
            }};

            // ポリゴンをクリアする関数
            window.clearDrawnPolygon = function() {{
                drawnItems.clearLayers();
                currentPolygonCoords = null;
                areaInfo.update(null);
            }};
        </script>
    </body>
    </html>
    '''

    return html


# =============================================================================
# DBからほ場一覧取得
# =============================================================================

def get_user_fields(user_id: int) -> List[Dict[str, Any]]:
    """ユーザーのほ場一覧をDBから取得"""
    if not user_id:
        return []
    return FieldRepository.get_fields(user_id)


def fields_to_dataframe(fields: List[Dict[str, Any]]) -> pd.DataFrame:
    """ほ場リストをDataFrameに変換"""
    if not fields:
        return pd.DataFrame(columns=["ID", "ほ場ID", "地区", "ほ場名", "面積(ha)", "面積(a)", "禁止"])

    rows = []
    for f in fields:
        area_ha = f.get("area_ha", 0)
        area_a = f.get("area_a", area_ha * 100)
        rows.append({
            "ID": f.get("id", ""),
            "ほ場ID": f.get("field_code", ""),
            "地区": f.get("district", ""),
            "ほ場名": f.get("name", ""),
            "面積(ha)": f"{area_ha:.4f}",
            "面積(a)": f"{area_a:.2f}",
            "禁止": "Yes" if f.get("beet_forbidden") else "No"
        })
    return pd.DataFrame(rows)


def get_fields_json_for_map(fields: List[Dict[str, Any]]) -> str:
    """地図表示用JSONを取得"""
    return json.dumps([
        {
            "field_id": f.get("field_code", f.get("id", "")),
            "name": f.get("name", ""),
            "coordinates": json.loads(f.get("coordinates_json", "[]")) if isinstance(f.get("coordinates_json"), str) else [],
            "area_a": f.get("area_a", f.get("area_ha", 0) * 100)
        }
        for f in fields
        if f.get("coordinates_json")
    ])


# =============================================================================
# UI操作関数（user_stateを使用）
# =============================================================================

def register_field_with_state(
    field_id: str,
    district: str,
    name: str,
    beet_forbidden: bool,
    coords_json: str,
    user_state: Dict[str, Any]
) -> Tuple[pd.DataFrame, str, str]:
    """ほ場を登録（user_state版）"""

    user_id = get_user_id_from_state(user_state)
    if not user_id:
        return pd.DataFrame(), "エラー: ログインが必要です", "[]"

    # 入力検証
    if not field_id.strip():
        fields = get_user_fields(user_id)
        return fields_to_dataframe(fields), "エラー: ほ場IDを入力してください", get_fields_json_for_map(fields)

    if not coords_json.strip():
        fields = get_user_fields(user_id)
        return fields_to_dataframe(fields), "エラー: 地図上でポリゴンを描画してください", get_fields_json_for_map(fields)

    try:
        coordinates = json.loads(coords_json)
        if len(coordinates) < 3:
            fields = get_user_fields(user_id)
            return fields_to_dataframe(fields), "エラー: 3点以上の頂点が必要です", get_fields_json_for_map(fields)
    except json.JSONDecodeError:
        fields = get_user_fields(user_id)
        return fields_to_dataframe(fields), "エラー: 座標データが不正です", get_fields_json_for_map(fields)

    # 重複チェック
    existing = FieldRepository.get_field_by_code(user_id, field_id.strip())
    if existing:
        fields = get_user_fields(user_id)
        return fields_to_dataframe(fields), f"エラー: ほ場ID '{field_id}' は既に登録されています", get_fields_json_for_map(fields)

    # 面積計算
    area_m2 = calculate_area_from_coords(coordinates)
    area_ha = m2_to_ha(area_m2)

    # ほ場データ作成
    field_data = {
        "field_code": field_id.strip(),
        "district": district.strip(),
        "name": name.strip() or field_id.strip(),
        "area_ha": area_ha,
        "beet_forbidden": 1 if beet_forbidden else 0,
        "coordinates_json": json.dumps(coordinates)
    }

    # DB登録
    try:
        new_field_id = FieldRepository.create_field(user_id, field_data)
        message = f"ほ場 '{field_id}' を登録しました（{area_ha:.4f} ha / {area_ha * 100:.2f} a）"
    except Exception as e:
        fields = get_user_fields(user_id)
        return fields_to_dataframe(fields), f"エラー: 登録に失敗しました - {str(e)}", get_fields_json_for_map(fields)

    fields = get_user_fields(user_id)
    return fields_to_dataframe(fields), message, get_fields_json_for_map(fields)


def delete_field_with_state(field_id: str, user_state: Dict[str, Any]) -> Tuple[pd.DataFrame, str, str]:
    """選択されたほ場を削除（user_state版）"""

    user_id = get_user_id_from_state(user_state)
    if not user_id:
        return pd.DataFrame(), "エラー: ログインが必要です", "[]"

    if not field_id.strip():
        fields = get_user_fields(user_id)
        return fields_to_dataframe(fields), "エラー: 削除するほ場IDを入力してください", get_fields_json_for_map(fields)

    # ほ場コードで検索
    field = FieldRepository.get_field_by_code(user_id, field_id.strip())
    if not field:
        fields = get_user_fields(user_id)
        return fields_to_dataframe(fields), f"エラー: ほ場 '{field_id}' が見つかりません", get_fields_json_for_map(fields)

    # 削除
    try:
        if FieldRepository.delete_field(field["id"]):
            message = f"ほ場 '{field_id}' を削除しました"
        else:
            message = f"エラー: ほ場 '{field_id}' の削除に失敗しました"
    except Exception as e:
        fields = get_user_fields(user_id)
        return fields_to_dataframe(fields), f"エラー: 削除に失敗しました - {str(e)}", get_fields_json_for_map(fields)

    fields = get_user_fields(user_id)
    return fields_to_dataframe(fields), message, get_fields_json_for_map(fields)


def search_and_move_map(query: str) -> Tuple[str, str, str]:
    """住所検索して地図を移動"""
    lat, lng, message = search_address(query)

    if lat is not None and lng is not None:
        return message, str(lat), str(lng)
    else:
        return message, "", ""


def export_csv_with_state(user_state: Dict[str, Any]) -> Tuple[str, str]:
    """CSVファイルをエクスポート（user_state版）"""

    user_id = get_user_id_from_state(user_state)
    if not user_id:
        return None, "エラー: ログインが必要です"

    fields = get_user_fields(user_id)

    if not fields:
        return None, "エラー: 登録されたほ場がありません"

    # CSV形式で出力（輪作計画メーカー形式）
    lines = ["ほ場ID,地区,ほ場名,area,beet_forbidden"]
    for f in fields:
        beet = 1 if f.get("beet_forbidden") else 0
        area_a = f.get("area_a", f.get("area_ha", 0) * 100)
        lines.append(f"{f.get('field_code', '')},{f.get('district', '')},{f.get('name', '')},{area_a:.2f},{beet}")

    csv_content = "\n".join(lines)
    csv_path = "/tmp/field_register_export.csv"

    with open(csv_path, 'w', encoding='utf-8-sig') as file:
        file.write(csv_content)

    return csv_path, f"CSVファイルを出力しました（{len(fields)}件）"


def update_map_with_search_state(lat_str: str, lng_str: str, user_state: Dict[str, Any]):
    """検索結果で地図を更新（HTMLを再生成）"""
    try:
        lat = float(lat_str) if lat_str else DEFAULT_LAT
        lng = float(lng_str) if lng_str else DEFAULT_LNG
    except ValueError:
        lat = DEFAULT_LAT
        lng = DEFAULT_LNG

    # ユーザーのほ場を取得
    user_id = get_user_id_from_state(user_state)
    fields = get_user_fields(user_id) if user_id else []

    return generate_map_html(lat, lng, 16, fields)


def refresh_map_with_state(user_state: Dict[str, Any]):
    """地図を更新"""
    user_id = get_user_id_from_state(user_state)
    fields = get_user_fields(user_id) if user_id else []

    return generate_map_html(DEFAULT_LAT, DEFAULT_LNG, DEFAULT_ZOOM, fields)


def load_initial_data_with_state(user_state: Dict[str, Any]) -> Tuple[pd.DataFrame, str, str]:
    """初期データ読み込み（user_state版）"""
    user_id = get_user_id_from_state(user_state)
    if not user_id:
        return pd.DataFrame(), generate_map_html(), "ログインしてください"

    display_name = user_state.get("display_name", user_state.get("username", ""))

    fields = get_user_fields(user_id)

    return (
        fields_to_dataframe(fields),
        generate_map_html(DEFAULT_LAT, DEFAULT_LNG, DEFAULT_ZOOM, fields),
        f"ようこそ、{display_name} さん（{len(fields)}件のほ場が登録されています）"
    )


def get_field_history_with_state(field_code: str, user_state: Dict[str, Any]) -> str:
    """ほ場の作付履歴を取得"""
    user_id = get_user_id_from_state(user_state)
    if not user_id:
        return "ログインが必要です"

    # ほ場を検索
    field = FieldRepository.get_field_by_code(user_id, field_code.strip())
    if not field:
        return f"ほ場 '{field_code}' が見つかりません"

    # 作付履歴を取得
    history = CropHistoryRepository.get_history(field["id"])

    if not history:
        return f"ほ場 '{field_code}' の作付履歴はありません"

    # 履歴を表示
    lines = [f"### ほ場 '{field_code}' の作付履歴\n"]
    for h in history:
        inferred = "（推定）" if h.get("is_inferred") else ""
        lines.append(f"- {h.get('year')}: {h.get('crop')}{inferred}")

    return "\n".join(lines)


# =============================================================================
# メインUIコンポーネント
# =============================================================================

def create_field_register_ui(user_state: gr.State) -> Dict[str, Any]:
    """
    ほ場登録UIコンポーネントを作成

    Args:
        user_state: ユーザー情報を保持するgr.State
                    {'user_id': int, 'username': str, 'display_name': str, ...}

    Returns:
        components: UI操作に必要なコンポーネントの辞書
    """

    # ユーザー情報表示
    welcome_msg = gr.Markdown("")

    with gr.Row():
        with gr.Column(scale=2):
            gr.Markdown("## 🗺️ 地図")

            # 住所検索
            with gr.Row():
                search_input = gr.Textbox(
                    label="住所・地名検索",
                    placeholder="例: 札幌市, 十勝, 美瑛町",
                    scale=3
                )
                search_btn = gr.Button("🔍 検索", scale=1)

            search_result = gr.Textbox(label="検索結果", interactive=False)

            # 隠しフィールド（検索結果の座標）
            search_lat = gr.Textbox(visible=False)
            search_lng = gr.Textbox(visible=False)

            # Leaflet地図（HTML）
            map_html = gr.HTML(
                value=generate_map_html(),
                label="地図"
            )

            gr.Markdown("""
            **使い方:**
            1. 右上の多角形ツール（六角形アイコン）をクリック
            2. 地図上をクリックしてポリゴンの頂点を打つ
            3. 最後にダブルクリックまたは最初の点をクリックして完了
            4. 編集は鉛筆アイコン、削除はゴミ箱アイコン
            """)

        with gr.Column(scale=1):
            gr.Markdown("## 📝 ほ場情報")

            field_id_input = gr.Textbox(
                label="ほ場ID（必須）",
                placeholder="例: F001"
            )

            district_input = gr.Textbox(
                label="地区",
                placeholder="例: 北地区"
            )

            name_input = gr.Textbox(
                label="ほ場名",
                placeholder="例: 北1号"
            )

            beet_forbidden_input = gr.Checkbox(
                label="馬鈴薯・てんさい禁止",
                value=False
            )

            # 座標データ（地図から受け取る）
            coords_input = gr.Textbox(
                label="座標データ（地図から自動入力）",
                placeholder="地図上でポリゴンを描画してください",
                interactive=True,
                lines=3
            )

            register_btn = gr.Button("✅ 登録", variant="primary", size="lg")

            gr.Markdown("---")

            gr.Markdown("## 🗑️ 削除")
            delete_id_input = gr.Textbox(
                label="削除するほ場ID",
                placeholder="削除したいほ場IDを入力"
            )
            delete_btn = gr.Button("🗑️ 削除", variant="stop")

            gr.Markdown("---")

            gr.Markdown("## 📜 作付履歴")
            history_id_input = gr.Textbox(
                label="ほ場ID",
                placeholder="履歴を見たいほ場ID"
            )
            history_btn = gr.Button("📜 履歴表示")
            history_output = gr.Markdown("")

    gr.Markdown("---")
    gr.Markdown("## 📋 登録済みほ場一覧")

    field_table = gr.Dataframe(
        value=pd.DataFrame(columns=["ID", "ほ場ID", "地区", "ほ場名", "面積(ha)", "面積(a)", "禁止"]),
        label="ほ場一覧",
        interactive=False
    )

    # 隠しフィールド（地図更新用）
    fields_json = gr.Textbox(visible=False, value="[]")

    message_box = gr.Textbox(label="メッセージ", interactive=False)

    gr.Markdown("## 📥 CSV出力")

    with gr.Row():
        export_btn = gr.Button("📥 CSVダウンロード", variant="primary")
        csv_file = gr.File(label="ダウンロード")

    export_message = gr.Textbox(label="出力結果", interactive=False)

    # イベントハンドラ
    search_btn.click(
        fn=search_and_move_map,
        inputs=[search_input],
        outputs=[search_result, search_lat, search_lng]
    ).then(
        fn=update_map_with_search_state,
        inputs=[search_lat, search_lng, user_state],
        outputs=[map_html]
    )

    search_input.submit(
        fn=search_and_move_map,
        inputs=[search_input],
        outputs=[search_result, search_lat, search_lng]
    ).then(
        fn=update_map_with_search_state,
        inputs=[search_lat, search_lng, user_state],
        outputs=[map_html]
    )

    register_btn.click(
        fn=register_field_with_state,
        inputs=[field_id_input, district_input, name_input, beet_forbidden_input, coords_input, user_state],
        outputs=[field_table, message_box, fields_json]
    ).then(
        fn=refresh_map_with_state,
        inputs=[user_state],
        outputs=[map_html]
    )

    delete_btn.click(
        fn=delete_field_with_state,
        inputs=[delete_id_input, user_state],
        outputs=[field_table, message_box, fields_json]
    ).then(
        fn=refresh_map_with_state,
        inputs=[user_state],
        outputs=[map_html]
    )

    export_btn.click(
        fn=export_csv_with_state,
        inputs=[user_state],
        outputs=[csv_file, export_message]
    )

    history_btn.click(
        fn=get_field_history_with_state,
        inputs=[history_id_input, user_state],
        outputs=[history_output]
    )

    # コンポーネント辞書を返す（初期化用に使用）
    return {
        "welcome_msg": welcome_msg,
        "map_html": map_html,
        "field_table": field_table,
        "message_box": message_box,
        "load_fn": load_initial_data_with_state,
    }


# =============================================================================
# 単独起動用（デバッグ・テスト用）
# =============================================================================

if __name__ == "__main__":
    from auth import authenticate

    with gr.Blocks(title="ほ場登録アプリ（テスト）") as demo:
        gr.Markdown("# 🗺️ ほ場登録アプリ（UIモジュールテスト）")

        # テスト用ユーザー状態
        user_state = gr.State({"user_id": 1, "username": "test", "display_name": "テストユーザー"})

        # UIコンポーネント作成
        components = create_field_register_ui(user_state)

        # 初期データロード
        demo.load(
            fn=components["load_fn"],
            inputs=[user_state],
            outputs=[components["field_table"], components["map_html"], components["welcome_msg"]]
        )

    demo.launch(server_port=7862, auth=authenticate)
