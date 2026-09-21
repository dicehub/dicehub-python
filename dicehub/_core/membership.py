from enum import Enum


class MembershipVisibility(str, Enum):
    HIDDEN = "HIDDEN"
    PRIVATE = "PRIVATE"
    PUBLIC = "PUBLIC"
