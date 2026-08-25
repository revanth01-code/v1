from app.core.supabase import supabase_as_user

TABLE = "retirement_plan"


class RetirementRepository:
    @staticmethod
    def get_by_user_id(access_token: str, user_id: str) -> dict | None:
        client = supabase_as_user(access_token)
        res = client.table(TABLE).select("*").eq("user_id", user_id).maybe_single().execute()
        return res.data if res else None

    @staticmethod
    def create(access_token: str, user_id: str, payload: dict) -> dict:
        client = supabase_as_user(access_token)
        row = {**payload, "user_id": user_id}
        res = client.table(TABLE).insert(row).execute()
        return res.data[0]

    @staticmethod
    def update(access_token: str, user_id: str, payload: dict) -> dict:
        client = supabase_as_user(access_token)
        res = client.table(TABLE).update(payload).eq("user_id", user_id).execute()
        return res.data[0]