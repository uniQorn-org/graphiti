"""Base ingester class for all data sources."""

import json
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any

from tqdm import tqdm

from shared.constants import DEFAULT_MCP_URL
from shared.exceptions import IngestionError
from .mcp_client import MCPClient


class BaseIngester(ABC):
    """Abstract base class for all data ingesters."""

    def __init__(
        self,
        mcp_url: str | None = None,
        translate: bool = True,
        save_to_disk: bool = True,
        data_dir: Path | None = None,
    ):
        """
        Initialize base ingester.

        Args:
            mcp_url: URL of the MCP server (defaults to DEFAULT_MCP_URL from constants)
            translate: Whether to translate content to English
            save_to_disk: Whether to save raw data to disk
            data_dir: Directory to save data (default: /app/data/{source_type})
        """
        self.mcp_url = mcp_url or DEFAULT_MCP_URL
        self.translate = translate
        self.save_to_disk = save_to_disk
        self.data_dir = data_dir
        self.mcp_client = MCPClient(self.mcp_url)

        # Import translator if needed
        if translate:
            from translator import translate_with_limit

            self.translator = translate_with_limit
        else:
            self.translator = None

    @abstractmethod
    async def fetch_data(self) -> list[dict[str, Any]]:
        """
        Fetch data from the source.

        Returns:
            List of raw data items to be ingested

        Raises:
            Exception: If data fetching fails
        """
        pass

    @abstractmethod
    def build_episode(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Convert raw data into episode format.

        Args:
            data: Raw data item

        Returns:
            Episode dict with keys: name, episode_body, source,
            source_description, source_url
        """
        pass

    @abstractmethod
    def get_source_type(self) -> str:
        """
        Get the source type identifier.

        Returns:
            Source type string (e.g., "github", "slack", "zoom")
        """
        pass

    def translate_text(self, text: str, max_chars: int | None = None) -> str:
        """
        Translate text if translation is enabled.

        Args:
            text: Text to translate
            max_chars: Maximum characters to translate (defaults to MAX_CHARS_DEFAULT from constants)

        Returns:
            Translated text if translation enabled, original text otherwise
        """
        if not self.translate or not text:
            return text

        return self.translator(text, max_chars=max_chars)

    def save_data(
        self, data: list[dict[str, Any]], metadata: dict[str, Any] | None = None
    ) -> Path:
        """
        Save data to disk.

        Args:
            data: List of data items to save
            metadata: Additional metadata to include

        Returns:
            Path to saved file
        """
        if not self.save_to_disk:
            return None

        # Determine data directory
        if self.data_dir is None:
            self.data_dir = Path("/app/data") / self.get_source_type()

        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        lang_suffix = "en" if self.translate else "original"
        filename = f"{self.get_source_type()}_data_{timestamp}_{lang_suffix}.json"
        filepath = self.data_dir / filename

        # Prepare data to save
        save_data = {
            "source_type": self.get_source_type(),
            "fetched_at": datetime.now().isoformat(),
            "item_count": len(data),
            "translated": self.translate,
            "data": data,
        }

        if metadata:
            save_data["metadata"] = metadata

        # Write to file
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(save_data, f, ensure_ascii=False, indent=2)

        return filepath

    async def ingest(self, clear_existing: bool = False) -> dict[str, Any]:
        """
        Execute the full ingestion pipeline.

        Args:
            clear_existing: Whether to clear existing graph data first

        Returns:
            Summary of ingestion results
        """
        print(f"🚀 Starting {self.get_source_type()} ingestion...")

        if self.translate:
            print("✓ Translation enabled: Content will be translated to English")

        # Fetch data
        print("📡 Fetching data...")
        data = await self.fetch_data()
        print(f"✓ Found {len(data)} items")

        # Save to disk if requested
        if self.save_to_disk:
            filepath = self.save_data(data)
            print(f"✓ Saved raw data to: {filepath}")

        # Connect to MCP and ingest
        async with self.mcp_client.connect() as session:
            # Clear existing data if requested
            if clear_existing:
                print("🗑️  Clearing existing graph data...")
                await self.mcp_client.clear_graph(session)

            # Ingest items
            success_count = 0
            error_count = 0

            for item in tqdm(data, desc=f"Ingesting {self.get_source_type()} items"):
                try:
                    episode = self.build_episode(item)
                    await self.mcp_client.add_episode(session, **episode)
                    success_count += 1
                except Exception as e:
                    error_count += 1
                    print(f"✗ Error processing item: {e}")

        # Print summary
        print("\n" + "=" * 60)
        print("📊 Ingestion Summary")
        print("=" * 60)
        print(f"Source: {self.get_source_type()}")
        print(f"Total items: {len(data)}")
        print(f"✓ Success: {success_count}")
        print(f"✗ Errors: {error_count}")
        print("=" * 60)

        return {
            "source_type": self.get_source_type(),
            "total": len(data),
            "success": success_count,
            "errors": error_count,
        }
