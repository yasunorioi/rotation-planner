"""
rotation_planner.field.kml_parser - KML/KMZパーサーモジュール

Google EarthのKML/KMZファイルからほ場ポリゴンを読み込む機能を提供。

Usage:
    from rotation_planner.field.kml_parser import (
        parse_kml_file,
        parse_kmz_file,
        parse_kml_or_kmz,
    )

    # ファイルから読み込み
    fields = parse_kml_or_kmz("/path/to/fields.kmz")

    # 結果
    # [
    #     {
    #         "name": "ほ場A",
    #         "coordinates": [[lat, lng], [lat, lng], ...],
    #         "area_m2": 12345.67,
    #         "area_a": 123.46,
    #         "area_ha": 1.23,
    #     },
    #     ...
    # ]
"""

import os
import zipfile
import tempfile
import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Optional, BinaryIO
from io import BytesIO

# 面積計算
from .map import calculate_area_from_coords, m2_to_a, m2_to_ha


# =============================================================================
# KML名前空間
# =============================================================================

# KMLの名前空間（Google Earthが使用）
KML_NS = {
    'kml': 'http://www.opengis.net/kml/2.2',
    'gx': 'http://www.google.com/kml/ext/2.2',
}


# =============================================================================
# 座標パース
# =============================================================================

def parse_coordinates_string(coord_string: str) -> List[List[float]]:
    """
    KMLのcoordinates文字列をパース

    KML形式: "経度,緯度,高度 経度,緯度,高度 ..."
    出力形式: [[緯度, 経度], [緯度, 経度], ...]

    Args:
        coord_string: KMLのcoordinates要素のテキスト

    Returns:
        [[lat, lng], ...] 形式の座標リスト
    """
    coordinates = []

    # 改行・スペースで分割
    parts = coord_string.strip().split()

    for part in parts:
        if not part.strip():
            continue

        # "経度,緯度,高度" または "経度,緯度" 形式
        values = part.strip().split(',')
        if len(values) >= 2:
            try:
                lng = float(values[0])
                lat = float(values[1])
                # KMLは経度,緯度の順なので、[緯度, 経度]に変換
                coordinates.append([lat, lng])
            except ValueError:
                continue

    return coordinates


# =============================================================================
# KMLパース
# =============================================================================

def parse_kml_content(kml_content: str) -> List[Dict[str, Any]]:
    """
    KML文字列をパースしてほ場リストを返す

    Args:
        kml_content: KMLファイルの内容（文字列）

    Returns:
        ほ場情報のリスト
    """
    fields = []

    try:
        root = ET.fromstring(kml_content)
    except ET.ParseError as e:
        print(f"KML parse error: {e}")
        return []

    # 名前空間を考慮してPlacemarkを検索
    # まず名前空間付きで検索
    placemarks = root.findall('.//kml:Placemark', KML_NS)

    # 見つからなければ名前空間なしで検索
    if not placemarks:
        placemarks = root.findall('.//{http://www.opengis.net/kml/2.2}Placemark')

    # それでも見つからなければ単純検索
    if not placemarks:
        placemarks = root.findall('.//Placemark')

    for placemark in placemarks:
        field = parse_placemark(placemark)
        if field:
            fields.append(field)

    return fields


def parse_placemark(placemark: ET.Element) -> Optional[Dict[str, Any]]:
    """
    Placemark要素をパースしてほ場情報を返す

    Args:
        placemark: Placemark XML要素

    Returns:
        ほ場情報の辞書、またはポリゴンがなければNone
    """
    # 名前を取得
    name = None
    for ns_prefix in ['kml:', '{http://www.opengis.net/kml/2.2}', '']:
        name_elem = placemark.find(f'{ns_prefix}name', KML_NS) if ns_prefix == 'kml:' else placemark.find(f'{ns_prefix}name')
        if name_elem is not None and name_elem.text:
            name = name_elem.text.strip()
            break

    if not name:
        name = "名称未設定"

    # 説明を取得（あれば）
    description = None
    for ns_prefix in ['kml:', '{http://www.opengis.net/kml/2.2}', '']:
        desc_elem = placemark.find(f'{ns_prefix}description', KML_NS) if ns_prefix == 'kml:' else placemark.find(f'{ns_prefix}description')
        if desc_elem is not None and desc_elem.text:
            description = desc_elem.text.strip()
            break

    # Polygonの座標を取得
    coordinates = None

    # Polygon/outerBoundaryIs/LinearRing/coordinates のパターン
    for ns_prefix in ['{http://www.opengis.net/kml/2.2}', '']:
        polygon = placemark.find(f'.//{ns_prefix}Polygon')
        if polygon is not None:
            coords_elem = polygon.find(f'.//{ns_prefix}coordinates')
            if coords_elem is not None and coords_elem.text:
                coordinates = parse_coordinates_string(coords_elem.text)
                break

    # LineStringも試す（ポリゴンとして扱う）
    if not coordinates:
        for ns_prefix in ['{http://www.opengis.net/kml/2.2}', '']:
            linestring = placemark.find(f'.//{ns_prefix}LineString')
            if linestring is not None:
                coords_elem = linestring.find(f'.//{ns_prefix}coordinates')
                if coords_elem is not None and coords_elem.text:
                    coordinates = parse_coordinates_string(coords_elem.text)
                    break

    # 座標がなければスキップ（ポイントマーカーなど）
    if not coordinates or len(coordinates) < 3:
        return None

    # 面積計算
    area_m2 = calculate_area_from_coords(coordinates)
    area_a = m2_to_a(area_m2)
    area_ha = m2_to_ha(area_m2)

    return {
        "name": name,
        "description": description,
        "coordinates": coordinates,
        "area_m2": area_m2,
        "area_a": round(area_a, 2),
        "area_ha": round(area_ha, 4),
    }


