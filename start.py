#!/usr/bin/env python3
import sys
import subprocess

def print_header():
    print("\n==============================================")
    print("             BUGREWIND LAUNCHER               ")
    print("==============================================\n")

def main():
    print_header()
    print("How would you like to run Vectra today?\n")
    print("  [1] GUI Dashboard (Interactive Web UI)")
    print("  [2] CLI Automation (Headless terminal scan)")
    print("  [3] MCP Server (Protocol for AI Assistants)")
    print("  [4] Exit")
    
    choice = input("\nEnter your choice [1-4]: ").strip()
    
    if choice == '1':
        print("\n🚀 Firing up the full dashboard...")
        subprocess.run([sys.executable, "-m", "vectra.gui"])
    
    elif choice == '2':
        print("\n💻 Selected Headless CLI.")
        repo_path = input("Enter the absolute path to the target repository: ").strip()
        if not repo_path:
            print("⚠️ Error: A repository path is required for CLI mode.")
            sys.exit(1)
        prompt = input("Enter a deploy prompt (or press Enter for default): ").strip()
        
        args = [sys.executable, "-m", "vectra.main", repo_path]
        if prompt:
            args.extend(["--prompt", prompt])
            
        print(f"\n🚀 Running Vectra on: {repo_path}")
        subprocess.run(args)
        
    elif choice == '3':
        print("\n🔌 Starting FastMCP Server... (listening for assistant connections on stdio)")
        subprocess.run([sys.executable, "-m", "vectra.mcp_server"])
        
    elif choice == '4':
        print("Exiting.")
        sys.exit(0)
    else:
        print("Invalid choice. Exiting.")
        sys.exit(1)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nLaunch cancelled by user.")
        sys.exit(0)
