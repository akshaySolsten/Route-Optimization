from google.cloud import bigquery, firestore

from app.config import BQ_PROJECT, FIRESTORE_PROJECT

_bq_client = None
_fs_client = None


def get_bq_client() -> bigquery.Client:
    global _bq_client
    if _bq_client is None:
        _bq_client = bigquery.Client(project=BQ_PROJECT)
    return _bq_client


def get_fs_client() -> firestore.Client:
    global _fs_client
    if _fs_client is None:
        _fs_client = firestore.Client(project=FIRESTORE_PROJECT)
    return _fs_client
