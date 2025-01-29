import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Set

from beanie import SortDirection
from beanie.operators import RegEx
from pymongo import UpdateOne
from pymongo.errors import BulkWriteError

from ..schemas.analysis import AnalyzedListingDocument
from ..schemas.analytics import FieldMapping, MappingLog, ModelPriceStats
from ..schemas.listings import ListingDocument

logger = logging.getLogger(__name__)


@dataclass
class ReversionPreview:
    """Preview of changes that would be made by a reversion operation."""

    document_id: str
    original_fields: Dict[str, Any]  # Original field name -> original value
    mapped_fields: Set[str]  # Fields that would be removed

    def __str__(self) -> str:
        return (
            f"Document {self.document_id}:\n"
            f"  - Fields to restore: {dict(self.original_fields)}\n"
            f"  - Mapped fields to remove: {self.mapped_fields}"
        )


@dataclass
class ReversionResult:
    """Result of a reversion operation."""

    mapping_id: str
    documents_reverted: int
    errors: List[str]

    def __str__(self) -> str:
        status = "Success" if not self.errors else "Failed"
        return (
            f"Mapping {self.mapping_id} - {status}\n"
            f"Documents reverted: {self.documents_reverted}\n"
            f"Errors: {', '.join(self.errors) if self.errors else 'None'}"
        )


async def get_active_field_mapping() -> Optional[FieldMapping]:
    """Get the currently active field mappings."""
    try:
        return await FieldMapping.find_one({"is_active": True})
    except Exception as e:
        logger.error(f"Error loading field mappings: {str(e)}")
        return None


async def create_new_field_mapping(mappings: Dict[str, str]) -> FieldMapping:
    """Create a new field mapping and deactivate old one.

    Args:
        mappings: Dictionary mapping original fields to canonical forms

    Returns:
        The created FieldMapping document
    """
    try:
        # Deactivate current active mapping
        current_mapping = await FieldMapping.find_one({"is_active": True})
        if current_mapping:
            current_mapping.is_active = False
            await current_mapping.save()

        # Create new active mapping
        mapping_doc = FieldMapping(
            mappings=mappings,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            is_active=True,
        )
        await mapping_doc.insert()
        return mapping_doc

    except Exception as e:
        logger.error(f"Error saving field mappings: {e.__class__}: {e}")
        raise


