# Change Context Document

> **Audience:** An AI agent making autonomous modifications to this codebase.
> **Tone:** Instructional and strict. Follow these rules to prevent breaking changes and preserve system intent.
> **Last Updated:** 2026-01-27

---

## 1. Design Philosophy

This system follows these core design principles. Every change you make must align with them.

### 1.1 Domain-Driven Design (System A)

System A uses a strict layered DDD architecture. The dependency rule flows inward:

```
API (routes/schemas) → Application (services/interfaces) → Domain (entities/events/value objects)
                                                           ↑ NO outward dependencies
```

- **Domain layer** is pure Python. No imports from FastAPI, SQLAlchemy, Redis, or any infrastructure library. Domain entities are `@dataclass` classes that inherit from `Entity` or `AggregateRoot` in `system_a/app/domain/entities/base.py`.
- **Application layer** defines interfaces (ABCs) that infrastructure implements. Services in `application/services/` depend ONLY on interfaces, never on concrete implementations.
- **Infrastructure layer** provides concrete implementations (SQLAlchemy repositories, Redis cache, SMTP email, JWT handling). These are injected via FastAPI's `Depends()` system.
- **API layer** handles HTTP concerns only: request validation (Pydantic schemas), response formatting, and dependency injection wiring. No business logic in route handlers.

### 1.2 Separation of Concerns (Two-Backend Architecture)

System A and System B are independent services with distinct responsibilities:

| System | Responsibility | Database | Port |
|--------|---------------|----------|------|
| **System A** | User auth, site/org management, dashboard APIs, billing, alerts | PostgreSQL (5432) | 8000 |
| **System B** | Device communication, telemetry ingestion, Modbus polling, device registry | TimescaleDB (5433) | 8001 |

**Coupling points (fragile - treat with extreme care):**
- **Shared Redis (6379):** System B writes `device:{serial}:telemetry` keys (TTL 120s). System A reads them. Key format and JSON structure are implicit contracts.
- **System B HTTP API:** System A calls System B to validate/claim devices during registration. The `SystemBClient` in System A must match System B's API contract.
- **Serial number format:** `MMHH-TTNN-NNNN-NNCC` (16 chars). Both systems validate and parse this format independently. Changes to the format require synchronized updates.

### 1.3 Device Serial Number as Universal Identifier

The device serial number (not UUID) is the cross-system identifier. Redis keys, System B API lookups, and telemetry cache all key on serial number. UUIDs are internal to each system's database.

### 1.4 Pakistan Market Context

The system is built for the Pakistan solar energy market. Hardcoded assumptions include:
- Default timezone: `Asia/Karachi` (UTC+5)
- Default currency: `PKR`
- DISCO providers (11 electricity distributors)
- Slab-based tariff billing
- Net metering support
- Phone numbers default to Pakistan format

Do not remove or generalize these defaults without explicit instruction.

### 1.5 Frontend Architecture

The frontend is a React SPA (Vite + TypeScript + Tailwind CSS + shadcn/ui) with:
- Class-based service layer (`frontend/src/api/services/*.service.ts`) exporting singleton instances
- Centralized Axios client with automatic token refresh (`frontend/src/api/client.ts`)
- `@/` path alias resolving to `./src/`
- TypeScript strict null checks are **disabled** (`strictNullChecks: false` in `tsconfig.json`)
- PWA support via `vite-plugin-pwa`

---

## 2. Stability Invariants

These are rules that must NEVER be violated. Breaking any of these will cause system failure or data corruption.

### 2.1 Absolute Invariants

1. **Domain entities must have zero infrastructure imports.** Files under `system_a/app/domain/` must never import from `sqlalchemy`, `fastapi`, `redis`, `pydantic`, `bcrypt`, `jose`, or any external library. Only standard library imports are allowed.

2. **UnitOfWork must be the sole transaction boundary.** All database writes in System A go through `UnitOfWork.commit()`. Never call `session.commit()` directly in route handlers or services. The UoW pattern in `system_a/app/infrastructure/database/unit_of_work.py` manages session lifecycle. **Repositories use `session.flush()` (not `commit()`)** to push changes to the database within the transaction — `commit()` is exclusively the UoW's responsibility.

3. **Repository interfaces must remain abstract.** The ABCs in `system_a/app/application/interfaces/repositories.py` define the contract. Adding a method to an interface REQUIRES implementing it in the corresponding SQLAlchemy repository under `infrastructure/database/repositories/`.

