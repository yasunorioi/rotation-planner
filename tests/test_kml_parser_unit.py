"""
KML/KMZパーサー（kml_parser.py）の単体テスト

テスト設計書: docs/TEST_UNIT.md セクション3.6
テストケース: KM-01 ～ KM-13
"""
import os
import zipfile

import pytest

from rotation_planner.field.kml_parser import (
    parse_coordinates_string,
    parse_kml_content,
    parse_kml_file,
    parse_kmz_file,
    parse_kml_or_kmz,
    generate_kml_content,
    export_fields_to_kml,
    fields_to_dataframe_format,
)


# ============================================================
# テスト用KMLデータ
# ============================================================

VALID_KML = """\
<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <Placemark>
      <name>テスト圃場</name>
      <Polygon>
        <outerBoundaryIs>
          <LinearRing>
            <coordinates>
              141.0,43.0,0 141.1,43.0,0 141.1,43.1,0 141.0,43.1,0 141.0,43.0,0
            </coordinates>
          </LinearRing>
        </outerBoundaryIs>
      </Polygon>
    </Placemark>
  </Document>
</kml>"""

MULTI_PLACEMARK_KML = """\
<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <Placemark>
      <name>圃場A</name>
      <Polygon>
        <outerBoundaryIs>
          <LinearRing>
            <coordinates>141.0,43.0,0 141.1,43.0,0 141.1,43.1,0 141.0,43.1,0 141.0,43.0,0</coordinates>
          </LinearRing>
        </outerBoundaryIs>
      </Polygon>
    </Placemark>
    <Placemark>
      <name>圃場B</name>
      <Polygon>
        <outerBoundaryIs>
          <LinearRing>
            <coordinates>142.0,44.0,0 142.1,44.0,0 142.1,44.1,0 142.0,44.1,0 142.0,44.0,0</coordinates>
          </LinearRing>
        </outerBoundaryIs>
      </Polygon>
    </Placemark>
  </Document>
</kml>"""

EMPTY_KML = """\
<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
  </Document>
</kml>"""

INVALID_XML = "<invalid>xml</broken>"


# ============================================================
# KM-01～KM-03: parse_coordinates_string テスト
# ============================================================

class TestParseCoordinatesString:
    """parse_coordinates_string のテスト"""

    def test_km01_single_coordinate(self):
        """KM-01: 正常座標 '141.0,43.0,0' → [[43.0, 141.0]]"""
        result = parse_coordinates_string("141.0,43.0,0")
        assert len(result) == 1
        assert result[0] == [43.0, 141.0]

    def test_km02_multiple_coordinates(self):
        """KM-02: 複数座標（3点ポリゴン）→ 3要素リスト"""
        coords = "141.0,43.0,0 141.1,43.0,0 141.1,43.1,0"
        result = parse_coordinates_string(coords)
        assert len(result) == 3
        assert result[0] == [43.0, 141.0]
        assert result[1] == [43.0, 141.1]
        assert result[2] == [43.1, 141.1]

    def test_km03_empty_string(self):
        """KM-03: 空文字 → 空リスト"""
        result = parse_coordinates_string("")
        assert result == []

    def test_coordinates_without_altitude(self):
        """補足: 高度なし（経度,緯度のみ）"""
        result = parse_coordinates_string("141.0,43.0")
        assert len(result) == 1
        assert result[0] == [43.0, 141.0]

    def test_coordinates_with_newlines(self):
        """補足: 改行区切りの座標"""
        coords = "141.0,43.0,0\n141.1,43.0,0\n141.1,43.1,0"
        result = parse_coordinates_string(coords)
        assert len(result) == 3

    def test_whitespace_only(self):
        """補足: 空白のみ"""
        result = parse_coordinates_string("   ")
        assert result == []


# ============================================================
# KM-04～KM-06: parse_kml_content テスト
# ============================================================

