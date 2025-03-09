"""Embeddings management service."""

import logging
from typing import Any, Dict, List, Optional, Union

from llama_index.core import Document, VectorStoreIndex
from llama_index.core.indices.vector_store import VectorIndexRetriever
from motor.motor_asyncio import AsyncIOMotorDatabase

from ..ai.providers.composite import CompositeProvider
from ..schemas.analysis import AnalyzedListingDocument
from ..schemas.listings import ListingDocument

logger = logging.getLogger(__name__)


class EmbeddingsService:
    """Service for managing embeddings and vector search."""

    def __init__(self, provider: Optional[CompositeProvider] = None):
        """Initialize the embeddings service.

        Args:
            provider: Optional AI provider for embeddings generation
        """
        self.provider = provider or CompositeProvider()
        self.logger = logging.getLogger(__name__)

    async def generate_embeddings(
        self, texts: Union[str, List[str]]
    ) -> List[List[float]]:
        """Generate embeddings for text.

        Args:
            texts: Text or list of texts to generate embeddings for

        Returns:
            List of embedding vectors
        """
        self.logger.debug(
            f"Generating embeddings for {len(texts) if isinstance(texts, list) else 1} texts"
        )
        return await self.provider.get_embeddings(texts)

    async def create_index(
        self,
        documents: List[Dict[str, Any]],
        text_key: str = "text",
        metadata_keys: Optional[List[str]] = None,
    ) -> VectorStoreIndex:
        """Create a vector index from documents.

        Args:
            documents: List of documents to index
            text_key: Key containing the text to embed
            metadata_keys: Optional keys to include as metadata

        Returns:
            VectorStoreIndex: The created index
        """
        self.logger.debug(f"Creating index from {len(documents)} documents")

        # Convert documents to LlamaIndex format
        llama_docs = []
        for doc in documents:
            metadata = {}
            if metadata_keys:
                metadata = {k: doc.get(k) for k in metadata_keys if k in doc}
            llama_docs.append(Document(text=doc[text_key], metadata=metadata))

        # Create index using provider's embedding function
        index = VectorStoreIndex.from_documents(
            documents=llama_docs, embed_model=self.provider.as_llamaindex_embedding()
        )

        self.logger.debug("Index created successfully")
        return index

    async def find_similar(
        self,
        query_embedding: List[float],
        index: VectorStoreIndex,
        limit: int = 10,
        score_threshold: Optional[float] = None,
    ) -> List[Document]:
        """Find similar documents using vector similarity.

        Args:
            query_embedding: Query embedding vector
            index: Vector index to search
            limit: Maximum number of results
            score_threshold: Optional similarity score threshold

        Returns:
            List of similar documents
        """
        self.logger.debug(f"Searching for {limit} similar documents")

        retriever = VectorIndexRetriever(
            index=index, similarity_top_k=limit, similarity_cutoff=score_threshold
        )

        results = await retriever.aretrieve(query_embedding)
        self.logger.debug(f"Found {len(results)} similar documents")
        return results

    async def find_similar_listings(
        self,
        listing: ListingDocument,
        db: AsyncIOMotorDatabase,
        limit: int = 6,
        offset: int = 0,
    ) -> List[ListingDocument]:
        """Find similar listings using vector similarity.

        Args:
            listing: The listing to find similar ones for
            db: Database instance
            limit: Maximum number of results
            offset: Number of results to skip

        Returns:
            List of similar listings
        """
        self.logger.debug(f"Finding similar listings for {listing.original_id}")

        # Get analysis with embeddings
        analysis = await AnalyzedListingDocument.find_one(
            {"original_listing_id": listing.original_id}
        )
        if not analysis or not analysis.embeddings:
            self.logger.warning(
                f"No embeddings found for listing {listing.original_id}"
            )
            return []

        # Get all analyzed listings of the same type
        analyzed_listings = await AnalyzedListingDocument.find(
            {"type": analysis.type, "original_listing_id": {"$ne": listing.original_id}}
        ).to_list()

        if not analyzed_listings:
            self.logger.debug(f"No other listings found of type {analysis.type}")
            return []

        # Create index from analyzed listings
        index = await self.create_index(
            documents=[doc.model_dump() for doc in analyzed_listings],
            text_key="info",
            metadata_keys=["original_listing_id", "type", "brand", "base_model"],
        )

        # Find similar listings
        similar = await self.find_similar(
            query_embedding=analysis.embeddings, index=index, limit=limit + offset
        )

        # Get original listings
        if not similar:
            return []

        original_ids = [doc.metadata["original_listing_id"] for doc in similar[offset:]]
        similar_listings = await ListingDocument.find(
            {"original_id": {"$in": original_ids}}
        ).to_list()

        self.logger.debug(f"Found {len(similar_listings)} similar listings")
        return similar_listings
