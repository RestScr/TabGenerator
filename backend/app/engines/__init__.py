"""Engine namespace with lazy imports for optional ML-heavy pipelines."""

from typing import Any

__all__ = ["GeneratedTabResult", "TabGenerationOptions", "generate_tab_from_audio"]


def __getattr__(name: str) -> Any:
    """Load tab generation only when a caller explicitly requests it.

    The Demucs-only subprocess imports ``app.engines.audio_preparation``.
    Eagerly importing the complete tab-generation stack here made that
    independent stage fail because of unrelated optional dependencies.
    """

    if name in __all__:
        from app.engines.tab_generation import GeneratedTabResult, TabGenerationOptions, generate_tab_from_audio

        return {
            "GeneratedTabResult": GeneratedTabResult,
            "TabGenerationOptions": TabGenerationOptions,
            "generate_tab_from_audio": generate_tab_from_audio,
        }[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