class TestParseKmlContent:
    """parse_kml_content のテスト"""

    def test_km04_valid_kml(self):
        """KM-04: 有効KML → List[Dict]"""
        result = parse_kml_content(VALID_KML)
        assert isinstance(result, list)
        assert len(result) == 1
        field = result[0]
        assert field["name"] == "テスト圃場"
        assert "coordinates" in field
        assert isinstance(field["coordinates"], list)
        assert len(field["coordinates"]) >= 3
        assert "area_m2" in field
        assert "area_a" in field
        assert "area_ha" in field

    def test_km04_multiple_placemarks(self):
        """KM-04補足: 複数Placemarkの有効KML"""
        result = parse_kml_content(MULTI_PLACEMARK_KML)
        assert len(result) == 2
        assert result[0]["name"] == "圃場A"
        assert result[1]["name"] == "圃場B"

    def test_km05_no_placemark(self):
        """KM-05: Placemark無しKML → 空リスト"""
        result = parse_kml_content(EMPTY_KML)
        assert result == []

    def test_km06_invalid_xml(self):
        """KM-06: 不正XML → 空リスト（ParseErrorをcatchして返す）"""
        result = parse_kml_content(INVALID_XML)
        assert result == []


# ============================================================
# KM-07: parse_kml_file テスト
# ============================================================

class TestParseKmlFile:
    """parse_kml_file のテスト"""

    def test_km07_file_not_found(self):
        """KM-07: 存在しないファイル → FileNotFoundError"""
        with pytest.raises(FileNotFoundError):
            parse_kml_file("/nonexistent/path/to/test.kml")

    def test_valid_kml_file(self, temp_dir):
        """補足: 有効なKMLファイルの読み込み"""
        kml_path = os.path.join(temp_dir, "test.kml")
        with open(kml_path, "w", encoding="utf-8") as f:
            f.write(VALID_KML)

        result = parse_kml_file(kml_path)
        assert len(result) == 1
        assert result[0]["name"] == "テスト圃場"


# ============================================================
# KM-08～KM-09: parse_kmz_file テスト
# ============================================================

