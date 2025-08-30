"""
Script to seed default LLM configurations in the database.
Run this after database initialization to set up default provider mappings.
"""

import logging
from sqlalchemy.orm import Session
from .database import get_db
from .models import LLMConfiguration


def seed_llm_configurations(db: Session):
    """
    Seed the database with default LLM configurations.

    Args:
        db: Database session
    """
    # Default configurations
    default_configs = [
        {
            "role_name": "rag_generator",
            "provider_name": "gemini",
            "model_name": "gemini-1.5-pro",
            "is_active": 1,
        },
        {
            "role_name": "parser",
            "provider_name": "gemini",
            "model_name": "gemini-1.5-pro",
            "is_active": 1,
        },
        {
            "role_name": "indexer",
            "provider_name": "gemini",
            "model_name": "gemini-1.5-pro",
            "is_active": 1,
        },
        {
            "role_name": "rag_generator_ollama",
            "provider_name": "ollama",
            "model_name": "llama2",
            "is_active": 0,  # Inactive by default
        },
    ]

    for config_data in default_configs:
        # Check if configuration already exists
        existing = (
            db.query(LLMConfiguration)
            .filter_by(role_name=config_data["role_name"])
            .first()
        )

        if not existing:
            config = LLMConfiguration(**config_data)
            db.add(config)
            logging.info(
                f"Added LLM configuration: {config_data['role_name']} -> {config_data['provider_name']}"
            )
        else:
            logging.info(
                f"LLM configuration already exists: {config_data['role_name']}"
            )

    db.commit()
    logging.info("LLM configurations seeding completed")


def initialize_llm_configurations():
    """
    Initialize LLM configurations by seeding defaults.
    Call this during application startup.
    """
    try:
        db = next(get_db())
        seed_llm_configurations(db)
    except Exception as e:
        logging.error(f"Failed to seed LLM configurations: {str(e)}")
        raise


if __name__ == "__main__":
    # Allow running as standalone script
    initialize_llm_configurations()