4. **Redis key format is a cross-system contract.** The key pattern `device:{serial}:telemetry` with its JSON structure (defined in `docs/architecture/telemetry-flow-design.md`) must match between System B's writer and System A's reader. Changing either side without updating the other will silently break real-time telemetry.

5. **Serial number validation must be consistent.** Both System A and System B validate serial numbers. The format `MMHH-TTNN-NNNN-NNCC` with modified Luhn check digits is defined in `system_b/app/application/services/serial_number_service.py`. Any change to validation logic must be applied to both systems.

6. **Authentication chain must not be bypassed.** The dependency chain in `system_a/app/api/dependencies.py` is:
   ```
   HTTPBearer → get_current_user → get_current_active_user → RoleChecker
   ```
   Every protected endpoint must use one of these dependencies. Never create alternative auth paths.

7. **ORM models must inherit from `BaseModel`.** All SQLAlchemy models in System A inherit from `BaseModel` (which composes `UUIDMixin`, `TimestampMixin`, `VersionMixin`). This ensures consistent UUID primary keys, `created_at`/`updated_at` timestamps, and optimistic locking via `version`.

8. **Device ownership lifecycle must be respected.** Devices transition: `orphan` → `claimed` (and back via release). A device can only be claimed if its status is `orphan`. A claimed device has `owner_id` and `site_id` set. Violating this state machine causes data inconsistency between System A and System B.

9. **TimescaleDB hypertables must not be altered with standard DDL.** The `telemetry_raw` table in System B is a TimescaleDB hypertable with continuous aggregates. Use TimescaleDB-specific APIs (`add_compression_policy`, `add_retention_policy`) instead of standard `ALTER TABLE`.

10. **Frontend token storage keys must match backend token structure.** The `tokenStorage` object in `frontend/src/api/client.ts` and the `JWTHandler` in `system_a/app/infrastructure/security/jwt_handler.py` must agree on token field names (`access_token`, `refresh_token`).

### 2.2 Database Invariants

- `users.email` has a UNIQUE constraint. Never insert without checking.
- `user_devices.device_serial` has a UNIQUE constraint. One serial = one owner.
- All primary keys are UUID v4, generated by the application (not the database).
- All timestamps are stored in UTC. The database connection sets `SET timezone = 'Asia/Karachi'` for display but storage is always UTC.
- Foreign keys use `ON DELETE CASCADE` for user-owned entities (sites, devices, alerts).

---

## 3. Safe-to-Change Areas

These areas can be modified with normal caution. Changes here are low-risk if you follow existing patterns.

### 3.1 Frontend Components and Pages

- **UI components** in `frontend/src/components/` - styling, layout, new widgets
- **Pages** in `frontend/src/pages/` - new pages, page restructuring
- **Dashboard widgets** - adding new dashboard cards or charts
- **Tailwind classes** and shadcn/ui component usage
- **SVG animations** (e.g., `EnergyFlowDiagram`) - purely visual

### 3.2 New API Endpoints (Additive)

- Adding new route files under `system_a/app/api/v1/` or `system_b/app/api/v1/`
- Adding new query parameters to existing endpoints (if optional with defaults)
- Adding new response fields (backward compatible by definition in JSON)

### 3.3 New Domain Entities and Events

- Creating new entity files under `system_a/app/domain/entities/`
- Adding new domain events under `system_a/app/domain/events/`
- Adding new value objects under `system_a/app/domain/value_objects/`

### 3.4 Logging and Monitoring

- Adjusting log levels, adding log statements
- Adding metrics or health check endpoints
- Modifying `RequestLoggingMiddleware` behavior

### 3.5 Frontend Service Methods (Additive)

- Adding new methods to existing service classes in `frontend/src/api/services/`
- Creating new service files following the same pattern

### 3.6 Configuration Defaults

- Adding new settings fields with defaults to `system_a/app/config.py` or `system_b/app/config.py`
- Adding new environment variables (as long as defaults are provided)

---

## 4. Areas Requiring Extra Validation

Changes to these areas have high blast radius. Validate thoroughly before and after modification.

### 4.1 Critical Files (Changes here affect the entire system)

