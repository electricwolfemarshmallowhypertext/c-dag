"""Local file-backed registries for model and policy configs."""

from __future__ import annotations

from pathlib import Path

from causal_credit_risk.interfaces import ModelRegistry, PolicyRegistry
from causal_credit_risk.model import CausalDAGModel
from causal_credit_risk.schemas import ModelConfig, PolicyConfig
from causal_credit_risk.settings import project_root


def default_model_config_path() -> Path:
    return project_root() / "configs" / "credit_risk_model.v1.json"


def default_policy_config_path() -> Path:
    return project_root() / "configs" / "decision_policy.v1.json"


class FileModelRegistry(ModelRegistry):
    def __init__(self, default_path: str | Path | None = None) -> None:
        self._default_path = Path(default_path) if default_path is not None else default_model_config_path()

    def load_model(self, model_config_path: str | None = None) -> CausalDAGModel:
        return CausalDAGModel.from_json(self._resolve_path(model_config_path))

    def load_model_config(self, model_config_path: str | None = None) -> ModelConfig:
        return ModelConfig.from_json(self._resolve_path(model_config_path))

    def _resolve_path(self, model_config_path: str | None) -> Path:
        return Path(model_config_path) if model_config_path else self._default_path


class FilePolicyRegistry(PolicyRegistry):
    def __init__(self, default_path: str | Path | None = None) -> None:
        self._default_path = Path(default_path) if default_path is not None else default_policy_config_path()

    def load_policy_config(self, policy_config_path: str | None = None) -> PolicyConfig:
        path = Path(policy_config_path) if policy_config_path else self._default_path
        return PolicyConfig.from_json(path)
