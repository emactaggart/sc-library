import random
from datetime import datetime
import time
import json
import requests
import os

TRACK_FILTERS = [
    "created_at",
    (
        "track",
        [
            "downloadable",
            "duration",
            "full_duration",
            "genre",
            "id",
            "has_downloads_left",
            "kind",
            "label_name",
            "permalink",
            "permalink_url",
            "public",
            "publisher_metadata",
            "purchase_title",
            "purchase_url",
            "release_date",
            "tag_list",
            "title",
            "track_format",
            "uri",
            "user_id",
            "display_date",
            (
                "user",
                [
                    "avatar_url",
                    "first_name",
                    "full_name",
                    "id",
                    "kind",
                    "last_name",
                    "permalink",
                    "permalink_url",
                    "uri",
                    "username",
                    "city",
                    "country_code",
                ],
            ),
        ],
    ),
]


def capture_tracks_from_url_list(all_likes, url_list, capture_command):
    likes_to_capture, missing = url_list_to_tracks(url_list, all_likes)
    if missing:
        raise Exception(missing)
    return capture_tracks(likes_to_capture, capture_command)


def url_list_to_tracks(url_list, all_likes):
    tracks = []
    missing = []
    for url in url_list:
        track = find_track_by_permalink(all_likes, url)
        if track:
            tracks.append(track)
        else:
            missing.append(url)

    return tracks, missing


def find_track_by_permalink(all_likes, permalink):
    return first(
        [like for like in all_likes if like["track"]["permalink_url"] == permalink]
    )


def capture_latest_tracks(
    all_likes, capture_command="echo", latest_captured_track=None
):
    if latest_captured_track:
        recent_likes = [
            like
            for like in all_likes
            if like["created_at"] > latest_captured_track["created_at"]
            and like["track"]["duration"] <= 16 * 60 * 1000
        ]
    else:
        recent_likes = all_likes
    return capture_tracks(recent_likes, capture_command)


def capture_tracks(likes_to_capture, capture_command="echo"):
    print("Begin Capturing Tracks (%s total)" % len(likes_to_capture))
    success = []
    failed = []
    for like in likes_to_capture:
        permalink = like["track"]["permalink_url"]
        error_code = os.system(capture_command + " " + permalink)
        if error_code:
            print("Capture Failed:", permalink, "Error Code:", error_code)
            failed.append(like)
        else:
            print("Capture Succeeded:", permalink)
            success.append(like)
        sleep_time = (like["track"]["duration"] / 1000) + 33
        print("Sleeping for", sleep_time, "seconds.")
        time.sleep(sleep_time)
    print("Capture Completed (%s of %s successful)" % (len(success), len(likes_to_capture)))
    print("Successful:", to_permalinks(success))
    print("Failed:", to_permalinks(failed))
    return success, failed


def to_permalinks(likes):
    return [like['track']['permalink_url'] for like in likes]


def fetch_all_likes_cached(
    user_id, client_id, cache_filepath=None, output_filepath=None
):
    if (
        cache_filepath
        and os.path.exists(cache_filepath)
        and os.path.isfile(cache_filepath)
    ):
        cached_likes = json_read_file(cache_filepath)
    else:
        cached_likes = []
    until_track = get_most_recent_liked_track(cached_likes)
    new_likes = fetch_all_likes(user_id, client_id, until_track=until_track)
    all_likes = sort_likes([*new_likes, *cached_likes])
    output_filepath = output_filepath or create_timestamped_filename("likes-cache")
    json_write_file(output_filepath, all_likes)
    return all_likes, output_filepath


def create_timestamped_filename(name):
    timestamp_str = datetime.now().strftime("%Y-%m-%dT%H-%M")
    return "%s-%s.json" % (timestamp_str, name)


def filter_tracks(tracks):
    return dict_filter(TRACK_FILTERS, tracks)


def get_most_recent_liked_track(tracks):
    if tracks:
        return sort_likes(tracks)[0]["track"]["id"]
    else:
        return None


def sort_likes(tracks):
    """
    By liked date desc
    """
    return sorted(tracks, key=lambda x: x["created_at"], reverse=True)


def dict_filter(filt, collection):
    if isinstance(collection, dict):
        collection = [collection]
    return [_dict_filter(filt, item) for item in collection]


def _dict_filter(filt, collection):
    if isinstance(filt, list):
        new_collection = {}
        for f in filt:
            new_collection |= _dict_filter(f, collection)
        return new_collection
    elif isinstance(filt, tuple):
        key = filt[0]
        return {key: _dict_filter(filt[1], collection.get(key))}
    elif isinstance(filt, str):
        return {k: v for k, v in collection.items() if filt == k}
    else:
        return collection


def keep_keys(dic, keys):
    if isinstance(dic, dict):
        return {k: v for k, v in dic.items() if k in keys}
    elif isinstance(dic, list):
        return [keep_keys(d, keys) for d in dic]


def drop_keys(dic, keys):
    if isinstance(dic, dict):
        return {k: v for k, v in dic.items() if k not in keys}
    elif isinstance(dic, list):
        return [drop_keys(d, keys) for d in dic]


def first(lis):
    try:
        return lis[0]
    except IndexError:
        return None


def fetch_all_likes(user_id, client_id, until_track=None, kindness_meter=3):
    tracks = []
    next_href = f"https://api-v2.soundcloud.com/users/{user_id}/track_likes"
    while True and next_href:
        next_href, collection = do_fetch_likes(next_href, client_id)
        if until_track and until_track in [like["track"]["id"] for like in collection]:
            next_href = None
            until_date = [tr for tr in collection if tr["track"]["id"] == until_track][
                0
            ]["track"]["created_at"]
            collection = [
                tr for tr in collection if tr["track"]["created_at"] > until_date
            ]
            print("Until track found, exiting...", until_track)
        tracks.extend(collection)
        time.sleep(kindness_meter)
        print(next_href)
        print(len(tracks))
    return filter_tracks(tracks)


def do_fetch_likes(url, client_id, limit=100):
    params = {
        "client_id": client_id,
        "limit": limit,
    }
    result = requests.get(url, params=params)
    j = result.json()
    return j["next_href"], j["collection"]


def json_read_file(filename):
    with open(filename, "r") as f:
        data = json.loads(f.read())
    return data


def json_write_file(filename, data):
    with open(filename, "w") as f:
        f.write(json.dumps(data))


def json_append_file(filename, new_data):
    try:
        existing_data = json_read_file(filename)
    except FileNotFoundError:
        existing_data = []
    if not isinstance(existing_data, list):
        existing_data = [existing_data]
    if not isinstance(new_data, list):
        new_data = [new_data]
    json_write_file(filename, [*existing_data, *new_data])


def read_file(filename):
    with open(filename, "r") as f:
        data = f.read().split("\n")
    return [d for d in data if d]
