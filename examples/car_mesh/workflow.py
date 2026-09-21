"""Starting point for automating a snappyHexMesh workflow with dicehub-python.

In this example, we:
  - find the snappyHexMesh template;
  - create a private project and app; and
  - upload and convert the bundled car STL; and
  - create the initial background mesh; and
  - rotate the CONFIG camera so Z is up; and
  - configure the wind-tunnel background mesh; and
  - set edge and surface refinement on the car; and
  - add a box-shaped volume-refinement region; and
  - add three boundary layers to the car; and
  - select one local node with four CPUs; and
  - start the mesh run and wait for it to finish; and
  - download the result ZIP; and
  - optionally download one result file through dicehub S3.

Copy this script and change its names, geometry, settings, and result handling for your own
workflow. The example leaves the project available for browser inspection.
"""

from __future__ import annotations

import os
import tarfile
import uuid
from pathlib import Path
from typing import BinaryIO, cast

import boto3  # type: ignore[import-not-found,import-untyped,unused-ignore]
from botocore.config import Config  # type: ignore[import-not-found,import-untyped,unused-ignore]

import dicehub as dh
from examples.car_mesh.background_mesh import configure_background_mesh
from examples.car_mesh.camera import rotate_config_camera_x
from examples.car_mesh.lifecycle import download_result, result_directory, wait_for_run
from examples.car_mesh.refinement import (
    configure_boundary_layers,
    configure_edge_refinement,
    configure_surface_refinement,
    create_refinement_box,
)
from examples.car_mesh.run_settings import configure_local_run

TEMPLATE_ROUTE = "/templates/openfoam_snappyhexmesh"
STL_FILENAME = "car_01_fixed_ground.stl"
STL_REGION_NAME = "PRO2STL_version_1.0"
STL_ARCHIVE = Path(__file__).parent / "assets" / f"{STL_FILENAME}.tar.gz"
STL_CONFIG_PATH = f"case/constant/triSurface/{STL_FILENAME}"
WIND_TUNNEL_MIN = (-7.49617331, -4.206044949, 0.0)
WIND_TUNNEL_MAX = (10.41749071, 3.415404429, 4.651878025)
BACKGROUND_CELL_SIZE = 0.2
MATERIAL_POINT = (-5.293068583, -0.7532025274, 0.752330886)
EDGE_REFINEMENT_DISTANCE = 0.01
EDGE_REFINEMENT_LEVEL = 1
SURFACE_REFINEMENT_MIN = 2
SURFACE_REFINEMENT_MAX = 2
REFINEMENT_BOX_NAME = "box_0"
REFINEMENT_BOX_MIN = (-3.249233311, -1.550625666, 0.0)
REFINEMENT_BOX_MAX = (4.683932371, 1.733308419, 2.230094484)
REFINEMENT_BOX_LEVEL = 1
BOUNDARY_LAYER_COUNT = 3
BOUNDARY_LAYER_EXPANSION_RATIO = 1.2
BOUNDARY_LAYER_FINAL_THICKNESS = 0.5
BOUNDARY_LAYER_MINIMUM_THICKNESS = 0.01
LOCAL_NODE_COUNT = 1
LOCAL_CPU_COUNT = 4
RESULTS_DIR = Path(os.environ.get("DICEHUB_RESULTS_DIR", "results"))
DOWNLOAD_RESULTS_WITH_S3 = os.environ.get("DICEHUB_DOWNLOAD_RESULTS_WITH_S3") == "1"


def default_config_id(client: dh.Client, app_id: str) -> str:
    """Return the app's default configuration ID."""

    configs = client.configs.list(app_id=app_id, limit=50).configs
    default = next(config for config in configs if config.is_default)
    return default.config_id


