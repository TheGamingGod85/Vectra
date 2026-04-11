import os
import base64
import time
from typing import Literal, Optional, Union, Any, List
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, BaseMessage, SystemMessage
from langchain_core.tools import tool
from langchain_core.language_models.chat_models import BaseChatModel
from rich.console import Console
from rich.table import Table
from pydantic import BaseModel, Field

from computers import EnvState, Computer

MAX_RECENT_TURN_WITH_SCREENSHOTS = 3

console = Console()

SYSTEM_PROMPT = """You are an advanced browser automation agent. Your goal is to fulfill the user's request by interacting with a web browser.

OPERATING PRINCIPLES:
1. **Multi-Step Planning**: Most tasks require multiple steps. Don't just do one thing and stop. Plan your next move based on what you see.
2. **Verification**: After every action, look at the new state of the page to verify if the action had the desired effect.
3. **Persistence**: If a task like "scroll to the bottom" or "find all links" is requested, you must continue performing actions (e.g., scrolling multiple times) until the goal is fully achieved.
4. **No Hallucinations**: Only report information that is explicitly visible in the provided screenshots or tool outputs.

If you have finished the task, provide a final answer. If you need more steps, continue calling tools."""

# Define Pydantic schemas for tool arguments to ensure strict typing
class ClickAtArgs(BaseModel):
    x: int = Field(..., description="The x coordinate (0-1000)")
    y: int = Field(..., description="The y coordinate (0-1000)")

class HoverAtArgs(BaseModel):
    x: int = Field(..., description="The x coordinate (0-1000)")
    y: int = Field(..., description="The y coordinate (0-1000)")

class TypeTextAtArgs(BaseModel):
    x: int = Field(..., description="The x coordinate (0-1000)")
    y: int = Field(..., description="The y coordinate (0-1000)")
    text: str = Field(..., description="The text to type")
    press_enter: bool = Field(False, description="Whether to press enter after typing")
    clear_before_typing: bool = Field(True, description="Whether to clear the field before typing")

class ScrollDocumentArgs(BaseModel):
    direction: Literal["up", "down", "left", "right"] = Field(..., description="The direction to scroll")

class ScrollAtArgs(BaseModel):
    x: int = Field(..., description="The x coordinate (0-1000)")
    y: int = Field(..., description="The y coordinate (0-1000)")
    direction: Literal["up", "down", "left", "right"] = Field(..., description="The direction to scroll")
    magnitude: int = Field(800, description="The magnitude of the scroll")

class NavigateArgs(BaseModel):
    url: str = Field(..., description="The URL to navigate to")

class KeyCombinationArgs(BaseModel):
    keys: str = Field(..., description="The key combination, e.g., 'control+c'")

class DragAndDropArgs(BaseModel):
    x: int = Field(..., description="The start x coordinate (0-1000)")
    y: int = Field(..., description="The start y coordinate (0-1000)")
    destination_x: int = Field(..., description="The end x coordinate (0-1000)")
    destination_y: int = Field(..., description="The end y coordinate (0-1000)")

