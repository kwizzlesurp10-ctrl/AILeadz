"""
Tests for clawmode_integration/config.py
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from clawmode_integration.config import (
    ClawWorkConfig,
    ClawWorkTokenPricing,
    load_clawwork_config,
)


class TestClawWorkTokenPricing:
    def test_default_prices(self):
        pricing = ClawWorkTokenPricing()
        assert pricing.input_price == 2.5
        assert pricing.output_price == 10.0

    def test_custom_prices(self):
        pricing = ClawWorkTokenPricing(input_price=1.0, output_price=5.0)
        assert pricing.input_price == 1.0
        assert pricing.output_price == 5.0


class TestClawWorkConfig:
    def test_defaults(self):
        cfg = ClawWorkConfig()
        assert cfg.enabled is False
        assert cfg.signature == ""
        assert cfg.initial_balance == 1000.0
        assert cfg.meta_prompts_dir == "./eval/meta_prompts"
        assert cfg.data_path == "./livebench/data/agent_data"
        assert cfg.enable_file_reading is True
        assert isinstance(cfg.token_pricing, ClawWorkTokenPricing)

    def test_custom_values(self):
        pricing = ClawWorkTokenPricing(input_price=3.0, output_price=12.0)
        cfg = ClawWorkConfig(
            enabled=True,
            signature="agent-001",
            initial_balance=500.0,
            token_pricing=pricing,
        )
        assert cfg.enabled is True
        assert cfg.signature == "agent-001"
        assert cfg.initial_balance == 500.0
        assert cfg.token_pricing.input_price == 3.0


class TestLoadClawworkConfig:
    def test_missing_file_returns_defaults(self, tmp_path):
        missing = tmp_path / "no_such_file.json"
        cfg = load_clawwork_config(config_path=missing)
        assert isinstance(cfg, ClawWorkConfig)
        assert cfg.enabled is False
        assert cfg.initial_balance == 1000.0

    def test_empty_json_returns_defaults(self, tmp_path):
        config_file = tmp_path / "config.json"
        config_file.write_text("{}")
        cfg = load_clawwork_config(config_path=config_file)
        assert isinstance(cfg, ClawWorkConfig)
        assert cfg.enabled is False

    def test_missing_clawwork_section_returns_defaults(self, tmp_path):
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({"agents": {"other": {}}}))
        cfg = load_clawwork_config(config_path=config_file)
        assert isinstance(cfg, ClawWorkConfig)
        assert cfg.enabled is False

    def test_full_config_is_loaded(self, tmp_path):
        payload = {
            "agents": {
                "clawwork": {
                    "enabled": True,
                    "signature": "test-agent",
                    "initialBalance": 250.0,
                    "taskValuesPath": "/tmp/tasks.json",
                    "metaPromptsDir": "/tmp/meta",
                    "dataPath": "/tmp/data",
                    "enableFileReading": False,
                    "tokenPricing": {
                        "inputPrice": 1.5,
                        "outputPrice": 6.0,
                    },
                }
            }
        }
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps(payload))
        cfg = load_clawwork_config(config_path=config_file)
        assert cfg.enabled is True
        assert cfg.signature == "test-agent"
        assert cfg.initial_balance == 250.0
        assert cfg.task_values_path == "/tmp/tasks.json"
        assert cfg.meta_prompts_dir == "/tmp/meta"
        assert cfg.data_path == "/tmp/data"
        assert cfg.enable_file_reading is False
        assert cfg.token_pricing.input_price == 1.5
        assert cfg.token_pricing.output_price == 6.0

    def test_partial_config_uses_defaults_for_missing_keys(self, tmp_path):
        payload = {"agents": {"clawwork": {"enabled": True, "signature": "partial"}}}
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps(payload))
        cfg = load_clawwork_config(config_path=config_file)
        assert cfg.enabled is True
        assert cfg.signature == "partial"
        assert cfg.initial_balance == 1000.0
        assert cfg.token_pricing.input_price == 2.5

    def test_invalid_json_returns_defaults(self, tmp_path):
        config_file = tmp_path / "config.json"
        config_file.write_text("not valid json {{{")
        cfg = load_clawwork_config(config_path=config_file)
        assert isinstance(cfg, ClawWorkConfig)
        assert cfg.enabled is False
