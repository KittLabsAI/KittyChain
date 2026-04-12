"""KittyChain tools."""

import warnings

warnings.filterwarnings("ignore")

from .agent import AgentTool
from .base import Tool
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
from .token_info import TokenInfoTool
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
    WriteTool,
    EditTool,
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
    TokenInfoTool,
    TokenSecurityTool,
]


def create_tool_instances():
    return [tool_type() for tool_type in _TOOL_TYPES]


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
    "TokenInfoTool",
    "TokenSecurityTool",
    "TodoWriteTool",
    "WebBrowserTool",
    "WebSearchTool",
    "WriteTool",
    "WriteReportTool",
    "ALL_TOOLS",
    "create_tool_instances",
    "get_tool",
]
