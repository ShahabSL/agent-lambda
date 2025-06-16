import os
from typing import TypedDict, Annotated, Sequence
import operator
from langchain_core.messages import BaseMessage, HumanMessage, ToolMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain_aws import ChatBedrock
from langchain_core.tools import BaseTool
from .tools import retrieve_realtime_stock_price, retrieve_historical_stock_price

# --- 1. Define the Agent's State ---
# This is the memory of our agent. It's a dictionary that holds the
# conversation history. `langgraph` will pass this state between nodes.
class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]

# --- 2. Set up Tools ---
# We create a list of the tools the agent can use.
tools = [retrieve_realtime_stock_price, retrieve_historical_stock_price]
# The ToolNode is a special node in langgraph that executes tools.
# It takes a list of tools and returns a function that takes a ToolMessage
# and runs the corresponding tool.
tool_node = ToolNode(tools)

# --- 3. Configure the Language Model ---
# We are now connecting to a real LLM, AWS Bedrock.
# We specify the model ID for Anthropic's Claude 3 Sonnet.
# We also set the AWS region where Bedrock will be called.
model = ChatBedrock(
    model_id="anthropic.claude-3-sonnet-20240229-v1:0",
    model_kwargs={"temperature": 0},
    region_name="us-east-1" # Or any other region with Bedrock access
)

# We now bind the tools to the model. This is essential for the LLM
# to know what tools it can call and in what format.
model = model.bind_tools(tools)


# --- 4. Define the Graph Nodes ---

# This is the "agent" node, the primary reasoning engine.
def should_continue(state: AgentState) -> str:
    """
    This function decides the next step for the agent.
    If the last message from the model is a tool call, it tells the graph
    to execute the tools. Otherwise, it ends the conversation.
    """
    last_message = state["messages"][-1]
    # If there are no tool calls, then we finish
    if not last_message.tool_calls:
        return "end"
    # Otherwise, we call the tools
    return "continue"

def call_model(state: AgentState) -> dict:
    """
    This is the "agent" node. It calls the LLM with the current conversation
    history and appends the new message to the state.
    """
    messages = state["messages"]
    response = model.invoke(messages)
    # We return a dictionary, because this is what the state expects
    return {"messages": [response]}


# --- 5. Construct the Graph ---
# We are now ready to define the graph's structure.
workflow = StateGraph(AgentState)

# Add the two nodes we defined above.
workflow.add_node("agent", call_model)
workflow.add_node("action", tool_node)

# Set the entrypoint of the graph. The first thing to run is the agent node.
workflow.set_entry_point("agent")

# Add the conditional edge. This is the logic that decides what to do next.
workflow.add_conditional_edges(
    "agent",
    should_continue,
    {
        "continue": "action",
        "end": END,
    },
)

# Add a normal edge from the action node back to the agent node.
# This means that after a tool is called, we always go back to the agent
# to process the result.
workflow.add_edge("action", "agent")

# --- 6. Compile the Graph ---
# We compile the graph into a runnable object.
app = workflow.compile() 