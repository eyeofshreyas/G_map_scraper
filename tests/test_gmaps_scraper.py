import csv
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from gmaps_scraper import build_search_url, save_to_csv


def test_build_search_url_encodes_spaces():
    url = build_search_url("Pimpri Chinchwad", "dental clinics")
    assert "dental+clinics+in+Pimpri+Chinchwad" in url
    assert url.startswith("https://www.google.com/maps/search/")


def test_build_search_url_special_chars():
    url = build_search_url("Mumbai", "gyms & fitness")
    assert "google.com/maps/search/" in url
    assert " " not in url
    assert "gyms+%26+fitness+in+Mumbai" in url


def test_save_to_csv_filters_out_businesses_with_website():
    rows = [
        {"business_name": "A", "phone": "1", "category": "dentist",
         "website": "http://a.com", "has_website": "Yes",
         "rating": 4.5, "review_count": "10", "address": "Addr A"},
        {"business_name": "B", "phone": "2", "category": "dentist",
         "website": "", "has_website": "No",
         "rating": 3.0, "review_count": "5", "address": "Addr B"},
    ]
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        path = f.name
    try:
        save_to_csv(rows, path)
        with open(path, newline="", encoding="utf-8") as fh:
            reader = list(csv.DictReader(fh))
        assert len(reader) == 1
        assert reader[0]["business_name"] == "B"
    finally:
        os.unlink(path)


def test_save_to_csv_sorts_by_rating_descending():
    rows = [
        {"business_name": "Low",  "phone": "", "category": "gym",
         "website": "", "has_website": "No",
         "rating": 2.5, "review_count": "3", "address": "X"},
        {"business_name": "High", "phone": "", "category": "gym",
         "website": "", "has_website": "No",
         "rating": 4.8, "review_count": "20", "address": "Y"},
        {"business_name": "Mid",  "phone": "", "category": "gym",
         "website": "", "has_website": "No",
         "rating": 3.9, "review_count": "8", "address": "Z"},
    ]
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        path = f.name
    try:
        save_to_csv(rows, path)
        with open(path, newline="", encoding="utf-8") as fh:
            reader = list(csv.DictReader(fh))
        names = [r["business_name"] for r in reader]
        assert names == ["High", "Mid", "Low"]
    finally:
        os.unlink(path)


def test_save_to_csv_unrated_entries_go_to_end():
    rows = [
        {"business_name": "Unrated", "phone": "", "category": "gym",
         "website": "", "has_website": "No",
         "rating": "", "review_count": "", "address": "X"},
        {"business_name": "Rated",   "phone": "", "category": "gym",
         "website": "", "has_website": "No",
         "rating": 3.0, "review_count": "5", "address": "Y"},
    ]
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        path = f.name
    try:
        save_to_csv(rows, path)
        with open(path, newline="", encoding="utf-8") as fh:
            reader = list(csv.DictReader(fh))
        assert reader[0]["business_name"] == "Rated"
        assert reader[1]["business_name"] == "Unrated"
    finally:
        os.unlink(path)
