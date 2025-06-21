import os
from typing import TypedDict, Annotated, Sequence
import operator
import boto3
from botocore.config import Config
from datetime import datetime
from langchain_core.messages import BaseMessage
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

# Global variable to cache the agent
_cached_agent = None

def get_agent_executor():
    """
    Creates and compiles the langgraph agent with caching.

    This function encapsulates the agent creation process and caches the result
    to avoid expensive re-initialization on every request.

    Returns:
        A compiled langgraph agent (Runnable).
    """
    global _cached_agent
    
    # Return cached agent if already initialized
    if _cached_agent is not None:
        return _cached_agent
    
    # --- 2. Set up Tools ---
    # We create a list of the tools the agent can use.
    tools = [retrieve_realtime_stock_price, retrieve_historical_stock_price]
    # The ToolNode is a special node in langgraph that executes tools.
    # It takes a list of tools and returns a function that takes a ToolMessage
    # and runs the corresponding tool.
    tool_node = ToolNode(tools)

    # --- 3. Configure the Language Model & Prompt ---
    # Add a retry configuration to handle potential ThrottlingExceptions
    retry_config = Config(
        retries={
            'max_attempts': 10,
            'mode': 'standard'
        }
    )
    # Create a boto3 client with the retry configuration
    bedrock_client = boto3.client(
        "bedrock-runtime",
        region_name="us-east-1",
        config=retry_config
    )

    # Pass the custom client to the ChatBedrock model
    model = ChatBedrock(
        client=bedrock_client,
        model_id="amazon.nova-pro-v1:0",
        model_kwargs={"temperature": 0},
        region_name="us-east-1"
    )

    # Add a system prompt to ground the model and control its behavior.
    system_prompt = (
        "You are a helpful financial assistant. Your goal is to provide accurate stock information "
        "by using the tools at your disposal.\n"
        "The current date is {current_date}.\n"
        "When you receive data from a tool, you MUST present that data directly in your response. "
        "Do not describe the tool's output; state the facts and numbers you are given."
    ).format(current_date=datetime.now().strftime("%Y-%m-%d"))

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        MessagesPlaceholder(variable_name="messages"),
    ])
    
    # Bind tools and chain the prompt with the model
    model = model.bind_tools(tools)
    chain = prompt | model

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
        # Use the chained prompt and model for invocation
        response = chain.invoke({"messages": messages})
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
    
    # Cache the agent for future requests
    _cached_agent = app
    return app 