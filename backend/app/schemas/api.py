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
    id:int; username:str; display_name:str; email:str; is_admin:bool; is_super_admin:bool=False; is_active:bool=True; team_id:int|None=None
    class Config: from_attributes=True

class MemberCreate(BaseModel):
    display_name:str=Field(min_length=1); email:EmailStr; username:str|None=None; password:str|None=None; is_admin:bool=False; team_id:int|None=None
class MemberUpdate(BaseModel): active: bool|None=None; display_name:str|None=None; email:EmailStr|None=None
class MemberOut(BaseModel):
    id:int; display_name:str; email:str; active:bool; created_at:datetime
    class Config: from_attributes=True
class QuarterOut(BaseModel):
    id:int; year:int; quarter:int; label:str; generated_at:datetime; is_active:bool; is_completed:bool; status:str="draft"; published_at:datetime|None=None; published_by_admin_id:int|None=None
    class Config: from_attributes=True
class PlanOut(BaseModel):
    id:int; quarter_id:int; from_member_id:int|None=None; to_member_id:int|None=None; from_participant_id:int|None=None; to_participant_id:int|None=None; from_name:str; to_name:str; amount:int; acknowledged:bool=False
class GenerateIn(BaseModel): year:int|None=None; quarter:int|None=None; preview:bool=False; seed:int|None=None
class OverviewOut(BaseModel): total_members:int; active_quarter:str|None; completion_rate:float; total_sent:int; total_planned:int
class UserAdminOut(BaseModel):
    id:int; username:str; display_name:str; email:str; is_admin:bool; is_super_admin:bool=False; is_active:bool; created_at:datetime; last_login_at:datetime|None=None; team_id:int|None=None; team_name:str|None=None
    class Config: from_attributes=True
class UserRoleUpdate(BaseModel): is_admin:bool
class UserTeamUpdate(BaseModel): team_id:int|None=None
class UserAdminUpdate(BaseModel):
    username:str|None=None
    display_name:str|None=None
    email:EmailStr|None=None
    is_admin:bool|None=None
    is_super_admin:bool|None=None
    is_active:bool|None=None
    password:str|None=Field(default=None, min_length=8)

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

class ParticipantCreate(BaseModel):
    display_name:str=Field(min_length=1, max_length=160)
    slug:str|None=None
    notes:str|None=None
    is_active:bool=True

    @field_validator("display_name", "slug")
    @classmethod
    def clean_text(cls, v):
        return v.strip() if isinstance(v, str) else v

class ParticipantBulkCreate(BaseModel): names:str=Field(min_length=1)
class ParticipantUpdate(BaseModel):
    display_name:str|None=Field(default=None, min_length=1, max_length=160)
    slug:str|None=None
    notes:str|None=None
    is_active:bool|None=None

class ParticipantOut(BaseModel):
    id:int; display_name:str; slug:str; is_active:bool; notes:str|None=None; created_at:datetime; updated_at:datetime
    public_url:str|None=None; included_in_current_quarter:bool=False
    class Config: from_attributes=True

class ParticipantBulkOut(BaseModel):
    created:list[ParticipantOut]
    duplicates:list[str]
    invalid:list[str]=[]
    ignored_blank_lines:int
    created_count:int=0
    duplicate_count:int=0
    invalid_count:int=0
    message:str=""

class CompatibilityRuleIn(BaseModel):
    from_participant_id:int
    to_participant_id:int
    is_allowed:bool=True
    mutual:bool=True

class CompatibilityRuleOut(BaseModel):
    id:int; from_participant_id:int; to_participant_id:int; is_allowed:bool; created_at:datetime; updated_at:datetime
    class Config: from_attributes=True

class CompatibilityBulkIn(BaseModel):
    from_participant_ids:list[int]
    to_participant_ids:list[int]
    is_allowed:bool=True
    mutual:bool=True

class CompatibilityCopyIn(BaseModel): source_participant_id:int; target_participant_id:int

class CompatibilityGroupIn(BaseModel): name:str=Field(min_length=1); notes:str|None=None; participant_ids:list[int]=[]
class CompatibilityGroupOut(BaseModel): id:int; name:str; notes:str|None=None; participant_ids:list[int]=[]

class QuarterCreateIn(BaseModel):
    year:int
    quarter:int=Field(ge=1, le=4)
    label:str|None=None
    allocation_min:int=10
    allocation_max:int=50
    preferred_min_recipients:int=2
    preferred_max_recipients:int=3

class QuarterParticipantsIn(BaseModel): participant_ids:list[int]
class QuarterGenerateIn(BaseModel): seed:int|None=None
class AllocationEditIn(BaseModel): from_participant_id:int; to_participant_id:int; amount:int

class AdminInvitationCreate(BaseModel):
    invitee_name:str=Field(min_length=1, max_length=160)
    invitee_email:EmailStr|None=None
    # 0 means never expires; otherwise choose an explicit period such as 24, 48, 168, 720 or 8760 hours.
    expires_in_hours:int=Field(default=168, ge=0, le=876000)

class AdminInvitationOut(BaseModel):
    id:int; invitee_name:str; invitee_email:str|None=None; created_by_admin_id:int|None=None; created_by_name:str|None=None; created_at:datetime; expires_at:datetime; used_at:datetime|None=None; revoked_at:datetime|None=None; status:str; expires_label:str|None=None

class AdminInvitationCreated(AdminInvitationOut):
    token:str
    invitation_url:str

class AdminInvitationPublic(BaseModel):
    invitee_name:str; invitee_email:str|None=None; expires_at:datetime; status:str

class AdminInvitationAccept(BaseModel):
    display_name:str=Field(min_length=1)
    username:str=Field(min_length=1)
    email:EmailStr
    password:str=Field(min_length=8)
    password_confirm:str=Field(min_length=8)

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
