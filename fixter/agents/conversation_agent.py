from typing import Dict, Any, List, Optional, Union, Annotated
import operator
import re
import json

from langchain_core.agents import AgentAction, AgentFinish
from langgraph.graph import StateGraph, END
from langchain_core.exceptions import OutputParserException
from langchain.agents import create_react_agent
from langchain import hub

from fixter.agents.agent_base import BaseAgent

class ConversationState(Dict):
    """State used by the conversation agent's graph"""
    input: str
    agent_outcome: Union[AgentAction, AgentFinish, None]
    intermediate_steps: Annotated[List[tuple[AgentAction, str]], operator.add]
    session_id: str
    memory_context: Optional[Dict[str, Any]]
    step_counter: int = 0
    reflections: List[Dict[str, Any]] = []

class ConversationAgent(BaseAgent):
    """Agent for general conversation and reasoning"""
    
    def __init__(self, llm, tools, session_manager=None):
        """Initialize the conversation agent"""
        super().__init__(llm, tools, session_manager)
        
        self.prompt = hub.pull("hwchase17/react") + """
You are a helpful assistant capable of handling a wide range of queries and tasks.
You have access to short-term memory from previous interactions in this session.

For factual questions:
1. If you know the answer with high confidence, answer directly.
2. If you need to verify, use search tools but limit repeated identical searches.
3. After 1-2 searches, synthesize what you've found into a clear answer.
4. Don't get stuck in loops of repeated identical tool calls.

IMPORTANT: For simple conversational queries or questions you can answer directly from your knowledge, 
provide a direct answer WITHOUT using any tools. Only use tools when necessary for complex queries 
or when you need to retrieve specific information.

For direct questions that don't require tools, provide a direct answer using
the "Final Answer:" format without using any tools.

Always follow this exact format:
Thought: I need to analyze the task and determine what to do.
Action: tool_name
Action Input: the input to the tool
Observation: the result of the action
... (repeat Action/Observation as needed)
Thought: I have enough information to provide a response.
Final Answer: your response here

Never respond with: "Action: None" as this will cause an error.
"""
        
        self.conversation_tools = [tool for tool in tools 
                                  if tool.name not in ["extract_content_local", "extract_git_content"]]
        self.agent_runnable = create_react_agent(
            tools=self.conversation_tools,
            llm=llm,
            prompt=self.prompt
        )
        
    def process(self, query: str, session_id: str = None) -> str:
        """Process a conversation query"""
        session = self._get_session(session_id)
        
        enhanced_query = self._enhance_with_memory(query, session)
        
        memory_context = {"original_input": query}
        
        graph = StateGraph(ConversationState)
        graph.add_node("reason", self._reason_node)
        graph.add_node("reflect", self._reflect_node)
        graph.add_node("act", self._act_node)
        graph.add_node("finish", self._finish_node)
        
        graph.set_entry_point("reason")
        
        graph.add_conditional_edges(
            "reason",
            self._should_continue,
            {
                "act": "reflect",  
                "finish": "finish" 
            }
        )
        
        graph.add_conditional_edges(
            "reflect",
            self._post_reflection_router,
            {
                "act": "act",     
                "finish": "finish" 
            }
        )
        
        graph.add_edge("act", "reason")
        graph.add_edge("finish", END)
        
        app = graph.compile()
        
        result = app.invoke({
            "input": enhanced_query,
            "agent_outcome": None,
            "intermediate_steps": [],
            "session_id": session.session_id,
            "memory_context": memory_context,
            "step_counter": 0,
            "reflections": []
        })
        
        output = result["agent_outcome"].return_values["output"]
        
        self._add_to_conversation_history(session, query, output)
        self._save_session(session.session_id)
        
        return output
    
    def can_handle(self, query: str) -> float:
        """Determine if this agent can handle the given query"""
        
        query_lower = query.lower()
        
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
        
        if any(re.search(pattern, query_lower) for pattern in extraction_patterns):
            return 0.3
        
        return 0.7
    
    def _enhance_with_memory(self, query: str, session) -> str:
        """Enhance the query with memory context"""
        session.extract_entities_from_query(query)
        
        has_context_reference = any(ref in query.lower() for ref in [
            "previous", "earlier", "before", "last time", "you mentioned", 
            "we discussed", "that", "those", "these", "it", "the file", "the repo",
            "again", "recall", "remember"
        ])
        
        if has_context_reference or len(session.conversation_history) > 0:
            context_parts = []
            
            if session.conversation_history:
                history = session.conversation_history[-3:]
                context_parts.append("Recent conversation:")
                for turn in history:
                    context_parts.append(f"- You: {turn.get('query', '')}")
                    if turn.get("response"):
                        response = turn.get("response", "")
                        if len(response) > 150:
                            response = response[:150] + "..."
                        context_parts.append(f"- Assistant: {response}")
            
            entities = session.get_recent_entities(limit=5)
            if entities:
                context_parts.append("\nRecently mentioned:")
                for entity in entities:
                    context_parts.append(f"- {entity.type}: {entity.value}")
            
            if session.active_task:
                context_parts.append("\nCurrent task:")
                context_parts.append(f"- {session.active_task.get('description', 'Unknown task')}")
            
            if context_parts:
                return f"Context from memory:\n{chr(10).join(context_parts)}\n\nCurrent query: {query}"
        
        return query
    
    def _reason_node(self, state: ConversationState) -> Dict[str, Any]:
        """Reasoning node for the conversation graph"""
        try:
            agent_outcome = self.agent_runnable.invoke({
                "input": state["input"],
                "intermediate_steps": state.get("intermediate_steps", [])
            })
            
            return {"agent_outcome": agent_outcome}
            
        except OutputParserException as e:
            error_text = str(e)
            output_text = error_text.split("Could not parse LLM output:")[-1].strip()
            
            final_answer_match = re.search(r'Final Answer:\s*(.*?)(?:\n|$)', output_text, re.DOTALL)
            if final_answer_match:
                output_text = final_answer_match.group(1).strip()
            elif not re.search(r'(Thought:|Action:|Action Input:|Observation:)', output_text, re.DOTALL):
                pass
            else:
                output_text = re.sub(r'Thought:.*?(?=Action:|Observation:|Final Answer:|$)', '', output_text, flags=re.DOTALL)
                output_text = re.sub(r'Action:.*?(?=Observation:|Final Answer:|$)', '', output_text, flags=re.DOTALL)
                output_text = re.sub(r'Action Input:.*?(?=Observation:|Final Answer:|$)', '', output_text, flags=re.DOTALL)
                output_text = re.sub(r'Observation:.*?(?=Thought:|Action:|Final Answer:|$)', '', output_text, flags=re.DOTALL)
            
            if not output_text.strip():
                output_text = "I apologize, but I couldn't process that correctly. Please try asking in a different way."
            
            agent_outcome = AgentFinish(return_values={"output": output_text}, log=output_text)
            return {"agent_outcome": agent_outcome}
    def _reflect_node(self, state: ConversationState) -> ConversationState:
        """Reflect on the current execution state and adjust strategy if needed"""
        current_steps = state.get("step_counter", 0)
        intermediate_steps = state.get("intermediate_steps", [])
        session_id = state.get("session_id")
        session = self._get_session(session_id)
        
        if isinstance(state["agent_outcome"], AgentFinish):
            return state
        
        if current_steps < 2 or len(intermediate_steps) < 2:
            return state
        
        tool_sequence = [step[0].tool for step in intermediate_steps[-3:]]
        
        if len(tool_sequence) >= 2 and len(set(tool_sequence[-2:])) == 1:
            reflection_prompt = f"""
            Analyze the following sequence of steps in the agent's execution:
            
            Tool Sequence: {tool_sequence}
            Recent Actions: 
            {intermediate_steps[-2:]}
            
            The agent appears to be calling the same tool repeatedly. Evaluate if this is productive
            or if the agent is stuck in a loop. Suggest a different approach if needed.
            """
            
            reflection = self.llm.invoke(reflection_prompt)
            
            session.add_entity(
                "reflection", 
                f"Reflection at step {current_steps}", 
                {"content": reflection, "tool_sequence": tool_sequence}
            )
            
            state["reflections"].append({
                "step": current_steps,
                "type": "loop_detection",
                "content": reflection
            })
            
            if current_steps > 3 and len(set(tool_sequence)) == 1:
                direct_answer = self._synthesize_from_tools(state)
                
                state["agent_outcome"] = AgentFinish(
                    return_values={"output": direct_answer},
                    log="Synthesized answer from repeated tool calls"
                )
        
        if current_steps > 5 and not isinstance(state["agent_outcome"], AgentFinish):
            reflection_prompt = f"""
            Analyze the following execution path:
            
            Total Steps: {current_steps}
            Recent Tools Used: {tool_sequence}
            Recent Actions: 
            {intermediate_steps[-3:]}
            
            The agent has taken {current_steps} steps without reaching a conclusion.
            Analyze if the current approach is making progress or if a more direct strategy is needed.
            """
            
            reflection = self.llm.invoke(reflection_prompt)
            
            session.add_entity(
                "reflection", 
                f"Efficiency reflection at step {current_steps}", 
                {"content": reflection}
            )
            
            state["reflections"].append({
                "step": current_steps,
                "type": "efficiency",
                "content": reflection
            })
            
            original_input = state.get("input", "")
            enhanced_input = f"""
            Your previous approach has taken multiple steps without reaching a conclusion.
            
            Reflection: {reflection}
            
            Please reconsider your strategy. Consider whether you can:
            1. Answer directly from existing information
            2. Use a different tool that might be more effective
            3. Break down the problem differently
            
            Original query: {original_input}
            """
            
            state["input"] = enhanced_input
        
        return state
    def _act_node(self, state: ConversationState) -> Dict[str, Any]:
        """Action node for the conversation graph"""
        current_steps = state.get("step_counter", 0)
        state["step_counter"] = current_steps + 1
        agent_action = state["agent_outcome"]
        
        if agent_action is None:
            return {"intermediate_steps": []}
        
        tool_name = agent_action.tool
        tool_input = agent_action.tool_input
        
        tool_map = {tool.name: tool for tool in self.conversation_tools}
        if tool_name not in tool_map:
            error_msg = f"Tool '{tool_name}' not found in conversation tools. Available tools: {list(tool_map.keys())}"
            return {"intermediate_steps": [(agent_action, error_msg)], "step_counter": state["step_counter"]}
        
        filtered_input = self._parse_tool_input(tool_name, tool_input)
        
        tool_result = tool_map[tool_name].invoke(filtered_input)
        
        session_id = state.get("session_id")
        session = self._get_session(session_id)
        
        if tool_name in ["get_conversation_history", "get_memory_entities"]:
            pass
        elif tool_name == "clear_memory_session":
            pass
        
        return {
            "intermediate_steps": [(agent_action, str(tool_result))],
            "step_counter": state["step_counter"]
        }
    
    def _finish_node(self, state: ConversationState) -> Dict[str, Any]:
        """Finish node for the conversation graph"""
        return state
    
    def _should_continue(self, state: ConversationState) -> str:
        """Determine whether to continue or finish"""
        current_steps = state.get("step_counter", 0)
        
        if current_steps >= 10:
            state["agent_outcome"] = AgentFinish(
                return_values={"output": "I've spent some time analyzing your request but couldn't reach a clear conclusion. Could you please clarify what you're looking for?"}, 
                log="Max steps reached"
            )
            return "finish"
        
        if isinstance(state["agent_outcome"], AgentFinish):
            return "finish"
        
        return "act"
    
    def _post_reflection_router(self, state: ConversationState) -> str:
        """Routes the flow after reflection based on the state"""
        if isinstance(state["agent_outcome"], AgentFinish):
            return "finish"
        return "act"
    
    def _parse_tool_input(self, tool_name: str, tool_input: Any) -> Dict[str, Any]:
        """Parse and normalize tool input"""
        if isinstance(tool_input, str):
            try:
                tool_input = json.loads(tool_input)
            except json.JSONDecodeError:
                if tool_name == "get_system_time":
                    return {"format": tool_input.strip().strip('"\'')}
                elif tool_name == "tavily_search_results_json":
                    return {"query": tool_input.strip().strip('"\'')}
                elif tool_name == "get_conversation_history":
                    try:
                        limit = int(tool_input)
                    except (ValueError, TypeError):
                        limit_match = re.search(r'limit\s*=\s*(\d+)', str(tool_input))
                        limit = int(limit_match.group(1)) if limit_match else 5
                    return {"limit": limit}
                elif tool_name == "get_memory_entities":
                    tool_input_str = str(tool_input)
                    entity_type_match = re.search(r'entity_type\s*=\s*["\']?([a-zA-Z_]+)["\']?', tool_input_str)
                    entity_type = entity_type_match.group(1) if entity_type_match else ""
                    
                    limit_match = re.search(r'limit\s*=\s*(\d+)', tool_input_str)
                    limit = int(limit_match.group(1)) if limit_match else 5
                    
                    return {
                        "entity_type": entity_type,
                        "limit": limit
                    }
                else:
                    return {"input": tool_input.strip().strip('"\'')}
        
        if tool_name == "get_system_time":
            return {"format": tool_input.get("format", "%Y-%m-%d %H:%M:%S").strip().strip('"\'')}
        elif tool_name == "tavily_search_results_json":
            query = tool_input.get("query") or tool_input.get("input")
            return {"query": query.strip().strip('"\'')}
        elif tool_name == "get_conversation_history":
            if isinstance(tool_input, int):
                return {"limit": tool_input}
            return {"limit": tool_input.get("limit", 5)}
        elif tool_name == "get_memory_entities":
            return {
                "entity_type": tool_input.get("entity_type", ""),
                "limit": tool_input.get("limit", 5)
            }
            
        return tool_input
    def _synthesize_from_tools(self, state: ConversationState) -> str:
        """Synthesize information from repeated tool calls"""
        intermediate_steps = state.get("intermediate_steps", [])
        user_query = state.get("input", "")
        
        tool_results = []
        for action, result in intermediate_steps:
            tool_results.append({
                "tool": action.tool,
                "result": result[:1000]  
            })
        
        synthesis_prompt = f"""
        I need to answer this user query directly: "{user_query}"
        
        I've gathered information using these tools:
        {json.dumps(tool_results, indent=2)}
        
        Based on this information, provide a direct answer to the query. 
        Be factual and concise. If there isn't enough information, provide
        your best answer based on what's available and general knowledge.
        Don't explain the tools or methods used, just provide the answer.
        """
        
        synthesis_response = self.llm.invoke(synthesis_prompt)
        return synthesis_response.content