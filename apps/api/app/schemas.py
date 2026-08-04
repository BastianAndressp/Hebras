from datetime import date, datetime
from uuid import UUID
from pydantic import BaseModel, Field


class BotUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    phone_number_id: str | None = None
    system_prompt: str = Field(min_length=20, max_length=12000)
    model: str = Field(default="deepseek/deepseek-chat", max_length=120)
    fallback_model: str | None = Field(default=None, max_length=120)
    temperature: float = Field(default=0.4, ge=0, le=1)
    max_tokens: int = Field(default=400, ge=50, le=500)



class HandoffRuleUpdate(BaseModel):
    keywords: list[str] = Field(default_factory=list, max_length=30)
    max_bot_attempts: int = Field(default=2, ge=1, le=10)
    notification_email: str | None = None
    ai_handoff_phrase: str | None = Field(default=None, max_length=300)


class BotResponse(BotUpdate):
    id: UUID
    company_id: UUID
    phone_number_id: str
    status: str


class BotCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    phone_number_id: str = Field(min_length=5, max_length=32)
    system_prompt: str = Field(
        default="Eres un asistente de atención al cliente amable y profesional. Responde en español.",
        min_length=20,
        max_length=12000,
    )


class ConversationResponse(BaseModel):
    id: UUID
    contact_phone: str
    status: str
    last_message_at: datetime
    messages: list[dict]


class ConversationStatusUpdate(BaseModel):
    status: str = Field(pattern="^(active|handoff|closed)$")


class ManualMessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=4096)



class AuditLogResponse(BaseModel):
    id: UUID
    actor_id: UUID | None
    action: str
    created_at: datetime


class TeamMemberResponse(BaseModel):
    id: UUID
    user_id: UUID
    role: str
    created_at: datetime


class TeamMemberCreate(BaseModel):
    user_id: UUID
    role: str = Field(pattern="^(owner|staff|solo-lectura)$")


class TeamMemberUpdate(BaseModel):
    role: str = Field(pattern="^(owner|staff|solo-lectura)$")


class PlanResponse(BaseModel):
    id: UUID
    slug: str
    name: str
    monthly_message_limit: int
    price_amount: float
    currency: str
    is_active: bool


class SubscriptionResponse(BaseModel):
    id: UUID
    status: str
    trial_ends_at: datetime | None = None
    days_remaining: int | None = None
    current_period_start: date
    current_period_end: date
    plan: PlanResponse


class SubscriptionUpdate(BaseModel):
    plan_id: str


class BillingOverviewResponse(BaseModel):
    subscription: SubscriptionResponse | None
    plans: list[PlanResponse]
    monthly_message_limit: int
    messages_used: int
    estimated_cost_usd: float
    total_conversations: int


class DocumentCreate(BaseModel):
    title: str = Field(min_length=1, max_length=140)
    content: str = Field(min_length=1, max_length=20000)


class DocumentUploadResponse(BaseModel):
    id: UUID
    title: str
    status: str
    chunk_count: int
    created_at: datetime


class DocumentResponse(BaseModel):
    id: UUID
    title: str
    status: str
    chunk_count: int
    created_at: datetime


class SettingsUpdate(BaseModel):
    business_hours_enabled: bool = False
    business_hours: dict = Field(default_factory=dict)
    out_of_hours_message: str = Field(default="Estamos fuera de nuestro horario de atención.")
    monthly_spending_limit_usd: float = Field(default=100.0, ge=0)
    default_language: str = Field(default="es")


class SettingsResponse(SettingsUpdate):
    id: UUID
    company_id: UUID
    bot_id: UUID


class ApiKeysUpdate(BaseModel):
    whatsapp_access_token: str | None = None
    whatsapp_app_secret: str | None = None
    openrouter_api_key: str | None = None


class ApiKeysResponse(BaseModel):
    has_whatsapp_access_token: bool
    has_whatsapp_app_secret: bool
    has_openrouter_api_key: bool


class NotificationResponse(BaseModel):
    id: UUID
    title: str
    message: str
    severity: str
    is_read: bool
    created_at: datetime


class SignUpRequest(BaseModel):
    email: str = Field(min_length=5, max_length=255)
    password: str = Field(min_length=6, max_length=128)
    company_name: str = Field(default="Mi Empresa", min_length=2, max_length=120)


class LoginRequest(BaseModel):
    email: str = Field(min_length=5, max_length=255)
    password: str = Field(min_length=1, max_length=128)


class VerifyEmailRequest(BaseModel):
    email: str = Field(min_length=5, max_length=255)
    code: str = Field(min_length=4, max_length=10)


class ResendCodeRequest(BaseModel):
    email: str = Field(min_length=5, max_length=255)


class ForgotPasswordRequest(BaseModel):
    email: str = Field(min_length=5, max_length=255)


class ResetPasswordRequest(BaseModel):
    email: str = Field(min_length=5, max_length=255)
    code: str = Field(min_length=4, max_length=10)
    new_password: str = Field(min_length=6, max_length=128)


class AuthTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: UUID
    company_id: UUID
    role: str = "owner"


class ServiceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=140)
    duration_minutes: int = Field(gt=0, le=480)
    price: float | None = Field(default=None, ge=0)
    active: bool = True


class ServiceUpdate(ServiceCreate):
    pass


class ServiceResponse(ServiceCreate):
    id: UUID


class AppointmentResponse(BaseModel):
    id: UUID
    service_id: UUID
    customer_name: str
    customer_phone: str
    scheduled_start: datetime
    scheduled_end: datetime
    status: str
    created_at: datetime


