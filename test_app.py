"""
輪作計画メーカー 動作確認テスト
"""
import asyncio
import os
from playwright.async_api import async_playwright

SCREENSHOT_DIR = "/tmp/rotation_test_screenshots"
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

async def run_tests():
    results = {
        "test1_app_launch": {"status": "NG", "note": ""},
        "test2_csv_upload": {"status": "NG", "note": ""},
        "test3_unknown_no_error": {"status": "NG", "note": ""},
        "test4_default_mode": {"status": "NG", "note": ""},
        "test5_safe_mode": {"status": "NG", "note": ""},
        "test6_unknown_display": {"status": "NG", "note": ""},
    }

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        # Test 1: アプリ起動確認
        try:
            await page.goto("http://localhost:7860", timeout=30000)
            await page.wait_for_selector("text=輪作計画メーカー", timeout=10000)
            await page.screenshot(path=f"{SCREENSHOT_DIR}/01_app_launched.png")
            results["test1_app_launch"]["status"] = "OK"
            results["test1_app_launch"]["note"] = "アプリ正常起動"
            print("✅ Test 1: アプリ起動 OK")
        except Exception as e:
            results["test1_app_launch"]["note"] = str(e)
            print(f"❌ Test 1: アプリ起動 NG - {e}")
            await browser.close()
            return results

        # Test 2: CSV読み込み
        try:
            csv_path = "/home/yasu/multi-agent-shogun/docs/rotation_planner_ui/template_example.csv"

            # ファイル入力を探す
            file_input = await page.query_selector('input[type="file"]')
            if file_input:
                await file_input.set_input_files(csv_path)
                await asyncio.sleep(2)
                await page.screenshot(path=f"{SCREENSHOT_DIR}/02_csv_uploaded.png")
                results["test2_csv_upload"]["status"] = "OK"
                results["test2_csv_upload"]["note"] = "CSV読み込み成功"
                print("✅ Test 2: CSV読み込み OK")
            else:
                results["test2_csv_upload"]["note"] = "ファイル入力が見つからない"
                print("❌ Test 2: CSV読み込み NG - ファイル入力が見つからない")
        except Exception as e:
            results["test2_csv_upload"]["note"] = str(e)
            print(f"❌ Test 2: CSV読み込み NG - {e}")

        # Test 3 & 4: デフォルトモード（制約をかけない）で計画生成
        try:
            # 「制約をかけない」がデフォルトで選択されているか確認
            default_radio = await page.query_selector('input[type="radio"][value="制約をかけない（推奨）"]:checked')
            if not default_radio:
                # ラジオボタンをクリック
                await page.click('text=制約をかけない（推奨）')

            # 計画生成ボタンをクリック
            await page.click('button:has-text("計画を生成")')

            # 結果を待つ
            await asyncio.sleep(5)
            await page.screenshot(path=f"{SCREENSHOT_DIR}/03_default_mode_result.png")

            # 結果メッセージを確認
            result_text = await page.text_content('textarea')
            if result_text and "計画生成完了" in result_text:
                results["test3_unknown_no_error"]["status"] = "OK"
                results["test3_unknown_no_error"]["note"] = "空欄でエラーなし"
                results["test4_default_mode"]["status"] = "OK"
                results["test4_default_mode"]["note"] = "デフォルトモードで生成成功"
                print("✅ Test 3: 空欄処理 OK")
                print("✅ Test 4: デフォルトモード OK")
            elif result_text and "エラー" in result_text:
                results["test3_unknown_no_error"]["note"] = f"エラー発生: {result_text[:100]}"
                results["test4_default_mode"]["note"] = f"エラー発生: {result_text[:100]}"
                print(f"❌ Test 3 & 4: エラー - {result_text[:100]}")
            else:
                results["test3_unknown_no_error"]["note"] = "結果不明"
                results["test4_default_mode"]["note"] = "結果不明"
                print("❌ Test 3 & 4: 結果不明")
        except Exception as e:
            results["test3_unknown_no_error"]["note"] = str(e)
            results["test4_default_mode"]["note"] = str(e)
            print(f"❌ Test 3 & 4: NG - {e}")

        # Test 5: 安全側モードで計画生成
        try:
            # ページリロード
            await page.goto("http://localhost:7860", timeout=30000)
            await page.wait_for_selector("text=輪作計画メーカー", timeout=10000)

            # CSV再アップロード
            file_input = await page.query_selector('input[type="file"]')
            if file_input:
                await file_input.set_input_files(csv_path)
                await asyncio.sleep(2)

            # 「安全側」を選択
            await page.click('text=安全側（不明年を考慮）')
            await asyncio.sleep(1)

            # 計画生成
            await page.click('button:has-text("計画を生成")')
            await asyncio.sleep(5)
            await page.screenshot(path=f"{SCREENSHOT_DIR}/04_safe_mode_result.png")

            # 結果確認
            result_text = await page.text_content('textarea')
            if result_text and "計画生成完了" in result_text:
                results["test5_safe_mode"]["status"] = "OK"
                results["test5_safe_mode"]["note"] = "安全側モードで生成成功"
                print("✅ Test 5: 安全側モード OK")
            else:
                results["test5_safe_mode"]["note"] = f"結果: {result_text[:100] if result_text else 'なし'}"
                print(f"❌ Test 5: 安全側モード NG")
        except Exception as e:
            results["test5_safe_mode"]["note"] = str(e)
            print(f"❌ Test 5: 安全側モード NG - {e}")

        # Test 6: 空欄が「(不明)」と表示されるか
        try:
            # 結果テーブルを探す
            await page.click('button:has-text("ほ場×年 計画表")')
            await asyncio.sleep(1)

            page_content = await page.content()
            await page.screenshot(path=f"{SCREENSHOT_DIR}/05_result_table.png", full_page=True)

            if "(不明)" in page_content:
                results["test6_unknown_display"]["status"] = "OK"
                results["test6_unknown_display"]["note"] = "空欄が(不明)と表示"
                print("✅ Test 6: (不明)表示 OK")
            else:
                results["test6_unknown_display"]["note"] = "「(不明)」が見つからない"
                print("❌ Test 6: (不明)表示 NG - 「(不明)」が見つからない")
        except Exception as e:
            results["test6_unknown_display"]["note"] = str(e)
            print(f"❌ Test 6: (不明)表示 NG - {e}")

        await browser.close()

    return results

if __name__ == "__main__":
    results = asyncio.run(run_tests())
    print("\n" + "="*50)
    print("テスト結果サマリ")
    print("="*50)
    for test_name, result in results.items():
        print(f"{test_name}: {result['status']} - {result['note']}")