| File | Risk | Why |
|------|------|-----|
| `system_a/app/api/dependencies.py` | **CRITICAL** | All auth and service injection flows through here. A bug breaks every protected endpoint. |
| `system_a/app/infrastructure/database/unit_of_work.py` | **CRITICAL** | All transactions flow through here. A bug causes data loss or corruption. |
| `system_a/app/infrastructure/database/connection.py` | **CRITICAL** | Database connection pool. A misconfiguration takes down System A entirely. |
| `system_a/app/domain/entities/base.py` | **CRITICAL** | Base classes for ALL domain entities. Changes cascade to every entity. |
| `system_a/app/infrastructure/database/models/base.py` | **CRITICAL** | ORM base model mixins. Changes affect every database table. |
| `system_a/app/main.py` | **HIGH** | App factory, middleware, exception handlers. Affects all requests. |
| `system_b/app/main.py` | **HIGH** | System B app factory and TCP server lifecycle. |
| `system_a/app/infrastructure/cache/telemetry_cache.py` | **HIGH** | Redis reader for real-time telemetry. Must match System B's writer. |
| `frontend/src/api/client.ts` | **HIGH** | All API calls and token management. A bug breaks the entire frontend. |
| `frontend/src/api/config.ts` | **HIGH** | API endpoint definitions. Wrong paths break all API calls. |
| `docker-compose.yml` | **HIGH** | Infrastructure topology. Port or volume changes affect all systems. |

### 4.2 Cross-System Contract Changes

Any change that affects communication between systems requires updating BOTH sides:

- **Redis key names or TTLs** → Update System B writer AND System A reader
- **System B API endpoints** → Update System B routes AND `SystemBClient` in System A
- **Telemetry JSON structure** → Update System B publisher AND System A consumer AND frontend widgets
- **Serial number format** → Update validation in BOTH systems AND frontend input masks
- **Auth token structure** → Update backend JWT handler AND frontend token storage

### 4.3 Database Schema Changes

- Adding columns: Must update ORM model, domain entity, repository mapping, and Pydantic schemas
- Removing columns: Must verify no code references the column (check ORM model, entity, repository, schemas, services)
- Adding tables: Must follow BaseModel pattern, register in `init_db()`, add repository + interface
- TimescaleDB changes in System B: Must use TimescaleDB APIs, not standard DDL

### 4.4 Authentication and Authorization

- Changes to `get_current_user`, `get_current_active_user`, or `RoleChecker`
- Adding or modifying `UserRole` enum values
- Changes to `UserStatus` enum or status transition logic
- JWT token generation, validation, or refresh logic
- Password hashing configuration

---

## 5. Coding and Architectural Patterns

Follow these patterns exactly. Deviating from them will create inconsistency that makes future changes harder.

### 5.1 System A: Adding a New Domain Entity

```python
# 1. Create domain entity (system_a/app/domain/entities/my_entity.py)
@dataclass(kw_only=True)
class MyEntity(AggregateRoot):  # or Entity if not an aggregate root
    name: str
    # ... fields

    def __post_init__(self) -> None:
        self._validate()

    def _validate(self) -> None:
        errors = {}
        if not self.name:
            errors['name'] = ['Name is required']
        if errors:
            raise ValidationException(message="Invalid data", errors=errors)

    @classmethod
    def create(cls, name: str, ...) -> 'MyEntity':
        entity = cls(name=name, ...)
        entity.add_domain_event(MyEntityCreated(entity_id=entity.id))
        return entity
```

### 5.2 System A: Adding a New Repository

```python
# 1. Define interface (system_a/app/application/interfaces/repositories.py)
class MyEntityRepository(Repository[MyEntity], ABC):
    @abstractmethod
    async def find_by_name(self, name: str) -> Optional[MyEntity]:
        pass

# 2. Implement (system_a/app/infrastructure/database/repositories/my_entity_repository.py)
class SQLAlchemyMyEntityRepository(MyEntityRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_id(self, entity_id: UUID) -> Optional[MyEntity]:
        result = await self._session.execute(
            select(MyEntityModel).where(MyEntityModel.id == entity_id)
        )
        model = result.scalar_one_or_none()
        return model.to_domain() if model else None  # Conversion lives on the ORM model

    async def add(self, entity: MyEntity) -> None:
        model = MyEntityModel.from_domain(entity)     # ORM model classmethod
        self._session.add(model)
        await self._session.flush()                    # flush(), NOT commit()

    # ... implement all abstract methods

# 3. Add to UnitOfWork interface AND implementation
# In application/interfaces/unit_of_work.py:
    my_entities: MyEntityRepository
# In infrastructure/database/unit_of_work.py:
    @property
    def my_entities(self) -> SQLAlchemyMyEntityRepository:
        if self._my_entities is None:
            self._my_entities = SQLAlchemyMyEntityRepository(self._session)
        return self._my_entities

# 4. Add to UoW close() to reset reference:
    self._my_entities = None
```

