"""Shared state and clients for the intelligence API."""
from __future__ import annotations

import logging
import time

from dotenv import load_dotenv

from intelligence.agent_research import AgentResearcher

logger = logging.getLogger(__name__)

# Ensure environment variables from .env are available for downstream clients
load_dotenv()

# Simple in-memory storage for sessions
data_sessions: dict[str, dict] = {}

# Initialize the researcher once to be reused across requests for efficiency
try:
    start_time = time.perf_counter()
    researcher = AgentResearcher()
    logger.info(
        "AgentResearcher initialized successfully",
        extra={
            "operation": "agent_init",
            "duration_ms": round((time.perf_counter() - start_time) * 1000, 2),
        },
    )
except Exception as exc:  # noqa: BLE001 - propagate through logging with stack trace
    researcher = None
    logger.critical(
        "Failed to initialize AgentResearcher",
        exc_info=exc,
        extra={"operation": "agent_init"},
    )

# Maintain backwards compatibility with modules importing `sessions`
sessions = data_sessions
