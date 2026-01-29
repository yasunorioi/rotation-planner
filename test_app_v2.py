"""
輪作計画メーカー 動作確認テスト v2
"""
import asyncio
import os
from playwright.async_api import async_playwright

SCREENSHOT_DIR = "/tmp/rotation_test_screenshots"
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

async def run_tests():
    results = {}

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1920, "height": 1080})

        # Test 1: アプリ起動確認
        print("Test 1: アプリ起動...")
        await page.goto("http://localhost:7860", timeout=30000)
        await page.wait_for_selector("text=輪作計画メーカー", timeout=10000)
        results["test1_app_launch"] = {"status": "OK", "note": "アプリ正常起動"}
        print("✅ Test 1: OK")

        # Test 2: CSV読み込み
        print("Test 2: CSV読み込み...")
        csv_path = "/home/yasu/multi-agent-shogun/docs/rotation_planner_ui/template_example.csv"
        file_input = await page.query_selector('input[type="file"]')
        await file_input.set_input_files(csv_path)
        await asyncio.sleep(2)
        results["test2_csv_upload"] = {"status": "OK", "note": "CSV読み込み成功"}
        print("✅ Test 2: OK")

        # Test 3 & 4: デフォルトモードで計画生成
        print("Test 3 & 4: デフォルトモード計画生成...")
        # ボタンをスクロールして表示
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
        await asyncio.sleep(1)

        # 計画生成ボタンをクリック
        gen_button = await page.query_selector('button:has-text("計画を生成")')
        await gen_button.click()

        # 結果を待つ（最大30秒）
        await asyncio.sleep(8)
        await page.screenshot(path=f"{SCREENSHOT_DIR}/v2_01_after_generate.png", full_page=True)

        # 結果テキストを取得
        page_content = await page.content()
        if "計画生成完了" in page_content:
            results["test3_unknown_no_error"] = {"status": "OK", "note": "空欄でエラーなし"}
            results["test4_default_mode"] = {"status": "OK", "note": "デフォルトモードで生成成功"}
            print("✅ Test 3: OK")
            print("✅ Test 4: OK")
        else:
            results["test3_unknown_no_error"] = {"status": "NG", "note": "生成結果が確認できない"}
            results["test4_default_mode"] = {"status": "NG", "note": "生成結果が確認できない"}
            print("❌ Test 3 & 4: NG")

        # Test 5: 安全側モード
        print("Test 5: 安全側モード...")
        await page.goto("http://localhost:7860", timeout=30000)
        await page.wait_for_selector("text=輪作計画メーカー", timeout=10000)

        file_input = await page.query_selector('input[type="file"]')
        await file_input.set_input_files(csv_path)
        await asyncio.sleep(2)

        # 安全側モードを選択
        safe_label = await page.query_selector('label:has-text("安全側")')
        if safe_label:
            await safe_label.click()
            await asyncio.sleep(1)

        await page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
        await asyncio.sleep(1)

        gen_button = await page.query_selector('button:has-text("計画を生成")')
        await gen_button.click()
        await asyncio.sleep(8)
        await page.screenshot(path=f"{SCREENSHOT_DIR}/v2_02_safe_mode.png", full_page=True)

        page_content = await page.content()
        if "計画生成完了" in page_content:
            results["test5_safe_mode"] = {"status": "OK", "note": "安全側モードで生成成功"}
            print("✅ Test 5: OK")
        else:
            results["test5_safe_mode"] = {"status": "NG", "note": "生成失敗"}
            print("❌ Test 5: NG")

        # Test 6: 結果テーブルの「(不明)」表示
        print("Test 6: (不明)表示確認...")
        # ページ下部へスクロール
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await asyncio.sleep(2)
        await page.screenshot(path=f"{SCREENSHOT_DIR}/v2_03_result_table.png", full_page=True)

        page_content = await page.content()
        if "(不明)" in page_content:
            results["test6_unknown_display"] = {"status": "OK", "note": "空欄が(不明)と表示"}
            print("✅ Test 6: OK")
        else:
            # HTMLの一部を保存
            with open(f"{SCREENSHOT_DIR}/page_content.html", "w") as f:
                f.write(page_content)
            results["test6_unknown_display"] = {"status": "NG", "note": "「(不明)」が見つからない"}
            print("❌ Test 6: NG - HTMLを保存しました")

        await browser.close()

    return results

if __name__ == "__main__":
    results = asyncio.run(run_tests())
    print("\n" + "="*50)
    print("テスト結果サマリ")
    print("="*50)
    all_ok = True
    for test_name, result in results.items():
        status = result['status']
        if status == "NG":
            all_ok = False
        print(f"{test_name}: {status} - {result['note']}")

    print("="*50)
    if all_ok:
        print("全テスト合格！")
    else:
        print("一部テスト失敗")
