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
from .social_search import SocialSearchTool
from .skill import SkillTool
from .token_holders import TokenHoldersTool
from .token_data import TokenDetailTool, TokenDataTool
from .token_market_data import TokenPriceTool, TokenMarketDataTool
from .token_search import TokenSearchTool
from .token_security import TokenSecurityTool
from .token_advanced import TokenAdvancedTool
from .transaction_detail import TransactionDetailTool
from .todo_write import TodoWriteTool
from .web_fetch import WebFetchTool
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
    WebFetchTool,
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
    TokenDetailTool,
    TokenPriceTool,
    TokenSearchTool,
    TokenSecurityTool,
    TokenAdvancedTool,
    TransactionDetailTool,
]

_CHAIN_ONLY_TOOL_NAMES = {
    "address_balance",
    "address_identity",
    "address_labels",
    "address_malicious",
    "address_pattern",
    "address_transfers",
    "token_detail",
    "token_holders",
    "token_price",
    "token_search",
    "token_security",
    "token_advanced",
    "transaction_detail",
    "write_report",
}

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
    WebFetchTool,
    WebSearchTool,
    WriteTool,
]


def create_tool_instances(tool_mode: str = "chain"):
    tool_types = list(_TOOL_TYPES)
    if tool_mode == "code":
        tool_types = list(_CODE_TOOL_TYPES)
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
    "SocialSearchTool",
    "SkillTool",
    "TokenHoldersTool",
    "TokenDetailTool",
    "TokenDataTool",
    "TokenPriceTool",
    "TokenMarketDataTool",
    "TokenSearchTool",
    "TokenSecurityTool",
    "TokenAdvancedTool",
    "TransactionDetailTool",
    "TodoWriteTool",
    "WebFetchTool",
    "WebSearchTool",
    "WriteTool",
    "WriteReportTool",
    "ALL_TOOLS",
    "create_tool_instances",
    "get_tool",
]
