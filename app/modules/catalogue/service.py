from app.modules.catalogue.schemas import (
    BudgetTemplate,
    MerchantMapping,
    SpendingCategory,
)


class CatalogueService:
    """
    Domain service providing standardized expense categories, merchant mapping rules,
    and budget allocation templates.
    """

    DEFAULT_CATEGORIES = [
        SpendingCategory(id="income", name="Income", icon="💰", color="#16a34a", description="Salaries, dividends, side-income, and deposits"),
        SpendingCategory(id="food", name="Food & Dining", icon="🍔", color="#f97316", description="Groceries, restaurants, takeaways, cafes"),
        SpendingCategory(id="shopping", name="Shopping", icon="🛍️", color="#8b5cf6", description="Clothing, electronics, household essentials"),
        SpendingCategory(id="transport", name="Transport", icon="🚗", color="#06b6d4", description="Fuel, cabs, public transit, flights"),
        SpendingCategory(id="utilities", name="Utilities & Bills", icon="⚡", color="#eab308", description="Electricity, water, gas, internet, mobile"),
        SpendingCategory(id="health", name="Health & Wellness", icon="💊", color="#ec4899", description="Medication, doctors, gym, supplements"),
        SpendingCategory(id="entertainment", name="Entertainment", icon="🎬", color="#3b82f6", description="Movies, gaming, outings, events"),
        SpendingCategory(id="subscriptions", name="Subscriptions", icon="📱", color="#6366f1", description="Netflix, Spotify, Cloud storage, Prime"),
        SpendingCategory(id="education", name="Education", icon="📚", color="#14b8a6", description="Courses, books, workshops, schooling"),
        SpendingCategory(id="other", name="Other", icon="📦", color="#64748b", description="Miscellaneous expenses"),
    ]

    MERCHANT_RULES = [
        MerchantMapping(pattern="swiggy", suggested_category="Food & Dining"),
        MerchantMapping(pattern="zomato", suggested_category="Food & Dining"),
        MerchantMapping(pattern="starbucks", suggested_category="Food & Dining"),
        MerchantMapping(pattern="mcdonald", suggested_category="Food & Dining"),
        MerchantMapping(pattern="uber", suggested_category="Transport"),
        MerchantMapping(pattern="ola", suggested_category="Transport"),
        MerchantMapping(pattern="rapido", suggested_category="Transport"),
        MerchantMapping(pattern="amazon", suggested_category="Shopping"),
        MerchantMapping(pattern="flipkart", suggested_category="Shopping"),
        MerchantMapping(pattern="myntra", suggested_category="Shopping"),
        MerchantMapping(pattern="netflix", suggested_category="Subscriptions"),
        MerchantMapping(pattern="spotify", suggested_category="Subscriptions"),
    ]

    BUDGET_TEMPLATES = [
        BudgetTemplate(
            template_name="50/30/20 Rule",
            description="50% Needs (Food, Utilities, Transport), 30% Wants (Shopping, Entertainment), 20% Savings/Goals",
            allocations={
                "Food & Dining": 25.0,
                "Utilities & Bills": 15.0,
                "Transport": 10.0,
                "Shopping": 15.0,
                "Entertainment": 10.0,
                "Subscriptions": 5.0,
                "Savings & Goals": 20.0,
            },
        ),
        BudgetTemplate(
            template_name="Aggressive Saver",
            description="Frugal spending targeting 40% monthly savings rate",
            allocations={
                "Food & Dining": 20.0,
                "Utilities & Bills": 15.0,
                "Transport": 10.0,
                "Shopping": 10.0,
                "Entertainment": 5.0,
                "Savings & Goals": 40.0,
            },
        ),
    ]

    def get_categories(self) -> list[SpendingCategory]:
        return self.DEFAULT_CATEGORIES

    def get_merchant_rules(self) -> list[MerchantMapping]:
        return self.MERCHANT_RULES

    def get_budget_templates(self) -> list[BudgetTemplate]:
        return self.BUDGET_TEMPLATES
