from supabase import create_client, Client
from app.core.config import settings

# Bypasses RLS — only for trusted server-side operations across users.
supabase_admin: Client = create_client(
    settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY
)

# Used for auth calls (signup/login/get_user).
supabase_public: Client = create_client(
    settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY
)


def supabase_as_user(access_token: str) -> Client:
    """RLS-scoped client acting as the given user. Used from Module 2
    onward for queries against user-owned tables."""
    client = create_client(settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY)
    client.postgrest.auth(access_token)
    return client