import uasyncio as asyncio
from app import App


def main():
    app = App()
    try:
        asyncio.run(app.run())
    finally:
        asyncio.new_event_loop()


if __name__ == "__main__":
    main()
