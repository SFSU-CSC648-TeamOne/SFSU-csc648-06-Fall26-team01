# List of allowed values for certain fields in the database. 
# These are used to validate input and ensure consistency across the application.
 
from enum import Enum

class UserRole(str, Enum):
    user = "user"
    administrator = "administrator"

class ExperienceLevel(str, Enum):
    beginner = "beginner"
    intermediate = "intermediate"  
    advanced = "advanced"

class ExerciseRole(str, Enum):
    core = "core"
    accessory = "accessory"

class EntryStatus(str, Enum):
    completed = "completed"
    skipped = "skipped"
    substituted = "substituted"

def sql_in(enum_cls: type[Enum]) -> str:
    return ", ".join(f"'{e.value}'" for e in enum_cls)