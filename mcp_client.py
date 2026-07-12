import os
import sys
import asyncio
from pathlib import Path

from dotenv import load_dotenv
from langchain_mcp_adapters.client import MultiServerMCPClient

load_dotenv(override=True)

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
AVIATION_STACK_API_KEY = os.getenv("AVIATIONSTACK_API_KEY")
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")

PROJECT_ROOT = Path(__file__).resolve().parent
AVIATIONSTACK_ROOT = PROJECT_ROOT / "aviationstack-mcp-main"
WEATHER_SERVER_SCRIPT = PROJECT_ROOT / "custom_weather_mcp_server.py"


def _venv_python(venv_dir: Path) -> Path:
    if sys.platform == "win32":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def _resolve_aviationstack_python() -> str:
    venv_python = _venv_python(AVIATIONSTACK_ROOT / ".venv")
    if venv_python.exists():
        return str(venv_python)
    return sys.executable


def _build_mcp_client() -> MultiServerMCPClient:
    aviation_python = _resolve_aviationstack_python()

    return MultiServerMCPClient(
        {
            "tavily": {
                "transport": "streamable_http",
                "url": f"https://mcp.tavily.com/mcp/?tavilyApiKey={TAVILY_API_KEY}",
            },
            "aviationstack": {
                "transport": "stdio",
                "command": aviation_python,
                "args": ["-m", "aviationstack_mcp", "mcp", "run"],
                "cwd": str(AVIATIONSTACK_ROOT),
                "env": {
                    "AVIATION_STACK_API_KEY": AVIATION_STACK_API_KEY or "",
                },
            },
            "weather": {
                "transport": "stdio",
                "command": sys.executable,
                "args": [str(WEATHER_SERVER_SCRIPT)],
                "env": {
                    "OPENWEATHER_API_KEY": OPENWEATHER_API_KEY or "",
                },
            },
        }
    )


client = _build_mcp_client()

search_tool = None
aviation_tools = {}


async def initialize_mcp():
    global search_tool
    global aviation_tools

    if search_tool is not None and aviation_tools:
        return

    tools = await client.get_tools()

    print("\nAvailable MCP Tools:\n")

    for tool in tools:
        print(tool.name)

    search_tool = next(
        tool for tool in tools if tool.name == "tavily_search"
    )

    aviation_tools = {
        tool.name: tool
        for tool in tools
        if tool.name
        not in {"tavily_search", "get_current_weather", "get_forecast"}
    }


async def tavily_mcp_search(query: str):
    await initialize_mcp()
    result = await search_tool.ainvoke({"query": query})
    return result


async def aviation_mcp_call(tool_name: str, tool_args: dict = None):
    await initialize_mcp()

    tool = aviation_tools.get(tool_name)
    if not tool:
        tools = await client.get_tools()
        tool = next(t for t in tools if t.name == tool_name)

    result = await tool.ainvoke(tool_args or {})
    return result


weather_tool = None
forecast_tool = None


async def initialize_weather_tools():
    global weather_tool, forecast_tool

    if weather_tool is not None and forecast_tool is not None:
        return

    tools = await client.get_tools()

    weather_tool = next(t for t in tools if t.name == "get_current_weather")
    forecast_tool = next(t for t in tools if t.name == "get_forecast")


async def weather_mcp_search(city: str):
    await initialize_weather_tools()
    return await weather_tool.ainvoke({"city": city})


async def forecast_mcp_search(city: str):
    await initialize_weather_tools()
    return await forecast_tool.ainvoke({"city": city})


from langchain_groq import ChatGroq

llm = ChatGroq(model="llama-3.3-70b-versatile")


def extract_destination(query: str):
    prompt = f"""
    Extract only the destination city or country.

    Query:
    {query}

    Return only destination name.
    """

    response = llm.invoke(prompt)
    return response.content.strip()


if __name__ == "__main__":
    async def _demo():
        await initialize_mcp()
        print("MCP client initialized successfully.")

    asyncio.run(_demo())
