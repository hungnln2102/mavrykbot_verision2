"""Helper functions for generating unique IDs from database."""
from __future__ import annotations

import logging
from mavrykbot.core.database import db

logger = logging.getLogger(__name__)


def get_next_id(table_name: str, column_name: str = "id") -> int:
    """
    Get the next available ID for a table by querying MAX(column_name) + 1.
    This ensures consistency with web backend's nextId() service.
    
    Args:
        table_name: Name of the table (e.g., "orders.order_list")
        column_name: Name of the ID column (default: "id")
    
    Returns:
        Next available ID as integer
    """
    try:
        query = f"SELECT COALESCE(MAX({column_name}), 0) + 1 AS next_id FROM {table_name}"
        result = db.fetch_one(query)
        
        if result and result[0]:
            next_id = int(result[0])
            logger.info(f"Next ID for {table_name}.{column_name}: {next_id}")
            return next_id
        
        logger.warning(f"Could not get next ID for {table_name}, defaulting to 1")
        return 1
        
    except Exception as e:
        logger.error(f"Error getting next ID for {table_name}: {e}", exc_info=True)
        return 1
