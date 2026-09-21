"""Discover app-template metadata through the public typed SDK."""

from __future__ import annotations

import os

import dicehub as dh


def main() -> None:
    with dh.Client(
        api_key=os.environ["DICEHUB_API_KEY"],
    ) as client:
        page = client.templates.list(
            template_type=dh.TemplateType.APP_TEMPLATE,
            tags=("openfoam",),
            limit=20,
        )

    for template in page.templates:
        print(template.model_dump_json(ensure_ascii=True))


if __name__ == "__main__":
    main()
