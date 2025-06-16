from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from langchain_core.messages import HumanMessage

from .agent import app

# --- 1. Initialize FastAPI App ---
api = FastAPI(
    title="Serverless AI Stock Analysis Agent",
    description="An API for a serverless AI agent that can retrieve real-time and historical stock prices.",
    version="1.0.0",
)

# --- 2. Define Request and Response Models ---
class InvokeRequest(BaseModel):
    """Defines the structure for the user's request."""
    query: str


# --- 3. Create a Root Endpoint ---
@api.get("/", status_code=200)
def root():
    """A simple endpoint to confirm the API is running."""
    return {"status": "ok"}


# --- 4. Create the Streaming Agent Endpoint ---
@api.post("/invoke")
async def invoke_agent(request: InvokeRequest) -> StreamingResponse:
    """
    The main endpoint to interact with the agent. It accepts a user query
    and streams the agent's thoughts and final response.
    """
    
    # This is the generator function that will stream responses.
    async def stream_generator():
        """
        This async generator function is the core of our streaming response.
        It calls the langgraph agent's `astream` method and yields each
        piece of the response as it comes in.
        """
        # The input to the agent must match the `AgentState` structure.
        # We start the conversation with a `HumanMessage`.
        inputs = {"messages": [HumanMessage(content=request.query)]}
        
        # `astream` returns an async generator that yields the state of the
        # graph at each step.
        async for output in app.astream(inputs):
            # The output dictionary contains the state of the graph.
            # We can inspect it to see what's happening.
            # The 'agent' key holds the latest message from the model.
            for key, value in output.items():
                if key == "agent":
                    # We only want to stream the actual message content
                    if value["messages"]:
                        last_message = value["messages"][-1]
                        if last_message.content:
                            # We yield the content, which FastAPI sends to the client.
                            yield f"data: {last_message.content}\\n\\n"

    # Return the StreamingResponse, passing it our generator function.
    return StreamingResponse(stream_generator(), media_type="text/event-stream") 