async def apply_field_mapping(mapping_id: str) -> int:
    """Apply field mapping to all analyzed listings using MongoDB aggregation.
    The operation is performed entirely in MongoDB for better performance.

    Args:
        mapping_id: ID of the FieldMapping document to apply

    Returns:
        Number of documents updated
    """
    try:
        # Get the mapping document
        mapping_doc = await FieldMapping.get(mapping_id)
        if not mapping_doc:
            logger.error(f"Field mapping {mapping_id} not found")
            return 0

        if not mapping_doc.mappings:
            logger.info("No mappings to apply")
            return 0

        # Convert mapping to array to handle dotted field names
        field_mapping_array = [
            {"k": k, "v": v} for k, v in mapping_doc.mappings.items()
        ]

        # Get MongoDB collections
        collection = AnalyzedListingDocument.get_motor_collection()

        # Create pipeline to transform the info dictionary
        pipeline = [
            # Match documents with info field
            {"$match": {"info": {"$exists": True}}},
            # Initial setup - convert both info and mapping to arrays
            {
                "$set": {
                    "field_mapping": field_mapping_array,
                    "info_array": {"$objectToArray": "$info"},
                }
            },
            # Process each field
            {
                "$set": {
                    "processed_fields": {
                        "$map": {
                            "input": "$info_array",
                            "as": "info_field",
                            "in": {
                                "$let": {
                                    "vars": {
                                        "matching_mapping": {
                                            "$first": {
                                                "$filter": {
                                                    "input": "$field_mapping",
                                                    "cond": {
                                                        "$eq": [
                                                            "$$this.k",
                                                            "$$info_field.k",
                                                        ]
                                                    },
                                                }
                                            }
                                        }
                                    },
                                    "in": {
                                        "$cond": {
                                            "if": {"$ne": ["$$matching_mapping", None]},
                                            "then": {
                                                "k": "$$matching_mapping.v",
                                                "v": "$$info_field.v",
                                                "original_field": "$$info_field.k",
                                                "was_mapped": 1,
                                            },
                                            "else": {
                                                "k": "$$info_field.k",
                                                "v": "$$info_field.v",
                                                "was_mapped": 0,
                                            },
                                        }
                                    },
                                }
                            },
                        }
                    }
                }
            },
            # Convert processed fields back to object and update document
            {
                "$set": {
                    "info": {
                        "$arrayToObject": {
                            "$map": {
                                "input": "$processed_fields",
                                "as": "field",
                                "in": {"k": "$$field.k", "v": "$$field.v"},
                            }
                        }
                    },
                    "mapped_fields": {
                        "$filter": {
                            "input": "$processed_fields",
                            "as": "field",
                            "cond": {"$eq": ["$$field.was_mapped", 1]},
                        }
                    },
                }
            },
            # Cleanup temporary fields
            {"$unset": ["info_array", "processed_fields", "field_mapping"]},
        ]

        try:
            # Execute the pipeline and get modified documents
            cursor = collection.aggregate(pipeline)
            modified_docs = await cursor.to_list(length=None)

            if not modified_docs:
                logger.info("No documents matched the criteria for update")
                return 0

            # Prepare bulk write operations and mapping logs
            bulk_operations = []
            mapping_logs = []
            now = datetime.utcnow()

            for doc in modified_docs:
                # Prepare document update
                bulk_operations.append(
                    UpdateOne({"_id": doc["_id"]}, {"$set": {"info": doc["info"]}})
                )

                # Prepare mapping logs for each mapped field
                for mapped_field in doc.get("mapped_fields", []):
                    mapping_logs.append(
                        MappingLog(
                            mapping_id=mapping_doc.id,  # type: ignore
                            document_id=doc["_id"],
                            original_field=mapped_field["original_field"],
                            mapped_field=mapped_field["k"],
                            original_value=mapped_field["v"],
                            timestamp=now,
                        )
                    )

            # Execute bulk write for document updates
            logger.info(f"Executing {len(bulk_operations)} document updates")
            result = await collection.bulk_write(bulk_operations)

            # Insert mapping logs if there were successful updates
            if result.modified_count > 0:
                if mapping_logs:
                    logger.info(f"Creating {len(mapping_logs)} mapping log entries")
                    await MappingLog.insert_many(mapping_logs)

                # Update mapping document to be active
                current_active = await FieldMapping.find_one({"is_active": True})
                if current_active:
                    await current_active.set({"is_active": False})
                await mapping_doc.set({"is_active": True})

            logger.info(
                f"Field mapping complete. Updated {result.modified_count} documents"
            )
            return result.modified_count

        except Exception as e:
            logger.error(f"Error during aggregation or bulk write: {str(e)}")
            raise

    except Exception as e:
        logger.error(f"Error applying field mapping: {str(e)}")
        return 0


async def get_field_mapping_history(days: int = 30) -> List[FieldMapping]:
    """Get history of field mappings.

    Args:
        days: Number of days of history to retrieve

    Returns:
        List of field mapping documents ordered by creation date
    """
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        return (
            await FieldMapping.find({"created_at": {"$gte": cutoff}})
            .sort("-created_at")
            .to_list()
        )
    except Exception as e:
        logger.error(f"Error getting field mapping history: {str(e)}")
        return []


