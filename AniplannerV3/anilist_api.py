import requests

def get_user_profile(token):
    url = "https://graphql.anilist.co"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    query = '''
    query {
      Viewer {
        id
        name
        avatar {
          large
        }
        statistics {
          anime {
            genres {
              genre
              count
            }
          }
        }
        favourites {
          anime {
            nodes {
              id
              title {
                romaji
              }
            }
          }
        }
      }
    }
    '''
    response = requests.post(url, json={'query': query}, headers=headers)
    data = response.json()['data']['Viewer']
    return {
        "name": data["name"],
        "genres": [g["genre"] for g in sorted(data["statistics"]["anime"]["genres"], key=lambda x: -x["count"])[:3]],
        "favourites": [a["title"]["romaji"] for a in data["favourites"]["anime"]["nodes"]],
        "avatar": data["avatar"]["large"] if data["avatar"] else None
    }

def get_watched_titles(token, username):
    url = "https://graphql.anilist.co"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    query = '''
    query ($userName: String) {
      MediaListCollection(userName: $userName, type: ANIME) {
        lists {
          entries {
            media {
              title {
                romaji
                english
                native
              }
            }
          }
        }
      }
    }
    '''
    response = requests.post(url, json={"query": query, "variables": {"userName": username}}, headers=headers)
    data = response.json()
    seen_titles = set()

    for lst in data['data']['MediaListCollection']['lists']:
        for entry in lst['entries']:
            title_data = entry['media']['title']
            for key in ['romaji', 'english', 'native']:
                title = title_data.get(key)
                if title and isinstance(title, str):
                    seen_titles.add(title.strip().lower())

    return seen_titles

def add_anime_to_watchlist(token, anime_title):
    
    url_search = "https://graphql.anilist.co"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    query_search = '''
    query ($search: String) {
      Media(search: $search, type: ANIME) {
        id
      }
    }
    '''
    response = requests.post(url_search, json={"query": query_search, "variables": {"search": anime_title}}, headers=headers)
    data = response.json()
    anime_id = data.get("data", {}).get("Media", {}).get("id")
    if not anime_id:
        return False

    
    mutation = '''
    mutation ($mediaId: Int) {
      SaveMediaListEntry(mediaId: $mediaId, status: PLANNING) {
        id
      }
    }
    '''
    response = requests.post(url_search, json={"query": mutation, "variables": {"mediaId": anime_id}}, headers=headers)
    return response.status_code == 200 and "errors" not in response.json()

def get_anime_metadata(token, anime_title):
    url = "https://graphql.anilist.co"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    query = '''
    query ($search: String) {
      Media(search: $search, type: ANIME) {
        id
        episodes
        duration
        format
        coverImage {
          large
          medium
        }
      }
    }
    '''
    variables = {"search": anime_title}
    
    try:
        response = requests.post(url, json={"query": query, "variables": variables}, headers=headers)
        data = response.json()
        media = data.get("data", {}).get("Media")

        if not media:
            return {"episodes": 12, "duration": 24, "cover": None, "format": "TV", "id": None}

        
        format_type = media.get("format")
        
        
        anime_id = media.get("id")
        
        
        cover_image = media.get("coverImage", {})
        cover_url = cover_image.get("large") or cover_image.get("medium")

        return {
            "episodes": media.get("episodes", 12),
            "duration": media.get("duration", 24),
            "cover": cover_url,  
            "format": format_type,  
            "id": anime_id  
        }
    except Exception as e:
        print(f"Erreur AniList lors de la récupération des métadonnées pour {anime_title}: {e}")
        return {"episodes": 12, "duration": 24, "cover": None, "format": "TV", "id": None}

def get_watched_anime_ids(token, username):
    url = "https://graphql.anilist.co"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    query = '''
    query ($userName: String) {
      MediaListCollection(userName: $userName, type: ANIME) {
        lists {
          entries {
            media {
              id
            }
          }
        }
      }
    }
    '''
    response = requests.post(url, json={"query": query, "variables": {"userName": username}}, headers=headers)
    data = response.json()
    anime_ids = set()
    for lst in data['data']['MediaListCollection']['lists']:
        for entry in lst['entries']:
            anime_id = entry['media'].get('id')
            if anime_id:
                anime_ids.add(anime_id)
    return anime_ids

