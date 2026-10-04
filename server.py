"""Single-process server for personal use."""
import argparse

from coachess import app


def main():
    from waitress import serve

    parser = argparse.ArgumentParser(description="Servidor personal de CoaChess")
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=5000)
    args = parser.parse_args()
    print(f"CoaChess: http://{args.host}:{args.port}", flush=True)
    serve(app, host=args.host, port=args.port, threads=4)


if __name__ == '__main__':
    main()
