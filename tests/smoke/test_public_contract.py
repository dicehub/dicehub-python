from __future__ import annotations

import subprocess
import sys
from importlib.metadata import distribution
from pathlib import Path

import dicehub
from dicehub.api_keys import ApiKey, ApiKeyStatus, ApiKeyValidityStatus
from dicehub.apps import (
    App,
    AppDetail,
    AppMemberTeam,
    AppMemberUser,
    AppOrderField,
    AppPage,
    AppRole,
    AppTeamMembership,
    AppTeamMembershipPage,
    AppUserMembership,
    AppUserMembershipPage,
)
from dicehub.auth import AuthContext
from dicehub.cli import app, main
from dicehub.configs import (
    Config,
    ConfigPage,
    ConfigValueUpdate,
    GeometryImportRuns,
)
from dicehub.groups import (
    Group,
    GroupDetail,
    GroupMemberTeam,
    GroupMemberUser,
    GroupOrderField,
    GroupPage,
    GroupRole,
    GroupTeamMembership,
    GroupTeamMembershipPage,
    GroupUserMembership,
    GroupUserMembershipPage,
    MembershipVisibility,
)
from dicehub.projects import (
    Project,
    ProjectDetail,
    ProjectMemberTeam,
    ProjectMemberUser,
    ProjectOrderField,
    ProjectRole,
    ProjectTeamMembership,
    ProjectTeamMembershipPage,
    ProjectUserMembership,
    ProjectUserMembershipPage,
    SortOrder,
)
from dicehub.resources import Resource, ResourcePage, ResourceType
from dicehub.runs import (
    MachinePrice,
    MachineType,
    Run,
    RunDetail,
    RunFailedError,
    RunPage,
    RunResultS3Credentials,
    RunState,
    RunStatus,
    RunTimeoutError,
)
from dicehub.storage import DownloadReceipt, UploadReceipt
from dicehub.teams import Team
from dicehub.templates import Template, TemplatePage
from dicehub.users import MembershipCandidate, User