### 5.3 System A: Adding a New API Endpoint

```python
# 1. Create Pydantic schemas (system_a/app/api/schemas/my_schemas.py)
class MyEntityCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)

class MyEntityResponse(BaseModel):
    id: UUID
    name: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

# 2. Create route file (system_a/app/api/v1/my_entities.py)
router = APIRouter(prefix="/my-entities", tags=["My Entities"])

@router.post("/", response_model=MyEntityResponse, status_code=status.HTTP_201_CREATED)
async def create_entity(
    request: MyEntityCreateRequest,
    current_user: User = Depends(get_current_active_user),
    uow: UnitOfWork = Depends(get_unit_of_work),
):
    entity = MyEntity.create(name=request.name)
    await uow.my_entities.add(entity)
    await uow.commit()
    return entity

# 3. Register in system_a/app/api/v1/__init__.py:
from .my_entities import router as my_entities_router
api_router.include_router(my_entities_router)
```

### 5.4 System A: Dependency Injection Pattern

Services that are **stateless** (password hasher, JWT handler, email service, System B client) use a **singleton** pattern with global variables and lazy initialization:

```python
_my_singleton: Optional[MyService] = None

def get_my_singleton() -> MyService:
    global _my_singleton
    if _my_singleton is None:
        _my_singleton = MyService(config=settings.my_config)
    return _my_singleton
```

Services that require **database access** receive repositories via `UnitOfWork`:

```python
def get_my_service(
    uow: UnitOfWork = Depends(get_unit_of_work),
) -> MyService:
    return MyService(repository=uow.my_entities)
```

### 5.5 System A: Application Service Result Pattern

Application services in System A return **result dataclasses**, not raw entities or exceptions:

```python
@dataclass
class AuthResult:
    success: bool
    user: Optional[User] = None
    tokens: Optional[TokenPair] = None
    error: Optional[str] = None
```

Services never raise exceptions for business logic failures. They return a result object with `success=False` and an `error` message. Only infrastructure failures (database down, etc.) propagate as exceptions. This pattern allows route handlers to choose the appropriate HTTP status code based on the result.

```python
# In a route handler:
result = await auth_service.login(credentials)
if not result.success:
    raise HTTPException(status_code=401, detail=result.error)
return LoginResponse(user=result.user, tokens=result.tokens)
```

### 5.6 System B: Route Handler Pattern

System B uses direct repository instantiation (NOT UnitOfWork pattern):

```python
@router.post("/my-endpoint")
async def my_endpoint(
    request: MyRequest,
    session: AsyncSession = Depends(get_db_session),
) -> MyResponse:
    repo = MyRepository(session)
    service = MyService(repo, None)
    result = await service.do_something(request.data)
    return MyResponse(...)
```

This is a deliberate architectural difference: System B is simpler, focused on device I/O, and does not use the full DDD stack.

System B route handlers use a **three-tier error handling** pattern:

```python
@router.post("/my-endpoint")
async def my_endpoint(request: MyRequest, session: AsyncSession = Depends(get_db_session)):
    try:
        repo = MyRepository(session)
        service = MyService(repo, None)
        result = await service.do_something(request.data)
        return MyResponse(...)
    except HTTPException:
        raise                                    # Tier 1: Re-raise HTTP exceptions as-is
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))  # Tier 2: Validation → 400
    except Exception as e:
        logger.error(f"Error: {e}")
        raise HTTPException(status_code=500, detail="Internal error")  # Tier 3: Everything else → 500
```

### 5.7 System B: Entity-to-Response Conversion

System B uses standalone converter functions (not methods on entities):

```python
def device_to_response(device, newly_registered: bool = True) -> DeviceResponse:
    metadata = device.metadata or {}
    return DeviceResponse(
        id=device.id,
        device_type=device.device_type.value if hasattr(device.device_type, 'value') else str(device.device_type),
        # ... map fields
    )
```

### 5.8 Frontend: Service Class Pattern

