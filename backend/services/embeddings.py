import logging
from datetime import datetime
from typing import Dict, List, Optional

from beanie.operators import In

from backend.schemas.embeddings import FieldEmbedding

logger = logging.getLogger(__name__)


async def save_field_embedding(
    field_name: str,
    embedding: List[float],
    provider: str,
    model: Optional[str] = None,
) -> None:
    now = datetime.utcnow()
    try:
        # Define the document state for insertion
        insert_doc = FieldEmbedding(
            field_name=field_name,
            embedding=embedding,
            provider=provider,
            model=model,
            updated_at=now,
        )

        # Define the update operation
        update_op = {
            "$set": {
                "embedding": embedding,
                "provider": provider,
                "model": model,
                "updated_at": now,
            }
        }

        await FieldEmbedding.find_one(FieldEmbedding.field_name == field_name).upsert(
            update_op, on_insert=insert_doc
        )
        # Log success - specific insert/update distinction is lost with upsert
        logger.debug(f"Upserted embedding for field: {field_name}")

    except Exception as e:
        logger.error(
            f"Error upserting embedding for field '{field_name}': {e}", exc_info=True
        )


async def get_field_embeddings(field_names: List[str]) -> Dict[str, List[float]]:
    """Retrieves stored embeddings for a list of field names."""
    try:
        results = await FieldEmbedding.find(
            In(FieldEmbedding.field_name, field_names)
        ).to_list()
        return {doc.field_name: doc.embedding for doc in results}
    except Exception as e:
        logger.error(f"Error retrieving embeddings for fields: {e}", exc_info=True)
        return {}


async def delete_all_field_embeddings() -> int:
    """Deletes all field embeddings using Beanie Document methods."""
    try:
        delete_result = await FieldEmbedding.find(True).delete()
        deleted_count = delete_result.deleted_count if delete_result else 0
        logger.info(f"Deleted {deleted_count} field embeddings.")
        return deleted_count
    except Exception as e:
        logger.error(f"Error deleting all field embeddings: {e}", exc_info=True)
        return -1