class TestParseKmzFile:
    """parse_kmz_file のテスト"""

    def test_km08_valid_kmz(self, temp_dir):
        """KM-08: 有効KMZ（ZIPファイル）→ List[Dict]"""
        kmz_path = os.path.join(temp_dir, "test.kmz")
        with zipfile.ZipFile(kmz_path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("doc.kml", VALID_KML)

        result = parse_kmz_file(kmz_path)
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["name"] == "テスト圃場"

    def test_km09_invalid_zip(self, temp_dir):
        """KM-09: 不正ZIP → 空リスト（BadZipFileをcatchして返す）"""
        bad_path = os.path.join(temp_dir, "bad.kmz")
        with open(bad_path, "w") as f:
            f.write("This is not a ZIP file")

        result = parse_kmz_file(bad_path)
        assert result == []

    def test_kmz_multiple_kml_files(self, temp_dir):
        """補足: KMZ内に複数KMLファイル"""
        kmz_path = os.path.join(temp_dir, "multi.kmz")
        with zipfile.ZipFile(kmz_path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("doc.kml", VALID_KML)
            zf.writestr("extra.kml", VALID_KML)

        result = parse_kmz_file(kmz_path)
        assert len(result) == 2


# ============================================================
# KM-10: parse_kml_or_kmz テスト
# ============================================================

class TestParseKmlOrKmz:
    """parse_kml_or_kmz のテスト"""

    def test_km10_kml_extension(self, temp_dir):
        """KM-10: .kml拡張子 → KMLとして処理"""
        kml_path = os.path.join(temp_dir, "test.kml")
        with open(kml_path, "w", encoding="utf-8") as f:
            f.write(VALID_KML)

        result = parse_kml_or_kmz(kml_path)
        assert len(result) == 1
        assert result[0]["name"] == "テスト圃場"

    def test_kmz_extension(self, temp_dir):
        """補足: .kmz拡張子 → KMZとして処理"""
        kmz_path = os.path.join(temp_dir, "test.kmz")
        with zipfile.ZipFile(kmz_path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("doc.kml", VALID_KML)

        result = parse_kml_or_kmz(kmz_path)
        assert len(result) == 1
        assert result[0]["name"] == "テスト圃場"


# ============================================================
# KM-11: generate_kml_content テスト
# ============================================================

class TestGenerateKmlContent:
    """generate_kml_content のテスト"""

    def test_km11_normal_generation(self):
        """KM-11: 正常生成 → Valid KML string"""
        fields = [
            {
                "name": "テスト圃場",
                "coordinates": [
                    [43.0, 141.0],
                    [43.0, 141.1],
                    [43.1, 141.1],
                    [43.1, 141.0],
                ],
                "area_ha": 1.23,
            }
        ]
        result = generate_kml_content(fields, "テスト出力")
        assert isinstance(result, str)
        assert '<?xml version="1.0"' in result
        assert "http://www.opengis.net/kml/2.2" in result
        assert "テスト圃場" in result
        assert "Placemark" in result
        assert "Polygon" in result

    def test_empty_fields(self):
        """補足: 空リスト → Placemarkなしの有効KML"""
        result = generate_kml_content([], "空テスト")
        assert '<?xml version="1.0"' in result
        assert "Placemark" not in result

    def test_xml_escape_in_name(self):
        """補足: 特殊文字のエスケープ"""
        fields = [
            {
                "name": "圃場<A>&B",
                "coordinates": [
                    [43.0, 141.0],
                    [43.0, 141.1],
                    [43.1, 141.1],
                    [43.1, 141.0],
                ],
            }
        ]
        result = generate_kml_content(fields)
        assert "&lt;" in result
        assert "&amp;" in result

    def test_json_string_coordinates(self):
        """補足: coordinates が JSON文字列の場合"""
        import json
        coords = [[43.0, 141.0], [43.0, 141.1], [43.1, 141.1], [43.1, 141.0]]
        fields = [
            {
                "name": "JSON座標テスト",
                "coordinates": json.dumps(coords),
            }
        ]
        result = generate_kml_content(fields)
        assert "JSON座標テスト" in result
        assert "Polygon" in result


# ============================================================
# KM-12: export_fields_to_kml テスト
# ============================================================

class TestExportFieldsToKml:
    """export_fields_to_kml のテスト"""

    def test_km12_file_output(self, temp_dir):
        """KM-12: ファイル出力 → ファイルが作成される"""
        fields = [
            {
                "name": "出力テスト圃場",
                "coordinates": [
                    [43.0, 141.0],
                    [43.0, 141.1],
                    [43.1, 141.1],
                    [43.1, 141.0],
                ],
            }
        ]
        output_path = os.path.join(temp_dir, "output.kml")

        result_path = export_fields_to_kml(fields, output_path, "エクスポートテスト")

        assert result_path == output_path
        assert os.path.exists(output_path)

        with open(output_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert '<?xml version="1.0"' in content
        assert "出力テスト圃場" in content


# ============================================================
# KM-13: fields_to_dataframe_format テスト
# ============================================================

class TestFieldsToDataframeFormat:
    """fields_to_dataframe_format のテスト"""

    def test_km13_conversion(self):
        """KM-13: パース結果 → DataFrame形式Dict"""
        fields = [
            {
                "name": "圃場A",
                "coordinates": [[43.0, 141.0], [43.0, 141.1], [43.1, 141.1]],
                "area_m2": 10000.0,
                "area_a": 100.0,
                "area_ha": 1.0,
            },
            {
                "name": "圃場B",
                "coordinates": [[44.0, 142.0], [44.0, 142.1], [44.1, 142.1]],
                "area_m2": 20000.0,
                "area_a": 200.0,
                "area_ha": 2.0,
            },
        ]

        result = fields_to_dataframe_format(fields)

        assert isinstance(result, list)
        assert len(result) == 2

        first = result[0]
        assert first["ほ場ID"] == "F001"
        assert first["ほ場名"] == "圃場A"
        assert first["面積(a)"] == 100.0
        assert first["面積(ha)"] == 1.0
        assert first["座標数"] == 3
        assert "_coordinates" in first

        second = result[1]
        assert second["ほ場ID"] == "F002"
        assert second["ほ場名"] == "圃場B"

    def test_empty_fields(self):
        """補足: 空リスト → 空リスト"""
        result = fields_to_dataframe_format([])
        assert result == []
