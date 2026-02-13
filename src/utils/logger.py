"""ログ設定モジュール"""
from loguru import logger
import sys
from pathlib import Path


def setup_logger(log_level: str = "INFO"):
    """
    Loguruロガーの初期設定

    Args:
        log_level: ログレベル（DEBUG, INFO, WARNING, ERROR, CRITICAL）
    """
    # 既存のハンドラーを削除
    logger.remove()

    # コンソール出力
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
        level=log_level,
        colorize=True,
    )

    # ファイル出力
    log_path = Path("logs")
    log_path.mkdir(exist_ok=True)

    logger.add(
        log_path / "polybot_{time:YYYY-MM-DD}.log",
        rotation="500 MB",
        retention="10 days",
        level=log_level,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function} - {message}",
    )

    return logger
