from datetime import datetime
from pydantic import BaseModel, EmailStr, Field, model_validator

class LoginIn(BaseModel): username: str; password: str
class UserOut(BaseModel):
    id:int; username:str; display_name:str; email:str; is_admin:bool
    class Config: from_attributes=True
class MemberCreate(BaseModel):
    display_name:str=Field(min_length=1); email:EmailStr; username:str|None=None; password:str|None=None; is_admin:bool=False
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
