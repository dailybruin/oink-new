import logging
logger = logging.getLogger(__name__)


def create_drive_folder(name, parent_id=None, service_account_file=None, impersonate_user=None, share_public=False, share_domain=None):
    logger.info('create_drive_folder called for %s (stub)', name)
    return None


def fetch_package_files(package):
    logger.info('fetch_package_files stub for %s', package.slug)
    return []
