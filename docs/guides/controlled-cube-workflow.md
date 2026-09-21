---
title: Controlled cube end-to-end example
description: Create a temporary OpenFOAM meshing app, run it locally, and validate its result ZIP.
read_when:
  - Testing project, app, configuration, run, and result-download automation together
  - Building an OpenFOAM STL workflow with a managed API key
  - Running the charged controlled-cube integration example
---

# Controlled cube end-to-end example

[`examples/controlled_cube_workflow.py`](../../examples/controlled_cube_workflow.py) is a complete,
deterministic automation workflow built only from public dicehub SDK operations. It creates a
temporary private project, meshes a generated watertight one-metre cube with the current
snappyHexMesh OpenFOAM template, validates the downloaded result ZIP, and attempts bounded cleanup
of the exact run and project IDs in a `finally` block.

The example is intentionally live, mutating, and double opt-in. A run may consume quota, use local
compute, or incur charges. Use a disposable development account. The normal test suite never
enables it.

## The six steps

1. Resolve the exact `/templates/openfoam_snappyhexmesh` route, create a uniquely named private
   project in the API key's personal scope, create a snappyHexMesh app from the returned immutable
   template ID, and resolve its single default configuration.
2. Upload the embedded ASCII STL to
   `case/constant/triSurface/cube.stl`. The STL contains twelve consistently wound triangles and no
   external file dependency. Call the fixed `client.configs.import_geometry()` operation for the
   bare `cube.stl` filename. The returned `GeometryImportRuns` contains the conversion run and, for
   this first geometry, the required setup run. Poll conversion to `FINISHED` first. dicehub starts
   the queued setup only after conversion succeeds, then the example polls setup to `FINISHED`.
   The client cannot submit either run's module, flow, queue, environment, or storage mappings.
3. Read and validate all server-generated outputs. `geometry/cube.stl.yaml` must contain unit-cube
   bounds, a non-empty `cube` region, and a renderable VTP collection. The exact
   `VTK/cube.stl/cube.vtp` download has a 1 MiB ceiling and must contain the 36 finite points and 12
   facets from the STL. The generated background mesh must have bounds `[-0.3, -0.3, 0.0]` to
   `[1.3, 1.3, 1.3]`, `10 × 10 × 10` cells, material point
   `[-0.275, -0.275, 1.275]`, and finite configuration-camera values. These checks prove that the
   setup run replaced the untouched template defaults.
4. Change only the generated geometry's surface refinement from `[0, 0]` to `[1, 1]`, its feature
   refinement from `[0, 0]` to `[0, 1]`, and `sceneSettings.config.camera.roll` to `15.0` degrees.
   Each narrow update is read back byte-for-byte and revalidated. The example does not author its
   own background mesh, material point, or camera position. Camera roll changes only the viewer.
5. Start the exact default configuration on machine type `local`, with one node, one CPU, and
   `notify=False`.
6. Poll the exact returned run UUID to a finite monotonic deadline. Only `FINISHED` proceeds to one
   bounded result-ZIP download. The example validates safe member names and CRCs without extracting
   anything, rejects `VTK` members, requires a non-empty
   `case/constant/polyMesh/boundary`, and requires the `case/project.foam` marker. The `case/`
   prefix is retained from the OpenFOAM runner's result-upload target.

`yaml2foam` deliberately creates `project.foam` as an empty ParaView marker, so the
`case/project.foam` member's presence—not a non-zero size—is the correct invariant. The OpenFOAM
boundary dictionary must contain data.

## Required API-key permissions

Create one managed API key in the signed-in user's personal namespace with exactly the capabilities
needed by this combined example:

| Permission | Use in the example |
| --- | --- |
| `CREATE_USER_PROJECT` | Create the temporary personal project |
| `DELETE_PROJECT` | Delete that exact project in cleanup |
| `CREATE_APP` | Instantiate the snappyHexMesh template |
| `VIEW_CONFIG_INFO` | Resolve the app's default configuration |
| `VIEW_CONFIG_CONTENT` | Validate generated geometry, domain, material, and camera resources |
| `EDIT_CONFIG_CONTENT` | Upload/import the STL and update refinement and camera roll |
| `START_RUN` | Start the two server-owned import stages and one local mesh run |
| `STOP_RUN` | Stop an exact active conversion, setup, or mesh run during cleanup |
| `VIEW_RUN_INFO` | Poll each returned run UUID's lifecycle status |
| `DOWNLOAD_RUN_RESULT` | Download only its result ZIP |

These ten grants remain independent. In particular, `VIEW_RUN_INFO` does not expose results, and
`DOWNLOAD_RUN_RESULT` does not grant lifecycle metadata or run mutation. `STOP_RUN` is required
because dicehub rejects project deletion while a descendant app is running.

No additional managed-key grant is needed to resolve the installed public template route. Template
discovery returns metadata only; `CREATE_APP` remains the separate authorization for instantiation.

The key must be personal-scoped because a project-scoped key cannot create a sibling project, and a
group-scoped key creates group projects rather than the personal project used here. The script
creates no API key and never receives a session cookie.

## Environment and run command

Install the repository's development environment first. The SDK resolves the stable
`/templates/openfoam_snappyhexmesh` route through its fixed typed template query before creating
anything; no deployment-specific numeric template ID is required.

From the repository root:

```bash
read -rsp "dicehub API key: " DICEHUB_API_KEY && export DICEHUB_API_KEY
printf '\n'

export DICEHUB_CONTROLLED_CUBE_RESULT_ZIP="$PWD/controlled-cube-results.zip"
export DICEHUB_RUN_TIMEOUT_SECONDS=1800
export DICEHUB_RUN_POLL_SECONDS=5
export DICEHUB_RUN_STOP_TIMEOUT_SECONDS=300

# Both flags are required because this creates data and starts compute.
export DICEHUB_LIVE_TEST=1
export DICEHUB_LIVE_CONTROLLED_CUBE_TEST=1

python -m examples.controlled_cube_workflow

unset DICEHUB_API_KEY DICEHUB_LIVE_CONTROLLED_CUBE_TEST DICEHUB_LIVE_TEST
```

The SDK connects to `https://dicehub.com` by default.

The result parent directory must already exist, and the destination itself must not exist. The
example caps both the streamed ZIP and its declared uncompressed members at 512 MiB, well below the
SDK's 2 GiB hard ceiling. The controlled cube should be much smaller.

The same lifecycle is wired into pytest but remains double opt-in:

```bash
pytest tests/integration/test_live_controlled_cube.py -vv
```

The test chooses a temporary local ZIP path. It uses the same environment-provided key and calls
the same public example entry point.

## Expected output

The program writes newline-delimited JSON progress. IDs below are illustrative:

```json
{"event":"0_template_resolved","route":"/templates/openfoam_snappyhexmesh","template_id":"12"}
{"event":"1_project_created","project_id":"401"}
{"app_id":"402","config_id":"403","event":"1_app_created"}
{"bytes":1423,"event":"2_cube_uploaded"}
{"event":"3_geometry_conversion_started","run_id":"12345678-1234-5678-9234-567812345678","state":"PREPARING"}
{"event":"3_geometry_setup_queued","run_id":"23456781-2345-6789-9234-567812345678","state":"IDLE"}
{"event":"3_geometry_conversion_status","run_id":"12345678-1234-5678-9234-567812345678","state":"FINISHED"}
{"event":"3_geometry_setup_status","run_id":"23456781-2345-6789-9234-567812345678","state":"FINISHED"}
{"bounds_max":[1.3,1.3,1.3],"bounds_min":[-0.3,-0.3,0.0],"cells":[10,10,10],"event":"3_geometry_import_validated","material_point":[-0.275,-0.275,1.275],"path":"geometry/cube.stl.yaml","vtp_path":"VTK/cube.stl/cube.vtp"}
{"event":"4_refinement_configured","feature_levels":[0,1],"path":"geometry/cube.stl.yaml","surface_level":[1,1]}
{"event":"4_camera_rotated","path":"sceneSettings.yaml","roll_degrees":15.0,"scene":"config"}
{"event":"5_run_started","run_id":"87654321-4321-6789-9234-567812345678","state":"PREPARING"}
{"event":"6_run_status","run_id":"87654321-4321-6789-9234-567812345678","state":"RUNNING"}
{"event":"6_run_status","run_id":"87654321-4321-6789-9234-567812345678","state":"FINISHED"}
{"boundary_bytes":1234,"destination":"/work/controlled-cube-results.zip","event":"6_results_validated","members":42,"project_foam_bytes":0,"run_id":"87654321-4321-6789-9234-567812345678","uncompressed_bytes":56789}
{"event":"cleanup_project_deleted","project_id":"401"}
```