async def update_model_price_stats() -> int:
    """
    Create a new snapshot of model price statistics.
    Uses the base_model field directly for grouping.
    Returns the number of models processed.
    """
    try:
        pipeline = [
            # Match only listings with valid prices
            {
                "$match": {
                    "price_value": {"$exists": True, "$ne": None, "$gt": 0},
                    "analysis_status": "completed",  # Only use analyzed listings
                }
            },
            {
                "$lookup": {
                    "from": "analyzed_listings",
                    "localField": "original_id",
                    "foreignField": "original_listing_id",
                    "as": "analysis",
                }
            },
            {"$unwind": "$analysis"},
            # Filter out listings without base_model
            {"$match": {"analysis.base_model": {"$exists": True, "$nin": [None, ""]}}},
            {
                "$group": {
                    "_id": "$analysis.base_model",
                    "prices": {"$push": {"$toDouble": "$price_value"}},
                    "count": {"$sum": 1},
                }
            },
            # Filter out groups with too few listings
            {
                "$match": {"count": {"$gte": 3}}
            },  # Require at least 3 listings for statistical relevance
            # Calculate statistics
            {
                "$project": {
                    "_id": 0,
                    "base_model": "$_id",
                    "avg_price": {"$round": [{"$avg": "$prices"}, 2]},
                    "min_price": {"$round": [{"$min": "$prices"}, 2]},
                    "max_price": {"$round": [{"$max": "$prices"}, 2]},
                    "median_price": {
                        "$round": [
                            {
                                "$arrayElemAt": [
                                    "$prices",
                                    {"$floor": {"$divide": [{"$size": "$prices"}, 2]}},
                                ]
                            },
                            2,
                        ]
                    },
                    "sample_size": "$count",
                    "timestamp": {"$literal": datetime.utcnow()},
                }
            },
        ]

        results = await ListingDocument.aggregate(pipeline).to_list()

        if not results:
            logger.warning("No price statistics generated - no valid data found")
            return 0

        stats = []
        for result in results:
            try:
                base_model = result.get("base_model")
                if not base_model:  # Skip if base_model is None
                    continue

                logger.info(f"Creating price stats for model: {base_model}")

                avg_price = result.get("avg_price")
                min_price = result.get("min_price")
                max_price = result.get("max_price")
                median_price = result.get("median_price")
                sample_size = result.get("sample_size")
                timestamp = result.get("timestamp")

                # Skip if any required field is None
                if any(
                    v is None
                    for v in [
                        avg_price,
                        min_price,
                        max_price,
                        median_price,
                        sample_size,
                        timestamp,
                    ]
                ):
                    logger.warning(f"Skipping incomplete stats for model {base_model}")
                    continue

                # Ensure sample_size is an integer
                if not isinstance(sample_size, (int, float, str)):
                    logger.warning(
                        f"Invalid sample size type for model {base_model}: {type(sample_size)}"
                    )
                    continue

                try:
                    sample_size_int = int(float(str(sample_size)))
                except (TypeError, ValueError):
                    logger.warning(
                        f"Invalid sample size for model {base_model}: {sample_size}"
                    )
                    continue

                stats.append(
                    ModelPriceStats(
                        base_model=base_model,
                        avg_price=Decimal(str(avg_price)),
                        min_price=Decimal(str(min_price)),
                        max_price=Decimal(str(max_price)),
                        median_price=Decimal(str(median_price)),
                        sample_size=sample_size_int,
                        timestamp=(
                            timestamp
                            if isinstance(timestamp, datetime)
                            else datetime.utcnow()
                        ),
                    )
                )
            except Exception as e:
                logger.error(
                    f"Failed to create stats for model {result.get('base_model')}: {str(e)}"
                )
                continue

        if stats:
            await ModelPriceStats.insert_many(stats)
            logger.info(f"Created price statistics for {len(stats)} models")
            return len(stats)
        return 0

    except Exception as e:
        logger.error(f"Failed to update model price statistics: {str(e)}")
        raise e


async def get_model_price_history(
    base_model: str, days: int = 30, limit: Optional[int] = None
) -> List[ModelPriceStats]:
    """
    Get price history for a specific model.

    Args:
        base_model: The base model name (case-insensitive)
        days: Number of days of history to retrieve
        limit: Optional limit on number of results

    Returns:
        List of price statistics ordered by timestamp
    """
    try:
        if not base_model:
            logger.error("Base model must be provided")
            return []

        if days < 1:
            logger.error("Days must be positive")
            return []

        cutoff = datetime.utcnow() - timedelta(days=days)
        logger.debug(f"Searching for price history with base_model: {base_model}")

        # Try exact match first
        results = (
            await ModelPriceStats.find(
                ModelPriceStats.base_model == base_model,
                ModelPriceStats.timestamp >= cutoff,
            )
            .sort(("timestamp", SortDirection.DESCENDING))
            .to_list()
        )

        if not results:
            logger.debug(
                f"No exact match found, trying case-insensitive search for: {base_model}"
            )
            # Try case-insensitive search if exact match fails
            results = (
                await ModelPriceStats.find(
                    ModelPriceStats.base_model == RegEx(f"{base_model}", "i"),
                    ModelPriceStats.timestamp >= cutoff,
                )
                .sort(("timestamp", SortDirection.DESCENDING))
                .to_list()
            )

        if limit:
            results = results[:limit]

        logger.info(
            f"Retrieved {len(results)} price statistics for base model {base_model}"
        )
        return results

    except Exception as e:
        logger.error(f"Failed to get model price history: {str(e)}")
        return []


