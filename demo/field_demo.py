"""
ほ場登録デモアプリ - 認証なし・DB保存なしのデモ版

地図上でポリゴンを描画し、面積を計算するデモ。
北海道十勝地方を初期表示。

起動方法:
    python demo/field_demo.py
    # http://localhost:7880 でアクセス
"""

import gradio as gr
import json
import requests
from typing import List, Dict, Optional, Tuple, Any
from pyproj import Geod

# =============================================================================
# 定数
# =============================================================================

# 北海道十勝地方（帯広付近）
DEFAULT_LAT = 43.0
DEFAULT_LNG = 143.2
DEFAULT_ZOOM = 11

# Nominatim API エンドポイント
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"

# サンプルほ場データ（十勝地方）
SAMPLE_FIELDS = [
    {
        "field_id": "DEMO-001",
        "name": "サンプル1号（てんさい）",
        "coordinates": [
            [42.98, 143.15],
            [42.98, 143.17],
            [42.97, 143.17],
            [42.97, 143.15],
        ],
        "area_a": 215.5,
        "coordinates_json": json.dumps([
            [42.98, 143.15],
            [42.98, 143.17],
            [42.97, 143.17],
            [42.97, 143.15],
        ])
    },
    {
        "field_id": "DEMO-002",
        "name": "サンプル2号（大豆）",
        "coordinates": [
            [43.01, 143.20],
            [43.01, 143.22],
            [43.00, 143.22],
            [43.00, 143.20],
        ],
        "area_a": 198.3,
        "coordinates_json": json.dumps([
            [43.01, 143.20],
            [43.01, 143.22],
            [43.00, 143.22],
            [43.00, 143.20],
        ])
    },
    {
        "field_id": "DEMO-003",
        "name": "サンプル3号（小麦）",
        "coordinates": [
            [43.03, 143.18],
            [43.03, 143.21],
            [43.02, 143.21],
            [43.02, 143.18],
        ],
        "area_a": 320.8,
        "coordinates_json": json.dumps([
            [43.03, 143.18],
            [43.03, 143.21],
            [43.02, 143.21],
            [43.02, 143.18],
        ])
    },
]


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

    # 座標を (lng, lat) 形式に変換
    coords_lnglat = [(coord[1], coord[0]) for coord in coordinates]

    # ポリゴンを閉じる
    if coords_lnglat[0] != coords_lnglat[-1]:
        coords_lnglat.append(coords_lnglat[0])

    # Geod（測地線計算）を使用して面積を計算
    geod = Geod(ellps="WGS84")

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
    """住所・地名からNominatim APIで座標を検索"""
    if not query.strip():
        return None, None, "検索語を入力してください"

    try:
        params = {
            "q": query,
            "format": "json",
            "limit": 1,
            "countrycodes": "jp",
        }
        headers = {
            "User-Agent": "FieldDemoApp/1.0"
        }

        response = requests.get(NOMINATIM_URL, params=params, headers=headers, timeout=10)
        response.raise_for_status()

        results = response.json()

        if results:
            lat = float(results[0]["lat"])
            lng = float(results[0]["lon"])
            display_name = results[0].get("display_name", query)
            return lat, lng, f"✅ {display_name}"
        else:
            return None, None, f"❌ 「{query}」の検索結果が見つかりません"

    except requests.exceptions.Timeout:
        return None, None, "⏱️ 検索がタイムアウトしました"
    except requests.exceptions.RequestException as e:
        return None, None, f"❌ 検索エラー: {str(e)}"
    except Exception as e:
        return None, None, f"❌ 予期しないエラー: {str(e)}"


# =============================================================================
# Leaflet HTML生成
# =============================================================================

