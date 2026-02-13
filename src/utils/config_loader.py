"""設定ファイル読み込みモジュール"""
import os
from pathlib import Path
from typing import Any, Dict

import yaml
from dotenv import load_dotenv


class ConfigLoader:
    """設定ファイル読み込みクラス"""

    def __init__(self, config_dir: str = "config"):
        self.config_dir = Path(config_dir)
        load_dotenv()

    def load_yaml(self, filename: str) -> Dict[str, Any]:
        """
        YAMLファイルを読み込む

        Args:
            filename: ファイル名（例: "config.yaml"）

        Returns:
            Dict: 設定内容
        """
        filepath = self.config_dir / filename

        if not filepath.exists():
            raise FileNotFoundError(f"設定ファイルが見つかりません: {filepath}")

        with open(filepath, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    def get_api_credentials(self) -> Dict[str, str]:
        """
        環境変数からAPI認証情報を取得

        Returns:
            Dict: API認証情報
        """
        required_keys = [
            "POLYMARKET_API_KEY",
            "POLYMARKET_API_SECRET",
            "POLYMARKET_API_PASSPHRASE",
            "POLYMARKET_PRIVATE_KEY",
            "POLYMARKET_FUNDER_ADDRESS",
        ]

        credentials = {}
        missing_keys = []

        for key in required_keys:
            value = os.getenv(key)
            if not value:
                missing_keys.append(key)
            credentials[key] = value

        if missing_keys:
            raise ValueError(
                f"必要な環境変数が設定されていません: {', '.join(missing_keys)}"
            )

        return credentials
