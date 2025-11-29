"""Custom LLM client for GPT-5 and other reasoning models.

This client handles the differences in API parameters for reasoning models like
gpt-5, o1, o3, and o4 series, which use max_completion_tokens instead of max_tokens.
"""

import logging
import os
from typing import Any

import httpx
from graphiti_core.llm_client import LLMClient
from graphiti_core.llm_client.config import LLMConfig
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)


class GPT5Client(LLMClient):
    """LLM client for GPT-5 and other reasoning models."""

    def __init__(
        self,
        config: LLMConfig,
        max_completion_tokens: int | None = None,
    ):
        """Initialize the GPT5 client.

        Args:
            config: LLM configuration
            max_completion_tokens: Maximum number of completion tokens (for reasoning models)
        """
        super().__init__(config)
        self.max_completion_tokens = max_completion_tokens

        # Create httpx client with proxy explicitly disabled
        # The base_url already points to the corporate reverse proxy
        # (https://openai-proxy.linecorp.com/v1), so we don't need httpx's proxy feature
        # Timeout is configurable via OPENAI_TIMEOUT env var (default: 300s for cc-throttle queue)
        timeout_seconds = float(os.getenv("OPENAI_TIMEOUT", "300"))
        http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout_seconds),
            # Don't set proxies parameter - httpx will not use proxies if HTTP_PROXY env vars are not set
        )

        # Create AsyncOpenAI client with custom httpx client
        self.client = AsyncOpenAI(
            api_key=config.api_key,
            base_url=config.base_url,
            http_client=http_client,
        )

    async def _generate_response(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        response_model: Any = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> Any:
        """Generate a response using the OpenAI API.

        Args:
            messages: List of message dictionaries
            model: Model to use (defaults to config.model)
            response_model: Pydantic model for structured output (if any)
            max_tokens: Maximum tokens (overrides max_completion_tokens if provided)
            temperature: Temperature for sampling (not supported for reasoning models)

        Returns:
            Model response
        """
        model = model or self.config.model

        # Determine if this is a reasoning model
        is_reasoning_model = (
            model.startswith("gpt-5")
            or model.startswith("o1")
            or model.startswith("o3")
            or model.startswith("o4")
        )

        # Use max_completion_tokens for reasoning models, max_tokens for standard models
        tokens_param = max_tokens or self.max_completion_tokens

        # Build request parameters
        request_params: dict[str, Any] = {
            "model": model,
            "messages": messages,
        }

        # Add appropriate token parameter based on model type
        if tokens_param:
            if is_reasoning_model:
                request_params["max_completion_tokens"] = tokens_param
            else:
                # For local models like gpt-oss-20b, use -1 for unlimited tokens
                # to prevent JSON truncation in structured output
                if "localhost" in str(self.config.base_url) or "host.docker.internal" in str(self.config.base_url):
                    request_params["max_tokens"] = -1
                else:
                    request_params["max_tokens"] = tokens_param

        # Temperature is not supported for reasoning models like gpt-5, o1, o3, o4
        # Standard models like gpt-4o support temperature parameter
        if temperature is not None and not is_reasoning_model:
            request_params["temperature"] = temperature

        logger.debug(f"Calling OpenAI API with model: {model}")
        logger.debug(f"Request parameters: {request_params}")

        try:
            # If response_model is provided, use structured output
            if response_model:
                # Use regular chat completion with response_format for proxy compatibility
                # Avoid beta.chat.completions.parse() which is not supported by corporate proxy
                import json
                from pydantic import ValidationError

                # Add response_format to request params for structured output
                # Ensure schema has additionalProperties: false for corporate proxy compatibility
                schema = response_model.model_json_schema()

                # Recursively add additionalProperties: false and ensure all properties are required
                # Corporate proxy requires stricter schema validation
                def fix_schema_for_corporate_proxy(obj):
                    if isinstance(obj, dict):
                        if obj.get("type") == "object":
                            # Add additionalProperties: false
                            if "additionalProperties" not in obj:
                                obj["additionalProperties"] = False
                            # Ensure all properties are in required array
                            if "properties" in obj:
                                all_props = list(obj["properties"].keys())
                                obj["required"] = all_props
                        for value in obj.values():
                            fix_schema_for_corporate_proxy(value)
                    elif isinstance(obj, list):
                        for item in obj:
                            fix_schema_for_corporate_proxy(item)

                fix_schema_for_corporate_proxy(schema)

                request_params["response_format"] = {
                    "type": "json_schema",
                    "json_schema": {
                        "name": response_model.__name__,
                        "schema": schema,
                        "strict": True,
                    }
                }

                response = await self.client.chat.completions.create(**request_params)
                content = response.choices[0].message.content

                # Parse the JSON response into the Pydantic model
                try:
                    parsed_data = json.loads(content)
                    validated_model = response_model.model_validate(parsed_data)
                    # Return the parsed data dictionary, not the Pydantic model instance
                    # This matches the behavior expected by graphiti-core
                    return parsed_data
                except (json.JSONDecodeError, ValidationError) as parse_error:
                    logger.error(f"Failed to parse structured output: {parse_error}")
                    logger.error(f"Raw content: {content}")
                    raise
            else:
                # Regular chat completion
                response = await self.client.chat.completions.create(**request_params)
                return response.choices[0].message.content

        except Exception as e:
            logger.error(f"Error calling OpenAI API: {e}")
            logger.error(f"Exception type: {type(e).__name__}")
            logger.error(f"Full exception details: {repr(e)}")
            import traceback
            logger.error(f"Traceback:\n{traceback.format_exc()}")
            raise

    async def generate_response(
        self,
        messages: list[dict[str, str]],
        response_model: Any = None,
        **kwargs,  # Accept additional keyword arguments
    ) -> Any:
        """Generate a response using the main model.

        Args:
            messages: List of message dictionaries
            response_model: Pydantic model for structured output (if any)
            **kwargs: Additional keyword arguments (e.g., group_id) - ignored for GPT-5

        Returns:
            Model response
        """
        return await self._generate_response(
            messages=messages,
            model=self.config.model,
            response_model=response_model,
        )

    async def generate_response_small(
        self,
        messages: list[dict[str, str]],
        response_model: Any = None,
        **kwargs,  # Accept additional keyword arguments
    ) -> Any:
        """Generate a response using the small model.

        Args:
            messages: List of message dictionaries
            response_model: Pydantic model for structured output (if any)
            **kwargs: Additional keyword arguments (e.g., group_id) - ignored for GPT-5

        Returns:
            Model response
        """
        small_model = self.config.small_model or self.config.model
        return await self._generate_response(
            messages=messages,
            model=small_model,
            response_model=response_model,
        )