def generate_demo_map_html(
    center_lat: float = DEFAULT_LAT,
    center_lng: float = DEFAULT_LNG,
    zoom: int = DEFAULT_ZOOM,
    sample_fields: List[Dict[str, Any]] = None
) -> str:
    """デモ用Leaflet地図のHTMLを生成"""

    sample_fields = sample_fields or SAMPLE_FIELDS

    # サンプルほ場のJSONデータ
    fields_json = json.dumps([
        {
            "field_id": f.get("field_id", ""),
            "name": f.get("name", ""),
            "coordinates": f.get("coordinates", []),
            "area_a": f.get("area_a", 0)
        }
        for f in sample_fields
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
                height: 550px;
                border: 2px solid #28a745;
                border-radius: 12px;
            }}
            .area-display {{
                background: white;
                padding: 12px 16px;
                border-radius: 8px;
                box-shadow: 0 2px 8px rgba(0,0,0,0.2);
                font-size: 14px;
            }}
            .area-display b {{
                color: #28a745;
            }}
            .field-popup {{
                min-width: 180px;
            }}
            .field-popup b {{
                color: #007bff;
            }}
            .leaflet-draw-toolbar a {{
                background-color: #28a745 !important;
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
                attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors | デモ用',
                maxZoom: 19
            }}).addTo(map);

            // 描画レイヤー
            var drawnItems = new L.FeatureGroup();
            map.addLayer(drawnItems);

            // サンプルほ場レイヤー
            var sampleFields = new L.FeatureGroup();
            map.addLayer(sampleFields);

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
                            fillOpacity: 0.3,
                            weight: 3
                        }}
                    }},
                    polyline: false,
                    circle: false,
                    rectangle: true,
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
                    this._div.innerHTML = '<b>📐 描画中の面積</b><br><br>' +
                        '🔹 ' + area_a + ' アール (a)<br>' +
                        '🔹 ' + area_ha + ' ヘクタール (ha)<br>' +
                        '🔹 ' + Math.round(area_m2).toLocaleString() + ' m²';
                }} else {{
                    this._div.innerHTML = '<b>📐 面積</b><br><br>' +
                        '右上の📐ツールで<br>ポリゴンを描画してください';
                }}
            }};
            areaInfo.addTo(map);

            // 現在の座標
            var currentPolygonCoords = null;

            // ポリゴン作成完了イベント
            map.on(L.Draw.Event.CREATED, function(event) {{
                var layer = event.layer;
                drawnItems.clearLayers();
                drawnItems.addLayer(layer);

                var latlngs = layer.getLatLngs()[0];
                currentPolygonCoords = latlngs.map(function(ll) {{
                    return [ll.lat, ll.lng];
                }});

                var area_m2 = L.GeometryUtil.geodesicArea(latlngs);
                areaInfo.update(area_m2);

                sendCoordinatesToGradio(currentPolygonCoords, area_m2);
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

                    sendCoordinatesToGradio(currentPolygonCoords, area_m2);
                }});
            }});

            // ポリゴン削除イベント
            map.on(L.Draw.Event.DELETED, function(event) {{
                currentPolygonCoords = null;
                areaInfo.update(null);
                sendCoordinatesToGradio(null, 0);
            }});

            // Gradioへ座標送信
            function sendCoordinatesToGradio(coords, area_m2) {{
                var coordsJson = coords ? JSON.stringify(coords) : '';

                if (window.parent) {{
                    window.parent.postMessage({{
                        type: 'polygon_coordinates',
                        coordinates: coordsJson,
                        area_m2: area_m2 || 0
                    }}, '*');
                }}
            }}

            // サンプルほ場を表示
            var sampleData = {fields_json};
            sampleData.forEach(function(field) {{
                if (field.coordinates && field.coordinates.length > 0) {{
                    var polygon = L.polygon(field.coordinates, {{
                        color: '#28a745',
                        fillColor: '#28a745',
                        fillOpacity: 0.25,
                        weight: 2
                    }}).addTo(sampleFields);

                    polygon.bindPopup(
                        '<div class="field-popup">' +
                        '<b>🌾 ' + field.field_id + '</b><br>' +
                        field.name + '<br><br>' +
                        '📐 ' + field.area_a.toFixed(2) + ' a' +
                        '</div>'
                    );
                }}
            }});

            // 地図の中心移動関数
            window.moveMapTo = function(lat, lng, zoom) {{
                map.setView([lat, lng], zoom || 14);
            }};

            // ポリゴンクリア関数
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
# Gradio UI
# =============================================================================

def search_and_move(query: str) -> Tuple[str, str, str]:
    """住所検索して地図移動用の情報を返す"""
    lat, lng, message = search_address(query)
    if lat is not None and lng is not None:
        return message, str(lat), str(lng)
    else:
        return message, "", ""