```typescript
// frontend/src/api/services/my.service.ts
import apiClient from '../client';
import { API_ENDPOINTS } from '../config';
import type { MyEntity, CreateMyEntityRequest } from '../types';

class MyService {
  async getAll(): Promise<MyEntity[]> {
    const response = await apiClient.get<MyEntity[]>(API_ENDPOINTS.myEntities.list);
    return response.data;
  }

  async create(data: CreateMyEntityRequest): Promise<{ success: boolean; error?: string }> {
    try {
      await apiClient.post(API_ENDPOINTS.myEntities.create, data);
      return { success: true };
    } catch (error: unknown) {
      const apiError = error as { message?: string };
      return { success: false, error: apiError.message || 'Failed' };
    }
  }
}

export const myService = new MyService();
export default myService;
```

Key rules:
- Service methods return `{ success: boolean; error?: string }` for mutations
- Error handling catches and wraps API errors uniformly
- Endpoints come from `API_ENDPOINTS` constant, never hardcoded strings
- Export a singleton instance AND a default export

### 5.9 Frontend: Context Provider Ordering

The app uses 11 nested context providers in `App.tsx` in a specific order. The order matters because inner providers may depend on outer ones:

```
ThemeProvider → AuthProvider → SiteProvider → ... → ToastProvider
```

When adding a new context provider, place it at the correct nesting level based on what it depends on. If your provider needs auth context, it must be nested inside `AuthProvider`. If it needs site context, it must be inside `SiteProvider`.

**Important caveats:**
- **TanStack Query is installed** (`@tanstack/react-query` is in `package.json`) but is **NOT used** in the data hooks. The existing hooks use manual `useState`/`useEffect` patterns for data fetching. Do not mix TanStack Query usage into existing hooks unless explicitly migrating.
- **Two toast systems exist:** `Toaster` (shadcn/ui) and `Sonner`. Use whichever is used by the nearest existing code. Do not add a third toast system.
- **Hook file naming is inconsistent:** Some use camelCase (`useAuth.ts`), others use kebab-case (`use-site-data.ts`). Match the convention of the directory you're adding to. Do not rename existing files for consistency.

### 5.10 System B: Redis Streams for Async Messaging

System B uses Redis Streams for internal async messaging between components:

```
Streams:
  - telemetry_ingestion    → Raw telemetry from devices
  - alert_evaluation       → Telemetry forwarded for alert checking
  - notifications          → Alert notifications to send
  - device_commands         → Commands to send to devices
```

Each stream has consumer groups. If adding a new async pipeline in System B, create a new stream rather than overloading existing ones. The consumer pattern uses `XREADGROUP` with acknowledgment via `XACK`.

### 5.11 ORM Model Pattern

```python
class MyEntityModel(BaseModel):
    __tablename__ = "my_entities"  # or rely on auto-generation from class name

    name = Column(String(100), nullable=False)
    status = Column(String(20), nullable=False, default="active")
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    metadata_ = Column("metadata", JSONB, default={})  # Note: use metadata_ to avoid SQLAlchemy conflict
```

BaseModel provides: `id` (UUID PK), `created_at`, `updated_at`, `version`. Do NOT redefine these.

Every ORM model must implement the **3-method domain mapping pattern**:

```python
class MyEntityModel(BaseModel):
    __tablename__ = "my_entities"
    name = Column(String(100), nullable=False)

    def to_domain(self) -> MyEntity:
        """Convert ORM model to domain entity."""
        return MyEntity(id=self.id, name=self.name, ...)

    @classmethod
    def from_domain(cls, entity: MyEntity) -> 'MyEntityModel':
        """Create ORM model from domain entity (for INSERT)."""
        return cls(id=entity.id, name=entity.name, ...)

    def update_from_domain(self, entity: MyEntity) -> None:
        """Update ORM model fields from domain entity (for UPDATE)."""
        self.name = entity.name
        # ... update mutable fields
```

This pattern keeps conversion logic on the ORM model, not in the repository. Repositories call `model.to_domain()` when reading and `Model.from_domain(entity)` or `model.update_from_domain(entity)` when writing.

### 5.12 Database Naming Convention

System A uses this SQLAlchemy naming convention (defined in `connection.py`):
```python
{
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}
```

All constraints must follow this pattern. Do not use anonymous constraints.

---

## 6. Anti-Patterns

These are things you MUST NOT do. Each is listed with the correct alternative.

### 6.1 Domain Layer Violations