def get_full_user_stats(token, username):
    url = "https://graphql.anilist.co"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    query = '''
    query ($userName: String) {
      MediaListCollection(userName: $userName, type: ANIME) {
        lists {
          status
          entries {
            media {
              id
              episodes
              duration
              title {
                romaji
              }
              genres
            }
            progress
          }
        }
      }
      User(name: $userName) {
        statistics {
          anime {
            genres {
              genre
              count
            }
          }
        }
      }
    }
    '''
    response = requests.post(url, json={"query": query, "variables": {"userName": username}}, headers=headers)
    data = response.json()["data"]
    lists = data["MediaListCollection"]["lists"]

    stats = {
        "watched": 0,
        "watching": 0,
        "planned": 0,
        "dropped": 0,
        "total": 0,
        "episodes_watched": 0,
        "time_spent": 0,  
        "total_episodes": 0,
        "anime_count": 0,
        "completion_base": 0,  
    }
    for lst in lists:
        status = (lst.get("status") or "").upper()
        count = len(lst["entries"])
        stats["total"] += count
        if status == "COMPLETED":
            stats["watched"] += count
            stats["completion_base"] += count
        elif status == "CURRENT":
            stats["watching"] += count
            stats["completion_base"] += count
        elif status == "PLANNING":
            stats["planned"] += count
            
        elif status == "DROPPED":
            stats["dropped"] += count
            stats["completion_base"] += count
        
        for entry in lst["entries"]:
            progress = entry.get("progress", 0)
            duration = entry["media"].get("duration") or 24  
            episodes = entry["media"].get("episodes") or 0
            stats["episodes_watched"] += progress
            stats["time_spent"] += progress * duration
            if episodes:
                stats["total_episodes"] += episodes
                stats["anime_count"] += 1

    
    genres = data["User"]["statistics"]["anime"]["genres"]
    top_genres = [g["genre"] for g in sorted(genres, key=lambda x: -x["count"])[:3]]
    stats["top_genres"] = top_genres

    
    stats["avg_episodes"] = round(stats["total_episodes"] / stats["anime_count"], 1) if stats["anime_count"] else 0

    
    stats["completion_pct"] = round(100 * stats["watched"] / stats["completion_base"], 1) if stats["completion_base"] else 0

    return stats

def get_top_rated_favourites(token, username, limit=5):
    """
    Récupère les 5 animés les mieux notés de l'utilisateur (status COMPLETED), avec affiche et nom.
    """
    url = "https://graphql.anilist.co"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    query = '''
    query ($userName: String) {
      MediaListCollection(userName: $userName, type: ANIME, status: COMPLETED, sort: SCORE_DESC) {
        lists {
          entries {
            score
            media {
              id
              title {
                romaji
              }
              coverImage {
                large
              }
            }
          }
        }
      }
    }
    '''
    variables = {"userName": username}
    try:
        response = requests.post(url, json={"query": query, "variables": variables}, headers=headers)
        data = response.json()
        mlc = data.get("data", {}).get("MediaListCollection")
        if not mlc or "lists" not in mlc:
            return []
        entries = []
        for lst in mlc.get("lists", []):
            for entry in lst.get("entries", []):
                media = entry.get("media", {})
                entries.append({
                    "score": entry.get("score", 0),
                    "title": media.get("title", {}).get("romaji", ""),
                    "cover": media.get("coverImage", {}).get("large", "")
                })
        
        top = sorted(entries, key=lambda x: x["score"], reverse=True)[:limit]
        return top
    except Exception as e:
        print("Erreur get_top_rated_favourites:", e)
        return []

def get_score_distribution(token, username):
    """
    Retourne la distribution des notes données par l'utilisateur sous forme de liste de tuples (score, count).
    """
    import collections
    url = "https://graphql.anilist.co"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    query = '''
    query ($userName: String) {
      MediaListCollection(userName: $userName, type: ANIME) {
        lists {
          entries {
            score
          }
        }
      }
    }
    '''
    response = requests.post(url, json={"query": query, "variables": {"userName": username}}, headers=headers)
    data = response.json()
    scores = []
    for lst in data.get("data", {}).get("MediaListCollection", {}).get("lists", []):
        for entry in lst.get("entries", []):
            score = entry.get("score", 0)
            if score:
                scores.append(score)
    score_counts = collections.Counter(scores)
    return sorted(score_counts.items())

def get_format_status_country_distributions(token, username):
    """
    Retourne la distribution par format, status et pays d'origine.
    """
    import collections
    url = "https://graphql.anilist.co"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    query = '''
    query ($userName: String) {
      MediaListCollection(userName: $userName, type: ANIME) {
        lists {
          status
          entries {
            media {
              format
              countryOfOrigin
            }
          }
        }
      }
    }
    '''
    response = requests.post(url, json={"query": query, "variables": {"userName": username}}, headers=headers)
    data = response.json()
    format_counts = collections.Counter()
    status_counts = collections.Counter()
    country_counts = collections.Counter()
    for lst in data.get("data", {}).get("MediaListCollection", {}).get("lists", []):
        status = lst.get("status", "UNKNOWN")
        for entry in lst.get("entries", []):
            media = entry.get("media", {})
            fmt = media.get("format", "UNKNOWN")
            country = media.get("countryOfOrigin", "??")
            format_counts[fmt] += 1
            status_counts[status] += 1
            country_counts[country] += 1
    return {
        "format": sorted(format_counts.items(), key=lambda x: -x[1]),
        "status": sorted(status_counts.items(), key=lambda x: -x[1]),
        "country": sorted(country_counts.items(), key=lambda x: -x[1]),
    }
