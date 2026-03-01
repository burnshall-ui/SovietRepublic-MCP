"""Soviet Republic MCP Server

Run via: python main.py
"""
import asyncio
import logging

logging.basicConfig(level=logging.WARNING)

from mcp_server import run_mcp

asyncio.run(run_mcp())
