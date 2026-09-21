"""Verify an API key supplied by the execution environment."""

from __future__ import annotations

import os

import dicehub as dh


def main() -> None:
    with dh.Client(api_key=os.environ["DICEHUB_API_KEY"]) as client:
        print(client.auth.context().identity_mode.value)


if __name__ == "__main__":
    main()
