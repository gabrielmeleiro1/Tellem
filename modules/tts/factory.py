"""
TTS Engine Factory
==================
Factory pattern for creating TTS strategy instances.
Enables runtime selection of TTS engines.
"""

from typing import Type, Optional

from modules.tts.strategies.base import TTSStrategy, TTSConfig
from modules.tts.strategies.kokoro import KokoroTTSStrategy, KokoroConfig
from modules.tts.strategies.orpheus import OrpheusTTSStrategy, OrpheusConfig


class TTSEngineFactory:
    """
    Factory for creating TTS strategy instances.
    
    Usage:
        # Create default Kokoro engine
        engine = TTSEngineFactory.create("kokoro")
        
        # Create with custom config
        config = KokoroConfig(quantization="4bit")
        engine = TTSEngineFactory.create("kokoro", config)
        
        # List available engines
        engines = TTSEngineFactory.available_engines()
    """
    
    # Registry of available strategies
    _strategies: dict[str, Type[TTSStrategy]] = {
        "kokoro": KokoroTTSStrategy,
        "orpheus": OrpheusTTSStrategy,
    }
    
    _config_types: dict[str, Type[TTSConfig]] = {
        "kokoro": KokoroConfig,
        "orpheus": OrpheusConfig,
    }
    
    @classmethod
    def create(
        cls,
        engine_type: str,
        config: Optional[TTSConfig] = None,
        **config_kwargs
    ) -> TTSStrategy:
        """
        Create a TTS strategy instance.
        
        Args:
            engine_type: Engine identifier ('kokoro', 'orpheus', etc.)
            config: Optional configuration object
            **config_kwargs: Configuration parameters if config not provided
            
        Returns:
            TTSStrategy instance
            
        Raises:
            ValueError: If engine_type is not registered
            TypeError: If config type doesn't match engine
            
        Example:
            # Simple creation
            engine = TTSEngineFactory.create("kokoro")
            
            # With config object
            config = KokoroConfig(quantization="4bit")
            engine = TTSEngineFactory.create("kokoro", config)
            
            # With kwargs
            engine = TTSEngineFactory.create("kokoro", quantization="4bit")
        """
        engine_type = engine_type.lower()
        
        if engine_type not in cls._strategies:
            available = ", ".join(cls.available_engines())
            raise ValueError(
                f"Unknown TTS engine: '{engine_type}'. "
                f"Available engines: {available}"
            )
        
        strategy_class = cls._strategies[engine_type]
        
        # Handle config
        if config is not None:
            # Validate config type
            expected_config_type = cls._config_types.get(engine_type, TTSConfig)
            if not isinstance(config, expected_config_type):
                raise TypeError(
                    f"Expected {expected_config_type.__name__} for {engine_type}, "
                    f"got {type(config).__name__}"
                )
            return strategy_class(config)
        
        # Create with kwargs
        if config_kwargs:
            config_type = cls._config_types.get(engine_type, TTSConfig)
            config = config_type(**config_kwargs)
            return strategy_class(config)
        
        # Create with default config
        return strategy_class()
    
    @classmethod
    def register(
        cls,
        name: str,
        strategy_class: Type[TTSStrategy],
        config_class: Type[TTSConfig] = TTSConfig
    ) -> None:
        """
        Register a new TTS strategy.
        
        Args:
            name: Engine identifier
            strategy_class: Strategy class implementing TTSStrategy
            config_class: Configuration class for this strategy
            
        Example:
            TTSEngineFactory.register(
                "custom",
                CustomTTSStrategy,
                CustomConfig
            )
        """
        cls._strategies[name.lower()] = strategy_class
        cls._config_types[name.lower()] = config_class
    
    @classmethod
    def unregister(cls, name: str) -> None:
        """
        Unregister a TTS strategy.
        
        Args:
            name: Engine identifier to remove
            
        Raises:
            KeyError: If engine not registered
        """
        name = name.lower()
        if name not in cls._strategies:
            raise KeyError(f"Engine '{name}' not registered")
        
        del cls._strategies[name]
        if name in cls._config_types:
            del cls._config_types[name]
    
    @classmethod
    def available_engines(cls) -> list[str]:
        """
        List available engine names.
        
        Returns:
            List of registered engine identifiers
        """
        return list(cls._strategies.keys())
    
    @classmethod
    def get_engine_info(cls, engine_type: str) -> dict:
        """
        Get information about an engine.
        
        Args:
            engine_type: Engine identifier
            
        Returns:
            Dict with engine info
            
        Raises:
            ValueError: If engine not found
        """
        engine_type = engine_type.lower()
        
        if engine_type not in cls._strategies:
            raise ValueError(f"Unknown engine: {engine_type}")
        
        strategy_class = cls._strategies[engine_type]
        
        # Create temporary instance to get info
        temp_instance = strategy_class()
        
        return {
            "name": temp_instance.name,
            "display_name": temp_instance.display_name,
            "version": temp_instance.version,
            "supports_batching": temp_instance.supports_batching,
            "supports_streaming": temp_instance.supports_streaming,
            "sample_rate": temp_instance.sample_rate,
            "voices": [
                {
                    "id": v.id,
                    "name": v.name,
                    "language": v.language,
                    "gender": v.gender,
                    "description": v.description,
                }
                for v in temp_instance.supported_voices
            ],
        }
    
    @classmethod
    def is_available(cls, engine_type: str) -> bool:
        """
        Check if an engine type is registered.
        
        Args:
            engine_type: Engine identifier
            
        Returns:
            True if engine is available
        """
        return engine_type.lower() in cls._strategies
    
    @classmethod
    def get_default_engine(cls) -> str:
        """
        Get the default engine identifier.
        
        Returns:
            Default engine name ('kokoro' if available)
        """
        if "kokoro" in cls._strategies:
            return "kokoro"
        
        # Return first available
        available = cls.available_engines()
        if available:
            return available[0]
        
        raise RuntimeError("No TTS engines registered")


# Convenience function for quick engine creation
def create_tts_engine(
    engine_type: Optional[str] = None,
    **config_kwargs
) -> TTSStrategy:
    """
    Convenience function to create a TTS engine.
    
    Args:
        engine_type: Engine type (defaults to 'kokoro')
        **config_kwargs: Configuration parameters
        
    Returns:
        TTSStrategy instance
        
    Example:
        engine = create_tts_engine("kokoro", quantization="bf16")
    """
    if engine_type is None:
        engine_type = TTSEngineFactory.get_default_engine()
    
    return TTSEngineFactory.create(engine_type, **config_kwargs)
