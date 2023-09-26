import random
from datetime import datetime, timedelta
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


CACHE_FILENAME = "latest_likes_cache.json"


# FIXME FIXME  FIXME
# - separate out super long tracks (like whole sets, and super short tracks like those that are only ~2 minutes long)


def do_capture_tracks_from_url_list():
    # all_likes = fetch_all_likes_cached(user_id=..., client_id=..., cache_filepath=..., output_cache_filepath=...)
    # success, failed = capture_tracks_from_url_list(all_likes, url_list=..., capture_command=...)
    ...


def do_capture_latest_tracks(
    user_id,
    client_id,
    all_likes_cache_filename,
    latest_capture_filename,
    capture_command="echo",
):
    # FIXME figure out consistent way of finding most recent all_likes_cache_filename
    # - always write to same file, have the timestamped files as backup
    # FIXME figure out better way of handling sc configs
    # FIXME make resumable?
    latest_captured_track = read_urls_file(latest_capture_filename)

    all_likes = fetch_all_likes_cached(
        user_id, client_id, all_likes_cache_filename, output_cache_filepath=None
    )
    success, failed = capture_latest_tracks(
        all_likes, capture_command, latest_captured_track
    )

    new_latest_capture = ""
    new_latest_capture_filename = ""
    write_file(new_latest_capture_filename, new_latest_capture)


def detect_free_tracks(likes):
    free_fields = [
        "title",
        "permalink",
        "permalink_url",
        "purchase_title",
        "tag_list",
        "album_title",
        "purchase_url",
        "genre",
        "artist",
        "full_name",
        "last_name",
        "username",
        "publisher",
        "label_name"]

    free_likes = list()
    for like in likes:
        tr = like['track']
        for field in free_fields:
            if "free" in (tr.get(field) or ""):
                free_likes.append(like)
                break

    return free_likes


def capture_tracks_from_url_list(all_likes, url_list, capture_command):
    def find_like_by_permalink(permalink):
        return first(
            [
                like
                for like in all_likes
                if like["track"]["permalink_url"] == permalink
            ],
        )

    def url_list_to_tracks(url_list):
        tracks = []
        missing = []
        for url in url_list:
            track = find_like_by_permalink(permalink=url)
            if track:
                tracks.append(track)
            else:
                missing.append(url)
        return tracks, missing

    likes_to_capture, missing = url_list_to_tracks(url_list)
    if missing:
        raise Exception(missing)
    return capture_tracks(likes_to_capture, capture_command)


def capture_latest_tracks(all_likes, capture_command, latest_captured_track):

    if latest_captured_track:
        # FIXME latest_captured_track to use a url or title instead of json
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
    def to_permalinks(likes):
        return [like["track"]["permalink_url"] for like in likes]

    time_before = datetime.now()
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
    print(
        "Capture Completed (%s of %s successful)"
        % (len(success), len(likes_to_capture))
    )
    print("Successful:", to_permalinks(success))
    print("Failed:", to_permalinks(failed))
    print("Total Time Taken:", datetime.now() - time_before)
    return success, failed


def fetch_all_likes_cached(user_id, client_id, cache_dir):
    def cache_file(cache_dir):
        return os.path.join(cache_dir, CACHE_FILENAME)

    def create_timestamped_filename(dirname, label):
        timestamp_str = datetime.now().strftime("%Y-%m-%dT%H-%M")
        return os.path.join(dirname, "%s-%s.json" % (timestamp_str, label))

    def get_most_recent_like(likes):
        if likes:
            return sort_likes(likes)[0]
        else:
            return None

    def track_id(like):
        return like["track"]["id"]

    try:
        cached_likes = json_read_file(cache_file(cache_dir))
    except FileNotFoundError:
        cached_likes = []
    new_likes = fetch_all_likes(
        user_id, client_id, until_track=get_most_recent_like(cached_likes)
    )
    cached_like_track_ids = [track_id(tr) for tr in cached_likes]
    for nl in new_likes:
        if not track_id(nl) in cached_like_track_ids:
            cached_likes.append(nl)
    all_likes = sort_likes(cached_likes)
    json_write_file(cache_file(cache_dir), all_likes)
    json_write_file(create_timestamped_filename(cache_dir, "likes-cache"), all_likes)
    return all_likes


def remove_unrelevent_track_data(tracks):
    return dict_filter(TRACK_FILTERS, tracks)


def sort_likes(likes):
    """
    By liked date desc
    """

    def parse_datetime(iso_date_string):
        return datetime.fromisoformat(iso_date_string[:-1])

    return sorted(
        likes, key=lambda like: parse_datetime(like["created_at"]), reverse=True
    )


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
    def like_created_at(like):
        return like["created_at"]

    def track_id(like):
        return like["track"]["id"]

    def permalink(like):
        return like["track"]["permalink_url"]

    def as_track_ids(likes):
        return [track_id(like) for like in likes]

    def as_permalinks(likes):
        return [permalink(like) for like in likes]

    def contains_until_track(collection):
        if until_track:
            return track_id(until_track) in as_track_ids(collection) or permalink(until_track) in as_permalinks(collection)
        return False

    def filter_already_seen_tracks(collection):
        return [
            like
            for like in collection
            if like_created_at(like) > like_created_at(until_track)
        ]

    def filter_undesireable(collection):
        """
        Songs that are too short, or too long.
        """
        too_short = timedelta(minutes=1, seconds=50)
        too_long = timedelta(minutes=16)
        get_duration = lambda like: timedelta(milliseconds=like['track']['full_duration'])
        is_desireable = lambda like: get_duration(like) > too_short and get_duration(like) < too_long
        keeping = [c for c in collection if is_desireable(c)]
        filtered = [c for c in collection if not is_desireable(c)]
        return keeping, filtered

    tracks = []
    ignored_tracks = []
    next_href = f"https://api-v2.soundcloud.com/users/{user_id}/track_likes"
    while True and next_href:
        next_href, collection = do_fetch_likes(next_href, client_id)
        if contains_until_track(collection):
            next_href = None

            collection = filter_already_seen_tracks(collection)
            print("Until track found, exiting...", permalink(until_track))
        desireable, undesireable = filter_undesireable(collection)
        tracks.extend(desireable)
        ignored_tracks.extend(undesireable)
        print("Fetching:", len(desireable), "Total:", len(tracks))
        time.sleep(kindness_meter)
    print("Desireable Tracks:", len(tracks))
    print("Undesireable Tracks:", len(ignored_tracks), ignored_tracks)
    return remove_unrelevent_track_data(tracks)


def do_fetch_likes(url, client_id, limit=100):
    params = {
        "client_id": client_id,
        "limit": limit,
    }
    result = requests.get(url, params=params)
    j = result.json()
    return j["next_href"], j["collection"]


def json_read_file(filename):
    return json.loads(read_file(filename))


def json_write_file(filename, data):
    write_file(filename, json.dumps(data))


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


def read_urls_file(filename):
    return filter_falsy(read_file(filename).split("\n"))


def write_urls_file(filename, data_list):
    return write_file(filename, "\n".join(data_list))


def read_file(filename):
    with open(absolute_path(filename), "r") as f:
        data = f.read()
    return data


def write_file(filename, data):
    os.makedirs(os.path.dirname(absolute_path(filename)), exist_ok=True)
    with open(filename, "w") as f:
        f.write(data)


def absolute_path(filename):
    return os.path.abspath(os.path.expanduser(filename))


def filter_falsy(lis):
    return [item for item in lis if item]
