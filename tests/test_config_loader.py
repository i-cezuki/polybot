"""ConfigLoaderのユニットテスト"""
import os
import tempfile
from pathlib import Path

import pytest
import yaml

from utils.config_loader import ConfigLoader


class TestConfigLoader:
    def test_load_yaml_success(self, tmp_path):
        """YAMLファイルを正常に読み込めること"""
        config_data = {"key": "value", "nested": {"a": 1}}
        config_file = tmp_path / "test.yaml"
        config_file.write_text(yaml.dump(config_data))

        loader = ConfigLoader(config_dir=str(tmp_path))
        result = loader.load_yaml("test.yaml")

        assert result == config_data

    def test_load_yaml_file_not_found(self, tmp_path):
        """存在しないファイルでFileNotFoundErrorが発生すること"""
        loader = ConfigLoader(config_dir=str(tmp_path))

        with pytest.raises(FileNotFoundError):
            loader.load_yaml("nonexistent.yaml")

    def test_get_api_credentials_success(self, monkeypatch):
        """環境変数からAPI認証情報を取得できること"""
        env_vars = {
            "POLYMARKET_API_KEY": "test_key",
            "POLYMARKET_API_SECRET": "test_secret",
            "POLYMARKET_API_PASSPHRASE": "test_pass",
            "POLYMARKET_PRIVATE_KEY": "test_pk",
            "POLYMARKET_FUNDER_ADDRESS": "test_addr",
        }
        for k, v in env_vars.items():
            monkeypatch.setenv(k, v)

        loader = ConfigLoader()
        creds = loader.get_api_credentials()

        for k, v in env_vars.items():
            assert creds[k] == v

    def test_get_api_credentials_missing(self, monkeypatch):
        """必要な環境変数が欠落しているとValueErrorが発生すること"""
        # 全ての関連環境変数をクリア
        for key in [
            "POLYMARKET_API_KEY",
            "POLYMARKET_API_SECRET",
            "POLYMARKET_API_PASSPHRASE",
            "POLYMARKET_PRIVATE_KEY",
            "POLYMARKET_FUNDER_ADDRESS",
        ]:
            monkeypatch.delenv(key, raising=False)

        loader = ConfigLoader()

        with pytest.raises(ValueError, match="必要な環境変数が設定されていません"):
            loader.get_api_credentials()
