import logging
import time
from datetime import date, timedelta

from .providers.nifty_provider import NiftyIndexProvider
from .benchmark_repository import BenchmarkRepository

logger = logging.getLogger(__name__)

# All benchmark indices we need — derived from benchmark_mapping's distinct
# index_name values, kept as a constant here for the ingestion job to iterate.
INDICES_TO_SYNC = ["NIFTY 50", "NIFTY 100", "NIFTY 500", "NIFTY MIDCAP 150", "NIFTY SMALLCAP 250"]

HISTORY_YEARS = 10  # need 7+ for rolling consistency, pad to 10 for safety


class BenchmarkIngestionService:
    @staticmethod
    def sync_all_indices() -> dict:
        provider = NiftyIndexProvider()
        end = date.today()
        start = end - timedelta(days=365 * HISTORY_YEARS)

        summary = {"synced": {}, "failed": []}
        for index_name in INDICES_TO_SYNC:
            try:
                rows = provider.fetch_index_history(index_name, start, end)
                if not rows:
                    logger.warning(f"No data returned for {index_name}")
                    summary["failed"].append(index_name)
                    continue
                count = BenchmarkRepository.upsert_observations(index_name, rows)
                summary["synced"][index_name] = count
                logger.info(f"Synced {count} observations for {index_name}")
                time.sleep(1)  # be polite to an undocumented endpoint
            except Exception as e:
                logger.error(f"Benchmark sync failed for {index_name}: {e}")
                summary["failed"].append(index_name)

        return summary