# =============================================================================
# ファイル読み込み
# =============================================================================

def parse_kml_file(file_path: str) -> List[Dict[str, Any]]:
    """
    KMLファイルを読み込んでパース

    Args:
        file_path: KMLファイルのパス

    Returns:
        ほ場情報のリスト
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    return parse_kml_content(content)


def parse_kmz_file(file_path: str) -> List[Dict[str, Any]]:
    """
    KMZファイルを読み込んでパース
    KMZはZIPアーカイブで、中にdoc.kmlまたは*.kmlが含まれる

    Args:
        file_path: KMZファイルのパス

    Returns:
        ほ場情報のリスト
    """
    fields = []

    try:
        with zipfile.ZipFile(file_path, 'r') as zf:
            # KMLファイルを探す
            kml_files = [name for name in zf.namelist() if name.lower().endswith('.kml')]

            for kml_name in kml_files:
                with zf.open(kml_name) as kml_file:
                    content = kml_file.read().decode('utf-8')
                    fields.extend(parse_kml_content(content))

    except zipfile.BadZipFile as e:
        print(f"Invalid KMZ file: {e}")
        return []

    return fields


def parse_kml_or_kmz(file_path: str) -> List[Dict[str, Any]]:
    """
    KMLまたはKMZファイルを自動判別してパース

    Args:
        file_path: ファイルパス

    Returns:
        ほ場情報のリスト
    """
    ext = os.path.splitext(file_path)[1].lower()

    if ext == '.kmz':
        return parse_kmz_file(file_path)
    elif ext == '.kml':
        return parse_kml_file(file_path)
    else:
        # 拡張子不明の場合、まずKMZ（ZIP）として試す
        try:
            return parse_kmz_file(file_path)
        except:
            return parse_kml_file(file_path)


def parse_kml_or_kmz_bytes(file_bytes: bytes, filename: str) -> List[Dict[str, Any]]:
    """
    バイトデータからKML/KMZをパース（Gradioアップロード用）

    Args:
        file_bytes: ファイルのバイトデータ
        filename: ファイル名（拡張子判定用）

    Returns:
        ほ場情報のリスト
    """
    ext = os.path.splitext(filename)[1].lower()

    if ext == '.kmz':
        # KMZ（ZIP）として処理
        try:
            with zipfile.ZipFile(BytesIO(file_bytes), 'r') as zf:
                fields = []
                kml_files = [name for name in zf.namelist() if name.lower().endswith('.kml')]

                for kml_name in kml_files:
                    with zf.open(kml_name) as kml_file:
                        content = kml_file.read().decode('utf-8')
                        fields.extend(parse_kml_content(content))

                return fields
        except zipfile.BadZipFile:
            # ZIPじゃなければKMLとして試す
            pass

    # KMLとして処理
    try:
        content = file_bytes.decode('utf-8')
        return parse_kml_content(content)
    except UnicodeDecodeError:
        # UTF-8以外のエンコーディングを試す
        for encoding in ['shift_jis', 'euc-jp', 'iso-8859-1']:
            try:
                content = file_bytes.decode(encoding)
                return parse_kml_content(content)
            except:
                continue

    return []


# =============================================================================
# ユーティリティ
# =============================================================================

def fields_to_dataframe_format(fields: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    パース結果をDataFrame用の形式に変換

    Args:
        fields: parse_kml_or_kmz の結果

    Returns:
        DataFrameに変換可能な辞書のリスト
    """
    result = []

    for i, field in enumerate(fields, 1):
        result.append({
            "ほ場ID": f"F{i:03d}",
            "ほ場名": field["name"],
            "面積(a)": field["area_a"],
            "面積(ha)": field["area_ha"],
            "座標数": len(field["coordinates"]),
            "_coordinates": field["coordinates"],  # 内部用
        })

    return result
