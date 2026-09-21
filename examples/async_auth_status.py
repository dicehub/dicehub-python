from __future__ import annotations

import asyncio
import json
import os

import dicehub as dh


async def main() -> None:
    async with dh.AsyncClient(api_key=os.environ["DICEHUB_API_KEY"]) as client:
        context = await client.auth.context()
        print(json.dumps(context.model_dump(mode="json"), ensure_ascii=True))


if __name__ == "__main__":
    asyncio.run(main())