def main() -> None:
    base_url = os.environ.get("DICEHUB_URL", "https://dicehub.com")
    api_key = os.environ["DICEHUB_API_KEY"]

    with dh.Client(base_url=base_url, api_key=api_key) as client:
        print("Finding the snappyHexMesh template...")
        template = client.templates.get_by_route(route=TEMPLATE_ROUTE)

        print("Creating a private project and app...")
        project = client.projects.create(
            name="dicehub car mesh",
            slug=f"dicehub-car-mesh-{uuid.uuid4().hex[:8]}",
            description="Created by the dicehub-python car-mesh example",
            visibility=dh.ProjectVisibility.PRIVATE,
        )
        print(f"Created project ID: {project.project_id}")
        print("Keep this ID for cleanup, including after an interrupted or failed workflow.")
        app = client.apps.create(
            project_id=project.project_id,
            template_id=template.template_id,
            name="Car mesh",
            description="Automated snappyHexMesh car workflow",
        )
        config_id = default_config_id(client, app.app_id)
        app_url = f"{base_url.rstrip('/')}/app{app.route}" if app.route is not None else None
        if app_url is not None:
            print(f"App URL: {app_url}")

        print(f"Uploading {STL_FILENAME}...")
        with tarfile.open(STL_ARCHIVE, "r:gz") as archive:
            stl = cast(BinaryIO, archive.extractfile(STL_FILENAME))
            client.configs.upload_file(
                config_id=config_id,
                path=STL_CONFIG_PATH,
                source=stl,
            )

        print("Converting the STL and creating the initial background mesh...")
        imported = client.configs.import_geometry(
            config_id=config_id,
            filename=STL_FILENAME,
        )
        wait_for_run(client, imported.conversion_run.run_id)
        if imported.setup_run is not None:
            wait_for_run(client, imported.setup_run.run_id)

        print("Rotating the CONFIG camera +90 degrees around the X axis...")
        scene_settings = client.configs.get_text(
            config_id=config_id,
            path="sceneSettings.yaml",
        )
        client.configs.set_text(
            config_id=config_id,
            path="sceneSettings.yaml",
            content=rotate_config_camera_x(scene_settings),
        )

        print("Configuring the wind-tunnel background mesh...")
        bounding_box = client.configs.get_text(
            config_id=config_id,
            path="geometry/boundingBox.yaml",
        )
        material_point = client.configs.get_text(
            config_id=config_id,
            path="geometry/materialPoint.yaml",
        )
        bounding_box, material_point = configure_background_mesh(
            bounding_box,
            material_point,
            WIND_TUNNEL_MIN,
            WIND_TUNNEL_MAX,
            BACKGROUND_CELL_SIZE,
            MATERIAL_POINT,
        )
        client.configs.set_text(
            config_id=config_id,
            path="geometry/boundingBox.yaml",
            content=bounding_box,
        )
        client.configs.set_text(
            config_id=config_id,
            path="geometry/materialPoint.yaml",
            content=material_point,
        )

        print("Setting edge refinement on the car...")
        geometry_path = f"geometry/{STL_FILENAME}.yaml"
        geometry = client.configs.get_text(
            config_id=config_id,
            path=geometry_path,
        )
        client.configs.set_text(
            config_id=config_id,
            path=geometry_path,
            content=configure_edge_refinement(
                geometry,
                STL_FILENAME,
                EDGE_REFINEMENT_DISTANCE,
                EDGE_REFINEMENT_LEVEL,
            ),
        )

        print("Setting surface refinement on the car...")
        geometry = client.configs.get_text(
            config_id=config_id,
            path=geometry_path,
        )
        client.configs.set_text(
            config_id=config_id,
            path=geometry_path,
            content=configure_surface_refinement(
                geometry,
                STL_FILENAME,
                SURFACE_REFINEMENT_MIN,
                SURFACE_REFINEMENT_MAX,
            ),
        )

        print("Adding a box-shaped volume-refinement region...")
        client.configs.set_text(
            config_id=config_id,
            path=f"geometry/{REFINEMENT_BOX_NAME}.yaml",
            content=create_refinement_box(
                REFINEMENT_BOX_NAME,
                REFINEMENT_BOX_MIN,
                REFINEMENT_BOX_MAX,
                REFINEMENT_BOX_LEVEL,
            ),
        )

        print("Adding three boundary layers to the car...")
        geometry = client.configs.get_text(
            config_id=config_id,
            path=geometry_path,
        )
        client.configs.set_text(
            config_id=config_id,
            path=geometry_path,
            content=configure_boundary_layers(
                geometry,
                STL_FILENAME,
                STL_REGION_NAME,
                BOUNDARY_LAYER_COUNT,
                BOUNDARY_LAYER_EXPANSION_RATIO,
                BOUNDARY_LAYER_FINAL_THICKNESS,
                BOUNDARY_LAYER_MINIMUM_THICKNESS,
            ),
        )

        print("Selecting one local node with four CPUs...")
        run_settings = client.configs.get_text(
            config_id=config_id,
            path=".dicehub/settings.yaml",
        )
        decomposition = client.configs.get_text(
            config_id=config_id,
            path="decomposeParDict.yaml",
        )
        run_settings, decomposition = configure_local_run(
            run_settings,
            decomposition,
            LOCAL_NODE_COUNT,
            LOCAL_CPU_COUNT,
        )
        client.configs.set_text(
            config_id=config_id,
            path=".dicehub/settings.yaml",
            content=run_settings,
        )
        client.configs.set_text(
            config_id=config_id,
            path="decomposeParDict.yaml",
            content=decomposition,
        )

        print("Starting the mesh run...")
        started = client.runs.start(
            config_id=config_id,
            machine_type_id="local",
            node_count=LOCAL_NODE_COUNT,
            cpu_count=LOCAL_CPU_COUNT,
            notify=False,
        )
        finished = wait_for_run(client, started.run_id)

        print(f"Mesh run {finished.run_id} finished.")
        directory = result_directory(RESULTS_DIR)
        print(f"Downloading results into {directory}...")
        result_zip = download_result(client, finished.run_id, directory)
        print(f"Downloaded results to {result_zip}.")

        if DOWNLOAD_RESULTS_WITH_S3:
            credentials = client.runs.get_result_s3_credentials(
                app_id=app.app_id,
                run_id=finished.run_id,
            )
            s3_destination = directory / "from-s3" / "points"
            s3_destination.parent.mkdir(parents=True, exist_ok=True)
            print(f"Downloading mesh points through S3 to {s3_destination}...")
            s3 = boto3.client(
                "s3",
                endpoint_url=f"{base_url.rstrip('/')}/api/v1/s3",
                region_name="us-east-1",
                aws_access_key_id=credentials.access_key_id.get_secret_value(),
                aws_secret_access_key=credentials.secret_access_key.get_secret_value(),
                config=Config(
                    signature_version="s3v4",
                    s3={"addressing_style": "path"},
                ),
            )
            s3.download_file(
                Bucket=credentials.bucket,
                Key="case/constant/polyMesh/points",
                Filename=str(s3_destination),
            )
            print("S3 download finished.")

        if app_url is not None:
            print(f"Result available in app: {app_url}")
            print("Open the Run step and click Show result to load the mesh.")
        print(f"Delete project {project.project_id} after inspection.")


if __name__ == "__main__":
    main()
