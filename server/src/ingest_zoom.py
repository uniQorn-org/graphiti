#!/usr/bin/env python3
"""
Zoom VTT transcript ingestion script for Graphiti MCP with English translation.
"""

import argparse
import asyncio
import os
import re
from datetime import datetime
from pathlib import Path

import boto3
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

# Import translation utility
from translator import translate_with_limit


def parse_vtt(vtt_content: str) -> list[dict]:
    """Parse VTT file and extract messages."""
    lines = vtt_content.split('\n')
    messages = []
    current_message = {}
    
    for line in lines:
        line = line.strip()
        
        # Skip WEBVTT header and empty lines
        if line.startswith('WEBVTT') or not line:
            continue
        
        # Detect speaker line (format: timestamp --> timestamp\nSpeaker Name)
        if '-->' in line:
            if current_message.get('text'):
                messages.append(current_message)
            current_message = {'timestamp': line}
        elif current_message.get('timestamp') and not current_message.get('speaker'):
            # This is the speaker name
            current_message['speaker'] = line
        elif current_message.get('speaker'):
            # This is the message text
            if 'text' not in current_message:
                current_message['text'] = line
            else:
                current_message['text'] += ' ' + line
    
    if current_message.get('text'):
        messages.append(current_message)
    
    return messages


async def ingest_zoom_transcript(
    session: ClientSession,
    vtt_path: Path,
    minio_client,
    bucket_name: str,
    minio_endpoint: str,
    minio_public_endpoint: str | None = None,
    translate: bool = True,
) -> None:
    """Ingest Zoom transcript into Graphiti with English translation."""
    meeting_id = vtt_path.stem.replace('_transcript', '')
    
    print(f"Processing: {vtt_path.name}")
    
    if translate:
        print("Translation enabled: Content will be translated to English")
    
    # Read VTT file
    with open(vtt_path, 'r', encoding='utf-8') as f:
        vtt_content = f.read()
    
    # Parse VTT
    messages = parse_vtt(vtt_content)
    print(f"  Found {len(messages)} messages")
    
    # Upload to MinIO
    object_key = vtt_path.name
    minio_client.put_object(
        Bucket=bucket_name,
        Key=object_key,
        Body=vtt_content.encode('utf-8'),
        ContentType='text/vtt'
    )
    
    # Build source URL
    public_endpoint = minio_public_endpoint or minio_endpoint
    source_url = f"http://{public_endpoint}/{bucket_name}/{object_key}"
    
    # Build conversation from messages
    conversation_lines = []
    for msg in messages:
        speaker = msg.get('speaker', 'Unknown')
        text = msg.get('text', '')
        
        # Translate if enabled
        if translate and text:
            text = translate_with_limit(text, max_chars=500)
        
        conversation_lines.append(f"{speaker}: {text}")
    
    conversation = "\n".join(conversation_lines)
    
    # Create episode
    episode_name = f"zoom:meeting:{meeting_id}"
    source_description = (
        f"Zoom meeting transcript, "
        f"file: {vtt_path.name}, "
        f"messages: {len(messages)}"
    )
    
    arguments = {
        "name": episode_name,
        "episode_body": conversation,
        "source": "message",
        "source_description": source_description,
        "source_url": source_url,
    }
    
    await session.call_tool("add_memory", arguments=arguments)
    print(f"✓ Ingested {vtt_path.name} -> {source_url}")


async def main():
    parser = argparse.ArgumentParser(
        description="Ingest Zoom transcripts into Graphiti MCP with English translation"
    )
    parser.add_argument(
        "--data-dir",
        type=str,
        default="/app/data/zoom",
        help="Directory containing VTT files",
    )
    parser.add_argument(
        "--minio-endpoint",
        type=str,
        default="localhost:20734",
        help="MinIO endpoint",
    )
    parser.add_argument(
        "--minio-public-endpoint",
        type=str,
        default=None,
        help="MinIO public endpoint (for browser access)",
    )
    parser.add_argument(
        "--minio-access-key",
        type=str,
        default="minio",
        help="MinIO access key",
    )
    parser.add_argument(
        "--minio-secret-key",
        type=str,
        default="miniosecret",
        help="MinIO secret key",
    )
    parser.add_argument(
        "--bucket-name",
        type=str,
        default="zoom-transcripts",
        help="MinIO bucket name",
    )
    parser.add_argument(
        "--clear-existing",
        action="store_true",
        help="Clear existing graph data before ingestion",
    )
    parser.add_argument(
        "--no-translate",
        action="store_true",
        help="Do not translate content to English",
    )
    args = parser.parse_args()

    # Initialize MinIO client
    minio_client = boto3.client(
        's3',
        endpoint_url=f"http://{args.minio_endpoint}",
        aws_access_key_id=args.minio_access_key,
        aws_secret_access_key=args.minio_secret_key,
    )

    # Create bucket if not exists
    try:
        minio_client.head_bucket(Bucket=args.bucket_name)
    except:
        minio_client.create_bucket(Bucket=args.bucket_name)
        print(f"Created bucket: {args.bucket_name}")

    # Find VTT files
    data_dir = Path(args.data_dir)
    vtt_files = list(data_dir.glob("*.vtt"))
    
    if not vtt_files:
        print(f"No VTT files found in {data_dir}")
        return
    
    print(f"Found {len(vtt_files)} VTT file(s)")

    async with streamablehttp_client("http://localhost:8001/mcp/") as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()

            if args.clear_existing:
                print("Clearing existing graph data...")
                await session.call_tool("clear_graph", arguments={})

            for vtt_file in vtt_files:
                await ingest_zoom_transcript(
                    session,
                    vtt_file,
                    minio_client,
                    args.bucket_name,
                    args.minio_endpoint,
                    args.minio_public_endpoint,
                    translate=not args.no_translate,
                )


if __name__ == "__main__":
    asyncio.run(main())