async def preview_field_mapping_reversion(
    mapping_ids: List[str],
) -> Dict[str, List[ReversionPreview]]:
    """Preview changes that would be made by reverting field mappings.

    Args:
        mapping_ids: List of mapping IDs to preview reversion for

    Returns:
        Dictionary mapping each mapping ID to its list of document changes
    """
    try:
        previews: Dict[str, List[ReversionPreview]] = {}

        for mapping_id in mapping_ids:
            # Get the mapping document
            mapping_doc = await FieldMapping.get(mapping_id)
            if not mapping_doc:
                logger.warning(f"Field mapping {mapping_id} not found")
                continue

            # Get MongoDB collections
            logs_collection = MappingLog.get_motor_collection()

            # Get all logs for this mapping grouped by document
            pipeline = [
                {"$match": {"mapping_id": mapping_doc.id}},
                {
                    "$group": {
                        "_id": "$document_id",
                        "changes": {
                            "$push": {
                                "mapped_field": "$mapped_field",
                                "original_field": "$original_field",
                                "original_value": "$original_value",
                            }
                        },
                    }
                },
            ]

            logs = await logs_collection.aggregate(pipeline).to_list()
            if not logs:
                continue

            mapping_previews = []
            for log in logs:
                original_fields = {}
                mapped_fields = set()

                for change in log["changes"]:
                    original_fields[change["original_field"]] = change["original_value"]
                    mapped_fields.add(change["mapped_field"])

                preview = ReversionPreview(
                    document_id=str(log["_id"]),
                    original_fields=original_fields,
                    mapped_fields=mapped_fields,
                )
                mapping_previews.append(preview)

            previews[mapping_id] = mapping_previews

        return previews

    except Exception as e:
        logger.error(f"Error creating reversion preview: {e.__class__}: {e}")
        return {}


