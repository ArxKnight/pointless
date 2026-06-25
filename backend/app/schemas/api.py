from datetime import datetime
from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

HEX_COLOUR = r"^#[0-9A-Fa-f]{6}$"

class LoginIn(BaseModel): username: str; password: str

class TeamGroupBrief(BaseModel):
    id:int; name:str; description:str|None=None; display_order:int; is_active:bool
    class Config: from_attributes=True

class TeamBrief(BaseModel):
    id:int; name:str; description:str|None=None; colour:str; display_order:int; is_active:bool; group_id:int|None=None; group_name:str|None=None
    class Config: from_attributes=True

class UserOut(BaseModel):
    id:int; username:str; display_name:str; email:str; is_admin:bool; team_id:int|None=None
    class Config: from_attributes=True

class MemberCreate(BaseModel):
    display_name:str=Field(min_length=1); email:EmailStr; username:str|None=None; password:str|None=None; is_admin:bool=False; team_id:int|None=None
class MemberUpdate(BaseModel): active: bool|None=None; display_name:str|None=None; email:EmailStr|None=None
class MemberOut(BaseModel):
    id:int; display_name:str; email:str; active:bool; created_at:datetime
    class Config: from_attributes=True
class QuarterOut(BaseModel):
    id:int; year:int; quarter:int; label:str; generated_at:datetime; is_active:bool; is_completed:bool
    class Config: from_attributes=True
class PlanOut(BaseModel):
    id:int; quarter_id:int; from_member_id:int; to_member_id:int; from_name:str; to_name:str; amount:int; acknowledged:bool
class GenerateIn(BaseModel): year:int|None=None; quarter:int|None=None; preview:bool=False; seed:int|None=None
class OverviewOut(BaseModel): total_members:int; active_quarter:str|None; completion_rate:float; total_sent:int; total_planned:int
class UserAdminOut(BaseModel):
    id:int; username:str; display_name:str; email:str; is_admin:bool; is_active:bool; created_at:datetime; team_id:int|None=None; team_name:str|None=None
    class Config: from_attributes=True
class UserRoleUpdate(BaseModel): is_admin:bool
class UserTeamUpdate(BaseModel): team_id:int|None=None

class TeamGroupBase(BaseModel):
    name:str=Field(min_length=1, max_length=120)
    description:str|None=None
    display_order:int=0
    is_active:bool=True

    @field_validator("name")
    @classmethod
    def clean_group_name(cls, v:str):
        v=v.strip()
        if not v: raise ValueError("Group name is required")
        return v

class TeamGroupCreate(TeamGroupBase): pass
class TeamGroupUpdate(BaseModel):
    name:str|None=Field(default=None, min_length=1, max_length=120)
    description:str|None=None
    display_order:int|None=None
    is_active:bool|None=None

    @field_validator("name")
    @classmethod
    def clean_group_update_name(cls, v:str|None):
        if v is None: return v
        v=v.strip()
        if not v: raise ValueError("Group name is required")
        return v

class TeamGroupOut(TeamGroupBase):
    id:int; created_at:datetime; updated_at:datetime; team_count:int=0; user_count:int=0; teams:list[TeamBrief]=[]
    class Config: from_attributes=True

class TeamBase(BaseModel):
    name:str=Field(min_length=1, max_length=120)
    description:str|None=None
    colour:str=Field(default="#6366f1", pattern=HEX_COLOUR)
    display_order:int=0
    is_active:bool=True
    group_id:int|None=None

    @field_validator("name")
    @classmethod
    def clean_team_name(cls, v:str):
        v=v.strip()
        if not v: raise ValueError("Team name is required")
        return v

class TeamCreate(TeamBase): pass
class TeamUpdate(BaseModel):
    name:str|None=Field(default=None, min_length=1, max_length=120)
    description:str|None=None
    colour:str|None=Field(default=None, pattern=HEX_COLOUR)
    display_order:int|None=None
    is_active:bool|None=None
    group_id:int|None=None

    @field_validator("name")
    @classmethod
    def clean_team_update_name(cls, v:str|None):
        if v is None: return v
        v=v.strip()
        if not v: raise ValueError("Team name is required")
        return v

class TeamDeleteIn(BaseModel):
    move_users_to_team_id:int|None=None

class TeamOut(TeamBase):
    id:int; created_at:datetime; updated_at:datetime; group_name:str|None=None; user_count:int=0
    class Config: from_attributes=True

class TeamMemberUserOut(BaseModel):
    id:int; username:str; display_name:str; email:str; is_admin:bool; is_active:bool; team_id:int|None=None
    class Config: from_attributes=True

class InstallDatabaseIn(BaseModel):
    host: str = "mysql"
    port: int = 3306
    database: str = "pointsdb"
    username: str = "pointsapp"
    password: str

class InstallAdminIn(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=8)
    display_name: str = Field(min_length=1)
    email: EmailStr

class InstallIn(BaseModel):
    database: InstallDatabaseIn
    reuse_existing_database: bool = False
    admin: InstallAdminIn | None = None

    @model_validator(mode="after")
    def require_admin_unless_reusing(self):
        if not self.reuse_existing_database and self.admin is None:
            raise ValueError("Admin details are required when not reusing an existing database")
        return self