| DO NOT | DO INSTEAD |
|--------|-----------|
| Import SQLAlchemy in domain entities | Keep domain entities as pure dataclasses |
| Import Pydantic BaseModel in domain entities | Use `@dataclass` from stdlib |
| Put business logic in route handlers | Put it in domain entities or application services |
| Call `session.commit()` in a route handler | Use `await uow.commit()` through the UnitOfWork |
| Import concrete repositories in services | Import and depend on abstract interfaces |
| Raise exceptions for business logic failures in services | Return result dataclasses with `success=False` and `error` message |
| Put domain-to-ORM conversion in repositories | Put `to_domain()`, `from_domain()`, `update_from_domain()` on ORM models |

### 6.2 Infrastructure Anti-Patterns

| DO NOT | DO INSTEAD |
|--------|-----------|
| Create a second database engine/session factory | Use `DatabaseManager` singleton |
| Bypass UnitOfWork for "quick" database operations | All DB writes go through UoW |
| Call `session.commit()` in a repository method | Use `session.flush()` in repositories; only UoW calls `commit()` |
| Create raw SQL strings with f-string interpolation | Use SQLAlchemy's `text()` with bound parameters |
| Store secrets in code or config files | Use environment variables via `settings` |
| Hardcode Redis key patterns in multiple places | Define constants and share them |

### 6.3 API Anti-Patterns

| DO NOT | DO INSTEAD |
|--------|-----------|
| Return raw SQLAlchemy models from endpoints | Convert to Pydantic response schemas |
| Accept raw dicts as request bodies | Define Pydantic request schemas |
| Create alternative auth mechanisms | Use the existing `get_current_user` dependency chain |
| Mix v1 and v2 in the same router | Keep separate versioned routers |
| Return 200 for creation (unless reconnect) | Return 201 for resource creation |

### 6.4 Frontend Anti-Patterns

| DO NOT | DO INSTEAD |
|--------|-----------|
| Hardcode API URLs in components | Use `API_ENDPOINTS` from config |
| Store tokens in cookies | Use `localStorage` via `tokenStorage` |
| Call `axios` directly in components | Use the `apiClient` instance |
| Create mock data fallbacks in services | Let the API call fail and handle in UI |
| Import from `../../..` chains | Use `@/` path alias |
| Use TanStack Query (`useQuery`) in existing hooks | Existing hooks use `useState`/`useEffect`; don't mix paradigms unless migrating |
| Add a third toast/notification system | Use existing `Toaster` (shadcn/ui) or `Sonner` — pick whichever nearby code uses |
| Throw exceptions from service class methods | Return `{ success: boolean; error?: string }` result objects |

### 6.5 Cross-System Anti-Patterns

| DO NOT | DO INSTEAD |
|--------|-----------|
| Make System A write to System B's database | Use System B's HTTP API |
| Make System B call System A's API | Use shared Redis for data flow |
| Share ORM models between systems | Each system has its own models |
| Assume same UUIDs across systems | Use serial number as cross-system identifier |

---

## 7. Backward Compatibility Rules

### 7.1 API Compatibility

- **Adding fields to responses:** Always safe. Frontend ignores unknown fields.
- **Adding optional query parameters with defaults:** Safe.
- **Removing response fields:** BREAKING. Frontend may depend on them. Check all service files in `frontend/src/api/services/` first.
- **Changing field types:** BREAKING. Frontend TypeScript types will mismatch.
- **Renaming endpoints:** BREAKING. Update `frontend/src/api/config.ts` simultaneously.
- **Changing required fields on request schemas:** BREAKING. Frontend forms submit specific fields.

### 7.2 Database Compatibility

- **Adding nullable columns:** Safe. Existing rows get NULL.
- **Adding columns with defaults:** Safe. Existing rows get the default.
- **Removing columns:** DANGEROUS. Verify no code references the column. Check ORM model, entity, repository, schemas, and any raw queries.
- **Renaming columns:** BREAKING. Must update ORM model property name or use `Column("old_name")` mapping.
- **Changing column types:** DANGEROUS. Requires data migration.

### 7.3 Redis Compatibility

- **Adding new keys:** Safe.
- **Adding fields to JSON values:** Safe if consumers ignore unknown fields.
- **Changing key naming pattern:** BREAKING. Both systems must be updated simultaneously.
- **Changing TTL values:** Low risk but may affect cache hit rates and data freshness.
- **Changing JSON field names in telemetry:** BREAKING. System A cache reader AND frontend must be updated.

