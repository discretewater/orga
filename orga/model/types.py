from enum import Enum

class WarningSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"

class SourceKind(str, Enum):
    HTTP_FETCH = "http_fetch"
    LOCAL_FIXTURE = "local_fixture"
    USER_SUPPLIED = "user_supplied"
    BROWSER_FETCH = "browser_fetch"

class ContactKind(str, Enum):
    PHONE = "phone"
    EMAIL = "email"
    SOCIAL = "social"
    CONTACT_FORM = "contact_form"
    WEBSITE = "website"
    MAP_LINK = "map_link"
