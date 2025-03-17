
from typing import Dict, Any, List, Union, Annotated, TypedDict, Optional
import operator

from langchain_core.agents import AgentAction, AgentFinish

class AgentState(TypedDict):
    """Base state type for agent graphs"""
    input: str
    agent_outcome: Union[AgentAction, AgentFinish, None]
    intermediate_steps: Annotated[List[tuple[AgentAction, str]], operator.add]
    session_id: str