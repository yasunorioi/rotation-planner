"""
FastAPI例外ハンドラ — カスタム例外をHTTPレスポンスに変換

rotation_planner.common.exceptions の例外階層を
適切なHTTPステータスコード + JSON {"detail": ...} に変換する。
"""

import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from rotation_planner.common.exceptions import (
    RotationPlannerError,
    DatabaseError,
    DatabaseConnectionError,
    DuplicateKeyError,
    ForeignKeyViolationError,
    NotNullViolationError,
    RecordNotFoundError,
    FileOperationError,
    ValidationError,
)

logger = logging.getLogger("rotation_planner.api")


def register_exception_handlers(app: FastAPI) -> None:
    """アプリケーションにグローバル例外ハンドラを登録する"""

    @app.exception_handler(RecordNotFoundError)
    async def record_not_found_handler(request: Request, exc: RecordNotFoundError):
        logger.warning("RecordNotFoundError: %s [%s %s]", exc.message, request.method, request.url.path)
        return JSONResponse(status_code=404, content={"detail": exc.user_message})

    @app.exception_handler(DuplicateKeyError)
    async def duplicate_key_handler(request: Request, exc: DuplicateKeyError):
        logger.warning("DuplicateKeyError: %s [%s %s]", exc.message, request.method, request.url.path)
        return JSONResponse(status_code=409, content={"detail": exc.user_message})

    @app.exception_handler(ForeignKeyViolationError)
    async def foreign_key_handler(request: Request, exc: ForeignKeyViolationError):
        logger.warning("ForeignKeyViolationError: %s [%s %s]", exc.message, request.method, request.url.path)
        return JSONResponse(status_code=400, content={"detail": exc.user_message})

    @app.exception_handler(NotNullViolationError)
    async def not_null_handler(request: Request, exc: NotNullViolationError):
        logger.warning("NotNullViolationError: %s [%s %s]", exc.message, request.method, request.url.path)
        return JSONResponse(status_code=400, content={"detail": exc.user_message})

    @app.exception_handler(DatabaseConnectionError)
    async def db_connection_handler(request: Request, exc: DatabaseConnectionError):
        logger.critical("DatabaseConnectionError: %s [%s %s]", exc.message, request.method, request.url.path)
        return JSONResponse(status_code=503, content={"detail": "データベースに接続できません"})

    @app.exception_handler(DatabaseError)
    async def database_error_handler(request: Request, exc: DatabaseError):
        logger.error("DatabaseError: %s [%s %s]", exc.message, request.method, request.url.path, exc_info=True)
        return JSONResponse(status_code=500, content={"detail": exc.user_message})

    @app.exception_handler(ValidationError)
    async def validation_error_handler(request: Request, exc: ValidationError):
        logger.info("ValidationError: field=%s %s [%s %s]", exc.field, exc.message, request.method, request.url.path)
        return JSONResponse(status_code=422, content={"detail": exc.user_message})

    @app.exception_handler(FileOperationError)
    async def file_operation_handler(request: Request, exc: FileOperationError):
        logger.error("FileOperationError: %s [%s %s]", exc.message, request.method, request.url.path, exc_info=True)
        return JSONResponse(status_code=500, content={"detail": exc.user_message})

    @app.exception_handler(RotationPlannerError)
    async def rotation_planner_error_handler(request: Request, exc: RotationPlannerError):
        logger.error("RotationPlannerError: %s [%s %s]", exc.message, request.method, request.url.path, exc_info=True)
        return JSONResponse(status_code=500, content={"detail": exc.user_message})


def require_found(obj, resource_name: str = "リソース"):
    """
    objがNoneの場合RecordNotFoundErrorを送出する。

    Usage:
        field = require_found(FieldRepository.get_field(field_id), "ほ場")
    """
    if obj is None:
        raise RecordNotFoundError(
            f"{resource_name} not found",
            f"{resource_name}が見つかりません"
        )
    return obj
