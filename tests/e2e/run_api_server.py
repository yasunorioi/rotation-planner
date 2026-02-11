"""
E2Eテスト用 FastAPI サーバーラッパー

DB_PATH をテスト用に差し替えてから FastAPI アプリを起動する。
フロントエンドの dist/ を静的配信し、SPA ルーティングに対応する。

環境変数:
  - TEST_DB_PATH: テスト用DBファイルのパス（必須）
  - JWT_SECRET: JWTトークンの署名鍵（必須）
  - API_PORT: APIサーバーのポート番号（デフォルト: 18000）
"""

import os
import sys
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# DB_PATH を差し替え（api.main をインポートする前に実行）
db_path = os.environ.get("TEST_DB_PATH")
if not db_path:
    print("ERROR: TEST_DB_PATH environment variable is required", file=sys.stderr)
    sys.exit(1)

import rotation_planner.common.db as db_mod
import rotation_planner.common.db_access as dba_mod

db_mod.DB_PATH = Path(db_path)
db_mod.DB_DIR = Path(db_path).parent
dba_mod.DB_PATH = Path(db_path)

# アプリをインポート（この時点で DB_PATH は差し替え済み）
from api.main import app  # noqa: E402
from fastapi.responses import FileResponse  # noqa: E402
from starlette.staticfiles import StaticFiles  # noqa: E402

# フロントエンドビルド済みファイルを配信
dist_dir = project_root / "frontend" / "app" / "dist"
if dist_dir.exists():
    # /assets 配下の JS/CSS/画像を配信
    assets_dir = dist_dir / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="static-assets")

    # SPA フォールバック: API 以外のパスは index.html を返す
    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        # 実ファイルが存在すればそのまま返す（vite.svg 等）
        file_path = dist_dir / full_path
        if full_path and ".." not in full_path and file_path.is_file():
            return FileResponse(str(file_path))
        # それ以外は index.html（React Router が処理）
        return FileResponse(str(dist_dir / "index.html"))
else:
    print(f"WARNING: Frontend dist not found at {dist_dir}", file=sys.stderr)

import uvicorn  # noqa: E402

port = int(os.environ.get("API_PORT", "18000"))
uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
