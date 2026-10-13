# User Permission Roles System

Reference documentation for AI agents working with the role-based permission system.

## Architecture Overview

Roles are implemented via **Django Groups** with **django-guardian** for object-level permissions. Each project has its own set of role groups. Users are assigned to groups, and permissions are checked against group membership.

**Key principle:** `UserProjectMembership` tracks membership only. Role assignment is separate via group membership.

## Core Files

### Role Definitions
- **File:** `ami/users/roles.py`
- **Lines 12-85:** `Role` base class with static methods
- **Lines 84-107:** `BasicMember`, `Researcher`, `Identifier`, `MLDataManager`, `ProjectManager` role classes
- **Lines 189-210:** `create_roles_for_project()` function

### Role Class Structure
```python
class Role:
    display_name = ""
    description = ""
    permissions = {Project.Permissions.VIEW_PROJECT}  # Set of permission strings

    @classmethod
    def get_group_name(cls, project) -> str  # Lines 21-24
    @classmethod
    def assign_user(cls, user, project)      # Lines 27-35
    @classmethod
    def unassign_user(cls, user, project)    # Lines 37-41
    @classmethod
    def has_role(cls, user, project) -> bool # Lines 43-46
    @staticmethod
    def get_primary_role(project, user)      # Lines 74-85
    @staticmethod
    def get_user_roles(project, user)        # Lines 62-71
```

### Group Naming Convention
Format: `{project.pk}_{project.name}_{RoleName}`
Example: `90_Singapore- Labelling Project_ProjectManager`

Defined at `ami/users/roles.py:21-24`

## Role Hierarchy (by permission count)

1. **ProjectManager** - Full admin access (lines 143-185)
2. **MLDataManager** - ML jobs, data management (lines 120-140)
3. **Identifier** - Create/update/delete identifications (lines 109-118)
4. **Researcher** - Data exports (lines 99-107)
5. **BasicMember** - View, star images, single image jobs (lines 84-96)

## Membership Model

### UserProjectMembership
- **File:** `ami/main/models.py:493-540`
- Through model for `Project.members` M2M relationship
- Fields: `user`, `project`, `created_at`, `updated_at`
- Does NOT store role - role is determined by group membership

### Project.members Field
- **File:** `ami/main/models.py` (search for `members =`)
- ManyToManyField with `through="main.UserProjectMembership"`

## Signal Handlers

### When user added to role group → Create membership
- **File:** `ami/users/signals.py:31-76`
- Signal: `m2m_changed` on `Group.user_set.through`
- Function: `manage_project_membership()`
- Creates `UserProjectMembership` when user added to any role group
- Deletes membership when user removed from ALL role groups

### When project created → Assign owner as ProjectManager
- **File:** `ami/main/signals.py:15-31`
- Signal: `post_save` on `Project`
- Function: `set_project_owner_permissions()`
- Also handles owner changes

### When member added via M2M → Assign BasicMember
- **File:** `ami/main/signals.py:49-65`
- Signal: `m2m_changed` on `Project.members.through`
- Function: `set_project_members_permissions()`
- Assigns `BasicMember` role to newly added members

## API Endpoints

### Membership Management
- **File:** `ami/users/api/views.py:32-100`
- ViewSet: `UserProjectMembershipViewSet`
- Endpoints: `/api/v2/projects/{project_pk}/members/`
- CRUD operations with role assignment

### Serializers
- **File:** `ami/users/api/serializers.py:107-225`
- `UserProjectMembershipSerializer` - handles `email` and `role_id` for create/update
- `role_id` validation at lines 150-158
- Role lookup via `Role.get_primary_role()` in `get_role()` method

### Roles List
- **File:** `ami/users/api/views.py:23-29`
- Endpoint: `/api/v2/users/roles/`
- Returns all available role classes

## Permissions

### Project-Level Permissions
- **Defined in:** `ami/main/models.py` (search for `class Permissions`)
- **Migration:** `ami/main/migrations/0079_alter_project_options.py`
- Examples: `create_identification`, `view_userprojectmembership`, `run_ml_job`

### Permission Checking
- **File:** `ami/base/permissions.py:92-118`
- Class: `UserMembershipPermission`
- Used by `UserProjectMembershipViewSet`

## Management Commands

### assign_roles
- **File:** `ami/main/management/commands/assign_roles.py`
- Resets all permissions and assigns default roles
- Assigns `BasicMember` to all project members
- Assigns `ProjectManager` to project owners
- Optional: reads CSV for specific role assignments

Usage:
```bash
python manage.py assign_roles
python manage.py assign_roles --source roles.csv
```

## Migrations

### 0080_userprojectmembership
- **File:** `ami/main/migrations/0080_userprojectmembership.py`
- Creates `UserProjectMembership` model
- Migrates data from old implicit M2M table `main_project_members`
- Updates `Project.members` to use explicit through model

## Common Operations

### Assign a role to user
```python
from ami.users.roles import ProjectManager
ProjectManager.assign_user(user, project)
```

### Check user's primary role
```python
from ami.users.roles import Role
role_cls = Role.get_primary_role(project, user)  # Returns class or None
role_name = role_cls.__name__ if role_cls else None
```

### Check if user has specific role
```python
from ami.users.roles import Researcher
has_role = Researcher.has_role(user, project)  # Returns bool
```

### Get all user's roles for a project
```python
from ami.users.roles import Role
roles = Role.get_user_roles(project, user)  # Returns list of role classes
```

## Testing

- **File:** `ami/users/tests/test_membership_management_api.py`
- Tests for membership API, role assignment, permissions

## Gotchas

1. **Signals can cause recursion** - `manage_project_membership` temporarily disconnects itself during updates (lines 42-43, 73-75 in `ami/users/signals.py`)

2. **Group names include project name** - If project name changes, existing groups become orphaned. Consider migration or cleanup.

3. **Migrations can't use Role classes directly** - Must construct group names manually using the format string. See `ami/main/migrations/0080_userprojectmembership.py:6`

4. **BasicMember is always added** - When assigning higher roles via API, `BasicMember` is NOT automatically added. The API unassigns all roles then assigns the new one (see `ami/users/api/views.py:60-70`).

5. **Primary role = most permissions** - `get_primary_role()` returns the role with the largest permission set, not the "highest" in any hierarchy.