async def revert_field_mappings(
    mapping_ids: List[str], dry_run: bool = False
) -> List[ReversionResult]:
    """Revert changes made by multiple field mapping operations.

    Args:
        mapping_ids: List of mapping IDs to revert
        dry_run: If True, only preview changes without applying them

    Returns:
        List of reversion results, one per mapping ID
    """
    if dry_run:
        previews = await preview_field_mapping_reversion(mapping_ids)
        return [
            ReversionResult(
                mapping_id=mapping_id, documents_reverted=len(preview_list), errors=[]
            )
            for mapping_id, preview_list in previews.items()
        ]

    results = []
    for mapping_id in mapping_ids:
        try:
            # Get the mapping document
            mapping_doc = await FieldMapping.get(mapping_id)
            if not mapping_doc:
                results.append(
                    ReversionResult(
                        mapping_id=mapping_id,
                        documents_reverted=0,
                        errors=["Mapping document not found"],
                    )
                )
                continue

            # Get MongoDB collections
            analyzed_collection = AnalyzedListingDocument.get_motor_collection()
            logs_collection = MappingLog.get_motor_collection()

            # Start a transaction session
            async with await analyzed_collection.database.client.start_session() as session:
                async with session.start_transaction():
                    try:
                        # Get all logs for this mapping grouped by document
                        pipeline = [
                            {"$match": {"mapping_id": mapping_doc.id}},
                            {
                                "$group": {
                                    "_id": "$document_id",
                                    "changes": {
                                        "$push": {
                                            "mapped_field": "$mapped_field",
                                            "original_field": "$original_field",
                                            "original_value": "$original_value",
                                        }
                                    },
                                }
                            },
                        ]

                        logs = await logs_collection.aggregate(
                            pipeline, session=session
                        ).to_list()

                        if not logs:
                            results.append(
                                ReversionResult(
                                    mapping_id=mapping_id,
                                    documents_reverted=0,
                                    errors=["No changes found to revert"],
                                )
                            )
                            continue

                        # Create update operations for each document
                        bulk_operations = []
                        skipped_docs = []

                        for log in logs:
                            try:
                                # Get current document
                                current_doc = await analyzed_collection.find_one(
                                    {"_id": log["_id"]}, session=session
                                )

                                if not current_doc or "info" not in current_doc:
                                    skipped_docs.append(str(log["_id"]))
                                    continue

                                # Start with current info
                                new_info = current_doc["info"].copy()

                                # Apply changes
                                for change in log["changes"]:
                                    if change["mapped_field"] in new_info:
                                        del new_info[change["mapped_field"]]
                                    new_info[change["original_field"]] = change[
                                        "original_value"
                                    ]

                                # Create update operation
                                bulk_operations.append(
                                    UpdateOne(
                                        {"_id": log["_id"]},
                                        {"$set": {"info": new_info}},
                                    )
                                )

                            except Exception as doc_error:
                                skipped_docs.append(f"{log['_id']}: {str(doc_error)}")

                        if bulk_operations:
                            try:
                                # Execute bulk update
                                result = await analyzed_collection.bulk_write(
                                    bulk_operations, session=session
                                )

                                # Delete the mapping logs
                                await logs_collection.delete_many(
                                    {"mapping_id": mapping_doc.id}, session=session
                                )

                                # Deactivate the mapping
                                await mapping_doc.set(
                                    {"is_active": False}, session=session
                                )

                                errors = []
                                if skipped_docs:
                                    errors.append(
                                        f"Skipped documents: {', '.join(skipped_docs)}"
                                    )

                                results.append(
                                    ReversionResult(
                                        mapping_id=mapping_id,
                                        documents_reverted=result.modified_count,
                                        errors=errors,
                                    )
                                )

                            except BulkWriteError as bwe:
                                results.append(
                                    ReversionResult(
                                        mapping_id=mapping_id,
                                        documents_reverted=0,
                                        errors=[
                                            f"Bulk write error: {str(bwe.details)}"
                                        ],
                                    )
                                )
                                raise bwe

                    except Exception as txn_error:
                        logger.error(
                            f"Transaction failed for mapping {mapping_id}: "
                            f"{str(txn_error)}"
                        )
                        results.append(
                            ReversionResult(
                                mapping_id=mapping_id,
                                documents_reverted=0,
                                errors=[f"Transaction error: {str(txn_error)}"],
                            )
                        )
                        raise txn_error

        except Exception as e:
            logger.error(f"Error reverting mapping {mapping_id}: {str(e)}")
            if mapping_id not in [r.mapping_id for r in results]:
                results.append(
                    ReversionResult(
                        mapping_id=mapping_id,
                        documents_reverted=0,
                        errors=[f"Unexpected error: {str(e)}"],
                    )
                )

    return results


async def get_current_model_price_stats(base_model: str) -> Optional[ModelPriceStats]:
    """Get the most recent price statistics for a specific model.

    Args:
        base_model: The base model to get stats for (case-insensitive)

    Returns:
        The most recent price statistics or None if no stats exist
    """
    try:
        logger.debug(f"Searching for price stats with base_model: {base_model}")
        result = (
            await ModelPriceStats.find(
                ModelPriceStats.base_model == base_model,
            )
            .sort(("timestamp", SortDirection.DESCENDING))
            .first_or_none()
        )

        if not result:
            logger.debug(
                f"No exact match found, trying case-insensitive search for: {base_model}"
            )
            # Try case-insensitive search if exact match fails
            result = (
                await ModelPriceStats.find(
                    ModelPriceStats.base_model == RegEx(f"{base_model}", "i"),
                )
                .sort(("timestamp", SortDirection.DESCENDING))
                .first_or_none()
            )

        return result
    except Exception as e:
        logger.error(f"Failed to get current model price stats: {str(e)}")
        return None
