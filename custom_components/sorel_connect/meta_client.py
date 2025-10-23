import aiohttp
import asyncio
import logging
import os
import json
import time
from typing import Optional
import aiofiles

_LOGGER = logging.getLogger(__name__)

class MetaClient:
    """
    Client for the Sorel metadata API with caching, poll limiting, and local fallback.
    """
    def __init__(self, api_server: str, api_url_template: str, session: aiohttp.ClientSession, cache_dir: Optional[str] = None):
        self._api_server = api_server
        self._api_url_template = api_url_template
        self._session = session
        # Cache in Home Assistant's writable /config directory
        self._cache_dir = cache_dir or "/config/sorel_meta_cache"
        os.makedirs(self._cache_dir, exist_ok=True)
        self._last_poll = {}  # (org, dev, fw) -> timestamp
        self._last_failed = {}  # (org, dev, fw) -> timestamp
        self._retry_intervals = [300, 600, 1800, 3600]  # 5min, 10min, 30min, 1h
        self._failed_count = {}  # Explicitly initialize
        self._retry_tasks = {}  # Manage active retry tasks

    def _cache_path(self, organization_id, device_enum_id, language, firmware_version):
        fname = f"meta_{organization_id}_{device_enum_id}_{language}_{firmware_version}.json"
        return os.path.join(self._cache_dir, fname)

    def _can_poll(self, key):
        now = time.time()
        last = self._last_poll.get(key, 0)
        return (now - last) > 60

    def _can_retry(self, key):
        """Checks if a retry attempt is allowed based on exponential backoff strategy"""
        # Check for permanent failure
        if self._failed_count.get(key, 0) == -1:
            return False

        now = time.time()
        last_failed = self._last_failed.get(key, 0)
        if last_failed == 0:
            return True

        # Calculate retry interval based on number of failed attempts
        failed_count = self._failed_count.get(key, 0)
        retry_interval = self._retry_intervals[min(failed_count, len(self._retry_intervals) - 1)]

        return (now - last_failed) > retry_interval

    def _record_failure(self, key):
        """Records a failure and increments the counter"""
        self._last_failed[key] = time.time()
        self._failed_count[key] = self._failed_count.get(key, 0) + 1

        # Start automatic retry task if not already active
        if key not in self._retry_tasks:
            self._retry_tasks[key] = asyncio.create_task(self._schedule_retry(key))

    def _record_success(self, key):
        """Resets failure counters after successful call"""
        if key in self._failed_count:
            del self._failed_count[key]
        if key in self._last_failed:
            del self._last_failed[key]

        # Stop running retry tasks
        if key in self._retry_tasks:
            self._retry_tasks[key].cancel()
            del self._retry_tasks[key]

    def _record_permanent_failure(self, key):
        """Records a permanent failure (no retries)"""
        # Set a special marker for permanently failed devices
        self._failed_count[key] = -1  # -1 means permanently failed
        self._last_failed[key] = time.time()

        # Stop running retry tasks
        if key in self._retry_tasks:
            self._retry_tasks[key].cancel()
            del self._retry_tasks[key]

    async def _schedule_retry(self, key):
        """Background task for automatic retry attempts"""
        try:
            while key in self._failed_count and self._failed_count[key] != -1:
                # Calculate wait time until next attempt
                failed_count = self._failed_count.get(key, 0)
                retry_interval = self._retry_intervals[min(failed_count - 1, len(self._retry_intervals) - 1)]
                last_failed = self._last_failed.get(key, 0)
                wait_time = max(0, (last_failed + retry_interval) - time.time())

                if wait_time > 0:
                    _LOGGER.debug(f"Waiting {wait_time:.0f} seconds until next retry for {key}")
                    await asyncio.sleep(wait_time)

                # Attempt to reload
                organization_id, device_enum_id, language, firmware_version = key
                _LOGGER.info(f"Automatic retry attempt for {key}")

                # Load metadata without cache check (force reload)
                success = await self._fetch_metadata_direct(organization_id, device_enum_id)

                if success:
                    _LOGGER.info(f"Retry successful for {key}")
                    break
                else:
                    _LOGGER.warning(f"Retry failed for {key}")

        except asyncio.CancelledError:
            _LOGGER.debug(f"Retry task for {key} was cancelled")
        finally:
            # Remove task from management
            if key in self._retry_tasks:
                del self._retry_tasks[key]

    async def _fetch_metadata_direct(self, organization_id, device_enum_id) -> bool:
        """Direct API call without cache check"""
        key = (organization_id, device_enum_id, "en", "latest")
        cache_file = self._cache_path(organization_id, device_enum_id, "en", "latest")
        
        url = f"https://{self._api_server}" + self._api_url_template.format(
            organizationId=organization_id,
            deviceEnumId=device_enum_id,
            language="en"
        )
        
        try:
            async with self._session.get(url, timeout=15) as resp:
                resp.raise_for_status()
                data = await resp.json()

                # Check for "Device not found" error
                if isinstance(data, dict) and data.get("error") == "Device not found":
                    _LOGGER.info(f"Device {organization_id}/{device_enum_id} not found - no metadata available")
                    # Mark as permanently failed (no retries)
                    self._record_permanent_failure(key)
                    return False

                # Save to cache
                async with aiofiles.open(cache_file, "w", encoding="utf-8") as f:
                    await f.write(json.dumps(data))

                # Record success
                self._record_success(key)
                return True

        except Exception as e:
            # Record failure (but without starting a new retry task)
            self._last_failed[key] = time.time()
            self._failed_count[key] = self._failed_count.get(key, 0) + 1
            _LOGGER.error(f"Retry attempt failed for {url}: {e}")
            return False

    async def get_metadata(self, organization_id, device_enum_id) -> Optional[dict]:
        """
        Fetches metadata from API or local cache.
        Returns None if device does not exist.
        """
        # TODO: Language could be made configurable if needed
        # By now the API does not support versioned metadata, so we use "latest" as placeholder for future use
        cache_file = self._cache_path(organization_id, device_enum_id, "en", "latest")
        key = (organization_id, device_enum_id, "en", "latest")

        # Check for permanently failed devices
        if self._failed_count.get(key, 0) == -1:
            _LOGGER.debug(f"Device {key} is permanently marked as unavailable.")
            return None

        # 1. Check local cache
        if os.path.exists(cache_file):
            try:
                async with aiofiles.open(cache_file, "r", encoding="utf-8") as f:
                    content = await f.read()
                    data = json.loads(content)
                # Also check cache for "Device not found" error
                if isinstance(data, dict) and data.get("error") == "Device not found":
                    self._record_permanent_failure(key)
                    return None
                # Optional: Check validity (e.g., max 7 days old)
                _LOGGER.info(f"Metadata loaded from cache for {key}.")
                return data
            except Exception as e:
                _LOGGER.warning(f"Error reading metadata cache: {e}")

        # 2. Check if new attempt is allowed (poll limit or retry limit)
        if not self._can_poll(key) and not self._can_retry(key):
            _LOGGER.debug(f"Poll and retry limit reached for {key}, not fetching new metadata.")
            return None

        self._last_poll[key] = time.time()

        # 3. API request
        success = await self._fetch_metadata_direct(organization_id, device_enum_id)

        if success:
            # Load from cache after successful API call
            try:
                async with aiofiles.open(cache_file, "r", encoding="utf-8") as f:
                    content = await f.read()
                    return json.loads(content)
            except Exception as e:
                _LOGGER.error(f"Error reading freshly saved cache: {e}")

        # 4. Fallback: Return old cache if available (but only if not "Device not found")
        if os.path.exists(cache_file):
            try:
                async with aiofiles.open(cache_file, "r", encoding="utf-8") as f:
                    content = await f.read()
                    data = json.loads(content)
                    # Check here too for "Device not found"
                    if isinstance(data, dict) and data.get("error") == "Device not found":
                        self._record_permanent_failure(key)
                        return None
                    _LOGGER.info(f"Fallback to old cache for {key}")
                    return data
            except Exception:
                pass

        return None

    def get_device_status(self, organization_id, device_enum_id) -> str:
        """
        Returns the metadata fetch status for a device.

        Returns:
            "ok" - metadata available or never attempted
            "not_found" - device permanently unavailable (404)
            "retry_pending" - temporary failure, retries scheduled
            "error" - fetch failed but retries not yet exhausted
        """
        key = (organization_id, device_enum_id, "en", "latest")
        failed_count = self._failed_count.get(key, 0)

        # Permanently failed (404 Not Found)
        if failed_count == -1:
            return "not_found"

        # Has failures and retry task is active
        if failed_count > 0:
            if key in self._retry_tasks:
                return "retry_pending"
            return "error"

        # No failures or metadata loaded successfully
        return "ok"

    def get_status_details(self, organization_id, device_enum_id) -> dict:
        """
        Returns detailed status information for a device.

        Returns dict with:
            status: "ok", "not_found", "retry_pending", "error"
            message: Human-readable status message
            retry_count: Number of failed attempts (0 if none)
            last_error_time: Timestamp of last failure (None if never failed)
        """
        key = (organization_id, device_enum_id, "en", "latest")
        failed_count = self._failed_count.get(key, 0)
        last_error = self._last_failed.get(key)
        status = self.get_device_status(organization_id, device_enum_id)

        # Build human-readable message
        message_map = {
            "ok": "Metadata available",
            "not_found": "Device not found (404) - device type not supported by API",
            "retry_pending": f"Temporary error - retry scheduled (attempt {failed_count})",
            "error": f"Failed to fetch metadata ({failed_count} attempts)",
        }

        return {
            "status": status,
            "message": message_map.get(status, "Unknown status"),
            "retry_count": max(0, failed_count) if failed_count != -1 else 0,
            "last_error_time": last_error,
        }

    async def close(self):
        """Cleanup method to terminate all retry tasks"""
        for task in self._retry_tasks.values():
            task.cancel()
        # Wait for all tasks to complete
        if self._retry_tasks:
            await asyncio.gather(*self._retry_tasks.values(), return_exceptions=True)
        self._retry_tasks.clear()