The local result ZIP remains after server cleanup. The temporary project, app, configuration, runs,
and server-side data are deleted with the project.

## Safety and ambiguous mutations

- Credentials come only from environment variables. The API key is excluded from settings
  representations, progress, errors, and output. The public template route and returned metadata
  are safe to emit.
- The script never invokes a shell, derives a local path from server data, extracts the ZIP, follows
  archive member paths, or executes returned content.
- Every mutation is sent once. `MUTATION_OUTCOME_UNKNOWN` is converted into a reconciliation message
  naming the unique project marker or exact known IDs and paths. It is never retried automatically.
- The conversion, queued setup, and mesh run IDs are tracked separately. After an error, timeout,
  or interruption, cleanup resolves conversion first, then setup, then mesh. It sends at most one
  stop request for each active run and polls for a terminal state for at most
  `DICEHUB_RUN_STOP_TIMEOUT_SECONDS`. It does not stop an `IDLE` setup directly; it waits for the
  queue to cancel it after an unsuccessful conversion. An ambiguous stop is reconciled through
  status reads and is not replayed.
- A run may finish between the cleanup status read and stop request. If stop returns an error,
  cleanup reads that exact run once more; a confirmed terminal state permits project deletion,
  while any other result preserves the project for manual reconciliation.
- Cleanup calls delete only for the immutable project ID returned by this invocation. It never
  searches by a broad prefix and never deletes a pre-existing project. Project deletion is skipped
  unless the known run is confirmed terminal, because deleting an active project is unsupported.
- If cleanup itself has an unknown outcome, stderr reports the exact project ID. Do not replay the
  deletion blindly; inspect that ID with a separately authorized identity first.
- If geometry import or mesh start has an unknown outcome before returning its run UUIDs, cleanup
  preserves the project and emits its exact ID. Reconcile the project's run history; do not start
  another run or delete the project blindly.
- A forced process kill, host loss, or unreachable server can prevent `finally` cleanup. Record the
  emitted project ID before investigating or manually removing anything.

## Troubleshooting

`API_ERROR` during setup usually means the key is missing one of the ten grants or the current
deployment does not expose the required template route to that credential. Fix the key or template
installation; do not broaden unrelated permissions.

If the new app does not expose exactly one default configuration, the script stops before content
mutation and deletes the project. Confirm that the selected template is the current
`openfoam_snappyhexmesh` template.

The fresh app must return a non-null setup run. A null setup run is valid for later imports because
dicehub preserves an already tuned domain and camera, but it is an error in this new-app example.

`FAILED`, `STOPPED`, `INTERRUPTED`, or `CANCELED` is terminal and never downloads results. Cleanup
may delete the project immediately because the run is already terminal. For slow local runners,
increase `DICEHUB_RUN_TIMEOUT_SECONDS` up to 14400; the deadline always remains finite.

If bounded stop reconciliation fails, cleanup emits the exact run ID, skips project deletion, and
emits the original error. Reconcile the run and project IDs before retrying any mutation. A forced
process kill, host loss, or unreachable server can likewise leave resources behind.

An archive-validation error means the result is incomplete, corrupt, unexpectedly contains VTK, or
lacks the OpenFOAM mesh contract. The partial or invalid local ZIP is retained only when download
completed; inspect it as untrusted data without extraction. Server cleanup still runs.
