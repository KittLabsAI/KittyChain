"""KittyChain tools."""

import warnings

warnings.filterwarnings("ignore")

from .agent import AgentTool
from .base import Tool
from ..config import Config
from .ask_user import AskUserTool
from .address_balance import AddressBalanceTool
from .address_identity import AddressIdentityTool
from .address_labels import AddressLabelsTool
from .address_mallicious import AddressMaliciousTool, AddressMalliciousTool
from .address_pattern import AddressPatternTool
from .address_transfers import AddressTransfersTool
from .bash import BashTool
from .brief import BriefTool
from .edit import EditTool
from .glob import GlobTool
from .grep import GrepTool
from .read import ReadTool
from .read_flow import ReadFlowTool
from .read_hits import ReadHitsTool
from .read_node import ReadNodeTool
from .read_rule import ReadRuleTool
from .strategy_simulation import StrategySimulationTool
from .social_search import SocialSearchTool
from .skill import SkillTool
from .token_holders import TokenHoldersTool
from .token_data import TokenDataTool
from .token_market_data import TokenMarketDataTool
from .token_search import TokenSearchTool
from .token_security import TokenSecurityTool
from .todo_write import TodoWriteTool
from .web_browser import WebBrowserTool
from .web_search import WebSearchTool
from .write import WriteTool
from .write_report import WriteReportTool

_TOOL_TYPES = [
    BashTool,
    ReadTool,
    SocialSearchTool,
    GlobTool,
    GrepTool,
    AgentTool,
    SkillTool,
    WebBrowserTool,
    WebSearchTool,
    WriteReportTool,
    TodoWriteTool,
    BriefTool,
    AskUserTool,
    AddressBalanceTool,
    AddressIdentityTool,
    AddressLabelsTool,
    AddressMaliciousTool,
    AddressPatternTool,
    AddressTransfersTool,
    TokenHoldersTool,
    TokenDataTool,
    TokenMarketDataTool,
    TokenSearchTool,
    TokenSecurityTool,
]

_CHAIN_ONLY_TOOL_NAMES = {
    "address_balance",
    "address_identity",
    "address_labels",
    "address_malicious",
    "address_pattern",
    "address_transfers",
    "token_data",
    "token_holders",
    "token_market_data",
    "token_search",
    "token_security",
    "write_report",
}

_COPILOT_ONLY_TOOL_TYPES = [
    ReadFlowTool,
    ReadNodeTool,
    ReadRuleTool,
    ReadHitsTool,
    StrategySimulationTool,
]

_CODE_TOOL_TYPES = [
    AgentTool,
    AskUserTool,
    BashTool,
    BriefTool,
    EditTool,
    GlobTool,
    GrepTool,
    ReadTool,
    SkillTool,
    TodoWriteTool,
    WebBrowserTool,
    WebSearchTool,
    WriteTool,
]


def create_tool_instances(tool_mode: str = "chain"):
    tool_types = list(_TOOL_TYPES)
    if tool_mode == "copilot":
        tool_types = [tool_type for tool_type in tool_types if tool_type.name not in _CHAIN_ONLY_TOOL_NAMES]
        tool_types.extend(_COPILOT_ONLY_TOOL_TYPES)
    elif tool_mode == "code":
        tool_types = list(_CODE_TOOL_TYPES)
    if not Config.from_file().apis.coingecko_api_key:
        tool_types = [tool_type for tool_type in tool_types if tool_type not in (TokenDataTool, TokenMarketDataTool)]
    return [tool_type() for tool_type in tool_types]


ALL_TOOLS = create_tool_instances()


def get_tool(name: str, tools=None):
    for tool in tools or ALL_TOOLS:
        if tool.name == name:
            return tool
    return None


__all__ = [
    "Tool",
    "AgentTool",
    "AskUserTool",
    "AddressBalanceTool",
    "AddressIdentityTool",
    "AddressLabelsTool",
    "AddressMaliciousTool",
    "AddressMalliciousTool",
    "AddressPatternTool",
    "AddressTransfersTool",
    "BashTool",
    "BriefTool",
    "EditTool",
    "GlobTool",
    "GrepTool",
    "ReadTool",
    "ReadFlowTool",
    "ReadHitsTool",
    "ReadNodeTool",
    "ReadRuleTool",
    "StrategySimulationTool",
    "SocialSearchTool",
    "SkillTool",
    "TokenHoldersTool",
    "TokenMarketDataTool",
    "TokenSearchTool",
    "TokenSecurityTool",
    "TodoWriteTool",
    "TokenDataTool",
    "WebBrowserTool",
    "WebSearchTool",
    "WriteTool",
    "WriteReportTool",
    "ALL_TOOLS",
    "create_tool_instances",
    "get_tool",
]
