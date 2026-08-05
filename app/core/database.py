from supabase import create_client, Client, ClientOptions
from app.core.config import settings

#Increase the timeout for Supabase client to handle large file uploads
options = ClientOptions(postgrest_client_timeout=60,storage_client_timeout=60)

# Public client for user-scoped operations
supabase: Client = create_client(settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY, options=options)

# Service client for admin actions (bypassing RLS when necessary)
supabase_admin: Client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY, options=options)