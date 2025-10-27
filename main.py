#!/usr/bin/env python3
"""
ReelCraft - Start the API server
"""
import uvicorn


def main():
    """Start the ReelCraft API server"""
    print("=" * 60)
    print("Starting ReelCraft API Server")
    print("=" * 60)
    print("\nServer will be available at:")
    print("  - Frontend: http://localhost:8000")
    print("  - API Docs: http://localhost:8000/docs")
    print("  - Health Check: http://localhost:8000/health")
    print("\nPress CTRL+C to stop the server\n")
    print("=" * 60)

    uvicorn.run(
        "services.api:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )


if __name__ == "__main__":
    main()
