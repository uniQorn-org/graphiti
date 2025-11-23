#!/usr/bin/env python3
"""
Translate Japanese content in Slack CSV data to English.

This script reads threads_ordered.csv, translates Japanese messages to English
using OpenAI API, and saves to threads_ordered_en.csv (preserving the original).
"""

import asyncio
import os
import re
from pathlib import Path
from typing import List, Optional

import pandas as pd
from dotenv import load_dotenv
from openai import AsyncOpenAI
from tqdm import tqdm


class SlackDataTranslator:
    """Translator for Slack CSV data."""

    def __init__(
        self,
        csv_path: str,
        output_path: Optional[str] = None,
        api_key: Optional[str] = None,
        model: str = "gpt-4o-mini",
        batch_size: int = 10,
        max_concurrent: int = 10,
    ):
        """
        Initialize the translator.

        Args:
            csv_path: Path to the source CSV file
            output_path: Path to the output CSV file (defaults to *_en.csv)
            api_key: OpenAI API key (defaults to env variable)
            model: OpenAI model to use
            batch_size: Number of messages to translate in one API call
            max_concurrent: Maximum concurrent API calls
        """
        self.csv_path = Path(csv_path)
        self.output_path = (
            Path(output_path)
            if output_path
            else self.csv_path.with_stem(f"{self.csv_path.stem}_en")
        )
        self.model = model
        self.batch_size = batch_size
        self.semaphore = asyncio.Semaphore(max_concurrent)

        # Load environment and initialize OpenAI client
        load_dotenv(self.csv_path.parent.parent / ".env")
        api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not found in environment")
        self.client = AsyncOpenAI(api_key=api_key)

    def is_japanese(self, text: str) -> bool:
        """
        Check if text contains Japanese characters.

        Args:
            text: Text to check

        Returns:
            True if text contains Japanese characters
        """
        if not text or pd.isna(text):
            return False

        # Check for Hiragana, Katakana, or Kanji
        japanese_pattern = re.compile(r"[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]")
        return bool(japanese_pattern.search(str(text)))

    async def translate_batch(self, messages: List[str]) -> List[str]:
        """
        Translate a batch of messages using OpenAI API.

        Args:
            messages: List of messages to translate

        Returns:
            List of translated messages
        """
        async with self.semaphore:
            try:
                # Create translation prompt
                numbered_messages = "\n\n".join(
                    f"[{i + 1}]\n{msg}" for i, msg in enumerate(messages)
                )

                prompt = f"""Translate the following Japanese Slack messages to English.
Preserve:
- URLs, code blocks, and technical terms
- User mentions (e.g., @username)
- Bullet points and formatting
- Numbers and timestamps

Return ONLY the translated messages in the same numbered format [1], [2], etc.
Do not add explanations or additional text.

Messages to translate:

{numbered_messages}"""

                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a professional translator specializing in technical content.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.3,
                )

                result = response.choices[0].message.content
                if not result:
                    return messages

                # Parse numbered responses
                translated = []
                pattern = r"\[(\d+)\]\s*\n(.*?)(?=\n\[\d+\]|\Z)"
                matches = re.findall(pattern, result, re.DOTALL)

                for i, msg in enumerate(messages):
                    if i < len(matches):
                        translated.append(matches[i][1].strip())
                    else:
                        translated.append(msg)

                return translated

            except Exception as e:
                print(f"\nError translating batch: {e}")
                return messages

    async def translate_messages(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Translate all Japanese messages in the dataframe.

        Args:
            df: DataFrame with 'content' column

        Returns:
            DataFrame with translated content
        """
        # Identify messages that need translation
        needs_translation = []
        translation_indices = []

        for idx, row in df.iterrows():
            content = row["content"]
            if self.is_japanese(content):
                needs_translation.append(str(content))
                translation_indices.append(idx)

        if not needs_translation:
            print("No messages need translation.")
            return df

        print(f"\nFound {len(needs_translation)} messages to translate")

        # Translate in batches
        translated_messages = []
        tasks = []

        for i in range(0, len(needs_translation), self.batch_size):
            batch = needs_translation[i : i + self.batch_size]
            tasks.append(self.translate_batch(batch))

        # Execute all translation tasks concurrently
        print(f"Translating {len(tasks)} batches...")
        results = await asyncio.gather(*tasks)

        # Flatten results (順序が保証される)
        for result in results:
            translated_messages.extend(result)

        # Update dataframe with translations
        for idx, translated in zip(translation_indices, translated_messages):
            df.at[idx, "content"] = translated

        return df

    async def translate_csv(self):
        """Main translation process."""
        print(f"Loading CSV from: {self.csv_path}")

        # Load CSV
        df = pd.read_csv(self.csv_path)
        print(f"Loaded {len(df)} rows")

        # Translate
        df_translated = await self.translate_messages(df)

        # Save translated CSV to output file
        df_translated.to_csv(self.output_path, index=False)
        print(f"\nTranslation complete!")
        print(f"Original file preserved: {self.csv_path}")
        print(f"Translated file saved: {self.output_path}")


async def main():
    """Main entry point."""
    # Get CSV path
    script_dir = Path(__file__).parent
    csv_path = script_dir.parent / "slack_data" / "threads_ordered.csv"

    if not csv_path.exists():
        print(f"Error: CSV file not found at {csv_path}")
        return

    # Initialize and run translator
    translator = SlackDataTranslator(
        csv_path=str(csv_path),
        model="gpt-4o-mini",
        batch_size=10,
        max_concurrent=10,
    )

    await translator.translate_csv()


if __name__ == "__main__":
    asyncio.run(main())
