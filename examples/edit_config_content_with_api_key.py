"""Edit config text and an optional file with narrow content permissions."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import dicehub as dh


def main() -> None:
    config_id = os.environ["DICEHUB_CONFIG_ID"]
    text_path = os.environ["DICEHUB_CONFIG_TEXT_PATH"]
    text_source = Path(os.environ["DICEHUB_CONFIG_TEXT_SOURCE"])
    file_path = os.environ.get("DICEHUB_CONFIG_FILE_PATH")
    file_source_value = os.environ.get("DICEHUB_CONFIG_FILE_SOURCE")

    text = text_source.read_text(encoding="utf-8")
    uploaded_file_bytes: int | None = None
    with dh.Client(
        api_key=os.environ["DICEHUB_API_KEY"],
    ) as client:
        try:
            client.configs.set_text(config_id=config_id, path=text_path, content=text)
            if file_path is not None and file_source_value is not None:
                file_source = Path(file_source_value)
                uploaded_file_bytes = file_source.stat().st_size
                with file_source.open("rb") as source:
                    client.configs.upload_file(
                        config_id=config_id,
                        path=file_path,
                        source=source,
                    )
        except dh.MutationOutcomeUnknownError:
            print(
                f"Reconcile config ID {config_id!r} and the requested paths; do not retry.",
                file=sys.stderr,
            )
            raise

    print(
        json.dumps(
            {
                "config_id": config_id,
                "text_path": text_path,
                "file_path": file_path,
                "uploaded_file_bytes": uploaded_file_bytes,
            }
        )
    )


if __name__ == "__main__":
    main()
