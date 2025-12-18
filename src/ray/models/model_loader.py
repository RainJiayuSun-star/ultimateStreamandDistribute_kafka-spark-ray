"""
Model loading utilities for Ray inference.
Handles loading trained models from disk or creating simple models if none exist.
"""

import os
import pickle
import logging
from pathlib import Path
from typing import Optional, Any

logger = logging.getLogger(__name__)

# Model storage paths
MODEL_BASE_PATH = os.getenv("MODEL_STORAGE_PATH", "/app/models")
FORECASTING_MODEL_PATH = os.path.join(MODEL_BASE_PATH, "forecasting")
ANOMALY_MODEL_PATH = os.path.join(MODEL_BASE_PATH, "anomaly")


def get_latest_model_version(model_type: str) -> Optional[str]:
    """
    Get the latest model version for a given model type.
    
    Args:
        model_type: "forecasting" or "anomaly"
    
    Returns:
        Latest version string (e.g., "v1.0") or None if no models exist
    """
    if model_type == "forecasting":
        model_dir = Path(FORECASTING_MODEL_PATH)
    elif model_type == "anomaly":
        model_dir = Path(ANOMALY_MODEL_PATH)
    else:
        logger.error(f"Unknown model type: {model_type}")
        return None
    
    if not model_dir.exists():
        logger.info(f"No models directory found for {model_type}")
        return None
    
    # Look for version directories (v1.0, v1.1, etc.)
    versions = []
    for item in model_dir.iterdir():
        if item.is_dir() and item.name.startswith("v"):
            versions.append(item.name)
    
    if not versions:
        logger.info(f"No model versions found for {model_type}")
        return None
    
    # Sort versions and return latest
    versions.sort(reverse=True)
    return versions[0]


def load_forecasting_model(model_path: Optional[str] = None) -> Any:
    """
    Load forecasting model from disk.
    
    Args:
        model_path: Optional path to specific model. If None, loads latest.
    
    Returns:
        Loaded model object, or None if loading fails
    """
    try:
        if model_path is None:
            # Get latest model version
            version = get_latest_model_version("forecasting")
            if version is None:
                logger.warning("No trained forecasting model found. Will use simple model.")
                return None
            model_path = os.path.join(FORECASTING_MODEL_PATH, version, "model.pkl")
        
        if not os.path.exists(model_path):
            logger.warning(f"Forecasting model not found at {model_path}")
            return None
        
        with open(model_path, 'rb') as f:
            model = pickle.load(f)
        
        logger.info(f"Successfully loaded forecasting model from {model_path}")
        return model
    
    except Exception as e:
        logger.error(f"Error loading forecasting model: {e}")
        return None


def load_anomaly_model(model_path: Optional[str] = None) -> Any:
    """
    Load anomaly detection model from disk.
    
    Args:
        model_path: Optional path to specific model. If None, loads latest.
    
    Returns:
        Loaded model object, or None if loading fails
    """
    try:
        if model_path is None:
            # Get latest model version
            version = get_latest_model_version("anomaly")
            if version is None:
                logger.warning("No trained anomaly model found. Will use simple model.")
                return None
            model_path = os.path.join(ANOMALY_MODEL_PATH, version, "model.pkl")
        
        if not os.path.exists(model_path):
            logger.warning(f"Anomaly model not found at {model_path}")
            return None
        
        with open(model_path, 'rb') as f:
            model = pickle.load(f)
        
        logger.info(f"Successfully loaded anomaly model from {model_path}")
        return model
    
    except Exception as e:
        logger.error(f"Error loading anomaly model: {e}")
        return None


def validate_model(model: Any, model_type: str) -> bool:
    """
    Validate that a loaded model has the expected interface.
    
    Args:
        model: Model object to validate
        model_type: "forecasting" or "anomaly"
    
    Returns:
        True if model is valid, False otherwise
    """
    if model is None:
        return False
    
    # Basic validation - check if model has predict method
    if not hasattr(model, 'predict'):
        logger.error(f"Model of type {model_type} does not have predict method")
        return False
    
    return True


def save_model(model: Any, model_type: str, version: str) -> bool:
    """
    Save a trained model to disk.
    
    Args:
        model: Model object to save
        model_type: "forecasting" or "anomaly"
        version: Version string (e.g., "v1.0")
    
    Returns:
        True if successful, False otherwise
    """
    try:
        if model_type == "forecasting":
            model_dir = Path(FORECASTING_MODEL_PATH) / version
        elif model_type == "anomaly":
            model_dir = Path(ANOMALY_MODEL_PATH) / version
        else:
            logger.error(f"Unknown model type: {model_type}")
            return False
        
        # Create directory if it doesn't exist
        model_dir.mkdir(parents=True, exist_ok=True)
        
        # Save model
        model_path = model_dir / "model.pkl"
        with open(model_path, 'wb') as f:
            pickle.dump(model, f)
        
        logger.info(f"Successfully saved {model_type} model to {model_path}")
        return True
    
    except Exception as e:
        logger.error(f"Error saving {model_type} model: {e}")
        return False