### 7.4 Domain Event Compatibility

- **Adding new event types:** Safe.
- **Adding fields to existing events:** Safe if consumers handle missing fields.
- **Removing event fields:** BREAKING for any event consumers.
- **Changing event type names:** BREAKING for any event routing.

### 7.5 Configuration Compatibility

- **Adding new settings with defaults:** Safe.
- **Removing settings:** DANGEROUS. Check all references to the setting.
- **Changing setting types:** BREAKING. Environment variables are strings; parsing logic must match.

---

## 8. Testing Expectations

### 8.1 Current Testing State

The project does not currently have a comprehensive test suite. When adding tests, follow these conventions:

### 8.2 Expected Test Structure

```
system_a/tests/
    unit/
        domain/          # Test entities, value objects, domain services
        application/     # Test application services with mocked repositories
    integration/
        api/             # Test route handlers with test database
        infrastructure/  # Test repository implementations
    conftest.py          # Shared fixtures

system_b/tests/
    unit/
    integration/
    conftest.py

frontend/
    src/__tests__/       # Component and service tests
```

### 8.3 Testing Rules

1. **Domain entity tests must not use any infrastructure.** Test entities as pure Python objects. Mock nothing - domain entities should have no external dependencies.

2. **Application service tests mock repositories.** Use the abstract interfaces as the mock type, not concrete implementations.

3. **Integration tests use a real test database.** Create a separate test database, not the development one.

4. **Frontend tests use MSW (Mock Service Worker) or similar** to intercept API calls. Do not mock the `apiClient` directly.

5. **Never mock the UnitOfWork by replacing its methods.** Instead, provide a test implementation or use a real database session.

### 8.4 Validation Before Committing

Before considering a change complete, verify:

1. **Import chain:** Ensure no domain layer file imports infrastructure
2. **Schema consistency:** Pydantic schema fields match domain entity fields being returned
3. **Repository contract:** If you added a method to an interface, the implementation exists
4. **UoW registration:** New repositories are accessible via UoW properties
5. **Route registration:** New route files are included in `api/v1/__init__.py`
6. **Frontend endpoint config:** New API endpoints are registered in `frontend/src/api/config.ts`

---

## 9. Impact Evaluation Methodology

Before making any change, evaluate its impact using this framework.

### 9.1 Impact Assessment Matrix

For each file you plan to modify, classify its impact:

| Impact Level | Criteria | Action |
|-------------|----------|--------|
| **LOW** | Changes only affect the file itself (e.g., adding a UI component, fixing a typo) | Proceed directly |
| **MEDIUM** | Changes affect 2-5 files in the same system (e.g., adding an endpoint requires schema + route + init) | List all affected files before starting |
| **HIGH** | Changes affect multiple systems or critical infrastructure (e.g., changing Redis key format) | Document the change chain before writing any code |
| **CRITICAL** | Changes to base classes, auth chain, or cross-system contracts | Consider whether the change is truly necessary |

### 9.2 Dependency Trace Procedure

When modifying a file, trace its dependents:

1. **Who imports this file?** Use grep for the module name.
2. **What interfaces does this implement?** Check if it's a concrete class implementing an ABC.
3. **What depends on this interface?** Check what services inject this interface.
4. **Does this cross system boundaries?** Check if System A and System B share the concept.
5. **Does this affect the frontend?** Check if the API response structure changes.

### 9.3 Change Ripple Map

```
Domain Entity changed
  → ORM Model may need update
    → Repository mapper may need update
      → Service return type may change
        → Pydantic schema may need update
          → API response changes
            → Frontend type definitions need update
              → Frontend components using that type need update
```

```
Redis Key Structure changed
  → System B writer must update
  → System A reader must update
  → System A cache TTL may need adjustment
  → Frontend polling behavior may change
```

```
New Repository Interface added
  → SQLAlchemy implementation required
  → ORM model must implement to_domain/from_domain/update_from_domain
  → UnitOfWork interface must add property
  → UnitOfWork implementation must add property + lazy init + close cleanup
  → Dependencies.py may need new provider function
```

```
Frontend Context Provider added/modified
  → App.tsx nesting order must respect dependency chain
  → All child components re-render on provider state changes
  → Hooks using the context must be inside the provider tree
  → Other providers nested inside may lose state if provider remounts
```

