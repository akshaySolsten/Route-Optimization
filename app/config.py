import os

GOOGLE_MAPS_API_KEY = os.environ.get("GOOGLE_MAPS_API_KEY")
BQ_PROJECT = os.environ.get("BQ_PROJECT", "prj-dev-hermes")
BQ_DATASET = os.environ.get("BQ_DATASET", "Hermes_Exports")
BQ_TABLE = os.environ.get("BQ_TABLE", "consignments_routing_test")
FIRESTORE_PROJECT = os.environ.get("FIRESTORE_PROJECT", BQ_PROJECT)

GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"
GEOHASH_LOCALITY_LEN = 5
GEOHASH_BUILDING_LEN = 6
MAX_ROWS_PER_MERGE = 500
MAX_ROWS_PER_UPDATE = 500
FIRESTORE_BATCH_SIZE = 500

TABLE_REF = f"{BQ_PROJECT}.{BQ_DATASET}.{BQ_TABLE}"
