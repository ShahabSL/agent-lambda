from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from langchain_core.messages import HumanMessage
import asyncio
import logging

from .agent import get_agent_executor

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- 1. Initialize FastAPI App ---
app = FastAPI(
    title="Serverless AI Stock Analysis Agent",
    description="An API for a serverless AI agent that can retrieve real-time and historical stock prices.",
    version="1.0.0",
)

# --- 2. Startup Event to Pre-initialize Agent ---
@app.on_event("startup")
async def startup_event():
    """Pre-initialize the agent during startup to avoid first-request delays."""
    try:
        logger.info("Initializing agent during startup...")
        # This will create and cache the agent
        agent = get_agent_executor()
        logger.info("Agent initialized successfully during startup")
    except Exception as e:
        logger.error(f"Failed to initialize agent during startup: {e}")
        # Don't fail startup, but log the error

# --- 2. Define Request and Response Models ---
class InvokeRequest(BaseModel):
    """Defines the structure for the user's request."""
    query: str


# --- 3. Create a Root Endpoint ---
@app.get("/", status_code=200)
def root():
    """A simple endpoint to confirm the API is running."""
    return {"status": "ok"}

@app.get("/health", status_code=200)
def health():
    """A health check endpoint that doesn't require agent initialization."""
    return {"status": "healthy", "message": "FastAPI server is running"}


# --- 4. Create a Non-Streaming Agent Endpoint for Testing ---
@app.post("/invoke-simple")
async def invoke_agent_simple(request: InvokeRequest):
    """
    A simple non-streaming endpoint to test the agent functionality.
    Returns the complete response as JSON.
    """
    try:
        logger.info(f"Processing query: {request.query}")
        agent = get_agent_executor()
        
        # The input to the agent must match the `AgentState` structure.
        inputs = {"messages": [HumanMessage(content=request.query)]}
        
        # Use invoke instead of astream for a simple response
        result = agent.invoke(inputs)
        
        # Extract the final message content
        if result and "messages" in result and result["messages"]:
            final_message = result["messages"][-1]
            response_content = final_message.content if hasattr(final_message, 'content') else str(final_message)
            logger.info("Agent response generated successfully")
            return {"response": response_content}
        else:
            logger.warning("No response generated from agent")
            return {"response": "No response generated"}
            
    except Exception as e:
        logger.error(f"Error processing request: {e}")
        return {"error": str(e)}

# --- 5. Create the Streaming Agent Endpoint ---
@app.post("/invoke")
async def invoke_agent(request: InvokeRequest) -> StreamingResponse:
    """
    The main endpoint to interact with the agent. It accepts a user query
    and streams the agent's thoughts and final response.
    """
    agent = get_agent_executor()

    # This is the generator function that will stream responses.
    async def stream_generator():
        """
        This async generator function is the core of our streaming response.
        It calls the langgraph agent's `astream` method and yields each
        piece of the response as it comes in.
        """
        try:
            # The input to the agent must match the `AgentState` structure.
            # We start the conversation with a `HumanMessage`.
            inputs = {"messages": [HumanMessage(content=request.query)]}
            
            # Send initial connection confirmation
            yield "data: {\"type\": \"connection\", \"message\": \"Connected to agent\"}\n\n"
            
            # `astream` returns an async generator that yields the state of the
            # graph at each step.
            async for output in agent.astream(inputs):
                # The output dictionary contains the state of the graph.
                # We can inspect it to see what's happening.
                for key, value in output.items():
                    if key == "agent":
                        # Stream the agent's response (including tool calls)
                        if value["messages"]:
                            last_message = value["messages"][-1]
                            
                            # Handle tool calls
                            if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
                                for tool_call in last_message.tool_calls:
                                    yield f"data: {{\"type\": \"tool_call\", \"name\": \"{tool_call['name']}\", \"args\": {tool_call['args']}}}\n\n"
                            
                            # Handle regular content
                            if hasattr(last_message, 'content') and last_message.content:
                                # Split content into smaller chunks for better streaming
                                content = str(last_message.content)
                                # Stream word by word for better visual effect
                                words = content.split()
                                current_chunk = ""
                                
                                for word in words:
                                    current_chunk += word + " "
                                    # Send chunks of 3-5 words for smooth streaming
                                    if len(current_chunk.split()) >= 4:
                                        yield f"data: {{\"type\": \"content\", \"text\": \"{current_chunk.strip()}\"}}\n\n"
                                        current_chunk = ""
                                        # Small delay for visual streaming effect
                                        await asyncio.sleep(0.05)
                                
                                # Send remaining content
                                if current_chunk.strip():
                                    yield f"data: {{\"type\": \"content\", \"text\": \"{current_chunk.strip()}\"}}\n\n"
                    
                    elif key == "action":
                        # Stream tool execution results
                        if value["messages"]:
                            for message in value["messages"]:
                                if hasattr(message, 'content') and message.content:
                                    yield f"data: {{\"type\": \"tool_result\", \"content\": \"{str(message.content)}\"}}\n\n"
            
            # Send completion signal
            yield "data: {\"type\": \"complete\", \"message\": \"Response complete\"}\n\n"
                    
        except Exception as e:
            logger.error(f"Error in streaming: {e}")
            yield f"data: {{\"type\": \"error\", \"message\": \"{str(e)}\"}}\n\n"

    # Return the StreamingResponse with proper headers for SSE
    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "Cache-Control"
    }
    
    return StreamingResponse(
        stream_generator(), 
        media_type="text/event-stream",
        headers=headers
    ) 