### 9.4 Pre-Change Checklist

Before modifying any file:

- [ ] I have READ the file I'm about to modify
- [ ] I have identified all files that import from or depend on this file
- [ ] I have checked if this change affects cross-system contracts (Redis, HTTP APIs)
- [ ] I have verified this change doesn't violate any stability invariant (Section 2)
- [ ] I have confirmed the change follows the correct pattern for this file type (Section 5)
- [ ] I have confirmed the change doesn't introduce any anti-pattern (Section 6)

---

## 10. Change Documentation Process

### 10.1 What to Document

Every non-trivial change should include context about:

1. **What changed** - Files modified, added, or removed
2. **Why it changed** - The business requirement or bug being addressed
3. **What it affects** - Other components that depend on the changed code
4. **What to watch for** - Potential side effects or areas to monitor

### 10.2 Commit Message Format

```
<type>: <short description>

<optional body explaining why, not what>

Affected systems: [System A | System B | Frontend | Infrastructure]
Breaking changes: [none | list of breaking changes]
```

Types: `feat`, `fix`, `refactor`, `docs`, `chore`, `test`, `perf`

### 10.3 When to Update Documentation

Update `SYSTEM_UNDERSTANDING.md` when:
- New system components are added
- Architecture changes (new services, databases, message flows)
- Cross-system contracts change
- New terminology is introduced

Update this document (`CHANGE_CONTEXT.md`) when:
- New architectural patterns are established
- New stability invariants are discovered
- New anti-patterns are identified
- Critical files list changes

### 10.4 Cross-System Change Protocol

When a change spans System A and System B:

1. Document the contract change (Redis key, API endpoint, data format)
2. Update System B first (it is the data producer)
3. Update System A second (it is the data consumer)
4. Update the frontend last (it displays the data)
5. Test the full chain: Device → System B → Redis/API → System A → Frontend

### 10.5 File Modification Logging

When you modify files, record:

```
Modified: system_a/app/api/v1/dashboards.py
  - Added new endpoint GET /api/v1/dashboard/environmental
  - Uses TelemetryService.get_environmental_stats()
  - Requires get_current_active_user authentication
  - Returns EnvironmentalStatsResponse schema

Added: system_a/app/api/schemas/environmental_schemas.py
  - EnvironmentalStatsResponse with co2_saved_kg, trees_equivalent fields

Modified: system_a/app/api/v1/__init__.py
  - Registered new environmental router
```

This log enables future sessions to understand what changed and why without re-reading the entire codebase.

---

## Appendix A: Quick Reference - File Ownership

| Directory | System | Layer | Pattern |
|-----------|--------|-------|---------|
| `system_a/app/domain/` | A | Domain | Pure Python dataclasses, no imports |
| `system_a/app/application/` | A | Application | ABCs + services depending on interfaces |
| `system_a/app/infrastructure/` | A | Infrastructure | Concrete implementations |
| `system_a/app/api/` | A | Presentation | FastAPI routes + Pydantic schemas |
| `system_b/app/domain/` | B | Domain | Simpler entities, less strict DDD |
| `system_b/app/application/` | B | Application | Services with direct repo access |
| `system_b/app/api/` | B | Presentation | FastAPI routes + schemas |
| `system_b/app/infrastructure/` | B | Infrastructure | DB, Redis, device communication |
| `frontend/src/api/` | FE | Data Layer | Axios client + typed services |
| `frontend/src/components/` | FE | UI | React components (shadcn/ui) |
| `frontend/src/pages/` | FE | Pages | Route-level page components |
| `frontend/src/hooks/` | FE | Logic | Custom React hooks |
| `frontend/src/contexts/` | FE | State | React Context providers |

## Appendix B: Port and Service Map

| Service | Port | Protocol | Notes |
|---------|------|----------|-------|
| System A (FastAPI) | 8000 | HTTP | Main platform API |
| System B (FastAPI) | 8001 | HTTP | Device & telemetry API |
| System B (TCP) | 8502 | Modbus TCP | Device communication |
| PostgreSQL | 5432 | TCP | System A database |
| TimescaleDB | 5433 | TCP | System B database |
| Redis | 6379 | TCP | Shared cache (DB 0 = A, DB 1 = B) |
| Mosquitto | 1883 / 9001 | MQTT / WS | Message broker |
| Frontend (dev) | 8080 | HTTP | Vite dev server |
