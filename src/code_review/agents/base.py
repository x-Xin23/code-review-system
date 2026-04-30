import json
import asyncio
from typing import Optional
from anthropic import AsyncAnthropic, APIError, APITimeoutError, RateLimitError

from ..config import settings
from ..models.findings import Finding
from ..models.context import ReviewContext, ReviewPlan


class AgentError(Exception):
    pass


class BaseAgent:
    name: str = "base"
    system_prompt: str = ""

    def __init__(self):
        self.client = AsyncAnthropic(api_key=settings.anthropic_api_key)

    async def analyze(self, context: ReviewContext, plan: ReviewPlan) -> list[Finding]:
        raise NotImplementedError

    async def _call_claude(
        self,
        user_message: str,
        system_prompt: str | None = None,
        thinking_budget: int | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """Call Claude API with retry logic, thinking mode, and error handling."""
        if thinking_budget is None:
            thinking_budget = settings.anthropic_thinking_budget
        if max_tokens is None:
            max_tokens = settings.anthropic_max_tokens

        prompt = system_prompt or self.system_prompt
        thinking = None
        if thinking_budget > 0:
            thinking = {"type": "enabled", "budget_tokens": thinking_budget}

        last_error = None
        for attempt in range(settings.max_retries):
            try:
                response = await self.client.messages.create(
                    model=settings.anthropic_model,
                    max_tokens=max_tokens,
                    system=prompt,
                    thinking=thinking,
                    messages=[{"role": "user", "content": user_message}],
                )
                # Extract text from response
                for block in response.content:
                    if block.type == "text":
                        return block.text
                return ""

            except (APITimeoutError, RateLimitError) as e:
                last_error = e
                wait = 2 ** attempt
                await asyncio.sleep(wait)
            except APIError as e:
                if e.status_code and e.status_code >= 500:
                    last_error = e
                    wait = 2 ** attempt
                    await asyncio.sleep(wait)
                else:
                    raise AgentError(f"API error: {e}") from e

        raise AgentError(f"Agent {self.name} failed after {settings.max_retries} retries: {last_error}")

    def _parse_json_response(self, text: str) -> dict:
        """Extract and parse JSON from Claude response, with repair attempts."""
        text = text.strip()

        # Try to extract JSON from markdown code blocks
        if "```json" in text:
            start = text.index("```json") + 7
            end = text.index("```", start)
            text = text[start:end].strip()
        elif "```" in text:
            start = text.index("```") + 3
            end = text.index("```", start)
            text = text[start:end].strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Attempt repairs
        try:
            # Try repairing truncated JSON by closing brackets
            repaired = self._repair_truncated_json(text)
            return json.loads(repaired)
        except json.JSONDecodeError:
            pass

        # Return empty dict on failure
        return {}

    def _repair_truncated_json(self, text: str) -> str:
        """Repair truncated JSON by closing unclosed brackets and strings."""
        open_braces = text.count("{") - text.count("}")
        open_brackets = text.count("[") - text.count("]")

        # Close truncated string if last non-space char is within quotes
        if text.rstrip().endswith('"') or text.rstrip().endswith('\\"'):
            pass  # Don't append if ending with a quote that might be truncated

        text += "]" * open_brackets
        text += "}" * open_braces
        return text

    def _validate_finding(self, finding: Finding) -> bool:
        """Validate a single finding has required fields."""
        if not finding.title or not finding.description:
            return False
        if not finding.file_path:
            return False
        if finding.confidence < 0.0 or finding.confidence > 1.0:
            return False
        return True

    def _load_file_contents(self, context: ReviewContext, file_assignments: list[str]) -> str:
        """Load file contents assigned to this agent."""
        parts = []
        for path in file_assignments:
            for f in context.files:
                if f.path == path:
                    parts.append(f"--- FILE: {f.path} ({f.language}) ---\n{f.content}")
                    break
            else:
                # Check diffs
                for d in context.diffs:
                    if d.new_path == path:
                        diff_content = "\n".join(h.content for h in d.hunks)
                        parts.append(f"--- DIFF: {d.new_path} ({d.language}) ---\n{diff_content}")
        return "\n\n".join(parts)
