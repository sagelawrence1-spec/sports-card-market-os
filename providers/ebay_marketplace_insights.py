from .base import ProviderResult

class EbayMarketplaceInsightsProvider:
    """Boundary for eBay's official sold-history API.

    eBay documents Marketplace Insights as Limited Release and restricted to existing
    approved users. Keeping this interface explicit lets the MVP switch to it without
    changing normalization/scoring once access is available.
    """
    provider_name="ebay_marketplace_insights"

    def search_sold(self, query: str, **kwargs) -> ProviderResult:
        raise PermissionError(
            "Marketplace Insights is restricted by eBay and not open to new users. "
            "Use the Product Research ingestion adapter until approved access exists."
        )
