# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import argparse
import os
from dotenv import load_dotenv

from agent import BrowserAgent
from computers import BrowserbaseComputer, PlaywrightComputer
# from langchain_groq import ChatGroq
from langchain_ollama import ChatOllama

load_dotenv()

PLAYWRIGHT_SCREEN_SIZE = (1440, 900)

def get_model(model_name: str):
    # Groq implementation (commented out)
    # api_key = os.getenv("GROQ_API_KEY")
    # if not api_key:
    #     raise ValueError("GROQ_API_KEY not found in environment variables.")
    # 
    # return ChatGroq(
    #     model=model_name,
    #     groq_api_key=api_key,
    #     temperature=0,
    # )

    # Ollama implementation
    return ChatOllama(
        model=model_name,
        temperature=0,
        include_reasoning=False,
    )

def main() -> int:
    parser = argparse.ArgumentParser(description="Run the browser agent with a query.")
    parser.add_argument(
        "--query",
        type=str,
        # required=True,
        help="The query for the browser agent to execute.",
    )
    parser.add_argument(
        "--env",
        type=str,
        choices=("playwright", "browserbase"),
        default="playwright",
        help="The computer use environment to use.",
    )
    parser.add_argument(
        "--initial_url",
        type=str,
        default="https://www.google.com",
        help="The inital URL loaded for the computer.",
    )
    parser.add_argument(
        "--highlight_mouse",
        action="store_true",
        default=False,
        help="If possible, highlight the location of the mouse.",
    )
    parser.add_argument(
        "--model",
        default='qwen3.5:4b',
        # default='llama3.2:3b',
        # default='qwen3-vl:8b',
        # default='gpt-oss:latest',1111
        help="Set which Ollama model to use.",
    )
    parser.add_argument(
        "--keep_open",
        action="store_true",
        default=False,
        help="Keep the browser open after the agent finishes.",
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        default=False,
        help="Run in interactive mode to provide follow-up queries.",
    )
    args = parser.parse_args()

    if args.env == "playwright":
        env = PlaywrightComputer(
            screen_size=PLAYWRIGHT_SCREEN_SIZE,
            initial_url=args.initial_url,
            highlight_mouse=args.highlight_mouse,
        )
    elif args.env == "browserbase":
        env = BrowserbaseComputer(
            screen_size=PLAYWRIGHT_SCREEN_SIZE,
            initial_url=args.initial_url
        )
    else:
        raise ValueError("Unknown environment: ", args.env)

    model = get_model(args.model)

    with env as browser_computer:
        # Define initial query
        initial_query = args.query if args.query else "Please wait for my instruction."
        
        agent = BrowserAgent(
            browser_computer=browser_computer,
            query=initial_query,
            model=model,
        )
        
        if args.query:
            # Run initial query if provided
            agent.agent_loop()
        else:
            print("\nBrowser initialized and ready for commands.")

        # Interactive loop
        if args.interactive:
            while True:
                print("\n" + "="*50)
                print(" CHAT MODE - Enter your command (or 'exit' to quit)")
                print("="*50)
                user_input = input("\n> ").strip()
                
                if user_input.lower() in ["exit", "quit"]:
                    break
                if not user_input:
                    continue
                
                agent.add_query(user_input)
                agent.agent_loop()

        if args.keep_open and not args.interactive:
            print("\n" + "="*50)
            print("Agent task complete. Browser is kept open.")
            input("Press Enter to close the browser and exit...")
            print("="*50)

    return 0

if __name__ == "__main__":
    main()