def test_editable_console_entry_point_and_public_exports() -> None:
    executable = Path(sys.executable).with_name("dicehub")

    assert executable.is_file()
    result = subprocess.run(
        [executable, "--help"],
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode == 0
    assert result.stderr == ""
    assert "auth" in result.stdout
    assert "api-key" in result.stdout
    assert distribution("dicehub-python").metadata["Name"] == "dicehub-python"
    assert ApiKeyStatus is dicehub.ApiKeyStatus
    assert dicehub.ApiKeyStatus.ACTIVE.value == "ACTIVE"
    assert ApiKeyValidityStatus is dicehub.ApiKeyValidityStatus
    assert dicehub.ApiKeyValidityStatus.EXPIRED.value == "EXPIRED"
    assert App is dicehub.App
    assert AppDetail is dicehub.AppDetail
    assert AppMemberTeam is dicehub.AppMemberTeam
    assert AppMemberUser is dicehub.AppMemberUser
    assert AppOrderField is dicehub.AppOrderField
    assert AppPage is dicehub.AppPage
    assert AppRole is dicehub.AppRole
    assert AppTeamMembership is dicehub.AppTeamMembership
    assert AppTeamMembershipPage is dicehub.AppTeamMembershipPage
    assert AppUserMembership is dicehub.AppUserMembership
    assert AppUserMembershipPage is dicehub.AppUserMembershipPage
    assert Config is dicehub.Config
    assert ConfigPage is dicehub.ConfigPage
    assert ConfigValueUpdate is dicehub.ConfigValueUpdate
    assert GeometryImportRuns is dicehub.GeometryImportRuns
    assert Group is dicehub.Group
    assert GroupDetail is dicehub.GroupDetail
    assert GroupOrderField is dicehub.GroupOrderField
    assert GroupPage is dicehub.GroupPage
    assert GroupMemberTeam is dicehub.GroupMemberTeam
    assert GroupMemberUser is dicehub.GroupMemberUser
    assert GroupRole is dicehub.GroupRole
    assert GroupTeamMembership is dicehub.GroupTeamMembership
    assert GroupTeamMembershipPage is dicehub.GroupTeamMembershipPage
    assert GroupUserMembership is dicehub.GroupUserMembership
    assert GroupUserMembershipPage is dicehub.GroupUserMembershipPage
    assert MembershipVisibility is dicehub.MembershipVisibility
    assert MembershipVisibility.PRIVATE.value == "PRIVATE"
    assert dicehub.NamespacePermission.DELETE_CONFIG.value == "DELETE_CONFIG"
    assert dicehub.NamespacePermission.START_RUN.value == "START_RUN"
    assert dicehub.NamespacePermission.STOP_RUN.value == "STOP_RUN"
    assert dicehub.NamespacePermission.DOWNLOAD_RUN_RESULT.value == "DOWNLOAD_RUN_RESULT"
    assert dicehub.NamespacePermission.VIEW_PUBLIC_APP_MEMBERS.value == ("VIEW_PUBLIC_APP_MEMBERS")
    assert dicehub.NamespacePermission.VIEW_PRIVATE_APP_MEMBERS.value == (
        "VIEW_PRIVATE_APP_MEMBERS"
    )
    assert dicehub.NamespacePermission.MANAGE_APP_MEMBERS.value == "MANAGE_APP_MEMBERS"
    assert dicehub.NamespacePermission.VIEW_RUN_INFO.value == "VIEW_RUN_INFO"
    assert dicehub.NamespacePermission.VIEW_CONFIG_INFO.value == "VIEW_CONFIG_INFO"
    assert dicehub.NamespacePermission.VIEW_USER_PROFILE.value == "VIEW_USER_PROFILE"
    assert dicehub.NamespacePermission.CREATE_SUBGROUP.value == "CREATE_SUBGROUP"
    assert dicehub.NamespacePermission.DELETE_GROUP.value == "DELETE_GROUP"
    assert dicehub.NamespacePermission.MANAGE_GROUP_MEMBERS.value == "MANAGE_GROUP_MEMBERS"
    assert ApiKey is dicehub.ApiKey
    assert AuthContext is dicehub.AuthContext
    assert Project is dicehub.Project
    assert ProjectDetail is dicehub.ProjectDetail
    assert ProjectMemberTeam is dicehub.ProjectMemberTeam
    assert ProjectMemberUser is dicehub.ProjectMemberUser
    assert ProjectOrderField is dicehub.ProjectOrderField
    assert ProjectRole is dicehub.ProjectRole
    assert ProjectTeamMembership is dicehub.ProjectTeamMembership
    assert ProjectTeamMembershipPage is dicehub.ProjectTeamMembershipPage
    assert ProjectUserMembership is dicehub.ProjectUserMembership
    assert ProjectUserMembershipPage is dicehub.ProjectUserMembershipPage
    assert SortOrder is dicehub.SortOrder
    assert MachinePrice is dicehub.MachinePrice
    assert MachineType is dicehub.MachineType
    assert Run is dicehub.Run
    assert RunDetail is dicehub.RunDetail
    assert RunFailedError is dicehub.RunFailedError
    assert RunPage is dicehub.RunPage
    assert RunResultS3Credentials is dicehub.RunResultS3Credentials
    assert RunState is dicehub.RunState
    assert RunStatus is dicehub.RunStatus
    assert RunTimeoutError is dicehub.RunTimeoutError
    assert Resource is dicehub.Resource
    assert ResourcePage is dicehub.ResourcePage
    assert ResourceType is dicehub.ResourceType
    assert ResourceType.FILE.value == "FILE"
    assert DownloadReceipt is dicehub.DownloadReceipt
    assert UploadReceipt is dicehub.UploadReceipt
    assert Template is dicehub.Template
    assert TemplatePage is dicehub.TemplatePage
    assert Team is dicehub.Team
    assert dicehub.SelectorResolutionError.code == "SELECTOR_RESOLUTION_ERROR"
    assert dicehub.MutationOutcomeUnknownError.code == "MUTATION_OUTCOME_UNKNOWN"
    assert MembershipCandidate is dicehub.MembershipCandidate
    assert User is dicehub.User
    assert callable(app)
    assert callable(main)
    expected_version = Path(__file__).parents[2].joinpath("VERSION").read_text().strip()
    assert dicehub.__version__ == expected_version
