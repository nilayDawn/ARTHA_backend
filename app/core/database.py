from supabase import create_client, Client
from app.core.config import settings

# Public client for user-scoped operations
supabase: Client = create_client(settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY)

# Service client for admin actions (bypassing RLS when necessary)
supabase_admin: Client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)