class BrowserAgent:
    def __init__(
        self,
        browser_computer: Computer,
        query: str,
        model: BaseChatModel,
        verbose: bool = True,
    ):
        self._browser_computer = browser_computer
        self._query = query
        self._model = model
        self._verbose = verbose
        self.final_reasoning = None
        self._last_state = None
        
        # Initialize messages with system prompt and user query
        self._messages: List[BaseMessage] = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=self._query)
        ]

        # Define tools using LangChain's @tool decorator
        self._tools = self._setup_tools()
        self._model_with_tools = self._model.bind_tools(self._tools)

    def add_query(self, query: str):
        """Adds a new user query to the conversation history."""
        # Check if the last message was a screenshot HumanMessage
        if self._messages and isinstance(self._messages[-1], HumanMessage) and isinstance(self._messages[-1].content, list):
            has_image = any(item.get("type") == "image_url" for item in self._messages[-1].content if isinstance(item, dict))
            if has_image:
                # Append the new query to the existing HumanMessage
                self._messages[-1].content.append({"type": "text", "text": f"\nFollow-up query: {query}"})
                return

        self._messages.append(HumanMessage(content=query))

    def _setup_tools(self):
        @tool
        def open_web_browser() -> str:
            """Opens the web browser."""
            state = self._browser_computer.open_web_browser()
            return self._format_tool_output(state)

        @tool(args_schema=ClickAtArgs)
        def click_at(x: int, y: int) -> str:
            """Clicks at a specific x, y coordinate on the webpage. x and y are 0-1000."""
            x, y = int(x), int(y)
            state = self._browser_computer.click_at(
                x=self.denormalize_x(x),
                y=self.denormalize_y(y)
            )
            return self._format_tool_output(state)

        @tool(args_schema=HoverAtArgs)
        def hover_at(x: int, y: int) -> str:
            """Hovers at a specific x, y coordinate on the webpage. x and y are 0-1000."""
            x, y = int(x), int(y)
            state = self._browser_computer.hover_at(
                x=self.denormalize_x(x),
                y=self.denormalize_y(y)
            )
            return self._format_tool_output(state)

        @tool(args_schema=TypeTextAtArgs)
        def type_text_at(x: int, y: int, text: str, press_enter: bool = False, clear_before_typing: bool = True) -> str:
            """Types text at a specific x, y coordinate. x and y are 0-1000."""
            x, y = int(x), int(y)
            if isinstance(press_enter, str): press_enter = press_enter.lower() == "true"
            if isinstance(clear_before_typing, str): clear_before_typing = clear_before_typing.lower() == "true"
            
            state = self._browser_computer.type_text_at(
                x=self.denormalize_x(x),
                y=self.denormalize_y(y),
                text=text,
                press_enter=press_enter,
                clear_before_typing=clear_before_typing
            )
            return self._format_tool_output(state)

        @tool(args_schema=ScrollDocumentArgs)
        def scroll_document(direction: Literal["up", "down", "left", "right"]) -> str:
            """Scrolls the entire webpage."""
            state = self._browser_computer.scroll_document(direction)
            return self._format_tool_output(state)

        @tool(args_schema=ScrollAtArgs)
        def scroll_at(x: int, y: int, direction: Literal["up", "down", "left", "right"], magnitude: int = 800) -> str:
            """Scrolls at a specific x, y coordinate. x and y are 0-1000."""
            x, y, magnitude = int(x), int(y), int(magnitude)
            state = self._browser_computer.scroll_at(
                x=self.denormalize_x(x),
                y=self.denormalize_y(y),
                direction=direction,
                magnitude=magnitude
            )
            return self._format_tool_output(state)

        @tool
        def wait_5_seconds() -> str:
            """Waits for 5 seconds."""
            state = self._browser_computer.wait_5_seconds()
            return self._format_tool_output(state)

        @tool
        def go_back() -> str:
            """Navigates back."""
            state = self._browser_computer.go_back()
            return self._format_tool_output(state)

        @tool
        def go_forward() -> str:
            """Navigates forward."""
            state = self._browser_computer.go_forward()
            return self._format_tool_output(state)

        @tool
        def search() -> str:
            """Jumps to search engine."""
            state = self._browser_computer.search()
            return self._format_tool_output(state)

        @tool(args_schema=NavigateArgs)
        def navigate(url: str) -> str:
            """Navigates to a URL."""
            state = self._browser_computer.navigate(url)
            return self._format_tool_output(state)

        @tool(args_schema=KeyCombinationArgs)
        def key_combination(keys: str) -> str:
            """Presses keys, e.g., 'control+c'. Use '+' to separate keys."""
            state = self._browser_computer.key_combination(keys.split("+"))
            return self._format_tool_output(state)

        @tool(args_schema=DragAndDropArgs)
        def drag_and_drop(x: int, y: int, destination_x: int, destination_y: int) -> str:
            """Drags from (x,y) to (destination_x, destination_y). x and y are 0-1000."""
            x, y, destination_x, destination_y = int(x), int(y), int(destination_x), int(destination_y)
            state = self._browser_computer.drag_and_drop(
                x=self.denormalize_x(x),
                y=self.denormalize_y(y),
                destination_x=self.denormalize_x(destination_x),
                destination_y=self.denormalize_y(destination_y)
            )
            return self._format_tool_output(state)

        return [
            open_web_browser, click_at, hover_at, type_text_at,
            scroll_document, scroll_at, wait_5_seconds, go_back,
            go_forward, search, navigate, key_combination, drag_and_drop
        ]

    def _format_tool_output(self, state: EnvState) -> str:
        """Helper to format tool output and store screenshot in state."""
        self._last_state = state
        return f"Current URL: {state.url}"

    def run_one_iteration(self) -> Literal["COMPLETE", "CONTINUE"]:
        if self._verbose:
            with console.status("Generating response from LLM...", spinner_style=None):
                response = self._model_with_tools.invoke(self._messages)
        else:
            response = self._model_with_tools.invoke(self._messages)

        self._messages.append(response)

        if not response.tool_calls:
            print(f"Agent Loop Complete: {response.content}")
            self.final_reasoning = response.content
            return "COMPLETE"

        # Handle tool calls
        tool_map = {tool.name: tool for tool in self._tools}
        
        for tool_call in response.tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call["args"]
            
            if self._verbose:
                table = Table(expand=True)
                table.add_column("Reasoning", header_style="magenta", ratio=1)
                table.add_column("Tool Call", header_style="cyan", ratio=1)
                table.add_row(response.content, f"Name: {tool_name}\nArgs: {tool_args}")
                console.print(table)

            if tool_name in tool_map:
                output = tool_map[tool_name].invoke(tool_args)
                
                # Append ToolMessage with text output only
                self._messages.append(ToolMessage(
                    content=output,
                    tool_call_id=tool_call["id"]
                ))
                
                # If there's a screenshot, append it as a separate HumanMessage
                # This is more compatible with Ollama's vision support
                if self._last_state:
                    screenshot_base64 = base64.b64encode(self._last_state.screenshot).decode("utf-8")
                    self._messages.append(HumanMessage(
                        content=[
                            {"type": "text", "text": f"Screenshot after {tool_name}:"},
                            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{screenshot_base64}"}}
                        ]
                    ))
                    self._last_state = None
            else:
                self._messages.append(ToolMessage(
                    content=f"Error: Tool {tool_name} not found.",
                    tool_call_id=tool_call["id"]
                ))

        self._cleanup_history()
        return "CONTINUE"

    def _cleanup_history(self):
        """Removes old screenshots from message history to save context window."""
        screenshot_count = 0
        for msg in reversed(self._messages):
            # Check for images in both ToolMessage and HumanMessage
            if (isinstance(msg, ToolMessage) or isinstance(msg, HumanMessage)) and isinstance(msg.content, list):
                has_image = any(item.get("type") == "image_url" for item in msg.content if isinstance(item, dict))
                if has_image:
                    screenshot_count += 1
                    if screenshot_count > MAX_RECENT_TURN_WITH_SCREENSHOTS:
                        # Remove image part
                        msg.content = [item for item in msg.content if isinstance(item, dict) and item.get("type") != "image_url"]

    def agent_loop(self, max_iterations: int = 5):
        """Runs the agent loop until completion or max iterations reached."""
        iterations = 0
        status = "CONTINUE"
        while status == "CONTINUE" and iterations < max_iterations:
            status = self.run_one_iteration()
            iterations += 1
            if status == "CONTINUE":
                time.sleep(1)
        
        if iterations >= max_iterations:
            print(f"Reached maximum iterations ({max_iterations}). Stopping.")

    def denormalize_x(self, x: int) -> int:
        return int(x / 1000 * self._browser_computer.screen_size()[0])

    def denormalize_y(self, y: int) -> int:
        return int(y / 1000 * self._browser_computer.screen_size()[1])
