"""Public facade for isolated EPConfig validation behavior."""

from __future__ import annotations

from core._protected.validator_core import (
    EPConfigValidator as LocalEPConfigValidator,
    ValidationLevel,
    ValidationResult,
)
from core.material_worker_client import MaterialWorkerError, run_worker_validation

ValidationLevel.__module__ = __name__
ValidationResult.__module__ = __name__


class EPConfigValidator:
    """Worker-backed EPConfig validator facade."""

    def __init__(self, base_dir: str = ""):
        self.base_dir = base_dir
        self.results: list[ValidationResult] = []
        self._local_fallback = LocalEPConfigValidator(base_dir)

    def validate(self, config: dict) -> list[ValidationResult]:
        try:
            raw_results = run_worker_validation(config, base_dir=self.base_dir)
            self.results = [
                ValidationResult(
                    level=ValidationLevel(item["level"]),
                    field=item["field"],
                    message=item["message"],
                )
                for item in raw_results
            ]
        except MaterialWorkerError:
            self.results = self._local_fallback.validate(config)
        return self.results

    def validate_config(self, config) -> list[ValidationResult]:
        return self.validate(config.to_dict())

    def has_errors(self) -> bool:
        return any(result.level == ValidationLevel.ERROR for result in self.results)

    def has_warnings(self) -> bool:
        return any(
            result.level == ValidationLevel.WARNING for result in self.results
        )

    def get_errors(self) -> list[ValidationResult]:
        return [
            result for result in self.results if result.level == ValidationLevel.ERROR
        ]

    def get_warnings(self) -> list[ValidationResult]:
        return [
            result
            for result in self.results
            if result.level == ValidationLevel.WARNING
        ]

    def get_infos(self) -> list[ValidationResult]:
        return [result for result in self.results if result.level == ValidationLevel.INFO]

    def get_summary(self) -> str:
        errors = len(self.get_errors())
        warnings = len(self.get_warnings())
        if errors == 0 and warnings == 0:
            return "Configuration is valid"
        if errors == 0:
            return f"Configuration is valid with {warnings} warning(s)"
        return f"Configuration is invalid: {errors} error(s), {warnings} warning(s)"


EPConfigValidator.__module__ = __name__

__all__ = ["EPConfigValidator", "ValidationLevel", "ValidationResult"]