def update_map(lat_str: str, lng_str: str) -> str:
    """検索結果で地図を更新"""
    try:
        lat = float(lat_str) if lat_str else DEFAULT_LAT
        lng = float(lng_str) if lng_str else DEFAULT_LNG
    except ValueError:
        lat = DEFAULT_LAT
        lng = DEFAULT_LNG

    return generate_demo_map_html(lat, lng, 14, SAMPLE_FIELDS)


def calculate_area_display(coords_json: str) -> str:
    """座標JSONから面積を計算して表示"""
    if not coords_json.strip():
        return "地図上でポリゴンを描画してください"

    try:
        coordinates = json.loads(coords_json)
        if len(coordinates) < 3:
            return "3点以上の頂点が必要です"

        area_m2 = calculate_area_from_coords(coordinates)
        area_a = m2_to_a(area_m2)
        area_ha = m2_to_ha(area_m2)

        return f"""
## 📐 面積計算結果

| 単位 | 値 |
|------|-----|
| 平方メートル | {area_m2:,.0f} m² |
| アール | {area_a:.2f} a |
| ヘクタール | {area_ha:.4f} ha |

### 座標データ
頂点数: {len(coordinates)} 点
"""
    except json.JSONDecodeError:
        return "座標データの形式が不正です"
    except Exception as e:
        return f"計算エラー: {str(e)}"


def create_field_demo_ui() -> gr.Blocks:
    """
    ほ場登録デモUIを作成

    Returns:
        gr.Blocks: Gradioアプリケーション
    """

    with gr.Blocks(
        title="ほ場登録デモ - 十勝地方",
        theme=gr.themes.Soft()
    ) as demo:

        gr.Markdown("""
        # 🗺️ ほ場登録デモ

        **北海道十勝地方** の地図上でポリゴンを描画し、面積を計算するデモです。

        ## 使い方
        1. 🔍 住所・地名を検索して地図を移動
        2. 📐 右上のツール（六角形）でポリゴンを描画
        3. 面積が自動計算されます（WGS84楕円体）

        ---
        """)

        with gr.Row():
            with gr.Column(scale=2):
                # 住所検索
                with gr.Row():
                    search_input = gr.Textbox(
                        label="🔍 住所・地名検索",
                        placeholder="例: 帯広市, 十勝, 音更町",
                        scale=3
                    )
                    search_btn = gr.Button("検索", scale=1, variant="primary")

                search_result = gr.Textbox(label="検索結果", interactive=False)

                # 隠しフィールド
                search_lat = gr.Textbox(visible=False)
                search_lng = gr.Textbox(visible=False)

                # Leaflet地図
                map_html = gr.HTML(
                    value=generate_demo_map_html(),
                    label="地図"
                )

            with gr.Column(scale=1):
                gr.Markdown("## 📐 面積計算")

                coords_input = gr.Textbox(
                    label="座標データ（地図から自動入力）",
                    placeholder="地図上でポリゴンを描画してください",
                    lines=4
                )

                calc_btn = gr.Button("面積を計算", variant="secondary")

                area_result = gr.Markdown("地図上でポリゴンを描画してください")

                gr.Markdown("""
                ---
                ### 📝 補足

                - **緑のポリゴン**: サンプルほ場（クリックで詳細）
                - **青のポリゴン**: 描画中のほ場
                - 面積はWGS84楕円体で計算

                ### 🌾 サンプルほ場
                - DEMO-001: てんさい（215.5 a）
                - DEMO-002: 大豆（198.3 a）
                - DEMO-003: 小麦（320.8 a）
                """)

        gr.Markdown("""
        ---
        **注意**: これはデモ版です。データは保存されません。
        """)

        # イベント
        search_btn.click(
            fn=search_and_move,
            inputs=[search_input],
            outputs=[search_result, search_lat, search_lng]
        ).then(
            fn=update_map,
            inputs=[search_lat, search_lng],
            outputs=[map_html]
        )

        search_input.submit(
            fn=search_and_move,
            inputs=[search_input],
            outputs=[search_result, search_lat, search_lng]
        ).then(
            fn=update_map,
            inputs=[search_lat, search_lng],
            outputs=[map_html]
        )

        calc_btn.click(
            fn=calculate_area_display,
            inputs=[coords_input],
            outputs=[area_result]
        )

    return demo


# =============================================================================
# メイン
# =============================================================================

if __name__ == "__main__":
    demo = create_field_demo_ui()
    demo.launch(
        server_name="0.0.0.0",
        server_port=7880,
        share=False
        # 認証なし
    )
