import argparse
import os
from dotenv import load_dotenv


def main():
    load_dotenv()
    parser = argparse.ArgumentParser(description="The Governor CRT companion")
    parser.add_argument("command", nargs="?", choices=["serve", "doctor", "listen"], default="serve")
    parser.add_argument("--port", type=int, default=int(os.getenv("GOVERNOR_PORT", "8765")))
    parser.add_argument("--demo", action="store_true", help="Run without an API or local model, overriding .env for this process")
    args = parser.parse_args()
    if args.demo:
        os.environ["GOVERNOR_PROVIDER"] = "demo"
    if args.command == "doctor":
        from .doctor import run
        run()
    elif args.command == "listen":
        from .audio import run
        run(args.port)
    else:
        import uvicorn
        # One process owns the robot, camera, and conversation state.
        uvicorn.run("governor.app:create_app", factory=True, host="127.0.0.1", port=args.port, workers=1, access_log=False)


if __name__ == "__main__":
    main()
