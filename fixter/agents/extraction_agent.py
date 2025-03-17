from typing import Dict, Any, List, Optional, Union, Annotated
import operator
import re
import json

from pydantic import BaseModel, Field
from langchain_core.agents import AgentAction, AgentFinish
from langgraph.graph import StateGraph, END
from langchain_core.exceptions import OutputParserException
from langchain.agents import create_react_agent
from langchain import hub

from fixter.agents.agent_base import BaseAgent

class ExtractionDetails(BaseModel):
    """Structured model for extraction parameters"""
    type: str = Field(
        description="Type of extraction (local or git)",
        examples=["local", "git"]
    )
    path: str = Field(
        description="Path or URL to extract from",
        examples=["/home/user/projects", "https://github.com/example/repo"]
    )
    extensions: Optional[List[str]] = Field(
        default=None, 
        description="File extensions to filter",
        examples=[".py", ".js", ".md"]
    )
    clipboard_only: bool = Field(default=True)
    clone: bool = Field(default=False)

class ExtractionState(Dict):
    """State used by the extraction agent's graph"""
    input: str
    agent_outcome: Union[AgentAction, AgentFinish, None]
    intermediate_steps: Annotated[List[tuple[AgentAction, str]], operator.add]
    session_id: str
    step_counter: int = 0

class ExtractionAgent(BaseAgent):
    def __init__(self, llm, tools, session_manager=None):
        """Initialize the extraction agent"""
        super().__init__(llm, tools, session_manager)
        
        self.extraction_tools = [
            tool for tool in tools 
            if tool.name in ["extract_content_local", "extract_git_content"]
        ]
        
        self.agent_runnable = create_react_agent(
            tools=self.extraction_tools,
            llm=llm,
            prompt=hub.pull("hwchase17/react")
        )

    def process(self, query: str, session_id: str = None) -> str:
        """
        Process an extraction query
        
        Args:
            query: The user's extraction query
            session_id: Optional session identifier
        
        Returns:
            Extraction result as a string
        """
        graph = StateGraph(ExtractionState)
        graph.add_node("reason", self._reason_node)
        graph.add_node("act", self._act_node)
        graph.add_node("finish", self._finish_node)
        
        graph.set_entry_point("reason")
        graph.add_conditional_edges("reason", self._should_continue)
        graph.add_edge("act", "reason")
        graph.add_edge("finish", END)
        
        app = graph.compile()
        
        result = app.invoke({
            "input": query,
            "agent_outcome": None,
            "intermediate_steps": [],
            "session_id": session_id or "",
            "step_counter": 0
        })
        
        res =result["agent_outcome"].return_values["output"]
        return res

    def _reason_node(self, state: ExtractionState) -> Dict[str, Any]:
        """Reasoning node for the extraction graph"""
        try:
            agent_outcome = self.agent_runnable.invoke({
                "input": state["input"],
                "intermediate_steps": state.get("intermediate_steps", [])
            })
            return {"agent_outcome": agent_outcome}
        except OutputParserException as e:
            error_text = str(e)
            output_text = error_text.split("Could not parse LLM output:")[-1].strip()
            agent_outcome = AgentFinish(
                return_values={"output": output_text}, 
                log=output_text
            )
            return {"agent_outcome": agent_outcome}

    def _act_node(self, state: ExtractionState) -> Dict[str, Any]:
        """Action node for the extraction graph"""
        current_steps = state.get("step_counter", 0)
        state["step_counter"] = current_steps + 1
        
        agent_action = state["agent_outcome"]
        
        if agent_action is None:
            return {"intermediate_steps": []}
        
        tool_name = agent_action.tool
        tool_input = agent_action.tool_input
        
        tool_map = {tool.name: tool for tool in self.extraction_tools}
        if tool_name not in tool_map:
            error_msg = f"Tool '{tool_name}' not found in extraction tools"
            return {
                "intermediate_steps": [(agent_action, error_msg)], 
                "step_counter": state["step_counter"]
            }
        
        filtered_input = self._parse_tool_input(tool_name, tool_input)
        
        tool_result = tool_map[tool_name].invoke(filtered_input)
        
        return {
            "intermediate_steps": [(agent_action, str(tool_result))],
            "step_counter": state["step_counter"]
        }

    def _finish_node(self, state: ExtractionState) -> Dict[str, Any]:
        """Finish node for the extraction graph"""
        return state

    def _should_continue(self, state: ExtractionState) -> str:
        """Determine whether to continue or finish"""
        current_steps = state.get("step_counter", 0)
        
        if current_steps >= 5:
            state["agent_outcome"] = AgentFinish(
                return_values={
                    "output": "Extraction process reached maximum steps. Please refine your query."
                },
                log="Max steps reached"
            )
            return "finish"
        
        if isinstance(state["agent_outcome"], AgentFinish):
            return "finish"
        
        return "act"

    def _parse_tool_input(self, tool_name: str, tool_input: Any) -> Dict[str, Any]:
        """
        Parse and normalize tool input
        
        Args:
            tool_name (str): Name of the tool being invoked
            tool_input (Any): Input to be parsed
        
        Returns:
            Dict[str, Any]: Normalized and parsed input
        """
        if isinstance(tool_input, dict):
            return tool_input
        
        if isinstance(tool_input, str):
            try:
                parsed_input = json.loads(tool_input)
            except json.JSONDecodeError:
                if tool_name == "extract_content_local":
                    parsed_input = self._parse_local_input(tool_input)
                elif tool_name == "extract_git_content":
                    parsed_input = self._parse_git_input(tool_input)
                else:
                    parsed_input = {"input": tool_input}
        
        if tool_name == "extract_content_local":
            parsed_input.setdefault('extensions', ['.py'])
            parsed_input.setdefault('clipboard_only', False)
        elif tool_name == "extract_git_content":
            parsed_input.setdefault('extensions', [])
            parsed_input.setdefault('clone', False)
            parsed_input.setdefault('clipboard_only', True)
        
        return parsed_input

    def _parse_local_input(self, input_str: str) -> Dict[str, Any]:
        """Parse local extraction input"""
        directory_match = re.search(r'/[\w/\.-]+', input_str)
        directory = directory_match.group(0) if directory_match else input_str.strip()
        
        ext_match = re.findall(r'\.[a-zA-Z]+', input_str)
        extensions = ext_match if ext_match else ['.py']
        
        return {
            "directory": directory,
            "extensions": extensions
        }

    def _parse_git_input(self, input_str: str) -> Dict[str, Any]:
        """Parse git extraction input"""
        git_url_match = re.search(r'https?://[^\s]+', input_str)
        git_url = git_url_match.group(0) if git_url_match else input_str.strip()
        
        ext_match = re.findall(r'\.[a-zA-Z]+', input_str)
        extensions = ext_match if ext_match else []
        
        return {
            "git_url": git_url,
            "extensions": extensions
        }

    def can_handle(self, query: str) -> float:
        """
        Determine if this agent can handle the given query
        
        Returns a confidence score between 0.0 and 1.0
        """
        extraction_patterns = [
            r'extract(ion)?',
            r'get content',
            r'pull files',
            r'fetch.*content',
            r'get.*files from',
            r'\.git',
            r'github\.com',
            r'repository',
            r'folder',
            r'directory'
        ]
        
        for pattern in extraction_patterns:
            if re.search(pattern, query.lower()):
                return 0.8
        
        return 0.2